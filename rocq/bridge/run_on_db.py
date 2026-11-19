"""Run the verified mutators on a file of SQL queries against a MySQL-compatible server.

    python3 bridge/run_on_db.py QUERIES.sql --host 127.0.0.1 --port 3306 --user root --password ... --database test

For every query in the supported fragment, the original and each mutant are executed
and the bag inclusion promised by the rule is checked:
    Up   : original  is included in  mutant
    Down : mutant    is included in  original
A violation is a candidate DBMS bug (or a gap between the SQL model and the DBMS).
A check is skipped when a query fails or when the column types of the two results
differ, because the values are then not comparable.
"""
import argparse
import collections
import os
import sys

import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sql_bridge import mutate_sql, Unsupported  # noqa: E402


def run(conn, sql):
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return collections.Counter(cur.fetchall()), [d[1] for d in cur.description]
    except Exception:
        return None, None


def included(small, large):
    return all(large[row] >= n for row, n in small.items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('queries')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--database', default='test')
    args = ap.parse_args()
    conn = pymysql.connect(host=args.host, port=args.port, user=args.user,
                           password=args.password, database=args.database, charset='utf8mb4')
    st = collections.Counter()
    by_rule = collections.Counter()
    for line in open(args.queries, encoding='utf-8'):
        sql = line.strip().rstrip(';')
        if not sql or sql.upper().startswith(('USE ', '--')):
            continue
        st['queries'] += 1
        try:
            original, mutants, skipped = mutate_sql(sql)
        except Unsupported:
            st['unsupported'] += 1
            continue
        except Exception:
            st['parse_error'] += 1
            continue
        base, base_types = run(conn, original)
        if base is None:
            st['original_failed'] += 1
            continue
        st['supported'] += 1
        st['mutants_not_printable'] += skipped
        for direction, rule, mutant in mutants:
            res, types = run(conn, mutant)
            if res is None:
                st['mutant_failed'] += 1
                continue
            if types != base_types:
                st['type_mismatch_skipped'] += 1
                continue
            st['checked'] += 1
            by_rule[rule] += 1
            ok = included(base, res) if direction == 'Up' else included(res, base)
            if not ok:
                st['VIOLATIONS'] += 1
                print('VIOLATION %s %s\n  original: %s\n  mutant  : %s' % (direction, rule, original, mutant))
    print(dict(st))
    print('checks per rule:', dict(by_rule))


if __name__ == '__main__':
    main()
