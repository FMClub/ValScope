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


# MySQL / MariaDB character sets -> Python codecs (MySQL's latin1 is Windows-1252).
MYSQL_CODECS = {
    'utf8mb4': 'utf-8', 'utf8mb3': 'utf-8', 'utf8': 'utf-8', 'latin1': 'cp1252', 'ascii': 'ascii',
    'ucs2': 'utf-16-be', 'utf16': 'utf-16-be', 'utf16le': 'utf-16-le', 'utf32': 'utf-32-be',
    'latin2': 'iso8859_2', 'latin5': 'iso8859_9', 'latin7': 'iso8859_13', 'greek': 'iso8859_7',
    'hebrew': 'iso8859_8', 'cp1250': 'cp1250', 'cp1251': 'cp1251', 'cp1256': 'cp1256', 'cp1257': 'cp1257',
    'cp850': 'cp850', 'cp852': 'cp852', 'cp866': 'cp866', 'koi8r': 'koi8_r', 'koi8u': 'koi8_u',
    'gbk': 'gbk', 'gb2312': 'gb2312', 'gb18030': 'gb18030', 'big5': 'big5', 'sjis': 'shift_jis',
    'cp932': 'cp932', 'ujis': 'euc_jp', 'eucjpms': 'euc_jp', 'euckr': 'euc_kr', 'tis620': 'tis_620',
    'macroman': 'mac_roman', 'swe7': 'latin-1', 'dec8': 'latin-1', 'hp8': 'latin-1', 'armscii8': 'latin-1',
    'keybcs2': 'latin-1', 'macce': 'mac_latin2', 'geostd8': 'latin-1', 'cp1251_bin': 'cp1251',
}


def decode_per_column(conn, charsets):
    """With character_set_results = NULL the server sends every text column in its own
    character set; make pymysql decode each column with that set (charsets: collation id
    -> character set name).  A set without a Python codec is decoded as latin-1, which
    keeps every byte."""
    import pymysql.connections as pc
    if getattr(pc.MySQLResult, '_valscope_patched', False):
        pc.MySQLResult._valscope_charsets.update(charsets)
        return
    original = pc.MySQLResult._get_descriptions

    def _get_descriptions(self):
        original(self)
        if not getattr(self.connection, '_valscope_per_column', False):
            return
        converters = []
        for field, (encoding, converter) in zip(self.fields, self.converters):
            if encoding is not None and encoding != 'ascii' and field.charsetnr != 63:
                cs = pc.MySQLResult._valscope_charsets.get(field.charsetnr)
                encoding = MYSQL_CODECS.get(cs, 'latin-1') if cs else 'latin-1'
            converters.append((encoding, converter))
        self.converters = converters
    pc.MySQLResult._get_descriptions = _get_descriptions
    pc.MySQLResult._valscope_charsets = dict(charsets)
    pc.MySQLResult._valscope_patched = True


class MariaDBColumns:
    """Per-column folds for MariaDB / MySQL results.

    With `character_set_results = NULL` the server sends strings without conversion and
    reports, for every result column, its real collation (also for expressions, derived
    tables and set operations).  `folds(collation_ids)` turns those ids into folds."""

    # a column whose values a de-duplication under some other collation of the query may
    # have picked: compared with the coarsest collation of the database (`fallback`)
    COARSEST = '*'

    def __init__(self, conn, fallback=None):
        self.conn, self.cache, self.fallback = conn, {}, fallback
        with conn.cursor() as cur:
            # (MariaDB 10.10+ also lists collation aliases without an ID)
            cur.execute('SELECT ID, COLLATION_NAME, CHARACTER_SET_NAME FROM information_schema.COLLATIONS '
                        'WHERE ID IS NOT NULL')
            rows = cur.fetchall()
            self.names = {int(i): n for i, n, _ in rows}
            decode_per_column(conn, {int(i): c for i, _, c in rows})
            conn._valscope_per_column = True
            cur.execute('SET character_set_results = NULL')

    def name(self, cid):
        return self.names.get(cid, 'binary')

    def fold(self, name):
        if name == self.COARSEST:
            return self.fallback or ExactFold()
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
            if self.COARSEST in (a, b):
                pick = self.COARSEST
            else:
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


