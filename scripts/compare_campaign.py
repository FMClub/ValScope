"""Compare the pairs of a campaign with those recorded for the same campaign.

    python3 scripts/compare_campaign.py TRIAGE.jsonl --image IMAGE --seeds N-M --options "OPTS"

results/server-campaigns.json lists, for campaigns run on servers other than the local
MariaDB (MySQL, MariaDB 13, TiDB), the violating pairs found after the checker's fixes:
per rule, the seeds and the number of pairs, and the issue they belong to.  Campaigns are
deterministic (the same seeds and options give the same queries), so a campaign that is
run again must find the same pairs, unless the server or the checker changed.

TRIAGE.jsonl is the output of scripts/triage_mysql.py.  Prints the recorded groups that were
not found as recorded and the pairs that belong to no recorded group.  Exit status 1 when
there is a difference, 0 otherwise, 2 when nothing is recorded for this campaign.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RECORDS = os.path.join(HERE, '..', 'results', 'server-campaigns.json')
sys.path.insert(0, os.path.join(HERE, '..', 'bridge'))
from recheck_mysql import violated  # noqa: E402


def norm(options):
    return ' '.join(sorted(options.split()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('triage')
    ap.add_argument('--image', required=True)
    ap.add_argument('--seeds', required=True)
    ap.add_argument('--options', default='')
    a = ap.parse_args()
    doc = json.load(open(RECORDS))
    rec = [c for c in doc['campaigns'] if c['image'] == a.image and c['seeds'] == a.seeds
           and norm(c['options']) == norm(a.options)]
    if not rec:
        print('nothing recorded for %s, seeds %s, %s' % (a.image, a.seeds, a.options))
        return 2
    found = collections.Counter()
    for line in open(a.triage):
        r = json.loads(line)
        if violated(r.get('recheck', 'violated')):
            found[(r['rule'], r['seed'])] += 1
    # groups of one rule and the same seeds are one group here (triage splits them by shape)
    groups = collections.OrderedDict()
    for g in rec[0]['pairs']:
        k = (g['rule'], tuple(sorted(g['seeds'])))
        n, issues = groups.get(k, (0, set()))
        groups[k] = (n + g['pairs'], issues | {g['issue']})
    differences, covered = 0, set()
    for (rule, seeds), (pairs, issues) in groups.items():
        keys = [(rule, s) for s in seeds]
        n = sum(found[k] for k in keys)
        covered.update(keys)
        if n != pairs:
            differences += 1
            print('DIFFERENT\t%s\tseeds %s\tissue %s\trecorded %d pairs, found %d'
                  % (rule, list(seeds), ', '.join(sorted(issues)), pairs, n))
    for (rule, seed), n in sorted(found.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        if (rule, seed) not in covered:
            differences += 1
            print('NEW\t%s\tseed %d\t%d pairs' % (rule, seed, n))
    total = sum(g['pairs'] for g in rec[0]['pairs'])
    print('%d recorded pairs in %d groups, %d found; %d differences'
          % (total, len(groups), sum(found.values()), differences))
    return 1 if differences else 0


if __name__ == '__main__':
    sys.exit(main())
