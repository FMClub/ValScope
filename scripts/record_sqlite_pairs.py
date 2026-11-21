#!/usr/bin/env python3
"""Add the new violating pairs of an SQLite campaign to results/.

    scripts/record_sqlite_pairs.py VIOLATIONS.jsonl --lib 3.26.0=LIB.so --lib 3.30.1=LIB.so ...
        --latest LIB-NEWEST.so --src SQLITE_GIT_CLONE [--cache DIR] [--work DIR]

The steps of results/sqlite-bisect.md, for the pairs that results/ does not have yet:

1. confirm (bridge/confirm_sqlite.py): reproduced on the reporting release, consistent on
   the SQLite that Python ships; a pair that is not confirmed stops the run;
2. bisect on the full database (bridge/bisect_sqlite.py --introduced --compat);
3. reduce, keeping the verdicts on the bisection boundaries (bridge/reduce_sqlite.py
   --boundaries); a pair that cannot be reduced stops the run;
4. bisect the reduced pairs;
5. append to results/sqlite-{confirmed,reduced,bisect,bisect-original}.jsonl, write
   results/sqlite-repro/pair-N.sql, and regenerate the reports (sqlite-confirmed.md, the
   table and the counts of sqlite-bisect.md, the blocks and the summary of
   sqlite-reduced.md).

Nothing in results/ is touched before step 5, and step 5 writes every file from memory, so
a failure leaves results/ as it was.  The narrative (results/sqlite-campaign.md, a new
entry in "The bugs" of sqlite-bisect.md for a bug with new commits) is written by hand.
"""
import argparse
import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
BRIDGE = os.path.join(ROOT, 'bridge')
RES = os.path.join(ROOT, 'results')
sys.path.insert(0, BRIDGE)


