"""Result checkers for the two kinds of mutation.

These functions are NOT verified.  They decide whether two query results stand in
the relation that the Rocq theorems promise:

- set-semantic  : bag inclusion between the original and the mutant, MODULO the
  equality of the DBMS (Semantics.v: q_le is bag_le (req db), inclusion up to the
  world's collation equivalence veq);
- value-semantic: the rows correspond one to one, agree outside the mutated
  column, and satisfy the rule's value relation inside it.

The collation equivalence
-------------------------
In the model, DISTINCT, UNION, INTERSECT and EXCEPT compare values with the world's
equivalence `veq`, and the theorems promise inclusion up to `veq`.  If a column has a
case-insensitive collation, 'a' and 'A' are equivalent, and SQL does not say which of
the two DISTINCT keeps.  So a correct DBMS may return 'a' in the original and 'A' in the
mutant.  To check the theorem, results must be compared with the DBMS's own equality.

A `Fold` maps a value to a key such that two values have the same key exactly when the
DBMS considers them equal:

- `ExactFold`        binary comparison (no collation);
- `SQLiteFold`       SQLite's built-in collations (BINARY, NOCASE: ASCII letters only,
                     RTRIM: trailing spaces ignored, or both);
- `MariaDBFold`      asks the server: WEIGHT_STRING under the collation, with trailing
                     spaces removed for PAD SPACE collations.

The verdicts of `check_inclusion` are
- 'ok'          the rows are included exactly;
- 'collation'   included modulo the DBMS's equality but not exactly: the theorem holds,
                and the difference is the choice of a representative, which SQL leaves open;
- 'violation'   not included even modulo the DBMS's equality: the theorem's relation fails.

When a result column could have one of several collations (the result does not say
which), the fold of the coarsest collation used in the database is applied to every
column.  This can classify a real violation on a binary column that differs only in case
as 'collation' (a missed bug), never the other way round.
"""
import collections
import datetime
from decimal import Decimal
from fractions import Fraction

NUMERIC = (int, float, Decimal)


# ---------------------------------------------------------------- folds
class ExactFold:
    name = 'exact'

    def __call__(self, value):
        return value


class SQLiteFold:
    """SQLite's built-in collations.  NOCASE folds the 26 ASCII letters only; RTRIM
    ignores trailing spaces.  With 'NOCASE+RTRIM' (a database that uses both), two
    strings are identified when one of the two collations, applied after the other,
    identifies them: the coarsest equivalence of the database."""

    _lower = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')

    def __init__(self, collation='BINARY'):
        self.name = collation.upper()
        self.parts = set(self.name.split('+')) - {'BINARY'}
        if not self.parts <= {'NOCASE', 'RTRIM'}:
            raise ValueError(collation)

    def __call__(self, value):
        if not isinstance(value, str):
            return value
        if 'NOCASE' in self.parts:
            value = value.translate(self._lower)
        if 'RTRIM' in self.parts:
            value = value.rstrip(' ')
        return value


def sqlite_fold(schema_sql):
    """The fold for a database whose CREATE statements are `schema_sql` (a list)."""
    text = ' '.join(schema_sql).upper()
    parts = [c for c in ('NOCASE', 'RTRIM') if 'COLLATE ' + c in text]
    return SQLiteFold('+'.join(parts) or 'BINARY')


