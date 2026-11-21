"""Reduce a recorded SQLite violation to a small query that still shows it.

    python3 bridge/reduce_sqlite.py VIOLATIONS.jsonl --lib 3.26.0=libsqlite3-3260000.so [--lib ...] [--pair N] [--out reduced.jsonl]

A recorded violation (campaign_sqlite.py, set-semantic) is a pair: an original query and
the mutant that a rule produced from it, on a database built from a seed.  The reducer
simplifies the ORIGINAL query step by step (greedy, until no step applies):

  - a UNION / INTERSECT / EXCEPT is replaced by one of its arms;
  - an AND / OR by one of its operands, NOT p by p;
  - WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, DISTINCT or a join is removed;
  - one select item is removed (the select list keeps at least one item), or the same
    column from every arm of a compound query;
  - a comparison in WHERE / ON / HAVING is replaced by 1 or 0;
  - a subquery predicate (EXISTS, IN) is replaced by 1 (true) or 0 (false).

After each step the verified mutator is run again on the smaller query, and the step is
kept only if a mutant of the SAME rule and direction still violates the relation on the
given SQLite library (and, with --latest, still holds on the newest release: the reduced
pair then shows the same bug, fixed since, and not some other behaviour).  So every reduced pair is again a pair the verified engine produced:
the theorem for that rule still says the relation must hold.

The result is printed (original, mutant, rows of each) and, with --out, written as JSON
lines in the format of the input (with "reduced_from" holding the original pair).

With --sql DIR the database is reduced too (rows, indexes and ANALYZE removed while the
reduced pair stays violated), and DIR/pair-N.sql is a self-contained reproduction: the
statements of the database, then the two queries.
"""
import argparse
import json
import os
import sys
import tempfile

import sqlglot
from sqlglot import exp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checker import check_inclusion, check_value, sqlite_fold  # noqa: E402
from gen_sqlite_db import build as build_db  # noqa: E402
from run_on_db import sqlite_exact_columns, sqlite_schema  # noqa: E402
from sql_bridge import mutate_sql, mutate_value  # noqa: E402
from sqlite_exec import SQLiteLib  # noqa: E402

CLAUSES = ('where', 'group', 'having', 'order', 'limit', 'distinct')


def variants(sql, dialect='sqlite'):
    """Smaller queries, one simplification each."""
    try:
        tree = sqlglot.parse_one(sql, read=dialect)
    except Exception:
        return
    nodes = list(tree.walk())
    for i in range(len(nodes)):
        node = nodes[i]
        for replace in _steps(node):
            t = tree.copy()
            target = list(t.walk())[i]
            try:
                new = replace(target)
                if new is not None:
                    if target is t:
                        t = new
                    else:
                        target.replace(new)
                yield t.sql(dialect=dialect)
            except Exception:
                continue


def _steps(node):
    steps = []
    if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
        steps += [lambda n: n.left.copy(), lambda n: n.right.copy()]
    if isinstance(node, (exp.And, exp.Or)):
        steps += [lambda n: n.left.copy(), lambda n: n.right.copy()]
    if isinstance(node, exp.Not):
        steps.append(lambda n: n.this.copy())
    if isinstance(node, (exp.Exists, exp.In)) and (node.find(exp.Select) is not None):
        steps += [lambda n: exp.Literal.number(1), lambda n: exp.Literal.number(0)]
    if isinstance(node, (exp.EQ, exp.NEQ, exp.LT, exp.LTE, exp.GT, exp.GTE, exp.Like, exp.Is)) \
            and isinstance(node.parent, (exp.Where, exp.Join, exp.And, exp.Or, exp.Not, exp.Paren, exp.Having)):
        steps += [lambda n: exp.Literal.number(1), lambda n: exp.Literal.number(0)]
    if isinstance(node, (exp.Union, exp.Intersect, exp.Except)) and not isinstance(node.parent, (exp.Union, exp.Intersect, exp.Except)):
        arms = _arms(node)
        width = len(arms[0].expressions) if all(isinstance(a, exp.Select) for a in arms) else 0
        if width > 1 and all(len(a.expressions) == width for a in arms):
            for j in range(width):
                steps.append(lambda n, j=j: (_drop_column(n, j), None)[1])
    if isinstance(node, exp.Select):
        for clause in CLAUSES:
            if node.args.get(clause):
                steps.append(lambda n, c=clause: (n.set(c, None), None)[1])
        for j in range(len(node.args.get('joins') or [])):
            steps.append(lambda n, j=j: (n.args['joins'].pop(j), None)[1])
        if len(node.expressions) > 1:
            for j in range(len(node.expressions)):
                steps.append(lambda n, j=j: (n.set('expressions', n.expressions[:j] + n.expressions[j + 1:]), None)[1])
    return steps


