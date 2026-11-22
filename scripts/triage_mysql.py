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
5. a hint: the known issue of this server whose look the reduced pair has (hint()).

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


def server_family(version):
    """'tidb', 'oceanbase', 'polardbx', 'mariadb' or 'mysql' (MySQL, Percona Server) from the
    version string of a server."""
    v = version or ''
    for mark, family in (('TiDB', 'tidb'), ('OceanBase', 'oceanbase'), ('PXC', 'polardbx'),
                         ('PolarDB', 'polardbx'), ('MariaDB', 'mariadb')):
        if mark in v:
            return family
    return 'mysql'


def _sum_minus_constant(o, m, both, index_only):
    for col in set(re.findall(r'COUNT\s*\(\s*DISTINCT\s+(T\w+\.C\d+)\s*\)', both)):
        c = re.escape(col)
        if re.search(r'\b(SUM|AVG|VAR\w*|STD\w*)\s*\(\s*\(?\s*%s\s*[-+]\s*\(?-?\d' % c, both) \
                and re.search(r'\b(SUM|AVG|VAR\w*|STD\w*)\s*\(\s*%s\s*\)' % c, both):
            return True
    return False


def _having_in_subquery(o, m, both, index_only):
    having = o.rfind(' HAVING ')
    return having >= 0 and ' IN (SELECT ' in o[having:]


# (issue, the servers it was found on, its look); in this order when the server is not known
HINTS = [
    ('020', {'polardbx'},       # an INTERSECT / EXCEPT arm, aggregates, no GROUP BY, constant false HAVING
     lambda o, m, both, ix: ('HAVING 1 = 0' in m or 'HAVING FALSE' in m) and (' INTERSECT ' in m or ' EXCEPT ' in m)
     and ' GROUP BY ' not in m),
    ('018', {'tidb'},           # AVG (a DECIMAL) gone from a UNION arm changes how the others are rounded
     lambda o, m, both, ix: ' UNION ' in o and o.count('AVG(') > m.count('AVG(')),
    ('016', {'tidb'},           # x NOT IN (q) and NOT (x IN (q)) differ (the translation check)
     lambda o, m, both, ix: ' NOT IN (SELECT ' in o and ' NOT IN (SELECT ' not in m and 'NOT (' in m),
    ('010', {'mariadb'},        # a window, a DISTINCT aggregate, a (semi-)join
     lambda o, m, both, ix: ' OVER ' in both and bool(DISTINCT_AGGREGATE.search(both))
     and (' JOIN ' in o or ' IN (SELECT ' in o)),
    ('003', {'mariadb'}, _having_in_subquery),      # HAVING <aggregate> IN (subquery)
    ('012', {'mariadb'},        # IN (subquery) that needs an index to go wrong
     lambda o, m, both, ix: ix and ' IN (SELECT ' in o),
    ('009', {'mariadb'},        # an aggregate computed at the end, under SELECT DISTINCT
     lambda o, m, both, ix: o.startswith('SELECT DISTINCT') and ' GROUP BY ' in o
     and bool(re.search(r'\b(AVG|STD\w*|VAR\w*)\s*\(', o))),
    ('013', {'mariadb'},        # GROUP BY x % n with a DISTINCT aggregate on one side
     lambda o, m, both, ix: bool(re.search(r' GROUP BY .*%', o)) and bool(DISTINCT_AGGREGATE.search(both))),
    ('008', {'mysql'},          # INTERSECT, and a NULL of an outer join or a COALESCE(x, 0)
     lambda o, m, both, ix: ' INTERSECT ' in o and (' LEFT JOIN ' in o or 'COALESCE(' in o)),
    ('015', {'mysql'},          # LEFT JOIN with an EXISTS, under a NOT EXISTS
     lambda o, m, both, ix: ' LEFT JOIN ' in o and 'NOT (EXISTS ' in o and o.count('EXISTS ') >= 2),
    ('023', {'oceanbase'}, _sum_minus_constant),    # SUM(x - k) next to SUM(x) and COUNT(DISTINCT x)
    ('024', {'polardbx'},       # UNION ALL with a parenthesized UNION on its right (or the other way round)
     lambda o, m, both, ix: bool(re.search(r'UNION ALL \(\(SELECT .*\) UNION \(SELECT ', m)
                                 or re.search(r' UNION \(\(SELECT .*\) UNION ALL \(SELECT ', m))),
    ('022', {'polardbx'},       # an INTERSECT / EXCEPT arm: DISTINCT table LEFT JOIN, WHERE ... IN (subquery)
     lambda o, m, both, ix: (' INTERSECT ' in m or ' EXCEPT ' in m) and ' LEFT JOIN ' in m
     and '(SELECT DISTINCT * FROM ' in m and ' IN (SELECT ' in m),
    ('021', {'polardbx'},       # a correlated IN over (SELECT DISTINCT * FROM t)
     lambda o, m, both, ix: ' IN (SELECT ' in m and '(SELECT DISTINCT * FROM ' in m[m.index(' IN (SELECT '):]),
]


def hint(original, mutant, index_only, server=None):
    """The known issue that a reduced pair looks like, or ''.  `server`: the family of the
    server (server_family()); only the issues found on it are considered.  Without it, all of
    them, in the order of HINTS.  A hint, not a verdict: it is checked against the classified
    pairs of results/mariadb-campaign.jsonl (bridge/test_bridge.py), and a new defect can have
    the look of a known one."""
    o, m = original.upper(), mutant.upper()
    both = o + ' ' + m
    for issue, servers, looks in HINTS:
        if (server is None or server in servers) and looks(o, m, both, index_only):
            return issue
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
    import pymysql
    with pymysql.connect(host=a.host, port=a.port, user=a.user, password=a.password) as conn, conn.cursor() as cur:
        cur.execute('SELECT VERSION()')
        server = server_family(cur.fetchone()[0])
    print('hints for the issues found on %s' % server)
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
            r['hint'] = hint(pair[0], pair[1], not violated(r['no_indexes']), server)
            with open(os.path.join(a.out_dir, 'pair-%d.sql' % n), 'w') as f:
                f.write(p.stdout)
            print('pair %d (seed %d): %s' % (n, r['seed'], pair[0][:150]), flush=True)
        r['pair'] = n
    if os.path.exists(one):        # no pair was still violated: nothing was reduced
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
