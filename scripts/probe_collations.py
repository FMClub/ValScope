"""Print what the bridge learns about the collations of result columns on a server.

    python3 scripts/probe_collations.py [--host H] [--port P] [--user U] [--password W]

The checker compares strings modulo the collation that the server reports for each result
column (bridge/run_on_db.py, MySQLTarget.run).  A server that reports the wrong collation
for a column makes the checker wrong: 'binary' for a case-insensitive column turns every
choice of 'a' or 'A' by a DISTINCT into a violation.  This script creates a scratch database
with a utf8mb4_general_ci and a utf8mb4_bin column, runs a few queries through the same code
path as a campaign and prints, per query, the collations the bridge would use and whether
they agree with the columns' declared collations.  When the server is known not to report
them (MySQLTarget.trusted_collations), the coarsest collation of the database ('*') is
the right answer.  Exit status 1 when a probe gets something else.
"""
import argparse
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bridge'))
from checker import MariaDBColumns  # noqa: E402
from run_on_db import MySQLTarget  # noqa: E402

DATABASE = 'vs_probe_collations'
# query, the collations the result columns must have
PROBES = [
    ('SELECT t.c, t.b FROM t', ['utf8mb4_general_ci', 'utf8mb4_bin']),
    ('SELECT DISTINCT t.c FROM t', ['utf8mb4_general_ci']),
    ('SELECT d.c FROM (SELECT DISTINCT t.c FROM t) AS d', ['utf8mb4_general_ci']),
    ('SELECT t.c FROM t GROUP BY t.c', ['utf8mb4_general_ci']),
    ('SELECT t.c FROM t UNION SELECT t.c FROM t', ['utf8mb4_general_ci']),
    ("SELECT CONCAT(t.c, '') FROM t", None),        # derived: printed, not checked
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    a = ap.parse_args()
    import pymysql
    admin = pymysql.connect(host=a.host, port=a.port, user=a.user, password=a.password, autocommit=True)
    cur = admin.cursor()
    cur.execute('SELECT VERSION()')
    print('server:', cur.fetchone()[0])
    cur.execute('DROP DATABASE IF EXISTS %s' % DATABASE)
    cur.execute('CREATE DATABASE %s' % DATABASE)
    cur.execute('CREATE TABLE %s.t (c VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci, '
                'b VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin)' % DATABASE)
    cur.execute("INSERT INTO %s.t VALUES ('a', 'a'), ('A', 'A'), ('a ', 'a ')" % DATABASE)
    wrong = 0
    try:
        target = MySQLTarget(types.SimpleNamespace(host=a.host, port=a.port, user=a.user, password=a.password,
                                                   database=DATABASE))
        print('the server reports the collations of result columns: %s' % target.trusted_collations)
        print('the checker compares text with:', target.name)
        for sql, expected in PROBES:
            rows, _ = target.run(sql)
            got = list(target.last_collations)
            ok = expected is None or got == expected or (not target.trusted_collations and all(
                g == MariaDBColumns.COARSEST for g in got))
            wrong += not ok
            print('%s\t%s\t%s rows\t%s' % ('ok' if ok else 'WRONG', got, None if rows is None else len(rows), sql))
    finally:
        cur.execute('DROP DATABASE IF EXISTS %s' % DATABASE)
    print('%d of %d probes report a collation the checker would get wrong' % (wrong, len(PROBES)))
    return 1 if wrong else 0


if __name__ == '__main__':
    sys.exit(main())
