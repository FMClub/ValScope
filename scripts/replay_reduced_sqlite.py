#!/usr/bin/env python3
"""Replay the reduced SQLite pairs of results/ on the releases that reported them.

    scripts/replay_reduced_sqlite.py --lib 3.26.0=LIB.so [--lib ...] [--latest NEWEST.so]

Every record of results/sqlite-reduced.jsonl is a database (its statements), an original
and a mutant.  On the library of the release that reported the pair the relation must be
violated; on --latest it must hold.  A pair that no longer shows its violation means that
the checker (or the execution layer) changed its verdict on a known bug: the run fails.
Pairs whose release has no library here are counted as skipped.
"""
import argparse
import ast
import json
import os
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'bridge'))
from checker import judge, sqlite_fold  # noqa: E402
from sqlite_exec import SQLiteLib  # noqa: E402


def verdict(lib, rec, path):
    stmts = rec['database']
    stmts = ast.literal_eval(stmts) if isinstance(stmts, str) else stmts
    db = SQLiteLib(lib, path)
    for s in stmts:
        db.query(s)
    fallback = sqlite_fold(stmts)
    base = db.query(rec['original'])
    coll = db.last_collations
    res = db.query(rec['mutant'])
    fold = db.folds(coll, db.last_collations, fallback)
    return judge(rec['expect'], base, res, fold=fold, cover=bool(rec.get('distinct')), strict_types=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lib', action='append', required=True, metavar='VERSION=LIB.so')
    ap.add_argument('--latest', default=None, metavar='LIB.so')
    ap.add_argument('--file', default=os.path.join(ROOT, 'results', 'sqlite-reduced.jsonl'))
    a = ap.parse_args()
    libs = dict(x.split('=', 1) for x in a.lib)
    recs = [json.loads(line) for line in open(a.file) if line.strip()]
    tmp = tempfile.mkdtemp(prefix='vs_replay_')
    bad, skipped = [], 0
    for i, rec in enumerate(recs, 1):
        lib = libs.get(rec['version'])
        if lib is None:
            skipped += 1
            continue
        v = verdict(lib, rec, os.path.join(tmp, 'p%d.db' % i))
        if v in ('ok', 'collation', 'incomparable'):
            bad.append('pair %d (%s, SQLite %s): no longer violated (%s)' % (i, rec['rule'], rec['version'], v))
        if a.latest:
            v = verdict(a.latest, rec, os.path.join(tmp, 'p%d-latest.db' % i))
            if v not in ('ok', 'collation'):
                bad.append('pair %d (%s): violated on the reference library (%s)' % (i, rec['rule'], v))
    for line in bad:
        print(line)
    print('%d pairs, %d replayed, %d skipped (no library), %d failures' % (len(recs), len(recs) - skipped, skipped, len(bad)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
