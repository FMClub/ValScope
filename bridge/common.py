"""Shared by the bridge modules: the exception for queries outside the fragment, the
S-expression reader of the mutator protocol, and small helpers on syntax trees."""
from sqlglot import exp


class Unsupported(Exception):
    """The query (or a mutant) is outside the fragment the bridge can translate."""


def parse_sexp(text):
    tokens = text.replace('(', ' ( ').replace(')', ' ) ').split()
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


def _strip_parens(node):
    """A copy of the expression without parentheses (they do not change its meaning
    in a syntax tree)."""
    def bare(n):
        while isinstance(n, exp.Paren):       # ((x)): every level
            n = n.this
        return n
    return bare(node.copy()).transform(bare)


CMP_SQL = {'eq': '=', 'ne': '<>', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}
SET_SQL = {'UnionAll': 'UNION ALL', 'Union': 'UNION', 'Intersect': 'INTERSECT', 'Except': 'EXCEPT',
           'IntersectAll': 'INTERSECT ALL', 'ExceptAll': 'EXCEPT ALL'}


def _quote(text):
    return "'%s'" % text.replace("'", "''")