class MariaDBFold:
    """The equality of a MariaDB / MySQL collation, computed by the server."""

    def __init__(self, conn, collation):
        self.conn, self.name, self.cache = conn, collation, {}
        with conn.cursor() as cur:
            cur.execute('SELECT CHARACTER_SET_NAME FROM information_schema.COLLATIONS '
                        'WHERE COLLATION_NAME = %s', (collation,))
            row = cur.fetchone()
            if row is None:
                raise ValueError('unknown collation %s' % collation)
            self.charset = row[0]
            try:        # MySQL 8 has the column; MariaDB names its NO PAD collations *_nopad_*
                cur.execute('SELECT PAD_ATTRIBUTE FROM information_schema.COLLATIONS '
                            'WHERE COLLATION_NAME = %s', (collation,))
                self.pad = cur.fetchone()[0] == 'PAD SPACE'
            except Exception:
                self.pad = 'nopad' not in collation

    def __call__(self, value):
        if not isinstance(value, str):
            return value
        if value not in self.cache:
            text = value.rstrip(' ') if self.pad else value
            with self.conn.cursor() as cur:
                cur.execute('SELECT WEIGHT_STRING(CONVERT(%%s USING %s) COLLATE %s)' % (self.charset, self.name),
                            (text,))
                self.cache[value] = ('w', bytes(cur.fetchone()[0]))
        return self.cache[value]


class MariaDBColumns:
    """Per-column folds for MariaDB / MySQL results.

    With `character_set_results = NULL` the server sends strings without conversion and
    reports, for every result column, its real collation (also for expressions, derived
    tables and set operations).  `folds(collation_ids)` turns those ids into folds."""

    def __init__(self, conn):
        self.conn, self.cache = conn, {}
        with conn.cursor() as cur:
            cur.execute('SET character_set_results = NULL')
            # (MariaDB 10.10+ also lists collation aliases without an ID)
            cur.execute('SELECT ID, COLLATION_NAME FROM information_schema.COLLATIONS WHERE ID IS NOT NULL')
            self.names = {int(i): n for i, n in cur.fetchall()}

    def name(self, cid):
        return self.names.get(cid, 'binary')

    def fold(self, name):
        if name == 'binary' or name is None:
            return ExactFold()
        if name not in self.cache:
            self.cache[name] = MariaDBFold(self.conn, name)
        return self.cache[name]

    def folds(self, names_a, names_b=None):
        """Folds for comparing a result whose columns have collations names_a with one
        whose columns have names_b: where they differ, the coarser (case- or
        accent-insensitive) one."""
        names_b = names_b or names_a
        out = []
        for a, b in zip(names_a, names_b):
            pick = a if a == b else next((n for n in (a, b) if n and ('_ci' in n or '_ai' in n)), a)
            out.append(self.fold(pick))
        return out


def mariadb_fold(conn, database):
    """The fold for the text columns of `database`: their collation when there is one;
    with several, the first case-insensitive one (the coarsest in practice)."""
    with conn.cursor() as cur:
        cur.execute('SELECT DISTINCT COLLATION_NAME FROM information_schema.COLUMNS '
                    'WHERE TABLE_SCHEMA = %s AND COLLATION_NAME IS NOT NULL', (database,))
        names = sorted(r[0] for r in cur.fetchall())
    if not names:
        return ExactFold()
    insensitive = [n for n in names if '_ci' in n or '_ai' in n]
    return MariaDBFold(conn, (insensitive or names)[0])


# ---------------------------------------------------------------- numbers
def _round_float(v, digits):
    return float('%.*g' % (digits, v))


def _norm(v, fold, digits):
    """A hashable key for one value.  Only binary floating-point numbers are rounded
    (to `digits` significant digits, when given); integers and decimals stay exact."""
    if isinstance(v, (bytes, bytearray, memoryview)):
        return ('b', bytes(v))
    if isinstance(v, bool):
        return ('n', int(v))
    if isinstance(v, float):
        return ('n', v if digits is None else _round_float(v, digits))
    if isinstance(v, (int, Decimal)):
        return ('n', v)
    if isinstance(v, (datetime.date, datetime.time, datetime.datetime, datetime.timedelta)):
        return ('d', str(v))
    if isinstance(v, str):
        return ('s', fold(v))
    return ('o', v)


def _column_folds(fold, width):
    """One fold per column.  `fold` is None, one fold for every column, or a list with
    one fold per column (the collation of each result column)."""
    if fold is None:
        return [ExactFold()] * width
    if isinstance(fold, (list, tuple)):
        return [f or ExactFold() for f in fold] + [ExactFold()] * (width - len(fold))
    return [fold] * width


