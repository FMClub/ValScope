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
import sql_bridge  # noqa: E402
from sql_bridge import mutate_sql, mutate_value, Unsupported  # noqa: E402
from checker import check_inclusion, check_value, comparable_types, MariaDBColumns, mariadb_fold, sqlite_fold  # noqa: E402


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
        # (a column that is neither grouped nor aggregated would take its value from any row
        # of the group; the bridge rejects such queries.  ONLY_FULL_GROUP_BY is not set:
        # MariaDB's also rejects determined expressions such as LN(c) + 3 with GROUP BY LN(c).)
        # the collation of every result column, reported by the server (checker.py)
        self.columns = MariaDBColumns(self.conn, mariadb_fold(self.conn, args.database))
        self.name = 'per result column (server metadata)'
        self.last_collations = []
        # table -> columns, for printing DISTINCT around a join (sql_bridge._join_columns)
        with self.conn.cursor() as cur:
            cur.execute('SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS '
                        'WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION', (args.database,))
            self.schema = {}
            for t, c in cur.fetchall():
                t, c = (x.decode() if isinstance(x, bytes) else x for x in (t, c))
                self.schema.setdefault(t, []).append('`%s`' % c if not c.isidentifier() else c)
            # columns of an integer type in every table that has them (collation law)
            cur.execute('SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS '
                        'WHERE TABLE_SCHEMA = %s', (args.database,))
            exact, other, by_table = set(), set(), {}
            for t, c, ty in cur.fetchall():
                t, c, ty = (x.decode() if isinstance(x, bytes) else x for x in (t, c, ty))
                if ty.lower() in ('tinyint', 'smallint', 'mediumint', 'int', 'integer', 'bigint'):
                    exact.add(c.lower())
                    by_table[(t.lower(), c.lower())] = 'integer'
                else:
                    other.add(c.lower())
            from sql_bridge import ExactColumns
            self.exact = ExactColumns({c: 'integer' for c in exact - other})
            self.exact.by_table = by_table

    def folds(self, collations_a, collations_b):
        return self.columns.folds(collations_a, collations_b)

    def run(self, sql):
        """(rows, column types), or (None, None) when the query fails.  The collations
        of the result columns are left in self.last_collations."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                rows = list(cur.fetchall())
                self.last_collations = [self.columns.name(f.charsetnr) for f in cur._result.fields]
                types = [d[1] for d in cur.description]
            if any(w in sql.upper() for w in ('UNION', 'INTERSECT', 'EXCEPT')):
                self.last_collations = self._compound_collations(sql, self.last_collations)
            return rows, types
        except self.pymysql.err.MySQLError as e:
            code = e.args[0] if e.args else None
            if code in self.CONNECTION_LOST or isinstance(e, self.pymysql.err.InterfaceError):
                sys.exit('connection to the server lost (%s); the run is stopped' % (e,))
            ERRORS['%s %s' % (code, str(e.args[1] if len(e.args) > 1 else e)[:70])] += 1
            return None, None


    def _compound_collations(self, sql, names):
        """The server reports for a compound column the collation it derives from all
        arms (MariaDB: that of the first arm in practice), but an arm can de-duplicate
        under a coarser collation (DISTINCT over a _ci column) and keep either of two
        equivalent strings.  Per column the coarsest of the arms' collations is used;
        for a compound nested in a derived table or a CTE, the coarsest collation of the
        database (MariaDBColumns.COARSEST)."""
        coarsest = [MariaDBColumns.COARSEST] * len(names)
        try:
            import sqlglot
            from sqlglot import exp
            tree = sqlglot.parse_one(sql, read='mysql')
        except Exception:
            return coarsest
        setops = (exp.Union, exp.Intersect, exp.Except)
        chain, arms = [], []

        def flatten(n):
            if isinstance(n, setops):
                chain.append(id(n))
                flatten(n.left)
                flatten(n.right)
            else:
                arms.append(n)
        flatten(tree)
        if any(isinstance(n, setops) and id(n) not in chain for n in tree.walk()):
            return coarsest
        if not chain:
            return names
        with_ = tree.args.get('with')
        prefix = with_.sql(dialect='mysql') + ' ' if with_ is not None else ''
        combined = [{n} for n in names]
        for arm in arms:
            while isinstance(arm, (exp.Paren, exp.Subquery)) and arm.args.get('alias') is None:
                arm = arm.this
            probe = '%sSELECT * FROM (%s) AS vs_arm LIMIT 0' % (prefix, arm.sql(dialect='mysql'))
            cache = self.__dict__.setdefault('_arm_cache', {})
            if probe not in cache:      # the same arm recurs in the original and its mutants
                try:
                    with self.conn.cursor() as cur:
                        cur.execute(probe)
                        cur.fetchall()
                        cache[probe] = [self.columns.name(f.charsetnr) for f in cur._result.fields]
                except self.pymysql.err.MySQLError:
                    cache[probe] = None
            got = cache[probe]
            if got is None:
                return coarsest
            if len(got) != len(names):
                return coarsest
            for c, g in zip(combined, got):
                c.add(g)
        out = []
        for c in combined:
            insensitive = [n for n in c if n and ('_ci' in n or '_ai' in n)]
            if len(c) == 1:
                out.append(next(iter(c)))
            elif len(insensitive) == 1 and all(n and n.endswith('_bin') or n == 'binary' or n in insensitive
                                               for n in c):
                out.append(insensitive[0])      # one coarse collation over exact ones
            else:
                out.append(MariaDBColumns.COARSEST)
        return out


class SQLiteTarget:
    """An SQLite database file."""
    dialect = 'sqlite'

    def __init__(self, args):
        from sqlite_exec import SQLiteLib
        if not os.path.exists(args.sqlite):
            sys.exit('no such database file: %s' % args.sqlite)
        self.db = SQLiteLib(args.sqlite_lib, args.sqlite)
        schema = [r[0] for r in self.db.query("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")]
        # the coarsest collation of the database, for columns whose collation is unknown
        self.fallback = sqlite_fold(schema)
        self.name = 'per result column where SQLite reports it, else %s' % self.fallback.name
        self.last_collations = []
        self.schema = sqlite_schema(self.db)
        self.exact = sqlite_exact_columns(self.db, self.schema)

    def folds(self, collations_a, collations_b):
        return self.db.folds(collations_a, collations_b, self.fallback)

    def run(self, sql):
        try:
            rows = self.db.query(sql)
            self.last_collations = self.db.last_collations
            return rows, None
        except Exception as e:      # RuntimeError (ctypes library) or sqlite3.Error
            ERRORS[str(e)[:70]] += 1
            return None, None


def same_rows(a, b):
    return check_inclusion('Up', a, b) == 'ok' and check_inclusion('Down', a, b) == 'ok'


def sqlite_schema(db):
    """table -> columns of an SQLite database (sqlite_exec.SQLiteLib)."""
    schema = {}
    for (t,) in db.query("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
        schema[t] = [r[1] for r in db.query("PRAGMA table_info('%s')" % t.replace("'", "''"))]
    return schema


def sqlite_exact_columns(db, schema):
    """Column name -> storage classes, for the columns whose equivalent values are identical
    in every table that has them (sql_bridge._exact_names); `by_table` per (table, column).
    A column qualifies when it does not mix integers with reals (1 = 1.0), holds no -0.0, and
    holds text only under the BINARY collation (NOCASE and RTRIM make 'a' = 'A', 'a' = 'a ').
    The value is the set of storage classes, as a sorted text ('integer', 'integer+text', ...)."""
    import re
    collations = {}
    for name, sql in db.query("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"):
        body = sql[sql.index('(') + 1:sql.rindex(')')]
        for part in body.split(','):
            m = re.match(r'\s*"?(\w+)"?\s', part + ' ')
            if m:
                c = re.search(r'COLLATE\s+(\w+)', part, re.I)
                collations[(name.lower(), m.group(1).lower())] = c.group(1).upper() if c else 'BINARY'
    classes, by_table = {}, {}
    for t, cols in schema.items():
        for c in cols:
            qt, qc = t.replace('"', '""'), c.replace('"', '""')
            kinds = {r[0] for r in db.query('SELECT DISTINCT typeof("%s") FROM "%s" WHERE "%s" IS NOT NULL'
                                             % (qc, qt, qc))}
            k = None
            ok = not {'integer', 'real'} <= kinds and \
                ('text' not in kinds or collations.get((t.lower(), c.lower()), 'BINARY') == 'BINARY') and \
                not ('real' in kinds and db.query("SELECT 1 FROM \"%s\" WHERE typeof(\"%s\") = 'real' AND \"%s\" = 0 "
                                                   "AND CAST(\"%s\" AS TEXT) LIKE '-%%' LIMIT 1" % (qt, qc, qc, qc)))
            if ok:
                k = '+'.join(sorted(kinds)) or 'null'
            classes.setdefault(c.lower(), set()).add(k)
            if k is not None:
                by_table[(t.lower(), c.lower())] = k
    from sql_bridge import ExactColumns
    out = ExactColumns({c: next(iter(ks)) for c, ks in classes.items() if len(ks) == 1 and None not in ks})
    out.by_table = by_table
    return out


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
    print('comparing modulo collation: %s' % target.name)
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
                original, mutants, skipped, probe, having_mutants = mutate_value(
                    sql, dialect=target.dialect, translation=trs, schema=target.schema, exact_columns=target.exact)
                mutants = mutants + having_mutants
            else:
                original, mutants, skipped = mutate_sql(sql, dialect=target.dialect, schema=target.schema,
                                                        exact_columns=target.exact)
        except Unsupported:
            st['unsupported'] += 1
            continue
        except Exception as e:
            st['bridge_error'] += 1
            ERRORS['bridge: %s %s' % (type(e).__name__, str(e)[:60])] += 1
            continue
        single = False
        probes = trs[0].type_probes() if args.value else []
        if args.value and target.dialect == 'mysql' and any(p[0] for p in probes):
            # The model computes with exact numbers.
            # - FLOAT / DOUBLE grouping keys: the server may compare rounded or unrounded
            #   values depending on the plan, so the number of groups is not determined;
            #   such queries are outside the model.
            # - single-precision inputs: results are compared with a looser tolerance.
            failed = approximate = False
            for probe_sql, nkeys in probes:          # one probe per arm of a UNION ALL
                if probe_sql is None:
                    continue
                _, probe_types = target.run(probe_sql)
                if probe_types is None:
                    failed = True
                    break
                approximate |= any(t in target.APPROXIMATE_TYPES for t in probe_types[:nkeys])
                single |= target.SINGLE in probe_types
            if failed:
                st['original_failed'] += 1
                continue
            if approximate:
                st['approximate_group_key'] += 1
                continue
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
        base_collations = target.last_collations
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
            fold = target.folds(base_collations, target.last_collations)
            if args.value and len(mutant) == 4:
                relation, rule, column, _ = mutant
                if args.flip:
                    if relation not in FLIP_VALUE:
                        continue
                    relation = FLIP_VALUE[relation]
                loose = single or (types is not None and target.SINGLE in (base_types[column], types[column]))
                verdict = check_value(relation, column, base, res, single_precision=loose, fold=fold,
                                      cover=bool(trs) and trs[0].cover_for(text))
                label = '%s col %d' % (relation, column)
            else:
                # set-semantic mutant, or a mutant of the HAVING predicate
                direction, rule, _ = mutant
                if args.value:
                    rule = 'HAVING ' + rule
                if comparable_types(base_types, types, base, res):
                    st['type_mismatch_skipped'] += 1
                    continue
                if args.flip:
                    direction = 'Down' if direction == 'Up' else 'Up'
                verdict = check_inclusion(direction, base, res, fold)
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
                        cover = bool(args.value and len(mutant) == 4 and trs and trs[0].cover_for(text))
                        out.write(json.dumps({'rule': rule, 'expect': label, 'verdict': verdict, 'distinct': cover,
                                              'query': sql, 'original': original, 'mutant': text,
                                              'original_rows': len(base), 'mutant_rows': len(res)}) + '\n')
                        out.flush()
    # mutants whose printed SQL did not parse back to the term of the verified engine
    if sql_bridge.STATS['not_in_dialect']:
        # rules whose operator the dialect lacks (SQLite: INTERSECT ALL, EXCEPT ALL)
        st['mutants_not_in_dialect'] = sql_bridge.STATS['not_in_dialect']
    if sql_bridge.STATS['roundtrip_rejected']:
        st['mutants_roundtrip_rejected'] = sql_bridge.STATS['roundtrip_rejected']
    # mutants that apply a collation-sensitive operation above a de-duplication
    if sql_bridge.STATS['outside_model']:
        st['mutants_outside_model'] = sql_bridge.STATS['outside_model']
    print(dict(st))
    print('ok checks per rule:', dict(by_rule))
    if ERRORS:
        print('most frequent errors:')
        for msg, n in ERRORS.most_common(10):
            print('  %6d  %s' % (n, msg))


if __name__ == '__main__':
    main()