def read(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def run(args, out=None):
    print('+ ' + ' '.join(os.path.basename(a) if os.path.sep in a else a for a in args[:6]) + ' ...', file=sys.stderr)
    r = subprocess.run([sys.executable] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    if out:
        open(out, 'w').write(r.stdout)
    return r.stdout


def database(rec):
    d = rec['database']
    return ast.literal_eval(d) if isinstance(d, str) else d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file')
    ap.add_argument('--lib', action='append', required=True, metavar='VERSION=LIB.so')
    ap.add_argument('--latest', required=True, metavar='LIB.so', help='the newest release, built from source')
    ap.add_argument('--src', required=True, help='git clone of https://github.com/sqlite/sqlite')
    ap.add_argument('--cache', default=None)
    ap.add_argument('--work', default='record-work', help='directory for the intermediate files')
    a = ap.parse_args()
    libs = [x.split('=', 1)[1] for x in a.lib]
    cache = a.cache or os.path.join(os.path.dirname(os.path.abspath(a.src)), 'bisect-cache')
    os.makedirs(a.work, exist_ok=True)
    w = lambda name: os.path.join(a.work, name)

    confirmed = read(os.path.join(RES, 'sqlite-confirmed.jsonl'))
    known = {(r['original'], r['mutant']) for r in confirmed}
    new, seen = [], set()
    for r in read(a.file):
        k = (r['original'], r['mutant'])
        if k not in known and k not in seen:
            seen.add(k)
            new.append(r)
    if not new:
        print('no new pair')
        return 0
    open(w('new.jsonl'), 'w').write(''.join(json.dumps(r) + '\n' for r in new))
    n, first = len(new), len(confirmed) + 1

    # 1. confirm
    rep = run([os.path.join(BRIDGE, 'confirm_sqlite.py'), w('new.jsonl'), '--libs'] + libs, w('confirm.md'))
    if '%d recorded, %d confirmed' % (n, n) not in rep:
        sys.exit('not every new pair is confirmed: see %s' % w('confirm.md'))
    # 2. bisect on the full databases
    common = ['--introduced', '--compat', '--src', a.src, '--cache', cache]
    run([os.path.join(BRIDGE, 'bisect_sqlite.py'), w('new.jsonl')] + common + ['--out', w('bisect-original.jsonl')])
    # 3. reduce
    lib_args = [x for l in a.lib for x in ('--lib', l)]
    run([os.path.join(BRIDGE, 'reduce_sqlite.py'), w('new.jsonl')] + lib_args +
        ['--latest', a.latest, '--boundaries', w('bisect-original.jsonl'), '--src', a.src, '--cache', cache,
         '--out', w('reduced.jsonl'), '--sql', w('repro')])
    reduced = read(w('reduced.jsonl')) if os.path.exists(w('reduced.jsonl')) else []
    if len(reduced) != n:
        sys.exit('%d of %d pairs reduced: see %s' % (len(reduced), n, a.work))
    # 4. bisect the reduced pairs
    run([os.path.join(BRIDGE, 'bisect_sqlite.py'), w('reduced.jsonl')] + common + ['--out', w('bisect.jsonl')])
    bis, orig = read(w('bisect.jsonl')), read(w('bisect-original.jsonl'))
    if len(bis) != n or len(orig) != n:
        sys.exit('bisection incomplete: see %s' % a.work)

    # 5. everything is there: compute the new contents, then write
    import bisect_sqlite
    for b in bis:
        b['pairs'] = [first - 1 + p for p in b.get('pairs', [b['pair']])]
    for b in orig:
        b['pair'] = first - 1 + b['pair']
        b.pop('pairs', None)
    files = {}

    def appended(name, recs):
        old = open(os.path.join(RES, name)).read()
        files[name] = old + ('' if old.endswith('\n') else '\n') + ''.join(json.dumps(r) + '\n' for r in recs)
    appended('sqlite-confirmed.jsonl', new)
    appended('sqlite-reduced.jsonl', reduced)
    appended('sqlite-bisect.jsonl', bis)
    appended('sqlite-bisect-original.jsonl', orig)
    for i in range(1, n + 1):
        text = open(os.path.join(w('repro'), 'pair-%d.sql' % i)).read()
        files['sqlite-repro/pair-%d.sql' % (first - 1 + i)] = text.replace('-- pair %d,' % i, '-- pair %d,' % (first - 1 + i), 1)
    # sqlite-reduced.md: the new blocks and the summary sentence
    all_red = read(os.path.join(RES, 'sqlite-reduced.jsonl')) + reduced
    md = open(os.path.join(RES, 'sqlite-reduced.md')).read().rstrip('\n') + '\n'
    for i, r in enumerate(reduced):
        md += ('\n-- pair %d (%s, expected %s): %d -> %d characters\n    original: %s\n    mutant  : %s\n'
               '    rows    : %d / %d\n' % (first + i, r['rule'], r['expect'], len(r['reduced_from']['original']),
                                           len(r['original']), r['original'], r['mutant'],
                                           r['original_rows'], r['mutant_rows']))
    before = [len(r['reduced_from']['original']) for r in all_red]
    after = [len(r['original']) for r in all_red]
    stmts = [len(database(r)) for r in all_red]
    rowid = sum('WITHOUT ROWID' in ' '.join(database(r)) for r in all_red)
    summary = ('All %d pairs are reduced: queries from %d to %d characters on average (%d to %d),\n'
               'databases to %d statements on average (%d to %d); %d of the %d databases'
               % (len(all_red), round(sum(before) / len(before)), round(sum(after) / len(after)), min(after), max(after),
                  round(sum(stmts) / len(stmts)), min(stmts), max(stmts), len(all_red) - rowid, len(all_red)))
    md, k = re.subn(r'All \d+ pairs are reduced: .*?\n.*? of the \d+ databases', lambda m: summary, md, count=1)
    if k != 1:
        sys.exit('sqlite-reduced.md: summary sentence not found')
    files['sqlite-reduced.md'] = md
    # sqlite-bisect.md: the table and the counts
    all_bis = read(os.path.join(RES, 'sqlite-bisect.jsonl')) + bis
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        bisect_sqlite.report(all_bis)
    table = buf.getvalue()
    table = table[table.index('| Bug'):].rstrip() + '\n'
    rows = [l for l in table.split('\n') if re.match(r'\| \d+ \|', l)]
    md = open(os.path.join(RES, 'sqlite-bisect.md')).read()
    md = md[:md.index('| Bug')] + table + '\n' + md[md.index('## The bugs'):]
    md, k = re.subn(r'\*\*The \d+ confirmed pairs come from \d+ distinct SQLite bugs\.\*\*',
                    '**The %d confirmed pairs come from %d distinct SQLite bugs.**' % (len(all_red), len(rows)), md, count=1)
    if k != 1:
        sys.exit('sqlite-bisect.md: headline not found')
    for row in rows:                      # "N. **title** (41 pairs; ..." or "(pairs 27, 28)" in "The bugs"
        bug, nums = row.split('|')[1].strip(), re.findall(r'#(\d+)', row.split('|')[2])
        text = ('%d pairs' % len(nums) if len(nums) > 6 else
                ('pairs ' if len(nums) > 1 else 'pair ') + ', '.join(nums))
        md, k = re.subn(r'(?m)^(%s\. \*\*.*?\*\* \()(?:\d+ pairs|pairs? \d+(?:, \d+)*)' % bug,
                        lambda m: m.group(1) + text, md, count=1)
        if k != 1:
            print('NOTE: bug %s has no entry in "The bugs" of sqlite-bisect.md: write it' % bug)
    files['sqlite-bisect.md'] = md
    os.makedirs(os.path.join(RES, 'sqlite-repro'), exist_ok=True)
    for name, text in files.items():
        with open(os.path.join(RES, name), 'w') as f:
            f.write(text)
    # the full report, from the complete file
    rep = run([os.path.join(BRIDGE, 'confirm_sqlite.py'), os.path.join(RES, 'sqlite-confirmed.jsonl'), '--libs'] + libs)
    total = len(confirmed) + n
    if '%d recorded, %d confirmed' % (total, total) not in rep:
        sys.exit('the complete file is not fully confirmed (results/sqlite-confirmed.md not rewritten)')
    open(os.path.join(RES, 'sqlite-confirmed.md'), 'w').write(rep)
    for row in rows:
        print(row[:200])
    print('recorded pairs %d to %d (%d confirmed pairs, %d bugs)' % (first, total, total, len(rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