def _arms(node):
    if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
        return _arms(node.left) + _arms(node.right)
    return [node]


def _drop_column(node, j):
    for a in _arms(node):
        a.set('expressions', a.expressions[:j] + a.expressions[j + 1:])


class Judge:
    """Checks a candidate pair on witnesses: (library, wanted verdict) where the verdict is
    'bad' (the relation of the rule is violated) or 'good' (it holds).  The reporting
    release must stay 'bad'; --latest adds the newest release as 'good'; --boundaries adds
    the commits around the fix and the introduction of the original pair (bisect_sqlite.py),
    so the reduced pair is fixed and introduced by the same commits: the same bug."""

    def __init__(self, rec, witnesses, tmp):
        self.rec, self.tmp, self.witnesses = rec, tmp, witnesses
        self.kind, self.rule, self.expect = rec.get('kind', 'set'), rec['rule'], rec['expect']
        self.cover = bool(rec.get('distinct'))
        self.dbs = []
        for i, (lib, want) in enumerate(witnesses):
            db = SQLiteLib(lib, os.path.join(tmp, 'w%d.db' % i))
            stmts = build_db(db, rec['seed'], rec.get('focus') in (True, 'True'))
            if i == 0:
                self.statements, self.db = stmts, db
            # a witness that cannot run every statement of the database would judge another one
            self.dbs.append((db if stmts == self.statements else None, want, sqlite_fold(stmts)))
        self.lib = witnesses[0][0]
        self.schema = sqlite_schema(self.db)
        self.exact = sqlite_exact_columns(self.db, self.schema)

    def verdict(self, db, fallback, original, mutant, relation=None):
        try:
            base = db.query(original)
            coll = db.last_collations
            res = db.query(mutant)
        except Exception:
            return None, None
        fold = db.folds(coll, db.last_collations, fallback)
        if self.kind == 'value':
            relation, column = relation
            v = check_value(relation, column, base, res, fold=fold, cover=self.cover)
        else:
            v = check_inclusion(self.expect if self.kind == 'set' else self.expect, base, res, fold)
        if v == 'incomparable':
            return None, None
        return ('good' if v in ('ok', 'collation') else 'bad'), (base, res)

    def holds(self, original, mutant, relation=None):
        """Rows on the reporting release when every witness gives its wanted verdict."""
        rows = None
        for i, (db, want, fallback) in enumerate(self.dbs):
            if db is None:
                return None
            v, r = self.verdict(db, fallback, original, mutant, relation)
            if v != want:
                return None
            if i == 0:
                rows = r
        return rows

    def violates(self, original, mutant):
        return self.holds(original, mutant, self._relation(self.expect))

    def _relation(self, expect):
        if self.kind != 'value':
            return None
        relation, _, column = expect.split()
        return relation, int(column)

    def pair(self, sql):
        """(printed original, mutant, rows) of the first mutant of the rule that gives every
        witness its verdict, or None."""
        try:
            if self.kind == 'set':
                original, mutants, _ = mutate_sql(sql, dialect='sqlite', schema=self.schema, exact_columns=self.exact)
                cands = [(m, None) for d, r, m in mutants if r == self.rule and d == self.expect]
            else:
                trs = []
                original, vm, _, _, hm = mutate_value(sql, dialect='sqlite', translation=trs, schema=self.schema,
                                                      exact_columns=self.exact)
                if self.kind == 'value':
                    rel = self._relation(self.expect)
                    cands = [(m, (r0, c)) for r0, r, c, m in vm if r == self.rule and (r0, c) == rel
                             and bool(trs[0].cover_for(m)) == self.cover]
                else:
                    cands = [(m, None) for d, r, m in hm if 'HAVING ' + r == self.rule and d == self.expect]
        except Exception:
            return None
        for mutant, rel in cands:
            rows = self.holds(original, mutant, rel)
            if rows is not None:
                return original, mutant, rows
        return None

    def holds_on_statements(self, statements, original, mutant):
        """The same, on databases made of these statements (database reduction)."""
        rel = self._relation(self.expect)
        for i, (lib, want) in enumerate(self.witnesses):
            path = os.path.join(self.tmp, 'd%d.db' % i)
            if os.path.exists(path):
                os.remove(path)
            db = SQLiteLib(lib, path)
            for st in statements:
                try:
                    db.executescript(st)
                except Exception:
                    return False
            v, _ = self.verdict(db, sqlite_fold(statements), original, mutant, rel)
            if v != want:
                return False
        return True


