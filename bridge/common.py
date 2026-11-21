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
    return node.copy().transform(lambda n: n.this if isinstance(n, exp.Paren) else n)
