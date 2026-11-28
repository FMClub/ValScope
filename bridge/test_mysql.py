"""Tests that need a MySQL-protocol server (run in CI against MariaDB and MySQL).

    python3 bridge/test_mysql.py [--host H] [--port P] [--user U] [--password W]

Creates and drops the database vs_test_mysql.
"""
import argparse
import os
import sys
import types
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_on_db import MySQLTarget, arm_mix_verdict, exact_in_double  # noqa: E402
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
        report(not target.last_arm_mix, 'compound of like arms: no mix')
        target.run('SELECT DISTINCT t.a FROM t EXCEPT ALL SELECT t.b FROM t')
        report('collations' in target.last_arm_mix, 'EXCEPT of a _ci arm and a _bin arm: mixed collations')
        target.run('SELECT DISTINCT t.a FROM t UNION ALL SELECT t.b FROM t')
        report('collations' not in target.last_arm_mix, 'UNION ALL compares nothing: mixed collations do not matter')
        report('coarser' in target.last_arm_mix, 'a _ci arm and a _bin arm: compared more coarsely than de-duplicated')
        target.run('(SELECT t.n FROM t UNION SELECT t.a FROM t) UNION ALL (SELECT t.n FROM t EXCEPT SELECT t.n + 0.5 FROM t)')
        report('types' in target.last_arm_mix, 'INT, DECIMAL and text arms, nested in parentheses: mixed types')
        target.run('SELECT d.n FROM (SELECT t.n FROM t UNION ALL SELECT t.n FROM t) AS d UNION SELECT t.a FROM t '
                   'UNION ALL SELECT t.n + 0.5 FROM t')
        report('types' in target.last_arm_mix and target.last_collations == [MariaDBColumns.COARSEST],
               'a compound in a derived table of an arm: the arms at the top are still probed')
        target.run('SELECT t.n FROM t UNION SELECT t.a FROM t')
        report('types' in target.last_arm_mix, 'a number arm and a text arm: mixed types')
        target.run('SELECT t.n FROM t UNION SELECT t.n + 0.5 FROM t')
        report(not target.last_arm_mix, 'two numeric types and no text: no mix')
        target.run('SELECT t.n FROM t UNION SELECT t.n + 0.5e0 FROM t')
        report('precision' not in target.last_arm_mix, 'small integers beside a DOUBLE arm: converted one to one')
        target.run('SELECT t.n * 9007199254740993 FROM t UNION SELECT t.n + 0.5e0 FROM t')
        report('precision' in target.last_arm_mix, 'an integer above 2^53 beside a DOUBLE arm: converted')
        target.run('SELECT CAST(t.n AS DECIMAL(30,20)) + 0.00000000000000000001 FROM t UNION SELECT t.n + 0.5e0 FROM t')
        report('precision' in target.last_arm_mix, 'a DECIMAL of 21 significant digits beside a DOUBLE arm: converted')
        target.run('SELECT t.n FROM t WHERE t.n IN (SELECT t.n * 9007199254740993 FROM t EXCEPT SELECT t.n + 0.5e0 FROM t)')
        report('precision' in target.last_arm_mix, 'the same in a compound nested in a condition')
        target.run('SELECT t.n FROM t WHERE t.n IN (SELECT t.n FROM t EXCEPT SELECT t.n + 0.5e0 FROM t)')
        report('precision' not in target.last_arm_mix, 'and small integers there: converted one to one')
        report(exact_in_double(2 ** 53) and not exact_in_double(2 ** 53 + 1) and exact_in_double(None) and
               exact_in_double(Decimal('2.3333')) and exact_in_double(Decimal('123456789012345.00')) and
               not exact_in_double(Decimal('0.10000000000000000001')) and not exact_in_double('1'),
               'exact_in_double: integers within 2^53, DECIMALs of at most 15 significant digits')
        target.run('SELECT t.n + 1e0 FROM t UNION ALL SELECT t.n + 0.5e0 FROM t')
        report('precision' not in target.last_arm_mix, 'two DOUBLE arms: nothing is converted')
        report(arm_mix_verdict('Up violated', set(), {'types'}) == 'Up violated' and
               arm_mix_verdict('Up violated', {'collations', 'types'}, set()) == 'collation' and
               arm_mix_verdict('Up violated', set(), set()) == 'Up violated' and
               arm_mix_verdict('ok', {'types'}, set()) == 'ok',
               'mixed collations under INTERSECT / EXCEPT: collation; mixed types: judged per column (rejudge)')
        target.run('SELECT t.n FROM t UNION SELECT t.a FROM t UNION SELECT t.n + 0.5 FROM t')
        report(target.last_mixed_columns == {0}, 'the mixed column of a compound is recorded %r' % target.last_mixed_columns)
        # a server that does not report the collations of result columns (TiDB): the
        # coarsest collation of the database for every text column, binary kept
        report(target.trusted_collations, 'this server reports the collations of result columns')
        target.trusted_collations = False
        target.run('SELECT t.a, t.b, t.n FROM t')
        report(target.last_collations[:2] == [MariaDBColumns.COARSEST] * 2,
               'untrusted metadata: text columns are compared with the coarsest collation %r' % target.last_collations)
        target.run('SELECT t.n FROM t UNION SELECT t.a FROM t')
        report('types' in target.last_arm_mix, 'untrusted metadata: the arms of a compound are still probed for types')
        target.run('SELECT t.a FROM t EXCEPT SELECT t.b FROM t')
        report('collations' in target.last_arm_mix, 'untrusted metadata: EXCEPT over text is judged modulo collation')
        target.trusted_collations = True
        # a value the driver cannot convert: the query fails, the connection is opened again
        from pymysql.constants import FIELD_TYPE
        saved = target.conn.decoders[FIELD_TYPE.LONG]
        target.conn.decoders[FIELD_TYPE.LONG] = lambda v: int('not a number')
        failed, _ = target.run('SELECT t.n FROM t')
        target.conn.decoders[FIELD_TYPE.LONG] = saved
        again, _ = target.run('SELECT t.a, t.n FROM t ORDER BY t.n')
        report(failed is None and again is not None and len(again) == 2
               and target.last_collations[0] == 'utf8mb4_general_ci',
               'a driver error fails one query; the next one runs with the column metadata (PolarDB-X)')
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
