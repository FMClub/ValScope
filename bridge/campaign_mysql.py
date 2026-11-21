"""Campaign on a MySQL-protocol server (MariaDB, MySQL, ...) over random databases.

    python3 bridge/campaign_mysql.py --seeds 1-30 --queries 40 [--focus] [--rich] [--value-ext]
        --host H --port P --user U --password W --out violations.jsonl

For every seed: the database `--database` (default vs_campaign; dropped and created) is
built by gen_mysql_db.py, N set-semantic and N value queries are generated for it
(gen_fragment.py --mysql-seed), and run_on_db.py checks them: translation validation,
then every mutant against the relation of its rule's theorem.  The violations are
appended to --out with the seed, so a pair is reproduced from

    python3 bridge/gen_mysql_db.py SEED | mysql --force DATABASE        # the database
    the `original` and `mutant` of the record

One server, one version: unlike campaign_sqlite.py there is no reference release, so every
violation is a candidate to analyse (a DBMS bug, or a gap of the bridge).
"""
import argparse
import ast
import collections
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_mysql_db  # noqa: E402


def parse_range(text):
    out = []
    for part in text.split(','):
        a, _, b = part.partition('-')
        out += range(int(a), int(b or a) + 1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--seeds', default='1-10')
    ap.add_argument('--queries', type=int, default=40, help='queries of each kind per seed')
    ap.add_argument('--focus', action='store_true')
    ap.add_argument('--rich', action='store_true')
    ap.add_argument('--value-ext', action='store_true')
    ap.add_argument('--no-value-distinct', action='store_true',
                    help='value queries without DISTINCT / UNION (MariaDB: issues/009 hides the rest)')
    ap.add_argument('--flip', action='store_true', help='negative control')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--database', default='vs_campaign')
    ap.add_argument('--out', default=None, help='JSON lines file for the violations')
    a = ap.parse_args()
    import pymysql
    admin = pymysql.connect(host=a.host, port=a.port, user=a.user, password=a.password, autocommit=True)
    cur = admin.cursor()
    cur.execute('SELECT VERSION()')
    version = cur.fetchone()[0]
    tmp = tempfile.mkdtemp(prefix='vs_mysql_')
    conn = ['--host', a.host, '--port', str(a.port), '--user', a.user, '--password', a.password,
            '--database', a.database]
    gen_opts = [o for o, on in (('--focus', a.focus), ('--rich', a.rich)) if on]
    total, pairs = collections.Counter(), set()
    for seed in parse_range(a.seeds):
        used = gen_mysql_db.build(cur, a.database, seed)
        new = 0
        for kind in ('set', 'value'):
            qfile = os.path.join(tmp, '%s-%d.sql' % (kind, seed))
            opts = gen_opts + (['--value'] + (['--value-ext'] if a.value_ext else []) +
                               (['--no-value-distinct'] if a.no_value_distinct else []) if kind == 'value' else [])
            with open(qfile, 'w') as f:
                subprocess.run([sys.executable, os.path.join(HERE, 'gen_fragment.py')] + opts +
                               ['--mysql-seed', str(seed), str(a.queries), str(seed)], stdout=f, check=True)
            vfile = os.path.join(tmp, 'v-%s-%d.jsonl' % (kind, seed))
            r = subprocess.run([sys.executable, os.path.join(HERE, 'run_on_db.py'), qfile] + conn +
                               (['--value'] if kind == 'value' else []) + (['--flip'] if a.flip else []) +
                               ['--out', vfile], capture_output=True, text=True)
            for line in r.stdout.splitlines():
                if line.startswith('{'):
                    for k, v in ast.literal_eval(line).items():
                        total[k] += v
            if r.returncode != 0:
                total['runs_failed'] += 1
                print('seed %d, %s queries: run_on_db failed: %s' % (seed, kind, r.stderr.strip()[-200:]), file=sys.stderr)
            if os.path.exists(vfile):
                for line in open(vfile):
                    rec = json.loads(line)
                    rec.update(seed=seed, server=version, kind=kind, database=used)
                    key = (rec['original'], rec['mutant'])
                    new += key not in pairs
                    pairs.add(key)
                    print('VIOLATION [seed %d] %s %s (%s)\n  original: %s\n  mutant  : %s'
                          % (seed, rec['expect'], rec['rule'], rec['verdict'], rec['original'], rec['mutant']))
                    if a.out:
                        with open(a.out, 'a') as f:
                            f.write(json.dumps(rec) + '\n')
        print('-- seed %d done: %d new violating pairs; %s' % (seed, new, dict(total)), flush=True)
    cur.execute('DROP DATABASE IF EXISTS `%s`' % a.database)
    shutil.rmtree(tmp, ignore_errors=True)
    total['violating_pairs'] = len(pairs)
    print('server: %s' % version)
    print(dict(total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
