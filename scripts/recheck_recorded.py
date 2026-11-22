"""Judge the recorded MariaDB pairs again with the present checker: a regression test of the
checker against its own history.

    python3 scripts/recheck_recorded.py [--port P] [--password W] [--campaigns 2-6] [--seeds N-M]

results/mariadb-campaign.jsonl holds every pair of the campaigns on MariaDB 10.11 with the
issue it was assigned to.  A pair assigned to a defect of the server must still be violated:
when a change of the checker makes it 'ok', 'incomparable' or 'collation', the change hides
that defect (round 16 of docs/JOURNAL.md found five such pairs this way).  A pair assigned to
the tool ('tool: ...') is a false alarm found later and must no longer be violated.

Known exceptions (pairs that a rule of the checker hides on purpose, with the reason) are
listed in KNOWN_HIDDEN.  Exit status 1 when a pair changed its verdict otherwise.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'bridge'))
from recheck_mysql import recheck, unique_pairs, violated  # noqa: E402

RECORDS = os.path.join(HERE, '..', 'results', 'mariadb-campaign.jsonl')
# (seed, rule): why the present checker does not report it
KNOWN_HIDDEN = {
    (42, 'DISTINCT-add'): 'an EXCEPT over a _ci and a _bin column, and the rows that differ hold strings with letters: which representative a DISTINCT kept can explain them',
}


def parse_range(text):
    a, _, b = text.partition('-')
    return int(a), int(b or a)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--campaigns', default='2-6', help='the campaigns whose pairs are rechecked')
    ap.add_argument('--seeds', default=None, help='only the pairs of these seeds (N-M)')
    a = ap.parse_args()
    lo, hi = parse_range(a.campaigns)
    slo, shi = parse_range(a.seeds) if a.seeds else (0, 10 ** 9)
    tmp = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'vs_recorded.jsonl')
    with open(RECORDS) as f, open(tmp, 'w') as out:
        for line in f:
            r = json.loads(line)
            if lo <= r.get('campaign', 1) <= hi and slo <= r['seed'] <= shi:
                out.write(line)
    recs = unique_pairs(tmp)
    os.remove(tmp)
    changed = hidden = 0
    for r, v in zip(recs, recheck(recs, a)):
        tool = r['issue'].startswith('tool')
        expected = not tool
        if violated(v) == expected:
            continue
        why = KNOWN_HIDDEN.get((r['seed'], r['rule']))
        if why and not tool:
            hidden += 1
            print('hidden on purpose\tseed %d\t%s\t%s\t%s (%s)' % (r['seed'], r['rule'], r['issue'], v, why))
            continue
        changed += 1
        print('CHANGED\tseed %d\t%s\tissue %s\t%s (expected %s)'
              % (r['seed'], r['rule'], r['issue'], v, 'violated' if expected else 'not violated'))
    print('%d recorded pairs, %d changed their verdict, %d hidden on purpose' % (len(recs), changed, hidden))
    return 1 if changed else 0


if __name__ == '__main__':
    sys.exit(main())
