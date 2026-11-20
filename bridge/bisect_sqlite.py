"""Find the SQLite commits that introduced and fixed each recorded violation.

    python3 bridge/bisect_sqlite.py VIOLATIONS.jsonl --src SQLITE_GIT_CLONE --out bisect.jsonl > bisect.md

A recorded violation (a pair: original query, mutant, database seed, rule, expected
relation; see campaign_sqlite.py) is checked on SQLite built from the source history:

    verdict(commit) = bad   the relation of the rule is violated on that commit
                      good  the relation holds (modulo the collation)
                      skip  the commit does not build, or one of the queries fails on it

1. Fixing commit.  The pair is bad on the release that reported it (--old, by default the
   release in the record) and good on --new (default: the newest release tag).  The
   first-parent history between them is bisected for the first commit that is good: the
   commit that fixed the bug.  (If the pair is bad on --new as well, the bug is live and
   there is no fixing commit.)
2. Introducing commit (--introduced).  Older release tags are tried, going back from
   --old (with doubling steps, then one release at a time), until one is good; the
   history between that release and the next bad one is
   bisected for the first bad commit: the commit that introduced the bug.

Pairs with the same (introducing, fixing) commits are reported as one bug: different
commits, different bugs.  Builds are cached by commit (--cache), so pairs share them.

SQLITE_GIT_CLONE is a clone of https://github.com/sqlite/sqlite (a partial clone without
blobs is enough: git clone --filter=blob:none --no-checkout ...).  Building needs gcc,
make and tclsh.
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checker import check_inclusion, check_value, sqlite_fold  # noqa: E402
from gen_sqlite_db import build as build_db  # noqa: E402
from sqlite_exec import SQLiteLib  # noqa: E402

CFLAGS = ['-O1', '-shared', '-fPIC', '-DSQLITE_THREADSAFE=0', '-DSQLITE_ENABLE_STAT4',
          '-DSQLITE_ENABLE_COLUMN_METADATA']


def git(src, *args):
    return subprocess.run(['git', '-C', src] + list(args), capture_output=True, text=True, check=True).stdout


class Builder:
    """Shared libraries of SQLite at given commits, built once and cached."""

    def __init__(self, src, cache, log=sys.stderr):
        self.src, self.cache, self.log = src, cache, log
        os.makedirs(cache, exist_ok=True)
        self.failed = set()

    def lib(self, sha):
        path = os.path.join(self.cache, 'libsqlite3-%s.so' % sha[:12])
        if os.path.exists(path):
            return path
        if sha in self.failed:
            return None
        work = os.path.join(self.cache, 'work')
        try:
            git(self.src, 'checkout', '-q', '--force', sha)
            shutil.rmtree(work, ignore_errors=True)
            os.makedirs(work)
            run = lambda cmd: subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=900)
            if run([os.path.join(self.src, 'configure'), '--disable-tcl']).returncode != 0 or \
                    run(['make', '-j8', 'sqlite3.c']).returncode != 0:
                raise RuntimeError('configure / make sqlite3.c failed')
            r = run(['gcc'] + CFLAGS + ['sqlite3.c', '-o', path, '-lm', '-ldl'])
            if r.returncode != 0:
                raise RuntimeError('gcc failed: ' + r.stderr[-200:])
            print('  built %s' % sha[:12], file=self.log)
            return path
        except Exception as e:      # a broken commit of the history: skipped
            print('  build of %s failed: %s' % (sha[:12], e), file=self.log)
            self.failed.add(sha)
            return None


def verdict(builder, sha, rec, tmp):
    """'bad', 'good' or 'skip' for one recorded pair on one commit."""
    lib = builder.lib(sha)
    if lib is None:
        return 'skip'
    path = os.path.join(tmp, 'v.db')
    if os.path.exists(path):
        os.remove(path)
    try:
        db = SQLiteLib(lib, path)
        fallback = sqlite_fold(build_db(db, rec['seed'], rec.get('focus', False)))
        base = db.query(rec['original'])
        base_coll = db.last_collations
        res = db.query(rec['mutant'])
    except Exception:
        return 'skip'
    fold = db.folds(base_coll, db.last_collations, fallback)
    if rec['kind'] == 'value':
        relation, _, column = rec['expect'].split()
        v = check_value(relation, int(column), base, res, fold=fold)
    else:
        v = check_inclusion(rec['expect'], base, res, fold)
    if v in ('ok', 'collation'):
        return 'good'
    if v == 'incomparable':
        return 'skip'
    return 'bad'


def first_change(builder, commits, rec, tmp, want, cache):
    """commits[0] has the opposite verdict of `want`, commits[-1] has `want`.  The first
    commit with verdict `want` (bisection; a commit that cannot be judged is skipped by
    testing its neighbours).  Returns (index of the first `want` commit, index of the last
    commit before it with the other verdict, number of verdicts computed); the two indices
    are adjacent unless the commits between them could not be judged."""
    lo, hi, steps = 0, len(commits) - 1, 0
    while hi - lo > 1:
        mid = (lo + hi) // 2
        # look for a judgeable commit near the middle
        probe, v = None, 'skip'
        for off in range(0, hi - lo):
            for cand in (mid + off, mid - off):
                if lo < cand < hi:
                    key = (commits[cand], rec['original'], rec['mutant'])
                    if key not in cache:
                        cache[key] = verdict(builder, commits[cand], rec, tmp)
                        steps += 1
                    v = cache[key]
                    if v != 'skip':
                        probe = cand
                        break
            if probe is not None:
                break
        if probe is None:
            break                     # everything between lo and hi is unjudgeable
        if v == want:
            hi = probe
        else:
            lo = probe
    return hi, lo, steps


def version_tags(src):
    tags = [t for t in git(src, 'tag', '--list', 'version-3.*').split() if re.match(r'version-3\.\d+\.\d+$', t)]
    return sorted(tags, key=lambda t: tuple(int(x) for x in t[len('version-'):].split('.')))


def tag_of_version(version):
    return 'version-' + version


def describe(src, sha):
    out = git(src, 'log', '-1', '--format=%H%x09%ad%x09%s', '--date=short', sha).strip().split('\t')
    contained = git(src, 'tag', '--contains', sha, '--list', 'version-3.*').split()
    first = version_tags_sorted(contained)
    return {'commit': out[0], 'date': out[1], 'subject': out[2], 'first_release': first[0] if first else None}


def version_tags_sorted(tags):
    tags = [t for t in tags if re.match(r'version-3\.\d+\.\d+$', t)]
    return sorted(tags, key=lambda t: tuple(int(x) for x in t[len('version-'):].split('.')))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('files', nargs='+', help='JSON lines of recorded violations')
    ap.add_argument('--src', required=True, help='git clone of https://github.com/sqlite/sqlite')
    ap.add_argument('--cache', default=None, help='directory for built libraries (default: SRC/../bisect-cache)')
    ap.add_argument('--old', default=None, help='a release tag where the pair is bad (default: the reporting version)')
    ap.add_argument('--new', default=None, help='release tag to compare with (default: newest release tag)')
    ap.add_argument('--introduced', action='store_true', help='also find the commit that introduced each bug')
    ap.add_argument('--out', default=None, help='write the per-pair results as JSON lines')
    args = ap.parse_args()
    src = os.path.abspath(args.src)
    builder = Builder(src, args.cache or os.path.join(os.path.dirname(src), 'bisect-cache'))
    tmp = os.path.join(builder.cache, 'db')
    os.makedirs(tmp, exist_ok=True)
    tags = version_tags(src)
    new = args.new or tags[-1]
    sha_of = lambda ref: git(src, 'rev-parse', ref + '^{commit}').strip()
    recs, seen = [], set()
    for f in args.files:
        for line in open(f):
            r = json.loads(line)
            key = (r['original'], r['mutant'])
            if key not in seen:
                seen.add(key)
                recs.append(r)
    cache, results = {}, []
    for i, rec in enumerate(recs, 1):
        old = args.old or tag_of_version(rec['version'])
        print('pair %d/%d: seed %s, %s, reported on %s' % (i, len(recs), rec['seed'], rec['rule'], rec['version']),
              file=sys.stderr)
        res = {'pair': i, 'seed': rec['seed'], 'rule': rec['rule'], 'reported_on': rec['version'],
               'original': rec['original'], 'mutant': rec['mutant']}
        v_old = cache.setdefault((sha_of(old), rec['original'], rec['mutant']), verdict(builder, sha_of(old), rec, tmp))
        v_new = cache.setdefault((sha_of(new), rec['original'], rec['mutant']), verdict(builder, sha_of(new), rec, tmp))
        res.update(old=old, new=new, verdict_old=v_old, verdict_new=v_new)
        if v_old != 'bad':
            res['note'] = 'not reproduced on %s (%s)' % (old, v_old)
        elif v_new == 'bad':
            res['note'] = 'still violated on %s: a live bug' % new
        elif v_new == 'good':
            commits = git(src, 'rev-list', '--first-parent', '--reverse', '%s..%s' % (old, new)).split()
            commits = [sha_of(old)] + commits
            idx, last, steps = first_change(builder, commits, rec, tmp, 'good', cache)
            res['fixed_by'] = describe(src, commits[idx])
            res['last_bad'] = commits[last]
            res['fix_exact'] = idx == last + 1
            res['fix_steps'] = steps
        if args.introduced and v_old == 'bad':
            older = [t for t in tags if tags.index(t) < tags.index(old)] if old in tags else []
            good_tag, bad_tag = None, old
            # go back with growing steps until a release where the pair is good
            k, step = len(older) - 1, 1
            while k >= 0:
                t = older[k]
                key = (sha_of(t), rec['original'], rec['mutant'])
                cache.setdefault(key, verdict(builder, sha_of(t), rec, tmp))
                if cache[key] == 'good':
                    good_tag = t
                    break
                if cache[key] == 'bad':
                    bad_tag = t
                k -= step
                step *= 2
            if good_tag is None:
                # the doubling steps may have jumped over releases: walk back one release
                # at a time from the oldest bad one, until a good one or 5 unjudgeable in a row
                k, unjudged = tags.index(bad_tag) - 1, 0
                while k >= 0 and unjudged < 5:
                    t = tags[k]
                    key = (sha_of(t), rec['original'], rec['mutant'])
                    cache.setdefault(key, verdict(builder, sha_of(t), rec, tmp))
                    if cache[key] == 'good':
                        good_tag = t
                        break
                    if cache[key] == 'bad':
                        bad_tag, unjudged = t, 0
                    else:
                        unjudged += 1
                    k -= 1
            res['oldest_bad_release'] = bad_tag
            if good_tag is None:
                res['introduced'] = 'before %s: bad on every older release that could be judged' % bad_tag
            else:
                # narrow to adjacent releases, then bisect the commits between them
                lo_i, hi_i = tags.index(good_tag), tags.index(bad_tag)
                while hi_i - lo_i > 1:
                    mid = (lo_i + hi_i) // 2
                    key = (sha_of(tags[mid]), rec['original'], rec['mutant'])
                    cache.setdefault(key, verdict(builder, sha_of(tags[mid]), rec, tmp))
                    if cache[key] == 'good':
                        lo_i = mid
                    elif cache[key] == 'bad':
                        hi_i = mid
                    else:
                        break
                commits = [sha_of(tags[lo_i])] + git(src, 'rev-list', '--first-parent', '--reverse',
                                                     '%s..%s' % (tags[lo_i], tags[hi_i])).split()
                idx, last, steps = first_change(builder, commits, rec, tmp, 'bad', cache)
                res['introduced_by'] = describe(src, commits[idx])
                res['last_good'] = commits[last]
                res['introduce_exact'] = idx == last + 1
                res['introduce_steps'] = steps
        print('  -> %s' % {k: (v['commit'][:12] if isinstance(v, dict) else v) for k, v in res.items()
                           if k in ('fixed_by', 'introduced_by', 'note', 'introduced')}, file=sys.stderr)
        results.append(res)
    if args.out:
        with open(args.out, 'w') as f:
            for r in results:
                f.write(json.dumps(r) + '\n')
    report(results)


def _oldest(rs):
    """For a bug whose introduction lies before every release that could be judged: the
    oldest release on which one of its pairs is bad."""
    tags = [r['oldest_bad_release'] for r in rs if r.get('oldest_bad_release')]
    if not tags:
        return rs[0].get('introduced') or '-'
    return 'before %s (bad on every older release that could be judged)' % version_tags_sorted(tags)[0]


def report(results):
    groups = collections.OrderedDict()
    for r in results:
        key = (r.get('introduced_by', {}).get('commit') if isinstance(r.get('introduced_by'), dict) else None,
               r.get('fixed_by', {}).get('commit') if isinstance(r.get('fixed_by'), dict) else None,
               r.get('note'))
        groups.setdefault(key, []).append(r)
    print('# SQLite violations grouped by commit\n')
    print('%d pairs, %d distinct bugs (pairs with the same introducing and fixing commits are one bug).\n'
          % (len(results), len(groups)))
    print('| Bug | Pairs | Introduced by | Fixed by | Fix first released in | Rules |')
    print('| --- | --- | --- | --- | --- | --- |')
    for n, ((intro, fix, note), rs) in enumerate(groups.items(), 1):
        f = rs[0].get('fixed_by') if fix else None
        i = rs[0].get('introduced_by') if intro else None
        print('| %d | %s | %s | %s | %s | %s |' % (
            n, ', '.join('#%d' % r['pair'] for r in rs),
            '`%s` %s %s' % (i['commit'][:12], i['date'], i['subject'][:60]) if i else _oldest(rs),
            ('`%s` %s %s%s' % (f['commit'][:12], f['date'], f['subject'][:60],
                               '' if rs[0].get('fix_exact') else ' (range: commits in between not judgeable)'))
            if f else (note or '-'),
            f['first_release'] if f else '-',
            ', '.join(sorted({r['rule'] for r in rs}))))
    print()


if __name__ == '__main__':
    main()