def nontrivial(fold):
    """Does the fold identify any two different strings?"""
    if fold is None:
        return False
    if isinstance(fold, (list, tuple)):
        return any(nontrivial(f) for f in fold)
    return not isinstance(fold, ExactFold) and not (isinstance(fold, SQLiteFold) and not fold.parts)


def bag(rows, fold=None, digits=None):
    if fold is None and digits is None:
        return collections.Counter(rows)
    folds = None
    out = collections.Counter()
    for row in rows:
        if folds is None or len(folds) != len(row):
            folds = _column_folds(fold, len(row))
        out[tuple(_norm(v, f, digits) for v, f in zip(row, folds))] += 1
    return out


def included(small, large):
    return all(large[row] >= n for row, n in small.items())


def check_inclusion(direction, original_rows, mutant_rows, fold=None):
    """'ok', 'collation' or 'violation' (see the module docstring).  direction 'Up':
    the original must be included in the mutant; 'Down': the other way round.

    Binary floating-point values are compared after rounding to 12, then 9 significant
    digits: an aggregate such as AVG or SUM over DOUBLE can differ in its last bits
    between two plans of the same query (the model computes exactly)."""
    small, large = (original_rows, mutant_rows) if direction == 'Up' else (mutant_rows, original_rows)
    if included(bag(small), bag(large)):
        return 'ok'
    for digits in (12, 9):
        if included(bag(small, None, digits), bag(large, None, digits)):
            return 'ok'
    if nontrivial(fold):
        for digits in (None, 12, 9):
            if included(bag(small, fold, digits), bag(large, fold, digits)):
                return 'collation'
    return 'violation'


# ---------------------------------------------------------------- value relations
# Results are compared exactly when both values are integers or decimals, and with a
# relative tolerance when one of them is a binary float.  A wrong result that differs by
# less than the tolerance is not detected.
#
# Single-precision FLOAT columns carry about 7 significant digits, and the server
# prints them rounded (MAX of a FLOAT gives 82.16) but widens them to double in
# arithmetic (AVG of the same column gives 82.160004).  When the mutated column is
# single precision in either result, the looser tolerance is used.
REL_TOL = 1e-9
REL_TOL_SINGLE = 1e-4


def _exact(v):
    return isinstance(v, (int, Decimal)) and not isinstance(v, bool)


class _Cmp:
    def __init__(self, tol):
        self.tol = tol

    def le(self, a, b):
        if _exact(a) and _exact(b):
            return Fraction(a) <= Fraction(b)
        a, b = float(a), float(b)
        return a <= b + self.tol * max(1.0, abs(a), abs(b))

    def near(self, a, b, factor=1):
        if _exact(a) and _exact(b):
            return Fraction(a) == Fraction(b)
        a, b = float(a), float(b)
        return abs(a - b) <= factor * self.tol * max(1.0, abs(a), abs(b))


def relation_holds(relation, a, b, tol=REL_TOL):
    """The value relations of Value.v."""
    c = _Cmp(tol)
    if relation == 'Le':
        return c.le(a, b)
    if relation == 'Ge':
        return c.le(b, a)
    pivot = 0 if relation == 'AwayZero' else 1
    if c.near(a, pivot):
        return c.near(a, b, 10)     # both branches apply: the value must stay
    above = c.le(pivot, a)
    if relation in ('AwayZero', 'AwayOne'):
        return c.le(a, b) if above else c.le(b, a)
    if relation == 'TowardOne':
        return c.le(b, a) if above else c.le(a, b)
    raise ValueError(relation)


def _key(row, column, fold, digits):
    """The columns other than the mutated one, as a dictionary key."""
    folds = _column_folds(fold, len(row))
    return tuple(_norm(v, f, digits) for i, (v, f) in enumerate(zip(row, folds)) if i != column)