REMOVABLE = ('INSERT', 'CREATE INDEX', 'CREATE UNIQUE INDEX', 'ANALYZE')


def reduce_database(judge, original, mutant, log=sys.stderr):
    """Remove rows (INSERT statements), indexes and ANALYZE, and drop WITHOUT ROWID, while
    every witness keeps its verdict: first in chunks, then one at a time.  The pair is fixed
    here, and its theorem holds on every database, so any database on which it is violated
    is a counterexample."""
    stmts = list(judge.statements)
    chunk = max(1, len(stmts) // 2)
    while True:
        i = 0
        while i < len(stmts):
            cut = [j for j in range(i, min(i + chunk, len(stmts))) if stmts[j].upper().startswith(REMOVABLE)]
            if cut:
                trial = [st for j, st in enumerate(stmts) if j not in cut]
                if judge.holds_on_statements(trial, original, mutant):
                    stmts = trial
                    continue
            i += chunk
        if chunk == 1:
            break
        chunk = max(1, chunk // 2)
    # tables without WITHOUT ROWID: older releases (before 3.8.2) can run the database
    for j, st in enumerate(stmts):
        if st.endswith(') WITHOUT ROWID;'):
            trial = stmts[:j] + [st[:-len(' WITHOUT ROWID;')] + ';'] + stmts[j + 1:]
            if judge.holds_on_statements(trial, original, mutant):
                stmts = trial
    print('  database: %d -> %d statements' % (len(judge.statements), len(stmts)), file=log)
    return stmts


def reduce(judge, sql, log=sys.stderr):
    best = judge.pair(sql)
    if best is None:
        return None
    current, steps = best[0], 0
    progress = True
    while progress:
        progress = False
        for cand in sorted(set(variants(current)), key=lambda c: (len(c), c)):
            if len(cand) >= len(current):
                continue
            got = judge.pair(cand)
            if got is not None and len(got[0]) < len(current):
                current, best, progress = got[0], got, True
                steps += 1
                print('  step %d: %d characters' % (steps, len(current)), file=log)
                break
    return best


def boundary_witnesses(entry, builder):
    """Witnesses from the bisection of the original pair: bad on the last bad commit and on
    the introducing commit, good on the fixing commit and on the last good commit."""
    out = []
    for key, want in (('last_bad', 'bad'), ('fixed_by', 'good'), ('introduced_by', 'bad'), ('last_good', 'good')):
        v = entry.get(key)
        sha = v.get('commit') if isinstance(v, dict) else v
        if sha:
            lib = builder.lib(sha)
            if lib is None:
                return None
            out.append((lib, want))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file', help='JSON lines of recorded violations (campaign_sqlite.py --out)')
    ap.add_argument('--lib', required=True, action='append',
                    help='libsqlite3 on which the pairs are violated; VERSION=PATH (repeatable) picks the '
                         'library by the version a pair was reported on')
    ap.add_argument('--pair', type=int, action='append', help='1-based pair number(s); default: all pairs')
    ap.add_argument('--latest', default=None, metavar='LIB',
                    help='a library of the newest release: a step is kept only if the relation holds '
                         'there, so that the reduced pair keeps showing a bug fixed since')
    ap.add_argument('--boundaries', default=None, metavar='BISECT.jsonl',
                    help='bisection of the original pairs (bisect_sqlite.py --out): a step is kept only if '
                         'the pair keeps its verdicts on the commits around the fix and the introduction, '
                         'so the reduced pair shows the same bug (needs --src)')
    ap.add_argument('--src', default=None, help='SQLite git clone, for --boundaries (as bisect_sqlite.py)')
    ap.add_argument('--cache', default=None, help='build cache, for --boundaries (as bisect_sqlite.py)')
    ap.add_argument('--out', default=None)
    ap.add_argument('--sql', default=None, metavar='DIR',
                    help='also reduce the database, and write DIR/pair-N.sql: the statements of the '
                         'reduced database, then the original and the mutant')
    args = ap.parse_args()
    recs = [json.loads(line) for line in open(args.file) if line.strip()]
    libs = dict(x.split('=', 1) if '=' in x else (None, x) for x in args.lib)
    bounds, builder = {}, None
    if args.boundaries:
        from bisect_sqlite import Builder
        src = os.path.abspath(args.src)
        builder = Builder(src, args.cache or os.path.join(os.path.dirname(src), 'bisect-cache'))
        for line in open(args.boundaries):
            e = json.loads(line)
            bounds[(e['original'], e['mutant'])] = e
    out = open(args.out, 'w') if args.out else None
    for k, rec in enumerate(recs, 1):
        if args.pair and k not in args.pair:
            continue
        print('pair %d: seed %s, %s' % (k, rec['seed'], rec['rule']), file=sys.stderr)
        lib = libs.get(rec.get('version'), libs.get(None))
        if lib is None:
            print('  no library for SQLite %s' % rec.get('version'), file=sys.stderr)
            continue
        witnesses = [(lib, 'bad')] + ([(args.latest, 'good')] if args.latest else [])
        if args.boundaries:
            entry = bounds.get((rec['original'], rec['mutant']))
            extra = boundary_witnesses(entry, builder) if entry else None
            if extra is None:
                print('  no bisection boundaries for this pair', file=sys.stderr)
                continue
            witnesses += extra
        with tempfile.TemporaryDirectory() as tmp:
            judge = Judge(rec, witnesses, tmp)
            if judge.violates(rec['original'], rec['mutant']) is None:
                print('  the pair does not give every witness its verdict', file=sys.stderr)
                continue
            got = reduce(judge, rec['original'])
            if got is None:
                print('  the mutator does not produce a violating mutant of this rule again', file=sys.stderr)
                continue
            original, mutant, (base, res) = got
            database = reduce_database(judge, original, mutant) if args.sql else None
        print('-- pair %d (%s, expected %s): %d -> %d characters' % (
            k, rec['rule'], rec['expect'], len(rec['original']), len(original)))
        print('original: %s\nmutant  : %s\nrows    : %d / %d\n' % (original, mutant, len(base), len(res)))
        if database is not None:
            os.makedirs(args.sql, exist_ok=True)
            with open(os.path.join(args.sql, 'pair-%d.sql' % k), 'w') as f:
                what = {'Up': 'a super-bag', 'Down': 'a sub-bag'}.get(rec['expect'], rec['expect'])
                f.write('-- pair %d, seed %s, rule %s: the mutant must return %s of the rows of the original\n'
                        '-- (SQLite %s; checked modulo the collations of the columns)\n'
                        % (k, rec['seed'], rec['rule'], what, rec.get('version')))
                f.write('\n'.join(database) + '\n')
                f.write('-- original\n%s;\n-- mutant\n%s;\n' % (original, mutant))
        if out:
            r = dict(rec, original=original, mutant=mutant, original_rows=len(base), mutant_rows=len(res),
                     reduced_from={'original': rec['original'], 'mutant': rec['mutant']})
            if database is not None:
                r['database'] = database
            out.write(json.dumps(r) + '\n')
    if out:
        out.close()


if __name__ == '__main__':
    main()
