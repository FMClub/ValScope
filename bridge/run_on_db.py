"""Run the verified mutators on a file of SQL queries against an existing database.

    # a MySQL-protocol server (MySQL, MariaDB, Percona, TiDB, OceanBase, PolarDB, ...)
    python3 bridge/run_on_db.py QUERIES.sql [--value] --host H --port P --user U --password W --database D

    # an SQLite database file, with the SQLite that Python ships or with a given library
    python3 bridge/run_on_db.py QUERIES.sql [--value] --sqlite FILE.db [--sqlite-lib libsqlite3.so]

QUERIES.sql has one query per line (lines starting with `--` and `USE` are skipped).
For every query in the supported fragment:
1. translation validation: the query as written and the query re-printed from its
   algebra term must return the same bag of rows; otherwise the bridge did not
   preserve the query and it is not used;
2. each mutant is executed and the relation promised by its rule is checked
   (bag inclusion, or with --value the value relation on the mutated column),
   modulo the equality of the database's collation (see checker.py).

A violation is a candidate DBMS bug, or a gap between the SQL model and the DBMS.
With --out, violations are also written as JSON lines.
"""
import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sql_bridge import mutate_sql, mutate_value, Unsupported  # noqa: E402
from checker import check_inclusion, check_value, mariadb_fold, sqlite_fold  # noqa: E402


ERRORS = collections.Counter()


