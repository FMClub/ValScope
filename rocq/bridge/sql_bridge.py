"""Bridge between SQL text and the verified mutator (cli/valscope_mutate).

    SQL text --sqlglot--> algebra term --valscope_mutate--> mutant terms --> SQL text

The mutator never looks inside scalar expressions, table references or predicates
it does not analyse; it only copies them.  The bridge therefore replaces each of
them by a numbered atom and puts the original SQL text back when printing.

This file is NOT verified.  It is part of the trusted base together with sqlglot:
the theorems are about the algebra term, and the bridge is responsible for the
term meaning the same as the SQL text.  It raises Unsupported for anything outside
the modelled fragment instead of approximating it.
"""
import os
import subprocess

import sqlglot
from sqlglot import exp

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CLI = os.path.join(HERE, '..', 'cli', 'valscope_mutate')


class Unsupported(Exception):
    """The query (or a mutant) is outside the fragment the bridge can translate."""


CMP = {exp.EQ: 'eq', exp.NEQ: 'ne', exp.LT: 'lt', exp.LTE: 'le', exp.GT: 'gt', exp.GTE: 'ge'}
CMP_SQL = {'eq': '=', 'ne': '<>', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}


def _tokens(text):
    return text.replace('(', ' ( ').replace(')', ' ) ').split()


def parse_sexp(text):
    tokens = _tokens(text)
    pos = 0

    def one():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok != '(':
            return tok
        items = []
        while tokens[pos] != ')':
            items.append(one())
        pos += 1
        return items

    return one()


