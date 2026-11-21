#!/usr/bin/env python3
"""Check that a reduction script of bridge/reduce_mysql.py still shows its violation.

    scripts/check_reduced_mysql.py REDUCED.sql EXPECT [--host H --port P --user U --password W]

The CREATE TABLE / INSERT statements are loaded into a fresh database `vs_check`, the
original and the mutant are run, and the relation (`Up` / `Down`, or `Le col 0` for a
value rule) must be violated; at most 3 rows per table must remain.
"""
import argparse
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bridge'))
from run_on_db import MySQLTarget  # noqa: E402
from checker import check_inclusion, check_value  # noqa: E402
from sql_bridge import mutate_value  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('script')
    ap.add_argument('expect')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='123456')
    ap.add_argument('--max-rows', type=int, default=3)
    a = ap.parse_args()
    text = open(a.script).read()
    stmts, original, mutant = [], None, None
    body, _, tail = text.partition('-- original\n')
    original, _, mutant = tail.partition('-- mutant\n')
    original, mutant = original.strip().rstrip(';'), mutant.strip().rstrip(';')
    for st in body.split(';\n'):
        st = '\n'.join(l for l in st.splitlines() if not l.startswith('--')).strip()
        if st:
            stmts.append(st)
    import pymysql
    conn = pymysql.connect(host=a.host, port=a.port, user=a.user, password=a.password, autocommit=True)
    cur = conn.cursor()
    cur.execute('DROP DATABASE IF EXISTS vs_check')
    cur.execute('CREATE DATABASE vs_check')
    cur.execute('USE vs_check')
    rows = {}
    for st in stmts:
        cur.execute(st)
        if st.upper().startswith('INSERT INTO'):
            t = st.split('`')[1]
            rows[t] = rows.get(t, 0) + 1
    try:
        target = MySQLTarget(types.SimpleNamespace(host=a.host, port=a.port, user=a.user, password=a.password,
                                                   database='vs_check'))
        base, _ = target.run(original)
        bc = target.last_collations
        res, _ = target.run(mutant)
        fold = target.folds(bc, target.last_collations)
        if ' col ' in a.expect:
            relation, _, column = a.expect.split()
            # a cover (VDistinct.v) or a one-to-one correspondence: as the bridge decides
            trs = []
            try:
                mutate_value(original, dialect='mysql', translation=trs, schema=target.schema, exact_columns=target.exact)
                cover = bool(trs[0].cover_for(mutant))
            except Exception:
                cover = original.upper().startswith('SELECT DISTINCT')
            v = check_value(relation, int(column), base, res, fold=fold, cover=cover)
        elif a.expect == 'Same':
            both = [check_inclusion(d, base, res, fold) for d in ('Up', 'Down')]
            v = 'ok' if all(x in ('ok', 'collation') for x in both) else 'translation mismatch'
        else:
            v = check_inclusion(a.expect, base, res, fold)
    finally:
        cur.execute('DROP DATABASE vs_check')
    print('rows per table: %s; verdict: %s' % (rows, v))
    ok = v not in ('ok', 'collation', 'incomparable') and all(n <= a.max_rows for n in rows.values())
    print('reduced case still violated' if ok else 'FAIL: the reduced case does not show the violation')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
