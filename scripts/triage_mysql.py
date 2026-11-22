"""Triage the violations of a campaign on a MySQL-protocol server (bridge/campaign_mysql.py).

    python3 scripts/triage_mysql.py VIOLATIONS.jsonl --port P --password W --out-dir DIR
        [--host H] [--user U] [--timeout SECONDS]

On such a server there is no reference release, so a violating pair is a candidate that a
person classifies.  This script does the mechanical part for every pair:

1. the pair again, with the present checker (a pair that is not violated any more was a
   false alarm that has been fixed, or depends on something that changed);
2. the pair without the secondary indexes (violated with them only: the access path);
3. the reduction (bridge/reduce_mysql.py --build-seed) to a short query and few rows;
4. the shape of the reduced original: its text with names and constants removed;
5. a hint: the known issue whose look the reduced pair has (hint()).

It writes DIR/pair-N.sql (the reduced scripts), DIR/triage.jsonl (the records with the
fields `recheck`, `no_indexes`, `reduced_original`, `reduced_mutant`, `shape`, `hint`) and prints a
table of the shapes, largest first.  Pairs of one shape are very likely one defect; which
defect, and whether two shapes are the same one, is for the reader to decide.
"""
import argparse
import collections
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(HERE, '..', 'bridge')
sys.path.insert(0, BRIDGE)
from recheck_mysql import recheck, unique_pairs, violated  # noqa: E402

SCRATCH_DB = 'vs_triage'


def shape(sql):
    """The query with table aliases, column names and constants replaced: what is left is
    the clauses, the operators and the functions."""
    s = re.sub(r"'[^']*'", 'S', sql)
    s = re.sub(r'\bt\d\w*\.c\d+\b', 'C', s)             # t3a.c9
    s = re.sub(r'\bt\d\w*\b', 'T', s)                   # t3, t3a, t3h88
    s = re.sub(r'\bk\d+\b', 'K', s)
    s = re.sub(r'\bd\.K\b|\bc\d+\b', 'C', s)
    s = re.sub(r'-?\b\d+(\.\d+)?\b', 'N', s)
    s = re.sub(r'\(N\)', 'N', s)
    return re.sub(r'\s+', ' ', s).strip()


