"""Run the verified mutators on a file of SQL queries against a MySQL-compatible server.

    python3 bridge/run_on_db.py QUERIES.sql [--value] --port 3306 --user root --password ... --database test

For every query in the supported fragment:
1. translation validation: the query as written and the query re-printed from its
   algebra term must return the same bag of rows; otherwise the bridge did not
   preserve the query and it is not used;
2. each mutant is executed and the relation promised by its rule is checked
   (bag inclusion, or with --value the value relation on the mutated column).

A violation is a candidate DBMS bug, or a gap between the SQL model and the DBMS.
"""
import argparse
import collections
import os
import sys

import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sql_bridge import mutate_sql, mutate_value, Unsupported  # noqa: E402
from checker import bag, check_inclusion, check_value  # noqa: E402


APPROXIMATE_TYPES = {4, 5}   # pymysql FIELD_TYPE.FLOAT, FIELD_TYPE.DOUBLE
SINGLE = 4


def run(conn, sql):
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall()), [d[1] for d in cur.description]
    except Exception:
        return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('queries')
    ap.add_argument('--value', action='store_true', help='value-semantic mutation')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--database', default='test')
    ap.add_argument('--flip', action='store_true',
                    help='negative control: expect the opposite relation (must report violations)')
    args = ap.parse_args()
    conn = pymysql.connect(host=args.host, port=args.port, user=args.user,
                           password=args.password, database=args.database, charset='utf8mb4')
    st, by_rule = collections.Counter(), collections.Counter()
    for line in open(args.queries, encoding='utf-8'):
        sql = line.strip().rstrip(';')
        if not sql or sql.upper().startswith(('USE ', '--')):
            continue
        st['queries'] += 1
        try:
            probe = None
            if args.value:
                original, mutants, skipped, probe, having_mutants = mutate_value(sql)
                mutants = mutants + having_mutants
            else:
                original, mutants, skipped = mutate_sql(sql)
        except Unsupported:
            st['unsupported'] += 1
            continue
        except Exception:
            st['parse_error'] += 1
            continue
        single = False
        if probe is not None and probe[0] is not None:
            # The model computes with exact numbers.
            # - FLOAT / DOUBLE grouping keys: the server may compare rounded or unrounded
            #   values depending on the plan, so the number of groups is not determined;
            #   such queries are outside the model.
            # - single-precision inputs: results are compared with a looser tolerance.
            _, probe_types = run(conn, probe[0])
            if probe_types is None:
                st['original_failed'] += 1
                continue
            if any(t in APPROXIMATE_TYPES for t in probe_types[:probe[1]]):
                st['approximate_group_key'] += 1
                continue
            single = SINGLE in probe_types
        as_written, _ = run(conn, sql)
        base, base_types = run(conn, original)
        if as_written is None or base is None:
            st['original_failed'] += 1
            continue
        if bag(as_written) != bag(base):
            st['TRANSLATION_MISMATCH'] += 1
            print('TRANSLATION MISMATCH\n  written  : %s\n  reprinted: %s' % (sql, original))
            continue
        st['supported'] += 1
        st['mutants_not_printable'] += skipped
        for mutant in mutants:
            text = mutant[-1]
            res, types = run(conn, text)
            if res is None:
                st['mutant_failed'] += 1
                continue
            if args.value and len(mutant) == 4:
                relation, rule, column, _ = mutant
                if args.flip:
                    relation = {'Le': 'Ge', 'Ge': 'Le', 'AwayZero': 'TowardZero',
                                'TowardOne': 'AwayOne', 'AwayOne': 'TowardOne'}[relation]
                    if relation == 'TowardZero':
                        continue
                loose = single or SINGLE in (base_types[column], types[column])
                verdict = check_value(relation, column, base, res, single_precision=loose)
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
                verdict = check_inclusion(direction, base, res)
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
    print(dict(st))
    print('ok checks per rule:', dict(by_rule))


if __name__ == '__main__':
    main()
