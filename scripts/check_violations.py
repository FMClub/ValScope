#!/usr/bin/env python3
"""Fail when a run reports a violation that is not in the baseline.

    scripts/check_violations.py VIOLATIONS.jsonl BASELINE.txt
    scripts/check_violations.py --keys VIOLATIONS.jsonl        # print the keys, for a baseline

A violation is identified by its rule and a hash of the original and the mutant SQL.  The
baseline lists the known ones (each with a comment: the issue or bug it shows).  A new key
means a new violation, which is either a DBMS bug to record or a false alarm of the tool:
CI fails so that it is looked at.  Known keys that do not appear are reported, not failed.

A known bug that many generated queries hit is listed by its signature instead, a line
`sig:NAME` of the baseline: a predicate on the record (SIGNATURES below), narrow enough
that another bug is unlikely to satisfy it.  The number of violations each signature
matched is printed.
"""
import hashlib
import json
import os
import re
import sys


def key(rec):
    h = hashlib.sha1((rec['original'] + '\n' + rec['mutant']).encode()).hexdigest()[:16]
    return '%s|%s' % (rec['rule'].replace(' ', '_'), h)


def _issue_009(rec):
    """issues/009 (MariaDB): under SELECT DISTINCT in a grouped query, AVG / STDDEV of the
    last group is copied into every row.  Seen by a value rule as a change in a column
    that the mutation does not touch."""
    sql = rec['original'].upper()
    return (' col ' in rec.get('expect', '') and rec.get('verdict') == 'other columns changed'
            and 'SELECT DISTINCT' in sql and ' GROUP BY ' in sql
            and re.search(r'\b(AVG|STDDEV\w*|STD)\s*\(', sql) is not None)


def _issue_010(rec):
    """issues/010 (MariaDB): in a grouped join with an aggregate with DISTINCT, an expression
    over a window function is 0.  Seen by a value rule as a mutated value 0."""
    sql = rec['original'].upper()
    return (' col ' in rec.get('expect', '') and 'the mutant value 0 ' in rec.get('verdict', '')
            and ' OVER ' in sql and ' JOIN ' in sql and ' GROUP BY ' in sql
            and re.search(r'\b(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*DISTINCT\b', sql) is not None)


SIGNATURES = {'mariadb-distinct-avg': _issue_009, 'mariadb-window-distinct-agg': _issue_010}


def read(path):
    if not os.path.exists(path):
        return []
    return [json.loads(line) for line in open(path) if line.strip()]


def main():
    if sys.argv[1] == '--keys':
        for rec in read(sys.argv[2]):
            print('%s  # %s' % (key(rec), rec['original'][:80]))
        return 0
    recs, base, sigs = read(sys.argv[1]), {}, []
    for line in open(sys.argv[2]):
        line = line.split('#')[0].strip()
        if line.startswith('sig:'):
            if line[4:] not in SIGNATURES:
                sys.exit('unknown signature %s' % line)
            sigs.append(line[4:])
        elif line:
            base[line] = True
    matched = {name: sum(1 for r in recs if key(r) not in base and SIGNATURES[name](r)) for name in sigs}
    new = [r for r in recs if key(r) not in base and not any(SIGNATURES[name](r) for name in sigs)]
    seen = {key(r) for r in recs}
    for k in base:
        if k not in seen:
            print('note: known violation %s did not appear in this run' % k)
    for name, n in matched.items():
        print('signature %s: %d violations' % (name, n))
    for r in new:
        print('NEW VIOLATION %s (%s)\n  original: %s\n  mutant  : %s' % (key(r), r.get('verdict'), r['original'], r['mutant']))
    print('%d violations, %d known, %d new' % (len(recs), len(recs) - len(new), len(new)))
    return 1 if new else 0


if __name__ == '__main__':
    sys.exit(main())