DISTINCT_AGGREGATE = re.compile(r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*DISTINCT\b')


def hint(original, mutant, index_only):
    """The known issue (MariaDB; 015: MySQL) that a reduced pair looks like, or ''.  A hint, not a
    verdict: it is checked against the classified pairs of results/mariadb-campaign.jsonl
    (bridge/test_bridge.py), and a new defect can have the look of a known one."""
    o, both = original.upper(), (original + ' ' + mutant).upper()
    if ' UNION ' in o and o.count('AVG(') > mutant.upper().count('AVG('):
        return '018'        # TiDB: AVG (a DECIMAL) gone from a UNION arm changes how the others are rounded
    if ' NOT IN (SELECT ' in o and ' NOT IN (SELECT ' not in mutant.upper() and 'NOT (' in mutant.upper():
        return '016'        # TiDB: x NOT IN (q) and NOT (x IN (q)) differ (the translation check)
    having = o.rfind(' HAVING ')
    if ' OVER ' in both and DISTINCT_AGGREGATE.search(both) and (' JOIN ' in o or ' IN (SELECT ' in o):
        return '010'        # a window, a DISTINCT aggregate, a (semi-)join
    if having >= 0 and ' IN (SELECT ' in o[having:]:
        return '003'        # HAVING <aggregate> IN (subquery)
    if index_only and ' IN (SELECT ' in o:
        return '012'        # IN (subquery) that needs an index to go wrong
    if o.startswith('SELECT DISTINCT') and ' GROUP BY ' in o and re.search(r'\b(AVG|STD\w*|VAR\w*)\s*\(', o):
        return '009'        # an aggregate computed at the end, under SELECT DISTINCT
    if re.search(r' GROUP BY .*%', o) and DISTINCT_AGGREGATE.search(both):
        return '013'        # GROUP BY x % n with a DISTINCT aggregate on one side
    if ' INTERSECT ' in o and (' LEFT JOIN ' in o or 'COALESCE(' in o):
        return '008'        # MySQL: INTERSECT, and a NULL of an outer join or a COALESCE(x, 0)
    if ' LEFT JOIN ' in o and 'NOT (EXISTS ' in o and o.count('EXISTS ') >= 2:
        return '015'        # MySQL: LEFT JOIN with an EXISTS, under a NOT EXISTS
    return ''


def reduced_pair(script):
    """(original, mutant) of a script printed by reduce_mysql.py, or None."""
    lines = script.splitlines()
    try:
        return lines[lines.index('-- original') + 1], lines[lines.index('-- mutant') + 1]
    except (ValueError, IndexError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--timeout', type=int, default=600, help='seconds for the reduction of one pair')
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    recs = unique_pairs(a.file)
    for r, v in zip(recs, recheck(recs, a)):
        r['recheck'] = v
    live = [r for r in recs if violated(r['recheck'])]
    for r, v in zip(live, recheck(live, a, no_indexes=True)):
        r['no_indexes'] = v
    print('%d pairs, %d still violated, %d of them only with the secondary indexes'
          % (len(recs), len(live), sum(not violated(r['no_indexes']) for r in live)), flush=True)
    one = os.path.join(a.out_dir, 'one.jsonl')
    for n, r in enumerate(live, 1):
        with open(one, 'w') as f:
            f.write(json.dumps(r) + '\n')
        cmd = [sys.executable, os.path.join(BRIDGE, 'reduce_mysql.py'), one, '--host', a.host, '--port', str(a.port),
               '--user', a.user, '--password', a.password, '--database', SCRATCH_DB, '--build-seed']
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout)
            pair = reduced_pair(p.stdout)
        except subprocess.TimeoutExpired:
            p, pair = None, None
        if pair is None:
            r['reduced_original'], r['reduced_mutant'] = r['original'], r['mutant']
            r['shape'] = 'not reduced: ' + shape(r['original'])
            r['hint'] = ''
            print('pair %d (seed %d): not reduced (%s)'
                  % (n, r['seed'], 'timeout' if p is None else p.stderr.strip()[-120:]), flush=True)
        else:
            r['reduced_original'], r['reduced_mutant'] = pair
            r['shape'] = shape(pair[0])
            r['hint'] = hint(pair[0], pair[1], not violated(r['no_indexes']))
            with open(os.path.join(a.out_dir, 'pair-%d.sql' % n), 'w') as f:
                f.write(p.stdout)
            print('pair %d (seed %d): %s' % (n, r['seed'], pair[0][:150]), flush=True)
        r['pair'] = n
    os.remove(one)
    with open(os.path.join(a.out_dir, 'triage.jsonl'), 'w') as f:
        f.write(''.join(json.dumps(r) + '\n' for r in recs))
    groups = collections.defaultdict(list)
    for r in live:
        groups[(r['rule'], r['shape'])].append(r)
    print('\n| Pairs | Rule | Looks like | Without indexes | Seeds | Reduced original (first pair) |\n'
          '| --- | --- | --- | --- | --- | --- |')
    for (rule, _), rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        still = sum(violated(r['no_indexes']) for r in rs)
        hints = sorted({r['hint'] for r in rs})
        print('| %s | `%s` | %s | %d of %d violated | %s | `%s` |'
              % (', '.join(str(r['pair']) for r in rs), rule,
                 ', '.join('issue ' + h if h else 'nothing known' for h in hints), still, len(rs),
                 ', '.join(sorted({str(r['seed']) for r in rs}, key=int)), rs[0]['reduced_original']))
    gone = [r for r in recs if not violated(r['recheck'])]
    if gone:
        print('\nNot violated any more: %s'
              % ', '.join('seed %d %s (%s)' % (r['seed'], r['rule'], r['recheck']) for r in gone))
    return 0


if __name__ == '__main__':
    sys.exit(main())