def _sql_text(v):
    """The SQL text of a date / time value, as a server prints it in a string column."""
    if isinstance(v, datetime.timedelta):
        sign, secs = ('-', -v) if v < datetime.timedelta(0) else ('', v)
        total = int(secs.total_seconds())
        frac = ('.%06d' % secs.microseconds) if secs.microseconds else ''
        return '%s%02d:%02d:%02d%s' % (sign, total // 3600, total % 3600 // 60, total % 60, frac)
    return str(v)


def _norm(v, fold, digits):
    """A hashable key for one value.

    The two results of a check can type the same column differently (BIGINT vs DOUBLE,
    TEXT vs BLOB, VARCHAR vs DATE) when a mutation changes how the server derives the
    column type.  Values are therefore compared by what they denote: bytes that are
    valid UTF-8 as text, dates and times as their SQL text, numbers by value.  With
    `digits`, floats and decimals are compared rounded to that many significant digits
    (last-bit differences between plans); integers are always exact."""
    if isinstance(v, (bytes, bytearray, memoryview)):
        try:
            v = bytes(v).decode('utf-8')
        except UnicodeDecodeError:
            return ('b', bytes(v))
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, int):
        return ('n', v)               # exact; an integral float or decimal is equal to it
    if isinstance(v, (float, Decimal)):
        if digits is not None:
            r = _round_float(float(v), digits)
            return ('n', int(r) if r.is_integer() and abs(r) < 2 ** 53 else r)
        return ('n', v)
    if isinstance(v, (datetime.date, datetime.time, datetime.datetime, datetime.timedelta)):
        return ('s', _sql_text(v))
    if isinstance(v, str):
        return ('s', fold(v))
    return ('o', v)


# Families of MySQL protocol column types: two results can be compared column by column
# when each column has types of the same family in both (or is NULL in one of them).
_FAMILIES = {}
for _codes, _family in (((0, 1, 2, 3, 4, 5, 8, 9, 13, 246), 'number'),
                        ((15, 247, 248, 249, 250, 251, 252, 253, 254, 7, 10, 11, 12, 14), 'text'),
                        ((16,), 'bit'), ((245,), 'json'), ((255,), 'geometry'), ((6,), 'null')):
    for _c in _codes:
        _FAMILIES[_c] = _family


def comparable_types(types_a, types_b, rows_a, rows_b):
    """None if the results can be compared column by column; otherwise the reason.
    Types are compared by family (numbers; text, binary strings and dates; bit; JSON;
    geometry); a column that holds only NULLs in one result fits any type."""
    if types_a is None or types_b is None:
        return None
    if len(types_a) != len(types_b):
        return 'different number of columns'
    for i, (a, b) in enumerate(zip(types_a, types_b)):
        fa, fb = _FAMILIES.get(a, 'other %s' % a), _FAMILIES.get(b, 'other %s' % b)
        if fa == fb or 'null' in (fa, fb):
            continue
        if all(r[i] is None for r in rows_a) or all(r[i] is None for r in rows_b):
            continue
        return 'column %d: %s vs %s' % (i, fa, fb)
    return None


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
    def __init__(self, tol, abs_tol=0.0):
        self.tol, self.abs_tol = tol, abs_tol

    def le(self, a, b):
        if _exact(a) and _exact(b):
            return Fraction(a) <= Fraction(b) + Fraction(self.abs_tol)
        a, b = float(a), float(b)
        return a <= b + self.tol * max(1.0, abs(a), abs(b)) + self.abs_tol

    def near(self, a, b, factor=1):
        if _exact(a) and _exact(b):
            return abs(Fraction(a) - Fraction(b)) <= Fraction(self.abs_tol)
        a, b = float(a), float(b)
        return abs(a - b) <= factor * self.tol * max(1.0, abs(a), abs(b)) + self.abs_tol


def relation_holds(relation, a, b, tol=REL_TOL, abs_tol=0.0):
    """The value relations of Value.v.  abs_tol: an absolute slack for values that the
    server rounded to a number of decimals on output (see check_value); it applies to exact
    values too (two DECIMALs of different scales)."""
    c = _Cmp(tol, abs_tol)
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


