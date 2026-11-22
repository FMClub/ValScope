"""Re-check recorded violations from scratch and summarise them.

    python3 bridge/confirm_sqlite.py --libs LIB.so ... [--latest NEWEST.so] VIOLATIONS.jsonl [...] > report.md

For every recorded violation, the database of its seed is rebuilt by every library and
by the SQLite that Python ships; the original and the mutant are run again on each,
and the relation is checked again.  A violation counts as CONFIRMED when it reproduces
on the version that reported it and the relation holds on the reference SQLite (so the
old version computed a wrong result that a later release corrected).  The reference is
the library given with --latest (the newest release, built from source), or the SQLite
that Python ships.  A bug that the Python SQLite still has is confirmed only with --latest.
"""
import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sqlite_records  # noqa: E402
from sqlite_exec import SQLiteLib  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--libs', nargs='+', required=True)
    ap.add_argument('--latest', default=None, metavar='LIB.so',
                    help='the reference library (default: the SQLite that Python ships)')
    ap.add_argument('files', nargs='+')
    args = ap.parse_args()
    recs = sqlite_records.read(*args.files)
    tmp = tempfile.mkdtemp(prefix='vs_confirm_')
    cache = {}

    def db_for(lib, rec):
        key = (lib, rec['seed'], sqlite_records.focus_of(rec))
        if key not in cache:
            path = os.path.join(tmp, '%s_%d_%d.db' % (os.path.basename(lib or 'python'), key[1], key[2]))
            cache[key] = sqlite_records.database(lib, path, rec)
        return cache[key]

    libs = [None if lib == 'python' else lib for lib in args.libs]
    confirmed = 0
    rows = []
    for i, rec in enumerate(recs, 1):
        per_version = {}
        for lib in libs + [None] + ([args.latest] if args.latest else []):
            db, used = db_for(lib, rec)
            per_version[db.version] = sqlite_records.verdict(db, rec, used)
        own = per_version[rec['version']][0]
        latest_version = SQLiteLib(args.latest, ':memory:').version
        latest = per_version[latest_version][0]
        ok = own not in ('ok', 'collation', 'incomparable') and not own.startswith('error') \
            and latest in ('ok', 'collation')
        confirmed += ok
        affected = sorted(v for v, r in per_version.items()
                          if r[0] not in ('ok', 'collation', 'incomparable') and not r[0].startswith('error'))
        rows.append((i, rec, ok, affected, per_version))
    print('# SQLite violations found by the verified mutators\n')
    print('%d recorded, %d confirmed (reproduced on the reporting version, relation holds on SQLite %s).\n'
          % (len(recs), confirmed, latest_version))
    print('| # | Reported on | Seed | Rule | Expected | Rows (original / mutant) | Violated on | Confirmed |')
    print('| --- | --- | --- | --- | --- | --- | --- | --- |')
    for i, rec, ok, affected, per_version in rows:
        _, base, res = per_version[rec['version']]
        print('| %d | %s | %d | `%s` | %s | %s / %s | %s | %s |' % (
            i, rec['version'], rec['seed'], rec['rule'], rec['expect'],
            len(base) if base is not None else '-', len(res) if res is not None else '-',
            ', '.join(affected), 'yes' if ok else 'no'))
    print()
    for i, rec, ok, affected, per_version in rows:
        _, base, res = per_version[rec['version']]
        print('## %d. `%s` on SQLite %s (seed %d)\n' % (i, rec['rule'], rec['version'], rec['seed']))
        print('Expected relation: %s. Verdict: %s.\n' % (rec['expect'], per_version[rec['version']][0]))
        print('```sql\n-- original\n%s;\n-- mutant\n%s;\n```\n' % (rec['original'], rec['mutant']))
        print('Original rows: `%s`\n\nMutant rows: `%s`\n' % (sorted(map(repr, base or []))[:12], sorted(map(repr, res or []))[:12]))
        print('Per version: %s\n' % ', '.join('%s: %s' % (v, r[0]) for v, r in sorted(per_version.items())))


if __name__ == '__main__':
    main()
