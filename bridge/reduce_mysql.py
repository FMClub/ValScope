"""Reduce a violation found on a MySQL-protocol server (MariaDB, MySQL, ...).

    python3 bridge/reduce_mysql.py VIOLATIONS.jsonl --pair N --host H --port P --user U --password W --database D

The pair (a line of `run_on_db.py --out`) is reduced like reduce_sqlite.py does it:

1. the query, step by step (an arm instead of a compound, an operand instead of AND / OR,
   a clause, a join or a column dropped, a comparison replaced by 1 or 0); after every step
   the verified mutator runs again, and the step is kept only if a mutant of the same rule
   (and, for a value rule, the same relation and column) still violates the relation;
2. the data: the tables the query reads are copied into the scratch database
   `vs_reduce`, and rows are deleted one by one while the reduced pair stays violated.

The result is printed as a script: CREATE TABLE and INSERT statements for the remaining
rows, then the original and the mutant.  The scratch database is dropped at the end.
"""
import argparse
import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checker import check_inclusion, check_value  # noqa: E402
from reduce_sqlite import variants  # noqa: E402
from run_on_db import MySQLTarget  # noqa: E402
from sql_bridge import mutate_sql, mutate_value  # noqa: E402

SCRATCH = 'vs_reduce'


class Judge:
    def __init__(self, target, rec):
        self.t, self.rec = target, rec
        self.rule = rec['rule']
        self.value = ' col ' in rec['expect']
        self.having = self.rule.startswith('HAVING ')

    def violated(self, original, mutant, rel=None):
        base, _ = self.t.run(original)
        bc = self.t.last_collations
        res, _ = self.t.run(mutant)
        if base is None or res is None:
            return False
        fold = self.t.folds(bc, self.t.last_collations)
        if self.value:
            relation, _, column = self.rec['expect'].split()
            v = check_value(relation, int(column), base, res, fold=fold, cover=self.rec.get('distinct', False))
        else:
            v = check_inclusion(self.rec['expect'], base, res, fold)
        return v not in ('ok', 'collation', 'incomparable')

    def pair(self, sql):
        try:
            if self.value or self.having:
                trs = []
                original, vm, _, _, hm = mutate_value(sql, dialect='mysql', translation=trs, schema=self.t.schema,
                                                      exact_columns=self.t.exact)
                self.rec['distinct'] = trs[0].value_distinct
                if self.value:
                    relation, _, column = self.rec['expect'].split()
                    cands = [m for r0, r, c, m in vm if r == self.rule and r0 == relation and c == int(column)]
                else:
                    cands = [m for d, r, m in hm if 'HAVING ' + r == self.rule and d == self.rec['expect']]
            else:
                original, mutants, _ = mutate_sql(sql, dialect='mysql', schema=self.t.schema, exact_columns=self.t.exact)
                cands = [m for d, r, m in mutants if r == self.rule and d == self.rec['expect']]
        except Exception:
            return None
        for m in cands:
            if self.violated(original, m):
                return original, m
        return None


def reduce_query(judge, sql, log):
    best = judge.pair(sql)
    if best is None:
        return None
    progress = True
    while progress:
        progress = False
        for cand in sorted(set(variants(best[0], 'mysql')), key=lambda c: (len(c), c)):
            if len(cand) >= len(best[0]):
                continue
            got = judge.pair(cand)
            if got is not None and len(got[0]) < len(best[0]):
                best, progress = got, True
                print('  query: %d characters' % len(best[0]), file=log)
                break
    return best


