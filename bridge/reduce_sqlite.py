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
from checker import check_inclusion, sqlite_fold  # noqa: E402
from gen_sqlite_db import build as build_db  # noqa: E402
from run_on_db import sqlite_exact_columns, sqlite_schema  # noqa: E402
from sql_bridge import mutate_sql, Unsupported  # noqa: E402
from sqlite_exec import SQLiteLib  # noqa: E402

CLAUSES = ('where', 'group', 'having', 'order', 'limit', 'distinct')


def variants(sql):
    """Smaller queries, one simplification each."""
    try:
        tree = sqlglot.parse_one(sql, read='sqlite')
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
                yield t.sql(dialect='sqlite')
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
    def __init__(self, lib, rec, tmp, latest=None):
        self.lib, self.tmp, self.latest = lib, tmp, latest
        if latest is not None:
            self.ldb = SQLiteLib(latest, os.path.join(tmp, 'l.db'))
            build_db(self.ldb, rec['seed'], rec.get('focus') in (True, 'True'))
        self.db = SQLiteLib(lib, os.path.join(tmp, 'r.db'))
        self.statements = build_db(self.db, rec['seed'], rec.get('focus') in (True, 'True'))
        self.fallback = sqlite_fold(self.statements)
        self.schema = sqlite_schema(self.db)
        self.exact = sqlite_exact_columns(self.db, self.schema)
        self.rule, self.expect = rec['rule'], rec['expect']

    def violates(self, original, mutant):
        try:
            base = self.db.query(original)
            coll = self.db.last_collations
            res = self.db.query(mutant)
        except Exception:
            return None
        fold = self.db.folds(coll, self.db.last_collations, self.fallback)
        v = check_inclusion(self.expect, base, res, fold)
        if v in ('ok', 'collation', 'incomparable'):
            return None
        if self.latest is not None and not holds_on(self.ldb, original, mutant, self.expect, self.fallback):
            return None     # violated on the latest release too: another phenomenon than the pair's
        return base, res

    def pair(self, sql):
        """(printed original, mutant, rows) of the first violating mutant of the rule, or None."""
        try:
            original, mutants, _ = mutate_sql(sql, dialect='sqlite', schema=self.schema, exact_columns=self.exact)
        except (Unsupported, Exception):
            return None
        for direction, rule, mutant in mutants:
            if rule == self.rule and direction == self.expect:
                rows = self.violates(original, mutant)
                if rows is not None:
                    return original, mutant, rows
        return None


def holds_on(db, original, mutant, expect, fallback):
    """Does the relation hold on this database (of the latest release)?"""
    try:
        base = db.query(original)
        coll = db.last_collations
        res = db.query(mutant)
    except Exception:
        return False
    return check_inclusion(expect, base, res, db.folds(coll, db.last_collations, fallback)) in ('ok', 'collation')


def violates_on(lib, statements, original, mutant, expect, path, latest=None):
    """Is the pair violated on the database made of these statements?"""
    if os.path.exists(path):
        os.remove(path)
    db = SQLiteLib(lib, path)
    for st in statements:
        try:
            db.executescript(st)
        except Exception:
            return False
    try:
        base = db.query(original)
        coll = db.last_collations
        res = db.query(mutant)
    except Exception:
        return False
    fold = db.folds(coll, db.last_collations, sqlite_fold(statements))
    if check_inclusion(expect, base, res, fold) in ('ok', 'collation', 'incomparable'):
        return False
    if latest is None:
        return True
    ldb_path = path + '.latest'
    if os.path.exists(ldb_path):
        os.remove(ldb_path)
    ldb = SQLiteLib(latest, ldb_path)
    for st in statements:
        try:
            ldb.executescript(st)
        except Exception:
            return False
    return holds_on(ldb, original, mutant, expect, sqlite_fold(statements))


REMOVABLE = ('INSERT', 'CREATE INDEX', 'CREATE UNIQUE INDEX', 'ANALYZE')


def reduce_database(judge, original, mutant, expect, log=sys.stderr):
    """Remove rows (INSERT statements), indexes and ANALYZE while the pair stays violated:
    first in chunks, then one at a time.  The pair is fixed here, and its theorem holds on
    every database, so any database on which it is violated is a counterexample."""
    stmts = list(judge.statements)
    path = os.path.join(judge.tmp, 'd.db')
    chunk = max(1, len(stmts) // 2)
    while True:
        i = 0
        while i < len(stmts):
            cut = [j for j in range(i, min(i + chunk, len(stmts))) if stmts[j].upper().startswith(REMOVABLE)]
            if cut:
                trial = [st for j, st in enumerate(stmts) if j not in cut]
                if violates_on(judge.lib, trial, original, mutant, expect, path, judge.latest):
                    stmts = trial
                    continue
            i += chunk
        if chunk == 1:
            break
        chunk = max(1, chunk // 2)
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


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file', help='JSON lines of recorded violations (campaign_sqlite.py --out)')
    ap.add_argument('--lib', required=True, action='append',
                    help='libsqlite3 on which the pairs are violated; VERSION=PATH (repeatable) picks the '
                         'library by the version a pair was reported on')
    ap.add_argument('--pair', type=int, action='append', help='1-based pair number(s); default: all set pairs')
    ap.add_argument('--latest', default=None, metavar='LIB',
                    help='a library of the newest release: a step is kept only if the relation holds '
                         'there, so that the reduced pair keeps showing the bug of the pair (a bug '
                         'fixed since) and does not drift to another behaviour')
    ap.add_argument('--out', default=None)
    ap.add_argument('--sql', default=None, metavar='DIR',
                    help='also reduce the database, and write DIR/pair-N.sql: the statements of the '
                         'reduced database, then the original and the mutant')
    args = ap.parse_args()
    recs = [json.loads(line) for line in open(args.file) if line.strip()]
    libs = dict(x.split('=', 1) if '=' in x else (None, x) for x in args.lib)
    out = open(args.out, 'w') if args.out else None
    for k, rec in enumerate(recs, 1):
        if (args.pair and k not in args.pair) or rec.get('kind') != 'set':
            continue
        print('pair %d: seed %s, %s' % (k, rec['seed'], rec['rule']), file=sys.stderr)
        lib = libs.get(rec.get('version'), libs.get(None))
        if lib is None:
            print('  no library for SQLite %s' % rec.get('version'), file=sys.stderr)
            continue
        with tempfile.TemporaryDirectory() as tmp:
            judge = Judge(lib, rec, tmp, args.latest)
            if judge.violates(rec['original'], rec['mutant']) is None:
                print('  not violated on this library', file=sys.stderr)
                continue
            got = reduce(judge, rec['original'])
            if got is None:
                print('  the mutator does not produce a violating mutant of this rule again', file=sys.stderr)
                continue
            original, mutant, (base, res) = got
            database = reduce_database(judge, original, mutant, rec['expect']) if args.sql else None
        print('-- pair %d (%s, expected %s): %d -> %d characters' % (
            k, rec['rule'], rec['expect'], len(rec['original']), len(original)))
        print('original: %s\nmutant  : %s\nrows    : %d / %d\n' % (original, mutant, len(base), len(res)))
        if database is not None:
            os.makedirs(args.sql, exist_ok=True)
            with open(os.path.join(args.sql, 'pair-%d.sql' % k), 'w') as f:
                f.write('-- pair %d, seed %s, rule %s: the mutant must return %s of the rows of the original\n'
                        '-- (SQLite %s; checked modulo the collations of the columns)\n'
                        % (k, rec['seed'], rec['rule'], 'a super-bag' if rec['expect'] == 'Up' else 'a sub-bag',
                           rec.get('version')))
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
