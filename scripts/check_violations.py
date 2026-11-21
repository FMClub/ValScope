#!/usr/bin/env python3
"""Fail when a run reports a violation that is not in the baseline.

    scripts/check_violations.py VIOLATIONS.jsonl BASELINE.txt
    scripts/check_violations.py --keys VIOLATIONS.jsonl        # print the keys, for a baseline

A violation is identified by its rule and a hash of the original and the mutant SQL.  The
baseline lists the known ones (each with a comment: the issue or bug it shows).  A new key
means a new violation, which is either a DBMS bug to record or a false alarm of the tool:
CI fails so that it is looked at.  Known keys that do not appear are reported, not failed.
"""
import hashlib
import json
import os
import sys


def key(rec):
    h = hashlib.sha1((rec['original'] + '\n' + rec['mutant']).encode()).hexdigest()[:16]
    return '%s|%s' % (rec['rule'].replace(' ', '_'), h)


def read(path):
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


def main():
    if sys.argv[1] == '--keys':
        for rec in read(sys.argv[2]):
            print('%s  # %s' % (key(rec), rec['original'][:80]))
        return 0
    recs, base = read(sys.argv[1]), {}
    for line in open(sys.argv[2]):
        line = line.split('#')[0].strip()
        if line:
            base[line] = True
    new = [r for r in recs if key(r) not in base]
    seen = {key(r) for r in recs}
    for k in base:
        if k not in seen:
            print('note: known violation %s did not appear in this run' % k)
    for r in new:
        print('NEW VIOLATION %s (%s)\n  original: %s\n  mutant  : %s' % (key(r), r.get('verdict'), r['original'], r['mutant']))
    print('%d violations, %d known, %d new' % (len(recs), len(recs) - len(new), len(new)))
    return 1 if new else 0


if __name__ == '__main__':
    sys.exit(main())