def tables_of(sql, tables):
    low = sql.lower()
    return [t for t in tables if ' %s ' % t.lower() in ' %s ' % low.replace('(', ' ').replace(')', ' ')]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--pair', type=int, default=1, help='1-based line of the file')
    ap.add_argument('--key', default=None, help='the pair with this key (scripts/check_violations.py)')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--database', required=True)
    ap.add_argument('--no-data', action='store_true', help='reduce the query only')
    ap.add_argument('--data-only', action='store_true',
                    help='keep the pair as it is and reduce rows and indexes only (no mutator needed)')
    args = ap.parse_args()
    recs = [json.loads(line) for line in open(args.file) if line.strip()]
    if args.key:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
        from check_violations import key
        recs = [r for r in recs if key(r) == args.key]
        if not recs:
            sys.exit('no pair with key %s' % args.key)
        rec = recs[0]
    else:
        rec = recs[args.pair - 1]
    log = sys.stderr
    # the scratch database: a copy of the tables, so rows can be deleted
    import pymysql
    admin = pymysql.connect(host=args.host, port=args.port, user=args.user, password=args.password, autocommit=True)
    cur = admin.cursor()
    cur.execute('DROP DATABASE IF EXISTS %s' % SCRATCH)
    cur.execute('CREATE DATABASE %s' % SCRATCH)
    cur.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = %s',
                (args.database, 'BASE TABLE'))
    tables = [r[0] for r in cur.fetchall()]
    for t in tables:
        cur.execute('CREATE TABLE %s.`%s` LIKE `%s`.`%s`' % (SCRATCH, t, args.database, t))
        cur.execute('INSERT INTO %s.`%s` SELECT * FROM `%s`.`%s`' % (SCRATCH, t, args.database, t))
    try:
        target = MySQLTarget(types.SimpleNamespace(host=args.host, port=args.port, user=args.user,
                                                   password=args.password, database=SCRATCH))
        judge = Judge(target, rec)
        if not judge.violated(rec['original'], rec['mutant']):
            sys.exit('the pair is not violated on this server')
        got = None if args.data_only else reduce_query(judge, rec.get('query') or rec['original'], log)
        got = got or (rec['original'], rec['mutant'])
        original, mutant = got
        used = tables_of(original + ' ' + mutant, tables)
        if not args.no_data:
            for t in used:
                cur.execute('SELECT * FROM %s.`%s`' % (SCRATCH, t))
                rows = list(cur.fetchall())
                cols = [d[0] for d in cur.description]
                for row in rows:
                    cond = ' AND '.join('`%s` <=> %%s' % c for c in cols)
                    cur.execute('DELETE FROM %s.`%s` WHERE %s LIMIT 1' % (SCRATCH, t, cond), row)
                    if not judge.violated(original, mutant):
                        cur.execute('INSERT INTO %s.`%s` VALUES (%s)' % (SCRATCH, t, ', '.join(['%s'] * len(cols))), row)
                cur.execute('SELECT COUNT(*) FROM %s.`%s`' % (SCRATCH, t))
                print('  %s: %d -> %d rows' % (t, len(rows), cur.fetchone()[0]), file=log)
            # then the secondary indexes: each is dropped, and added back if the pair is no
            # longer violated without it
            for t in used:
                cur.execute('SHOW INDEX FROM %s.`%s`' % (SCRATCH, t))
                idx = {}
                for r in cur.fetchall():
                    d = dict(zip([c[0] for c in cur.description], r))
                    if d['Key_name'] == 'PRIMARY':
                        continue
                    part = '`%s`%s' % (d['Column_name'], '(%d)' % d['Sub_part'] if d.get('Sub_part') else '')
                    idx.setdefault(d['Key_name'], (d['Non_unique'] == 0, []))[1].append((d['Seq_in_index'], part))
                kept = 0
                for name, (unique, parts) in idx.items():
                    cols = ', '.join(p for _, p in sorted(parts))
                    cur.execute('ALTER TABLE %s.`%s` DROP INDEX `%s`' % (SCRATCH, t, name))
                    if not judge.violated(original, mutant):
                        cur.execute('ALTER TABLE %s.`%s` ADD %sINDEX `%s` (%s)'
                                    % (SCRATCH, t, 'UNIQUE ' if unique else '', name, cols))
                        kept += 1
                print('  %s: %d -> %d secondary indexes' % (t, len(idx), kept), file=log)
        # the reproduction script
        print('-- %s (%s): reduced on %s' % (rec['rule'], rec['expect'], target.conn.get_server_info()))
        for t in used:
            cur.execute('SHOW CREATE TABLE %s.`%s`' % (SCRATCH, t))
            print(cur.fetchone()[1] + ';')
            cur.execute('SELECT * FROM %s.`%s`' % (SCRATCH, t))
            for row in cur.fetchall():
                print('INSERT INTO `%s` VALUES (%s);' % (t, ', '.join(admin.escape(v) for v in row)))
        print('-- original\n%s;\n-- mutant\n%s;' % (original, mutant))
    finally:
        cur.execute('DROP DATABASE IF EXISTS %s' % SCRATCH)


if __name__ == '__main__':
    main()