class Translation:
    """One SQL query translated to an algebra term, with its atom tables."""

    def __init__(self, sql, dialect='mysql'):
        self.dialect = dialect
        self.tables, self.exprs, self.preds = [], [], []
        tree = sqlglot.parse_one(sql, read=dialect)
        self.term = self._query(tree)

    # ---------------- SQL -> term ----------------
    def _text(self, node):
        return node.sql(dialect=self.dialect)

    def _atom(self, table, text):
        if text not in table:
            table.append(text)
        return table.index(text)

    def _expr(self, node):
        return '(Col %d)' % self._atom(self.exprs, self._text(node))

    def _query(self, node):
        while isinstance(node, (exp.Subquery, exp.Paren)):
            if isinstance(node, exp.Subquery) and node.alias:
                raise Unsupported('aliased subquery as a query')
            node = node.this
        if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            for key in ('limit', 'offset', 'with_', 'with'):
                if node.args.get(key):
                    raise Unsupported('%s on a set operation' % key)
            distinct = node.args.get('distinct')
            if isinstance(node, exp.Union):
                tag = 'Union' if distinct else 'UnionAll'
            elif not distinct:
                raise Unsupported('INTERSECT ALL / EXCEPT ALL')
            else:
                tag = 'Intersect' if isinstance(node, exp.Intersect) else 'Except'
            return '(%s %s %s)' % (tag, self._query(node.this), self._query(node.expression))
        if isinstance(node, exp.Select):
            return self._select(node)
        raise Unsupported(type(node).__name__)

    def _select(self, node):
        for key in ('group', 'having', 'limit', 'offset', 'qualify', 'windows', 'with_', 'with',
                    'locks', 'sample', 'pivots', 'laterals'):
            if node.args.get(key):
                raise Unsupported(key)
        for item in node.expressions:
            for inner in item.walk():
                if isinstance(inner, (exp.AggFunc, exp.Window, exp.Select)):
                    raise Unsupported('aggregate, window or subquery in the select list')
                if isinstance(inner, exp.Anonymous):
                    raise Unsupported('unknown function in the select list')
        source = node.args.get('from_') or node.args.get('from')
        if source is None:
            raise Unsupported('SELECT without FROM')
        term = self._table(source.this)
        for join in node.args.get('joins') or []:
            if join.args.get('using') or join.args.get('method'):
                raise Unsupported('USING / NATURAL join')
            side = str(join.args.get('side') or '').upper()
            kind = str(join.args.get('kind') or '').upper()
            right = self._table(join.this)
            on = self._pred(join.args['on']) if join.args.get('on') is not None else 'True'
            if side == 'LEFT':
                term = '(Left 0 %s %s %s)' % (on, term, right)
            elif side == '' and kind in ('', 'INNER', 'CROSS'):
                term = '(Inner %s %s %s)' % (on, term, right)
            else:
                raise Unsupported('%s %s join' % (side, kind))
        if node.args.get('where') is not None:
            term = '(Where %s %s)' % (self._pred(node.args['where'].this), term)
        # ORDER BY does not change the bag of rows and is dropped
        items = ' '.join(self._expr(item) for item in node.expressions)
        term = '(Proj (%s) %s)' % (items, term)
        if node.args.get('distinct'):
            term = '(Distinct %s)' % term
        return term

    def _table(self, node):
        if isinstance(node, exp.Table) or (isinstance(node, exp.Subquery) and node.alias):
            # a derived table is kept as an opaque table: it is not mutated
            return '(T %d 0)' % self._atom(self.tables, self._text(node))
        raise Unsupported('FROM item %s' % type(node).__name__)

    def _pred(self, node):
        if isinstance(node, exp.Paren):
            return self._pred(node.this)
        if isinstance(node, exp.And):
            return '(And %s %s)' % (self._pred(node.this), self._pred(node.expression))
        if isinstance(node, exp.Or):
            return '(Or %s %s)' % (self._pred(node.this), self._pred(node.expression))
        if isinstance(node, exp.Not):
            return '(Not %s)' % self._pred(node.this)
        if isinstance(node, exp.Boolean):
            return 'True' if node.this else 'False'
        if type(node) in CMP and node.this.find(exp.Select) is None \
                and node.expression.find(exp.Select) is None:
            return '(Cmp %s %s %s)' % (CMP[type(node)], self._expr(node.this), self._expr(node.expression))
        if isinstance(node, exp.Is) and isinstance(node.expression, exp.Null) \
                and node.this.find(exp.Select) is None:
            return '(IsNull %s)' % self._expr(node.this)
        if isinstance(node, exp.Exists) and isinstance(node.this, exp.Select):
            try:
                return '(Exists %s)' % self._query(node.this)
            except Unsupported:
                pass
        # anything else is an opaque predicate: it can only be replaced as a whole
        return '(Atom %d)' % self._atom(self.preds, self._text(node))

    # ---------------- term -> SQL ----------------
    def to_sql(self, term):
        return self._q_sql(parse_sexp(term) if isinstance(term, str) else term)

    def _e_sql(self, e):
        if e[0] == 'Col':
            return self.exprs[int(e[1])]
        raise Unsupported('expression %s' % e[0])

    def _p_sql(self, p):
        if p == 'True':
            return '1 = 1'
        if p == 'False':
            return '1 = 0'
        tag = p[0]
        if tag == 'Cmp':
            return '%s %s %s' % (self._e_sql(p[2]), CMP_SQL[p[1]], self._e_sql(p[3]))
        if tag == 'IsNull':
            return '%s IS NULL' % self._e_sql(p[1])
        if tag == 'Not':
            return 'NOT (%s)' % self._p_sql(p[1])
        if tag in ('And', 'Or'):
            return '(%s) %s (%s)' % (self._p_sql(p[1]), tag.upper(), self._p_sql(p[2]))
        if tag == 'Exists':
            return 'EXISTS (%s)' % self._q_sql(p[1])
        if tag == 'Atom':
            return '(%s)' % self.preds[int(p[1])]
        raise Unsupported('predicate %s' % tag)

    def _from_sql(self, f, nested=False):
        tag = f[0]
        if tag == 'T':
            return self.tables[int(f[1])]
        if tag in ('Inner', 'Left'):
            on, left, right = (f[1], f[2], f[3]) if tag == 'Inner' else (f[2], f[3], f[4])
            text = '%s %s JOIN %s ON %s' % (self._from_sql(left), 'INNER' if tag == 'Inner' else 'LEFT',
                                           self._from_sql(right, nested=True), self._p_sql(on))
            return '(%s)' % text if nested else text
        raise Unsupported('%s in FROM position' % tag)

    def _q_sql(self, q):
        tag = q[0]
        names = {'UnionAll': 'UNION ALL', 'Union': 'UNION', 'Intersect': 'INTERSECT', 'Except': 'EXCEPT'}
        if tag in names:
            return '(%s) %s (%s)' % (self._q_sql(q[1]), names[tag], self._q_sql(q[2]))
        distinct, items, where = False, '*', None
        if q[0] == 'Distinct':
            distinct, q = True, q[1]
        if q[0] == 'Proj':
            items, q = ', '.join(self._e_sql(e) for e in q[1]), q[2]
        if q[0] == 'Where':
            where, q = self._p_sql(q[1]), q[2]
        sql = 'SELECT %s%s FROM %s' % ('DISTINCT ' if distinct else '', items, self._from_sql(q))
        return sql + (' WHERE ' + where if where else '')


def mutate_sql(sql, cli=DEFAULT_CLI, dialect='mysql'):
    """Return (original_sql, [(direction, rule_name, mutant_sql), ...], skipped).

    original_sql is the input re-printed from its algebra term; it is the query the
    mutants must be compared with.  `skipped` counts mutants the bridge cannot print
    as SQL (for example DISTINCT added around a FROM item)."""
    tr = Translation(sql, dialect)
    out = subprocess.run([cli], input=tr.term + '\n', capture_output=True, text=True, check=True).stdout
    mutants, skipped = [], 0
    for line in out.splitlines():
        if line == 'END':
            break
        if line.startswith('ERROR'):
            raise Unsupported(line)
        direction, rule, term = line.split('\t')
        try:
            mutants.append((direction, rule, tr.to_sql(term)))
        except Unsupported:
            skipped += 1
    return tr.to_sql(tr.term), mutants, skipped


if __name__ == '__main__':
    import sys
    original, mutants, skipped = mutate_sql(sys.argv[1])
    print('original:', original)
    for direction, rule, text in mutants:
        print('%-4s %-20s %s' % (direction, rule, text))
    print('(%d mutants not printable as SQL)' % skipped)
