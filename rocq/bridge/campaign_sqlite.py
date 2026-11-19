"""Testing campaign on SQLite with the verified mutators.

    python3 bridge/campaign_sqlite.py --libs LIB.so [LIB.so ...] --seeds 1-50 --queries 100 --out violations.jsonl

For every database seed, a random database is built (gen_sqlite_db.py) by each SQLite
library under test, random queries are generated (gen_fragment.py, SQLite profile),
and every query is

1. translated to an algebra term and back (translation validation: the query as
   written and the re-printed query must return the same rows on that library);
2. mutated by the verified mutators (set-semantic, value-semantic and HAVING);
3. checked: the relation stated by the rule's theorem must hold between the
   original and the mutant on that library.

A violation is re-checked on the SQLite that Python ships (`latest`).  If the
relation holds there, the old library computed a wrong result that a later release
corrected.  If it is violated there as well, the cause is either a live bug or a gap
between the model and SQLite, and needs a closer look.
"""
import argparse
import collections
import json
import os
import random
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_fragment  # noqa: E402
from gen_sqlite_db import build  # noqa: E402
from sqlite_exec import SQLiteLib  # noqa: E402
from sql_bridge import mutate_sql, mutate_value, Unsupported  # noqa: E402
from checker import bag, check_inclusion, check_value  # noqa: E402


def run(db, sql):
    try:
        return db.query(sql)
    except Exception:
        return None


def verdict_for(kind, mutant, base, res):
    """Check one mutant. kind is 'set', 'value' or 'having'."""
    if kind == 'value':
        relation, rule, column, _ = mutant
        return check_value(relation, column, base, res), '%s col %d' % (relation, column)
    direction = mutant[0]
    return check_inclusion(direction, base, res), direction


def parse_range(text):
    a, _, b = text.partition('-')
    return range(int(a), int(b or a) + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--libs', nargs='+', required=True, help='shared libraries; "python" = the SQLite Python ships')
    ap.add_argument('--seeds', default='1-10')
    ap.add_argument('--queries', type=int, default=100, help='queries of each kind per seed')
    ap.add_argument('--out', default=None, help='JSON lines file for the violations')
    ap.add_argument('--flip', action='store_true', help='negative control: expect the opposite relation')
    ap.add_argument('--rich', action='store_true', help='opaque predicates and derived tables')
    args = ap.parse_args()
    gen_fragment.use_sqlite()
    gen_fragment.RICH = args.rich
    libs = [None if lib == 'python' else lib for lib in args.libs]
    tmp = tempfile.mkdtemp(prefix='vs_sqlite_')
    st = collections.Counter()
    by_rule = collections.Counter()
    out = open(args.out, 'a') if args.out else None
    for seed in parse_range(args.seeds):
        dbs = []
        for lib in libs + [None]:          # the last one is the reference (latest)
            path = os.path.join(tmp, '%s_%d.db' % (os.path.basename(lib or 'python'), seed))
            if os.path.exists(path):
                os.remove(path)
            db = SQLiteLib(lib, path)
            build(db, seed)
            dbs.append(db)
        latest = dbs.pop()
        rng = random.Random(seed)
        queries = [('set', gen_fragment.query(rng)) for _ in range(args.queries)]
        queries += [('value', gen_fragment.value_query(rng)) for _ in range(args.queries)]
        for kind, sql in queries:
            st['queries'] += 1
            numeric_probe = None
            try:
                if kind == 'set':
                    original, mutants, skipped = mutate_sql(sql, dialect='sqlite')
                    work = [('set', m) for m in mutants]
                else:
                    trs = []
                    original, mutants, skipped, _, having = mutate_value(sql, dialect='sqlite', translation=trs)
                    work = [('value', m) for m in mutants] + [('having', m) for m in having]
                    numeric_probe = trs[0].numeric_probe()
            except Unsupported:
                st['unsupported'] += 1
                continue
            except Exception:
                st['parse_error'] += 1
                continue
            st['mutants_not_printable'] += skipped
            for db in dbs:
                if kind == 'value' and numeric_probe is not None:
                    # outside the model when an aggregated expression is text somewhere
                    count = run(db, numeric_probe)
                    if count is None or count[0][0] != 0:
                        st['non_numeric_input'] += 1
                        continue
                written, base = run(db, sql), run(db, original)
                if written is None or base is None:
                    st['original_failed'] += 1
                    continue
                if bag(written) != bag(base):
                    st['TRANSLATION_MISMATCH'] += 1
                    print('TRANSLATION MISMATCH [%s seed %d]\n  written  : %s\n  reprinted: %s'
                          % (db.version, seed, sql, original))
                    continue
                st['supported'] += 1
                for mk, mutant in work:
                    res = run(db, mutant[-1])
                    if res is None:
                        st['mutant_failed'] += 1
                        continue
                    m = mutant
                    if args.flip:
                        if mk == 'value':
                            flipped = {'Le': 'Ge', 'Ge': 'Le', 'TowardOne': 'AwayOne', 'AwayOne': 'TowardOne'}
                            if m[0] not in flipped:
                                continue
                            m = (flipped[m[0]],) + tuple(m[1:])
                        else:
                            m = ('Down' if m[0] == 'Up' else 'Up',) + tuple(m[1:])
                    verdict, label = verdict_for(mk, m, base, res)
                    rule = ('HAVING ' if mk == 'having' else '') + m[1]
                    if verdict == 'ok':
                        st['checked_ok'] += 1
                        by_rule[rule] += 1
                        continue
                    if verdict in ('incomparable', 'collation'):
                        st[verdict] += 1
                        continue
                    st['VIOLATIONS'] += 1
                    if args.flip:
                        continue
                    # re-check on the latest SQLite
                    lb, lr = run(latest, original), run(latest, mutant[-1])
                    on_latest = None if lb is None or lr is None else verdict_for(mk, m, lb, lr)[0]
                    fixed = on_latest == 'ok'
                    st['violations_fixed_in_latest' if fixed else 'violations_also_in_latest'] += 1
                    rec = {'version': db.version, 'seed': seed, 'kind': mk, 'rule': rule, 'expect': label,
                           'verdict': verdict, 'latest_verdict': on_latest, 'original': original,
                           'mutant': mutant[-1], 'original_rows': len(base), 'mutant_rows': len(res)}
                    print('VIOLATION [%s seed %d] %s %s (%s) latest: %s\n  original: %s\n  mutant  : %s'
                          % (db.version, seed, label, rule, verdict, on_latest, original, mutant[-1]))
                    if out:
                        out.write(json.dumps(rec) + '\n')
                        out.flush()
        print('-- seed %d done: %s' % (seed, dict(st)), file=sys.stderr)
    print(dict(st))
    print('ok checks per rule:', dict(by_rule))


if __name__ == '__main__':
    main()