def check_value(relation, column, original_rows, mutant_rows, single_precision=False, fold=None):
    """'ok', 'incomparable' (the mutated column is not numeric in one of the results)
    or a string describing the violation.

    The other columns are compared exactly, then with floats rounded to 12 and 9
    significant digits, then (with a fold) modulo the DBMS's equality: a grouping key
    with a case-insensitive collation may be returned as 'a' by one plan and 'A' by
    another."""
    tol = REL_TOL_SINGLE if single_precision else REL_TOL
    attempts = [(ExactFold(), None), (ExactFold(), 12), (ExactFold(), 9)]
    if nontrivial(fold):
        attempts += [(fold, None), (fold, 9)]
    verdict = None
    for f, digits in attempts:
        verdict = _check_value(relation, column, original_rows, mutant_rows, f, digits, tol)
        if verdict != 'other columns changed':
            return verdict
    return verdict


def _check_value(relation, column, original_rows, mutant_rows, fold, digits, tol):
    """The theorem (vmut_sound) says: the rows of the original and of the mutant can be
    put in one-to-one correspondence so that corresponding rows agree outside the
    mutated column and their values in it satisfy the relation (NULL only with NULL).
    The DBMS returns rows in any order, so the check is whether SUCH a correspondence
    exists.

    Rows that agree outside the mutated column form a group; only rows of the same
    group can correspond.  Within a group, NULLs must correspond to NULLs, and for the
    other values a perfect bipartite matching (edge: the relation holds) must exist.
    It is first tried by sorting (which finds one whenever the rule function is
    non-decreasing), and otherwise searched exhaustively with augmenting paths, so
    the verdict does not depend on any property of the rule."""
    if len(original_rows) != len(mutant_rows):
        return 'row count %d vs %d' % (len(original_rows), len(mutant_rows))
    groups = collections.defaultdict(lambda: ([], []))
    for row in original_rows:
        groups[_key(row, column, fold, digits)][0].append(row[column])
    for row in mutant_rows:
        groups[_key(row, column, fold, digits)][1].append(row[column])
    for key, (orig, mut) in groups.items():
        if len(orig) != len(mut):
            return 'other columns changed'
        for values in (orig, mut):
            if any(v is not None and (isinstance(v, bool) or not isinstance(v, NUMERIC)) for v in values):
                return 'incomparable'
        nulls_o, nulls_m = orig.count(None), mut.count(None)
        if nulls_o != nulls_m:
            return 'NULL-ness changed (%d NULLs vs %d)' % (nulls_o, nulls_m)
        a = [v for v in orig if v is not None]
        b = [v for v in mut if v is not None]
        unmatched = _perfect_matching(a, b, lambda x, y: relation_holds(relation, x, y, tol))
        if unmatched is not None:
            return '%s violated: no mutant value corresponds to %r (mutant values %r)' % (
                relation, unmatched, sorted(b, key=float)[:8])
    return 'ok'


def _perfect_matching(a, b, ok):
    """None if every element of a can be paired with a distinct element of b such that
    ok(x, y) holds (len(a) == len(b)); otherwise an element of a left unmatched."""
    key = lambda v: float(v)
    sa, sb = sorted(a, key=key), sorted(b, key=key)
    if all(ok(x, y) for x, y in zip(sa, sb)):
        return None
    # Kuhn's augmenting-path algorithm on the bipartite graph of related pairs
    adj = [[j for j, y in enumerate(b) if ok(x, y)] for x in a]
    match_b = [-1] * len(b)

    def augment(i, seen):
        for j in adj[i]:
            if not seen[j]:
                seen[j] = True
                if match_b[j] < 0 or augment(match_b[j], seen):
                    match_b[j] = i
                    return True
        return False
    for i in range(len(a)):
        if not augment(i, [False] * len(b)):
            return a[i]
    return None