def check_value(relation, column, original_rows, mutant_rows, single_precision=False, fold=None, cover=False,
                strict_types=False, output_decimals=None):
    """'ok', 'incomparable' (the mutated column is not numeric in one of the results)
    or a string describing the violation.

    strict_types: the inputs of the query are known to be numeric (SQLite: the numeric
    probe of the bridge returned 0), so the mutated column is a number in both results.
    Text in one result only is then a violation ('type changed'), not 'incomparable':
    SQLite converted a value on the way (results/sqlite-bisect.md, bug 5).

    The other columns are compared exactly, then with floats rounded to 12 and 9
    significant digits, then (with a fold) modulo the DBMS's equality: a grouping key
    with a case-insensitive collation may be returned as 'a' by one plan and 'A' by
    another."""
    # output_decimals: the server rounded the mutated column to that many decimals in one
    # of the results and to more in the other (MariaDB: VAR_SAMP of a DECIMAL is a float
    # printed with 4, an AVG over it with 8; AVG of a DECIMAL(10,2) has scale 6, an AVG
    # over that scale 10), so a value can be off by one unit of the last digit
    tol = (REL_TOL_SINGLE if single_precision else REL_TOL,
           10.0 ** -output_decimals if output_decimals is not None else 0.0)
    attempts = [(ExactFold(), None), (ExactFold(), 12), (ExactFold(), 9)]
    if nontrivial(fold):
        attempts += [(fold, None), (fold, 9)]
    verdict = None
    check = _check_cover if cover else _check_value
    for f, digits in attempts:
        verdict = check(relation, column, original_rows, mutant_rows, f, digits, tol, strict_types)
        if verdict != 'other columns changed':
            return verdict
    return verdict


def _non_numeric(orig, mut, strict_types):
    """None when the values of the mutated column are numbers (or NULL) on both sides;
    otherwise 'incomparable', or a violation when only one side has non-numbers and the
    inputs are known to be numeric."""
    other = [[v for v in values if v is not None and (isinstance(v, bool) or not isinstance(v, NUMERIC))]
             for values in (orig, mut)]
    if not other[0] and not other[1]:
        return None
    # (reached only after the row counts and the other columns were found to agree: a value
    # rule on a date or text item still checks those, so such mutants are worth running)
    if strict_types and bool(other[0]) != bool(other[1]):
        return 'type changed: the mutated column holds a non-number in the %s only (%r)' % (
            'original' if other[0] else 'mutant', (other[0] or other[1])[0])
    return 'incomparable'


def _check_value(relation, column, original_rows, mutant_rows, fold, digits, tol, strict_types=False):
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
        typed = _non_numeric(orig, mut, strict_types)
        if typed:
            return typed
        nulls_o, nulls_m = orig.count(None), mut.count(None)
        if nulls_o != nulls_m:
            return 'NULL-ness changed (%d NULLs vs %d)' % (nulls_o, nulls_m)
        a = [v for v in orig if v is not None]
        b = [v for v in mut if v is not None]
        unmatched = _perfect_matching(a, b, lambda x, y: relation_holds(relation, x, y, *tol))
        if unmatched is not None:
            return '%s violated: no mutant value corresponds to %r (mutant values %r)' % (
                relation, unmatched, sorted(b, key=float)[:8])
    return 'ok'


def _check_cover(relation, column, original_rows, mutant_rows, fold, digits, tol, strict_types=False):
    """Under DISTINCT (VDistinct.v, tmutate_distinct_sound) the rows no longer correspond
    one to one; the theorem says every row of each result is related to some row of the
    other: it agrees outside the mutated column, and the values in it satisfy the
    relation (NULL only with NULL)."""
    groups = collections.defaultdict(lambda: ([], []))
    for row in original_rows:
        groups[_key(row, column, fold, digits)][0].append(row[column])
    for row in mutant_rows:
        groups[_key(row, column, fold, digits)][1].append(row[column])
    for key, (orig, mut) in groups.items():
        if not orig or not mut:
            return 'other columns changed'
        typed = _non_numeric(orig, mut, strict_types)
        if typed:
            return typed
        related = lambda x, y: (x is None and y is None) or (
            x is not None and y is not None and relation_holds(relation, x, y, *tol))
        for y in mut:
            if not any(related(x, y) for x in orig):
                return '%s violated: no original value is related to the mutant value %r (original values %r)' % (
                    relation, y, orig[:8])
        for x in orig:
            if not any(related(x, y) for y in mut):
                return '%s violated: no mutant value is related to the original value %r (mutant values %r)' % (
                    relation, x, mut[:8])
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
