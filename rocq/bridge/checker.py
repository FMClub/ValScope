"""Result checkers for the two kinds of mutation.

These functions are NOT verified.  They decide whether two query results stand in
the relation that the Rocq theorems promise:

- set-semantic  : bag inclusion between the original and the mutant;
- value-semantic: the rows correspond one to one, agree outside the mutated
  column, and satisfy the rule's value relation inside it.
"""
import collections
import datetime
from decimal import Decimal

NUMERIC = (int, float, Decimal)


def bag(rows):
    return collections.Counter(rows)


def included(small, large):
    return all(large[row] >= n for row, n in small.items())


def _fold(value):
    """Approximation of collation equality: case-insensitive, trailing spaces ignored."""
    if isinstance(value, str):
        return value.casefold().rstrip(' ')
    return value


def included_modulo_collation(small_rows, large_rows):
    fold = lambda rows: collections.Counter(tuple(_fold(v) for v in row) for row in rows)
    return included(fold(small_rows), fold(large_rows))


def check_inclusion(direction, original_rows, mutant_rows):
    """Return 'ok', 'collation' (holds only up to case / trailing spaces: DISTINCT and
    set operations compare strings with the column collation, the model with exact
    equality) or 'violation'."""
    small, large = (original_rows, mutant_rows) if direction == 'Up' else (mutant_rows, original_rows)
    if included(bag(small), bag(large)):
        return 'ok'
    if included_modulo_collation(small, large):
        return 'collation'
    return 'violation'


# Results are compared as floats with a relative tolerance.  A wrong result that
# differs by less than the tolerance is not detected.
#
# Single-precision FLOAT columns carry about 7 significant digits, and the server
# prints them rounded (MAX of a FLOAT gives 82.16) but widens them to double in
# arithmetic (AVG of the same column gives 82.160004).  When the mutated column is
# single precision in either result, the looser tolerance is used.
REL_TOL = 1e-9
REL_TOL_SINGLE = 1e-4
_tolerance = REL_TOL


def _tol(a, b):
    return _tolerance * max(1.0, abs(a), abs(b))


def _le(a, b):
    return a <= b + _tol(a, b)


def relation_holds(relation, a, b):
    """The value relations of Value.v on floats, with a relative tolerance."""
    if relation == 'Le':
        return _le(a, b)
    if relation == 'Ge':
        return _le(b, a)
    pivot = 0.0 if relation == 'AwayZero' else 1.0
    tol = _tol(a, pivot)
    if abs(a - pivot) <= tol:
        return abs(a - b) <= 10 * _tol(a, b)   # both branches apply: the value must stay
    above = a > pivot
    if relation in ('AwayZero', 'AwayOne'):
        return _le(a, b) if above else _le(b, a)
    if relation == 'TowardOne':
        return _le(b, a) if above else _le(a, b)
    raise ValueError(relation)


def _key(row, column):
    def norm(v):
        if isinstance(v, (bytes, bytearray)):
            return ('b', bytes(v))
        if isinstance(v, NUMERIC) and not isinstance(v, bool):
            return ('n', float(v))
        if isinstance(v, (datetime.date, datetime.time, datetime.timedelta)):
            return ('d', str(v))
        return ('o', v)
    return tuple(norm(v) for i, v in enumerate(row) if i != column)


def check_value(relation, column, original_rows, mutant_rows, single_precision=False):
    global _tolerance
    _tolerance = REL_TOL_SINGLE if single_precision else REL_TOL
    try:
        return _check_value(relation, column, original_rows, mutant_rows)
    finally:
        _tolerance = REL_TOL


def _check_value(relation, column, original_rows, mutant_rows):
    """Return 'ok', 'incomparable' (the mutated column is not numeric in one of the
    results, so the relation is not defined) or a string describing the violation.

    Rows are matched within each group of rows that agree outside the mutated
    column.  The intended transformations are non-decreasing in the original
    value, so if the DBMS is correct the i-th smallest original value corresponds
    to the i-th smallest mutated value."""
    if len(original_rows) != len(mutant_rows):
        return 'row count %d vs %d' % (len(original_rows), len(mutant_rows))
    groups = collections.defaultdict(lambda: ([], []))
    for row in original_rows:
        groups[_key(row, column)][0].append(row[column])
    for row in mutant_rows:
        groups[_key(row, column)][1].append(row[column])
    for key, (orig, mut) in groups.items():
        if len(orig) != len(mut):
            return 'other columns changed'
        for values in (orig, mut):
            if any(v is not None and (isinstance(v, bool) or not isinstance(v, NUMERIC)) for v in values):
                return 'incomparable'
        order = lambda values: sorted(values, key=lambda v: (v is not None, float(v) if v is not None else 0.0))
        for a, b in zip(order(orig), order(mut)):
            if (a is None) != (b is None):
                return 'NULL-ness changed (%r vs %r)' % (a, b)
            if a is not None and not relation_holds(relation, float(a), float(b)):
                return '%s violated: %r vs %r' % (relation, a, b)
    return 'ok'