class MySQLTarget:
    """A server that speaks the MySQL protocol."""
    dialect = 'mysql'
    APPROXIMATE_TYPES = {4, 5}      # pymysql FIELD_TYPE.FLOAT, FIELD_TYPE.DOUBLE
    SINGLE = 4
    # client errors that mean the server is gone, not that the query is wrong
    CONNECTION_LOST = {2003, 2006, 2013, 2055}

    def __init__(self, args):
        import pymysql
        self.pymysql = pymysql
        self.conn = pymysql.connect(host=args.host, port=args.port, user=args.user, password=args.password,
                                    database=args.database, charset='utf8mb4', autocommit=True)
        self.fold = mariadb_fold(self.conn, args.database)

    def run(self, sql):
        """(rows, column types), or (None, None) when the query fails."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                return list(cur.fetchall()), [d[1] for d in cur.description]
        except self.pymysql.err.MySQLError as e:
            code = e.args[0] if e.args else None
            if code in self.CONNECTION_LOST or isinstance(e, self.pymysql.err.InterfaceError):
                sys.exit('connection to the server lost (%s); the run is stopped' % (e,))
            ERRORS['%s %s' % (code, str(e.args[1] if len(e.args) > 1 else e)[:70])] += 1
            return None, None


class SQLiteTarget:
    """An SQLite database file."""
    dialect = 'sqlite'

    def __init__(self, args):
        from sqlite_exec import SQLiteLib
        if not os.path.exists(args.sqlite):
            sys.exit('no such database file: %s' % args.sqlite)
        self.db = SQLiteLib(args.sqlite_lib, args.sqlite)
        schema = [r[0] for r in self.db.query("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")]
        self.fold = sqlite_fold(schema)

    def run(self, sql):
        try:
            return self.db.query(sql), None
        except Exception as e:      # RuntimeError (ctypes library) or sqlite3.Error
            ERRORS[str(e)[:70]] += 1
            return None, None


def same_rows(a, b):
    return check_inclusion('Up', a, b) == 'ok' and check_inclusion('Down', a, b) == 'ok'


FLIP_VALUE = {'Le': 'Ge', 'Ge': 'Le', 'TowardOne': 'AwayOne', 'AwayOne': 'TowardOne'}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('queries', help='file with one SQL query per line')
    ap.add_argument('--value', action='store_true', help='value-semantic and HAVING mutation')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--database', default='test')
    ap.add_argument('--sqlite', metavar='FILE.db', help='test this SQLite database file instead of a server')
    ap.add_argument('--sqlite-lib', metavar='LIB.so', default=None,
                    help='SQLite shared library to use (default: the one Python ships)')
    ap.add_argument('--out', metavar='FILE.jsonl', help='append the violations to this file')
    ap.add_argument('--flip', action='store_true',
                    help='negative control: expect the opposite relation (must report violations)')
    args = ap.parse_args()
    target = SQLiteTarget(args) if args.sqlite else MySQLTarget(args)
    print('comparing modulo collation %s' % target.fold.name)
    out = open(args.out, 'a') if args.out else None
    st, by_rule = collections.Counter(), collections.Counter()
    for line in open(args.queries, encoding='utf-8'):
        sql = line.strip().rstrip(';')
        if not sql or sql.upper().startswith(('USE ', '--')):
            continue
        st['queries'] += 1
        trs = []
        try:
            if args.value:
                original, mutants, skipped, probe, having_mutants = mutate_value(sql, dialect=target.dialect,
                                                                                translation=trs)
                mutants = mutants + having_mutants
            else:
                original, mutants, skipped = mutate_sql(sql, dialect=target.dialect)
        except Unsupported:
            st['unsupported'] += 1
            continue
        except Exception as e:
            st['bridge_error'] += 1
            ERRORS['bridge: %s %s' % (type(e).__name__, str(e)[:60])] += 1
            continue
        single = False
        if args.value and target.dialect == 'mysql' and probe[0] is not None:
            # The model computes with exact numbers.
            # - FLOAT / DOUBLE grouping keys: the server may compare rounded or unrounded
            #   values depending on the plan, so the number of groups is not determined;
            #   such queries are outside the model.
            # - single-precision inputs: results are compared with a looser tolerance.
            _, probe_types = target.run(probe[0])
            if probe_types is None:
                st['original_failed'] += 1
                continue
            if any(t in target.APPROXIMATE_TYPES for t in probe_types[:probe[1]]):
                st['approximate_group_key'] += 1
                continue
            single = target.SINGLE in probe_types
        if args.value and target.dialect == 'sqlite':
            # an SQLite column can hold text in any row; aggregates then follow SQLite's
            # own rules, outside the model (see Translation.numeric_probe)
            count_sql = trs[0].numeric_probe()
            if count_sql is not None:
                count, _ = target.run(count_sql)
                if count is None or count[0][0] != 0:
                    st['non_numeric_input'] += 1
                    continue
        as_written, _ = target.run(sql)
        base, base_types = target.run(original)
        if as_written is None or base is None:
            st['original_failed'] += 1
            continue
        if not same_rows(as_written, base):
            st['TRANSLATION_MISMATCH'] += 1
            print('TRANSLATION MISMATCH\n  written  : %s\n  reprinted: %s' % (sql, original))
            continue
        st['supported'] += 1
        st['mutants_not_printable'] += skipped
        for mutant in mutants:
            text = mutant[-1]
            res, types = target.run(text)
            if res is None:
                st['mutant_failed'] += 1
                continue
            if args.value and len(mutant) == 4:
                relation, rule, column, _ = mutant
                if args.flip:
                    if relation not in FLIP_VALUE:
                        continue
                    relation = FLIP_VALUE[relation]
                loose = single or (types is not None and target.SINGLE in (base_types[column], types[column]))
                verdict = check_value(relation, column, base, res, single_precision=loose, fold=target.fold)
                label = '%s col %d' % (relation, column)
            else:
                # set-semantic mutant, or a mutant of the HAVING predicate
                direction, rule, _ = mutant
                if args.value:
                    rule = 'HAVING ' + rule
                if types != base_types:
                    st['type_mismatch_skipped'] += 1
                    continue
                if args.flip:
                    direction = 'Down' if direction == 'Up' else 'Up'
                verdict = check_inclusion(direction, base, res, target.fold)
                label = direction
            if verdict == 'ok':
                st['checked_ok'] += 1
                by_rule[rule] += 1
            elif verdict in ('incomparable', 'collation'):
                st[verdict] += 1
            else:
                st['VIOLATIONS'] += 1
                if not args.flip:
                    print('VIOLATION %s %s (%s)\n  original: %s\n  mutant  : %s'
                          % (label, rule, verdict, original, text))
                    if out:
                        out.write(json.dumps({'rule': rule, 'expect': label, 'verdict': verdict,
                                              'query': sql, 'original': original, 'mutant': text,
                                              'original_rows': len(base), 'mutant_rows': len(res)}) + '\n')
                        out.flush()
    print(dict(st))
    print('ok checks per rule:', dict(by_rule))
    if ERRORS:
        print('most frequent errors:')
        for msg, n in ERRORS.most_common(10):
            print('  %6d  %s' % (n, msg))


if __name__ == '__main__':
    main()
