"""Re-check the violations of a MySQL-protocol campaign (campaign_mysql.py --out).

    python3 bridge/recheck_mysql.py VIOLATIONS.jsonl --host H --port P --user U --password W
        [--no-indexes] [--out STILL.jsonl]

For every recorded pair the database of its seed is rebuilt (gen_mysql_db.py) and the
original and the mutant are run and judged again, with the present checker.  With
--no-indexes the secondary indexes are dropped first: a pair that is violated with them and
not without depends on the access path, which no query result may do.

Prints one line per pair and the counts; --out keeps the pairs that are still violated.
"""
import argparse
import collections
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_mysql_db  # noqa: E402
from run_on_db import MySQLTarget, capture, judge_results  # noqa: E402

DATABASE = 'vs_recheck'


def drop_indexes(cur):
    cur.execute("SELECT TABLE_NAME, INDEX_NAME FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = %s AND INDEX_NAME <> 'PRIMARY' GROUP BY TABLE_NAME, INDEX_NAME", (DATABASE,))
    for table, index in cur.fetchall():
        cur.execute('ALTER TABLE `%s` DROP INDEX `%s`' % (table, index))
    for table in gen_mysql_db.COLUMNS:
        cur.execute('ANALYZE TABLE `%s`' % table)
        cur.fetchall()


def judge(target, rec):
    """The verdict on a recorded pair, judged as run_on_db.py judges it (judge_results)."""
    base = capture(target, rec['original'])
    res = capture(target, rec['mutant'])
    if base is None or res is None:
        return 'error'
    if rec['rule'] == 'TRANSLATION':
        v = judge_results(target, base, res, 'Same')
        return v if v in ('ok', 'collation', 'incomparable') else 'translation mismatch'
    return judge_results(target, base, res, rec['expect'], cover=bool(rec.get('distinct')),
                         single=bool(rec.get('single')), sql=rec['original'])


def unique_pairs(path):
    """The records of a campaign file, one per (original, mutant), sorted by seed."""
    recs, seen = [], set()
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            if (r['original'], r['mutant']) not in seen:
                seen.add((r['original'], r['mutant']))
                recs.append(r)
    recs.sort(key=lambda r: r['seed'])
    return recs


def violated(verdict):
    return verdict not in ('ok', 'collation', 'incomparable', 'type_mismatch', 'error')


def recheck(recs, conn, no_indexes=False):
    """The verdicts of the records (sorted by seed) on the server of `conn` (host, port,
    user, password); the database of every seed is rebuilt."""
    import pymysql
    admin = pymysql.connect(host=conn.host, port=conn.port, user=conn.user, password=conn.password, autocommit=True)
    cur = admin.cursor()
    seed, target, verdicts = None, None, []
    for r in recs:
        if r['seed'] != seed:
            seed = r['seed']
            gen_mysql_db.build(cur, DATABASE, seed)
            if no_indexes:
                drop_indexes(cur)
            target = MySQLTarget(types.SimpleNamespace(host=conn.host, port=conn.port, user=conn.user,
                                                       password=conn.password, database=DATABASE))
        verdicts.append(judge(target, r))
    cur.execute('DROP DATABASE IF EXISTS `%s`' % DATABASE)
    return verdicts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--no-indexes', action='store_true', help='drop the secondary indexes before the check')
    ap.add_argument('--out', default=None, help='write the pairs that are still violated')
    a = ap.parse_args()
    recs = unique_pairs(a.file)
    counts, kept = collections.Counter(), []
    for r, v in zip(recs, recheck(recs, a, a.no_indexes)):
        bad = violated(v)
        counts['violated' if bad else v] += 1
        r['recheck'] = v
        if bad:
            kept.append(r)
        print('%s\tseed %d\t%s\t%s' % ('VIOLATED' if bad else v, r['seed'], r['rule'], r['expect']))
    if a.out:
        with open(a.out, 'w') as f:
            f.write(''.join(json.dumps(r) + '\n' for r in kept))
    print(dict(counts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
