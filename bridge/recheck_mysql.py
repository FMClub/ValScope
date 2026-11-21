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
from checker import check_inclusion, check_value  # noqa: E402
from run_on_db import MySQLTarget, printed_decimals  # noqa: E402

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
    base, base_types = target.run(rec['original'])
    bc, bs = target.last_collations, getattr(target, 'last_scales', None)
    res, types_ = target.run(rec['mutant'])
    if base is None or res is None:
        return 'error'
    fold = target.folds(bc, target.last_collations)
    if rec['rule'] == 'TRANSLATION':
        both = [check_inclusion(d, base, res, fold) for d in ('Up', 'Down')]
        return 'ok' if all(v in ('ok', 'collation') for v in both) else 'translation mismatch'
    if ' col ' in rec['expect']:
        relation, _, column = rec['expect'].split()
        column = int(column)
        decimals = printed_decimals(target, column, base_types, types_, bs)
        return check_value(relation, column, base, res, fold=fold, cover=bool(rec.get('distinct')),
                           output_decimals=decimals)
    return check_inclusion(rec['expect'], base, res, fold)


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
    import pymysql
    admin = pymysql.connect(host=a.host, port=a.port, user=a.user, password=a.password, autocommit=True)
    cur = admin.cursor()
    recs, seen = [], set()
    for line in open(a.file):
        r = json.loads(line)
        if (r['original'], r['mutant']) not in seen:
            seen.add((r['original'], r['mutant']))
            recs.append(r)
    recs.sort(key=lambda r: r['seed'])
    counts, seed, target, kept = collections.Counter(), None, None, []
    for r in recs:
        if r['seed'] != seed:
            seed = r['seed']
            gen_mysql_db.build(cur, DATABASE, seed)
            if a.no_indexes:
                drop_indexes(cur)
            target = MySQLTarget(types.SimpleNamespace(host=a.host, port=a.port, user=a.user,
                                                       password=a.password, database=DATABASE))
        v = judge(target, r)
        bad = v not in ('ok', 'collation', 'incomparable', 'error')
        counts['violated' if bad else v] += 1
        r['recheck'] = v
        if bad:
            kept.append(r)
        print('%s\tseed %d\t%s\t%s' % ('VIOLATED' if bad else v, seed, r['rule'], r['expect']))
    cur.execute('DROP DATABASE IF EXISTS `%s`' % DATABASE)
    if a.out:
        with open(a.out, 'w') as f:
            f.write(''.join(json.dumps(r) + '\n' for r in kept))
    print(dict(counts))
    return 0


if __name__ == '__main__':
    sys.exit(main())
