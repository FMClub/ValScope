"""Tests that need a MySQL-protocol server (run in CI against MariaDB and MySQL).

    python3 bridge/test_mysql.py [--host H] [--port P] [--user U] [--password W]

Creates and drops the database vs_test_mysql.
"""
import argparse
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_on_db import MySQLTarget, arm_mix_verdict  # noqa: E402
from checker import MariaDBColumns, check_inclusion  # noqa: E402

failures = 0


def report(ok, text):
    global failures
    print(('ok    ' if ok else 'FAIL  ') + text)
    failures += 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='123456')
    a = ap.parse_args()
    import pymysql
    conn = pymysql.connect(host=a.host, port=a.port, user=a.user, password=a.password, autocommit=True)
    cur = conn.cursor()
    cur.execute('DROP DATABASE IF EXISTS vs_test_mysql')
    cur.execute('CREATE DATABASE vs_test_mysql')
    cur.execute('USE vs_test_mysql')
    cur.execute('CREATE TABLE t (a VARCHAR(5) COLLATE utf8mb4_general_ci, b VARCHAR(5) COLLATE utf8mb4_bin, '
                'l VARCHAR(5) CHARACTER SET latin1, n INT)')
    cur.execute("INSERT INTO t VALUES ('A', 'x', 'é', 1), ('a', 'y', 'e', 2)")
    target = MySQLTarget(types.SimpleNamespace(host=a.host, port=a.port, user=a.user, password=a.password,
                                               database='vs_test_mysql'))
    try:
        # a column of a compound: the coarsest collation of its arms
        target.run('SELECT t.b FROM t UNION ALL SELECT DISTINCT t.a FROM t')
        report(target.last_collations == ['utf8mb4_general_ci'],
               'compound: collation of the DISTINCT arm %r' % target.last_collations)
        rows_a, _ = target.run('SELECT t.b FROM t UNION ALL SELECT DISTINCT t.a FROM t')
        fold = target.folds(target.last_collations, target.last_collations)
        report(check_inclusion('Up', rows_a, [(b'x',), (b'y',), (b'a',)], fold) in ('ok', 'collation'),
               "compound: 'A' and 'a' are equivalent in the DISTINCT arm")
        target.run('SELECT t.b, t.n FROM t UNION SELECT t.b, t.n FROM t')
        report(target.last_collations[0] == 'utf8mb4_bin', 'compound of exact arms stays exact %r' % target.last_collations)
        target.run('SELECT d.b FROM (SELECT t.b FROM t UNION SELECT t.a FROM t) AS d')
        report(target.last_collations == [MariaDBColumns.COARSEST], 'nested compound: coarsest of the database')
        # arms that no fold repairs (run_on_db.arm_mix_verdict)
        target.run('SELECT t.b, t.n FROM t UNION SELECT t.b, t.n FROM t')
        report(target.last_arm_mix is None, 'compound of like arms: no mix')
        target.run('SELECT DISTINCT t.a FROM t EXCEPT ALL SELECT t.b FROM t')
        report(target.last_arm_mix == 'collations', 'EXCEPT of a _ci arm and a _bin arm: mixed collations')
        target.run('SELECT DISTINCT t.a FROM t UNION ALL SELECT t.b FROM t')
        report(target.last_arm_mix is None, 'UNION ALL compares nothing: mixed collations do not matter')
        target.run('(SELECT t.n FROM t UNION SELECT t.a FROM t) UNION ALL (SELECT t.n FROM t EXCEPT SELECT t.n + 0.5 FROM t)')
        report(target.last_arm_mix == 'types', 'INT, DECIMAL and text arms, nested in parentheses: mixed types')
        target.run('SELECT d.n FROM (SELECT t.n FROM t UNION ALL SELECT t.n FROM t) AS d UNION SELECT t.a FROM t '
                   'UNION ALL SELECT t.n + 0.5 FROM t')
        report(target.last_arm_mix == 'types' and target.last_collations == [MariaDBColumns.COARSEST],
               'a compound in a derived table of an arm: the arms at the top are still probed')
        target.run('SELECT t.n FROM t UNION SELECT t.a FROM t')
        report(target.last_arm_mix == 'types', 'a number arm and a text arm: mixed types')
        target.run('SELECT t.n FROM t UNION SELECT t.n + 0.5 FROM t')
        report(target.last_arm_mix is None, 'two numeric types and no text: no mix')
        report(arm_mix_verdict('Up violated', None, 'types') == 'incomparable' and
               arm_mix_verdict('Up violated', 'collations', None) == 'collation' and
               arm_mix_verdict('Up violated', None, None) == 'Up violated' and
               arm_mix_verdict('ok', 'types', None) == 'ok', 'a violation over mixed arms is not reported as one')
        target.run('SELECT t.a, t.b FROM t')
        report(target.last_collations == ['utf8mb4_general_ci', 'utf8mb4_bin'], 'plain columns %r' % target.last_collations)
        # every text column is decoded with its own character set
        rows, _ = target.run('SELECT t.l FROM t ORDER BY t.n')
        report(rows is not None and rows[0][0] in ('é', 'é'.encode('latin-1'), b'\xc3\xa9'),
               'latin1 column decoded: %r' % (rows,))
        # an expression over a grouping key is determined, and the server accepts it
        rows, _ = target.run('SELECT t.n + 3 AS k, COUNT(*) AS c FROM t GROUP BY t.n')
        report(rows is not None and sorted(r[0] for r in rows) == [4, 5], 'expression over a grouping key runs')
    finally:
        cur.execute('DROP DATABASE vs_test_mysql')
    print('%d failures' % failures)
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
