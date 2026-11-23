"""The collation law (which queries and mutants are outside the model because an operation
tells collation-equivalent values apart above a de-duplication) and the storage classes
of columns that exempt an operation from it."""
import sqlglot
from sqlglot import exp

from common import parse_sexp, _strip_parens

# ---------------------------------------------------------------- the collation law
#
# The theorems hold in every world whose operations respect the collation equivalence
# (Semantics.v: veq).  Under a case-insensitive or PAD SPACE collation, 'a', 'A' and 'a '
# are equivalent, and DISTINCT / UNION / INTERSECT / EXCEPT (and GROUP BY, MIN, MAX in
# opaque parts) keep ONE of them, which SQL does not specify.  An operation that tells
# equivalent strings apart (LENGTH, HEX, CONCAT, LIKE, a BINARY cast, ...) applied to
# such a representative makes the result undetermined, and the world law fails.  The
# bridge therefore refuses such an operation ABOVE a de-duplication: the original query
# is rejected, a mutant is dropped (STATS['outside_model']).

SENSITIVE_FUNCS = {
    'LENGTH', 'CHAR_LENGTH', 'CHARACTER_LENGTH', 'OCTET_LENGTH', 'BIT_LENGTH', 'LEN', 'HEX', 'UNHEX',
    'ASCII', 'ORD', 'UNICODE', 'CHAR', 'CHR', 'BINARY', 'CONCAT', 'CONCAT_WS', 'SUBSTR', 'SUBSTRING',
    'SUBSTRING_INDEX', 'MID', 'LEFT', 'RIGHT', 'REVERSE', 'REPLACE', 'INSERT', 'INSTR', 'LOCATE',
    'POSITION', 'STRPOS', 'STR_POSITION', 'LPAD', 'RPAD', 'PAD', 'REPEAT', 'MD5', 'SHA', 'SHA1', 'SHA2',
    'CRC32', 'TO_BASE64', 'FROM_BASE64', 'QUOTE', 'TYPEOF', 'SOUNDEX', 'FIELD', 'ELT', 'FIND_IN_SET',
    'MAKE_SET', 'EXPORT_SET', 'FORMAT', 'PRINTF', 'GROUP_CONCAT', 'GROUPCONCAT', 'WEIGHT_STRING_BINARY',
}
# Functions known to map equivalent arguments to equivalent results (numeric functions,
# case mapping, trimming of trailing spaces, conditionals, aggregates that the theorems or
# _dedup_tree cover, dates).  Any other function, including one sqlglot does not know, is
# treated as able to tell equivalent strings apart: the list of SENSITIVE_FUNCS documents
# the usual ones, but it is not what makes the check safe.
RESPECTING_FUNCS = {
    'AND', 'OR', 'NOT', 'XOR', 'EXISTS', 'COUNT', 'COUNT_IF', 'SUM', 'AVG', 'MIN', 'MAX', 'TOTAL',
    'VARIANCE', 'VARIANCE_POP', 'VAR_SAMP', 'VAR_POP', 'STDDEV', 'STDDEV_POP', 'STDDEV_SAMP',
    'BITWISE_AND_AGG', 'BITWISE_OR_AGG', 'BITWISE_XOR_AGG', 'BIT_AND', 'BIT_OR', 'BIT_XOR',
    'ABS', 'SIGN', 'ROUND', 'FLOOR', 'CEIL', 'CEILING', 'TRUNCATE', 'TRUNC', 'SQRT', 'POW', 'POWER',
    'EXP', 'LN', 'LOG', 'LOG2', 'LOG10', 'MOD', 'SIN', 'COS', 'TAN', 'COT', 'ASIN', 'ACOS', 'ATAN',
    'ATAN2', 'DEGREES', 'RADIANS', 'PI', 'GREATEST', 'LEAST', 'COALESCE', 'IFNULL', 'NVL', 'NULLIF',
    'IF', 'IIF', 'CASE', 'LIKELY', 'UNLIKELY', 'LIKELIHOOD', 'CAST', 'TRY_CAST', 'UPPER', 'LOWER',
    'UCASE', 'LCASE', 'RTRIM', 'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'TIME_TO_STR',
    'TS_OR_DS_TO_TIMESTAMP', 'YEAR', 'MONTH', 'DAY', 'DAYOFMONTH', 'DAYOFWEEK', 'DAYOFYEAR',
    'QUARTER', 'WEEK', 'HOUR', 'MINUTE', 'SECOND', 'DATE', 'CURRENT_DATE',
}
SENSITIVE_NODES = (exp.DPipe, exp.Like, exp.ILike, exp.Glob, exp.RegexpLike, exp.Collate)
BINARY_TYPES = ('BINARY', 'VARBINARY', 'BLOB', 'TINYBLOB', 'MEDIUMBLOB', 'LONGBLOB', 'BIT')


# SQLite: functions whose result is the text of a number argument ('1' or '1.0')
SQLITE_TEXT_OF_NUMBER = {'UPPER', 'LOWER', 'UCASE', 'LCASE', 'TRIM', 'LTRIM', 'RTRIM', 'TIME_TO_STR'}
TEXT_TYPES = ('TEXT', 'CHAR', 'VARCHAR', 'NCHAR', 'NVARCHAR', 'CLOB', 'STRING')


def _sqlite_to_text(n):
    if isinstance(n, (exp.Cast, exp.TryCast)) and n.args.get('to') is not None:
        return n.args['to'].sql().upper().split('(')[0] in TEXT_TYPES
    if isinstance(n, (exp.Anonymous, exp.Func)):
        name = (n.name if isinstance(n, exp.Anonymous) else n.sql_name()).upper()
        return name in SQLITE_TEXT_OF_NUMBER
    return False


_SENSITIVE = {}


def _sensitive_tree(tree, dialect):
    k = (id(tree), dialect)
    if k not in _SENSITIVE:
        _SENSITIVE[k] = (tree, _sensitive_tree_uncached(tree, dialect))   # keep tree alive for id()
    return _SENSITIVE[k][1]


def _sensitive_tree_uncached(tree, dialect):
    for n in tree.walk():
        if isinstance(n, SENSITIVE_NODES):
            return True
        if isinstance(n, (exp.Cast, exp.TryCast)) and n.args.get('to') is not None and \
                n.args['to'].sql().upper().split('(')[0] in BINARY_TYPES:
            return True
        if isinstance(n, (exp.Anonymous, exp.Func)) and not isinstance(n, (exp.Cast, exp.TryCast)):
            name = (n.name if isinstance(n, exp.Anonymous) else n.sql_name()).upper()
            if name in SENSITIVE_FUNCS or name not in RESPECTING_FUNCS:
                return True
        if dialect == 'sqlite' and isinstance(n, exp.Div):
            return True     # 1 and 1.0 are equal in SQLite, but 1/2 = 0 and 1.0/2 = 0.5
        if dialect == 'sqlite' and _sqlite_to_text(n):
            return True     # 1 and 1.0 are equal in SQLite, but their text is '1' and '1.0'
    return False


def _dedup_tree(tree):
    """Does an opaque query or table pick representatives (DISTINCT, a set operation
    without ALL, GROUP BY, MIN / MAX)?"""
    for n in tree.walk():
        if isinstance(n, exp.Select) and (n.args.get('distinct') or n.args.get('group')):
            return True
        if isinstance(n, exp.Union) and n.args.get('distinct'):
            return True
        if isinstance(n, (exp.Intersect, exp.Except, exp.Min, exp.Max)):
            return True
    return False


_GLOBAL_PARSE = {}


def _cached_parse(cache, text, dialect, wrap=None):
    """sqlglot's tree of an atom text (shared by all translations: the same atom text
    occurs in the original and in every re-parsed mutant)."""
    cache = _GLOBAL_PARSE
    if len(cache) > 200000:
        cache.clear()
    key = (text, dialect, wrap)
    if key not in cache:
        try:
            if wrap == 'table':
                cache[key] = sqlglot.parse_one('SELECT * FROM ' + text, read=dialect)
            else:
                cache[key] = sqlglot.parse_one(text, read=dialect)
        except Exception:
            cache[key] = None
    return cache[key]


def outside_collation_law(tr, term):
    """The reason why `term` (of translation tr) may apply an operation that tells apart
    collation-equivalent values to a representative chosen by a de-duplication; None if
    it does not."""
    cache = tr._law_cache
    exact = getattr(tr, '_exact_names', set())

    def reads_exact_only(t):
        """Does the atom read only columns that hold integers (or NULL)?  Equivalent values
        of such columns are identical, so the operation gives the same result whichever
        representative a de-duplication kept."""
        cols = [n for n in t.walk() if isinstance(n, (exp.Column, exp.Star))]
        by_table = getattr(tr.exact_columns, 'by_table', None) or {}
        if not exact and not by_table:
            return False
        return all(isinstance(c, exp.Column) and not isinstance(c.this, exp.Star)
                   and (c.name.lower() in exact or _column_class(c, tr._sources, by_table, tr.schema) is not None)
                   for c in cols)
    tree = parse_sexp(term) if isinstance(term, str) else term

    query_tags = ('Proj', 'Where', 'Inner', 'Left', 'Distinct', 'Union', 'UnionAll', 'Intersect', 'Except',
                  'IntersectAll', 'ExceptAll', 'T', 'Named', 'QAtom')

    def bound_in(q):
        """The table aliases a nested query binds itself."""
        out = set()

        def walk(y):
            if isinstance(y, list) and y:
                if y[0] == 'T':
                    out.add(tr.aliases[int(y[1])].lower())
                elif y[0] == 'Named':
                    out.add(tr.named[int(y[1])].lower())
                for z in y[1:]:
                    walk(z)
        walk(q)
        return out

    def local(t, bound):
        """Inside a nested query: does the atom read only rows of that query (every column
        qualified by an alias the nested query binds)?  Then it does not see the
        representative the outer de-duplication kept."""
        return bound is not None and all(
            isinstance(c, exp.Column) and c.table and c.table.lower() in bound
            for c in t.walk() if isinstance(c, (exp.Column, exp.Star)))

    def sensitive(x, bound=None):
        """Does the item / predicate list x contain such an operation (also inside the
        subqueries of x, when an atom there refers to the current row)?"""
        if not isinstance(x, list) or not x:
            return False
        if isinstance(x[0], list):                  # a list of items or keys
            return any(sensitive(y, bound) for y in x)
        tag = x[0]
        if tag in query_tags:
            bound = (bound or set()) | bound_in(x)
        texts = {'EAtom': (tr.exprs, None), 'Atom': (tr.preds, None), 'AOpaque': (tr.opaque_items, None)}
        if tag in ('Like', 'Regex'):
            # the operand and the pattern: exempt only if every part is an atom over exact columns
            parts = [y for y in x[1:] if isinstance(y, list)]
            if all(p and p[0] in texts for p in parts):
                trees = [_cached_parse(cache, texts[p[0]][0][int(p[1])], tr.dialect) for p in parts]
                if all(t is not None and (reads_exact_only(t) or local(t, bound)) for t in trees):
                    return False
            return True
        if tag in texts:
            t = _cached_parse(cache, texts[tag][0][int(x[1])], tr.dialect)
            return t is None or (_sensitive_tree(t, tr.dialect) and not reads_exact_only(t)
                                 and not local(t, bound))
        return any(sensitive(y, bound) for y in x[1:])

    def dedup(q):
        """Does the input q pick representatives somewhere?"""
        if not isinstance(q, list) or not q:
            return False
        tag = q[0]
        if tag in ('Distinct', 'Union', 'Intersect', 'Except', 'IntersectAll', 'ExceptAll'):
            return True
        if tag == 'T':
            t = _cached_parse(cache, tr.tables[int(q[1])], tr.dialect, 'table')
            return t is None or _dedup_tree(t)
        if tag == 'QAtom':
            t = _cached_parse(cache, tr.qatoms[int(q[1])], tr.dialect)
            return t is None or _dedup_tree(t)
        if tag == 'Named':
            return dedup(q[2])
        if tag in ('Proj', 'Where'):
            return dedup(q[2])
        if tag == 'Inner':
            return dedup(q[2]) or dedup(q[3])
        if tag == 'Left':
            return dedup(q[3]) or dedup(q[4])
        if tag == 'UnionAll':
            return dedup(q[1]) or dedup(q[2])
        return False

    def check(q):
        if not isinstance(q, list) or not q:
            return None
        tag = q[0]
        own, inputs = [], []
        if tag in ('Proj', 'Where'):
            own, inputs = [q[1]], [q[2]]
        elif tag == 'Inner':
            own, inputs = [q[1]], [q[2], q[3]]
        elif tag == 'Left':
            own, inputs = [q[2]], [q[3], q[4]]
        elif tag == 'VProj':
            own, inputs = [q[1]], [q[2]]
        elif tag == 'VGroup':
            own, inputs = [q[1], q[2], q[3]], [q[4]]
        elif tag == 'VGlobal':
            own, inputs = [q[1], q[2]], [q[3]]
        if own and any(sensitive(o) for o in own) and any(dedup(i) for i in inputs):
            return '%s applies an operation that distinguishes collation-equivalent values ' \
                   'to the output of a de-duplication' % tag
        for x in q[1:]:
            r = check(x)
            if r:
                return r
        return None
    return check(tree)


COMPARING = ('Distinct', 'Union', 'Intersect', 'Except', 'IntersectAll', 'ExceptAll')


def compared_selections(tr, term):
    """The sub-queries of `term` that compare rows (DISTINCT and the set operations but
    UNION ALL) over a WHERE or ON condition which may tell equivalent rows apart.

    A rule proved for a class of worlds can turn `q WHERE c1 AND c2` into `(q WHERE c1)
    INTERSECT (q WHERE c2)`.  Its proof uses the law that a condition has one truth value
    on equivalent rows.  With 'a' and 'A' in a case-insensitive column, `HEX(s) = '61'`
    and `HEX(s) = '41'` each keep one of the two rows, and the INTERSECT finds them equal:
    the mutant has a row and the original none.  So a mutant of such a rule is outside
    the model when it does not have exactly these sub-queries of the original.

    Only two forms of condition are taken not to tell equivalent rows apart: a comparison
    all of whose operands read only integer columns or are number literals, and a
    comparison of a bare column with a string literal (made in the collation of the
    column, which is the one a de-duplication of that column uses); and IS NULL of a bare
    column or of such an integer operand.  Anything else may: a function or an arithmetic
    operation on a string column converts it ('12' and a string with the same collation
    key need not be the same number; a cast to binary tells 'a' from 'A'), as does a
    comparison of a string column with a number or with another column, a CASE, a
    sub-query."""
    cache = tr._law_cache
    exact = getattr(tr, '_exact_names', set())
    by_table = getattr(tr.exact_columns, 'by_table', None) or {}

    def foreign_tables():
        """Does the query read a table of another database?  The integer columns are known
        by name for the tables of the database under test only."""
        for text in tr.tables:
            t = _cached_parse(cache, text, tr.dialect, 'table')
            if t is None or any(n.args.get('db') or n.args.get('catalog') for n in t.find_all(exp.Table)):
                return True
        return False
    foreign = foreign_tables()

    def exact_only(t):
        cols = [n for n in t.walk() if isinstance(n, (exp.Column, exp.Star))]
        if not cols or foreign or any(c.args.get('db') or c.args.get('catalog') for c in cols
                                      if isinstance(c, exp.Column)):
            return False
        return (bool(exact) or bool(by_table)) and all(
            isinstance(c, exp.Column) and not isinstance(c.this, exp.Star)
            and (c.name.lower() in exact or _column_class(c, tr._sources, by_table, tr.schema) is not None)
            for c in cols)

    def operand(x):
        if not (isinstance(x, list) and x and x[0] == 'EAtom'):
            return 'other'
        t = _cached_parse(cache, tr.exprs[int(x[1])], tr.dialect)
        if t is None:
            return 'other'
        inner, negated = t, False
        while isinstance(inner, (exp.Paren, exp.Neg)):
            negated = negated or isinstance(inner, exp.Neg)
            inner = inner.this
        if isinstance(inner, exp.Literal) and t.find(exp.Introducer, exp.Cast, exp.Collate) is None:
            if inner.is_number:
                return 'number'
            return 'other' if negated else 'string'      # -'12' is a number made from a string
        if _sensitive_tree(t, tr.dialect):
            return 'other'
        if exact_only(t):
            return 'exact'
        return 'column' if isinstance(inner, exp.Column) and inner is _strip(t) else 'other'

    def telling(p):
        if not isinstance(p, list) or not p:
            return False
        tag = p[0]
        if tag in ('True', 'False'):
            return False
        if tag in ('Not', 'And', 'Or'):
            return any(telling(y) for y in p[1:])
        if tag == 'IsNull':
            return operand(p[1]) not in ('column', 'exact')
        if tag == 'Cmp':
            kinds = sorted([operand(p[2]), operand(p[3])])
            if kinds == ['column', 'string']:
                return False
            return not all(k in ('number', 'exact') for k in kinds)
        if tag == 'Atom':
            t = _cached_parse(cache, tr.preds[int(p[1])], tr.dialect)
            return t is None or not exact_only(t) or _sensitive_tree(t, tr.dialect)
        return True                     # LIKE, REGEXP, IN, EXISTS, anything else

    def _strip(t):
        while isinstance(t, exp.Paren):
            t = t.this
        return t

    def selects_apart(q):
        if not isinstance(q, list) or not q:
            return False
        if isinstance(q[0], list):
            return any(selects_apart(y) for y in q)
        if q[0] == 'Where' and telling(q[1]):
            return True
        if q[0] == 'Inner' and telling(q[1]):
            return True
        if q[0] == 'Left' and telling(q[2]):
            return True
        return any(selects_apart(y) for y in q[1:])

    out = set()

    def walk(q):
        if not isinstance(q, list) or not q:
            return
        if isinstance(q[0], list):
            for y in q:
                walk(y)
            return
        if q[0] in COMPARING and selects_apart(q):
            out.add(repr(q))
        for y in q[1:]:
            walk(y)
    walk(parse_sexp(term) if isinstance(term, str) else term)
    return frozenset(out)


def _exact_names(tree, exact_columns, schema):
    """The column names of the query whose values have one representation each on this
    database, so that two equivalent values are identical: `exact_columns` maps a base
    column name to its storage class ('integer', or 'real' without -0.0) when the column
    holds only that class (or NULL) in every table that has it (a set means 'integer').
    A select alias is exact when every definition of it (in any SELECT of the query) is
    a plain column of an exact name, all of the same class: 1 and 1.0 must not meet in a
    compound.  A computed definition (AVG, arithmetic, ...) is never exact.  Returns the
    exact names."""
    if not exact_columns:
        return set()
    if not isinstance(exact_columns, dict):
        exact_columns = {c: 'integer' for c in exact_columns}
    base = {c.lower() for cols in schema.values() for c in cols} if schema else set()
    defs = {}
    for n in tree.walk():
        if isinstance(n, exp.Alias) and n.alias:
            defs.setdefault(n.alias.lower(), []).append(n.this)
        elif isinstance(n, exp.Column) and isinstance(n.parent, exp.Select) and n in n.parent.expressions:
            defs.setdefault(n.name.lower(), []).append(n)        # an unaliased item keeps its name
    for n in tree.walk():                                         # column lists of derived tables
        if isinstance(n, exp.TableAlias) and n.columns:
            for c in n.columns:
                defs.setdefault(c.name.lower(), []).append(None)  # positional: not followed
    cls = {c: k for c, k in exact_columns.items() if c in base}
    changed = True
    names = set(defs) | base
    while changed:
        changed = False
        for name in names:
            if name in cls or (name in base and name not in exact_columns):
                continue
            ds = _proper_defs(name, defs)
            k = _combine_classes([_def_class(d, cls) for d in ds]) if ds else None
            if k is not None:
                cls[name] = k
                changed = True
    # a base column that is redefined by an alias needs its definitions to be exact too
    return {n for n, k in cls.items()
            if _combine_classes([k] + [_def_class(d, cls) for d in _proper_defs(n, defs)]) is not None}


class ExactColumns(dict):
    """Column name -> storage class (see _exact_names), with `by_table`: (table, column)
    -> storage class, for the columns of each table that hold one class only."""
    by_table = {}


def _alias_sources(tree):
    """Table alias -> what it names: ('table', name), or ('query', a SELECT or compound) for
    a derived table or a CTE.  An alias used twice names all of its sources."""
    ctes = {c.alias.lower(): c.this for c in tree.find_all(exp.CTE) if c.alias}
    out = {}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        alias = (t.alias or t.name).lower()
        out.setdefault(alias, []).append(('query', ctes[name]) if name in ctes else ('table', name))
    for sq in tree.find_all(exp.Subquery):
        if sq.alias:
            cols = sq.args.get('alias').columns if sq.args.get('alias') is not None else None
            out.setdefault(sq.alias.lower(), []).append(('positional', None) if cols else ('query', sq.this))
    return out


def _column_class(col, sources, by_table, schema=None, depth=0):
    """The storage class of a qualified column, followed to its table (by_table) or through
    a derived table or CTE to the item that defines it; None if not exact or not known.
    An alias bound in several scopes names several sources; a source without a column of
    that name cannot be the one meant and is skipped (a table of the schema, or a query
    whose select list lacks the name)."""
    if depth > 8 or not col.table:
        return None
    srcs = sources.get(col.table.lower())
    if not srcs:
        return None
    name, classes = col.name.lower(), set()
    schema = schema or {}
    for kind, x in srcs:
        if kind == 'table':
            cols = [c.lower() for c in schema.get(x, [])]
            if schema and x in schema and name not in cols:
                continue
            k = by_table.get((x, name))
        elif kind == 'query':
            if not _has_output(x, name):
                continue
            k = _item_class(x, name, sources, by_table, schema, depth + 1)
        else:
            k = None
        if k is None:
            return None
        classes.add(k)
    return _combine_classes(classes) if classes else None


def _has_output(q, name):
    while isinstance(q, (exp.Union, exp.Intersect, exp.Except)):
        q = q.this
    while isinstance(q, (exp.Paren, exp.Subquery)) and not q.args.get('alias'):
        q = q.this
    return isinstance(q, exp.Select) and any(e.alias_or_name.lower() == name for e in q.expressions)


def _item_class(q, name, sources, by_table, schema, depth):
    """The class of the output column `name` of a SELECT or compound: every arm must define
    it as a plain qualified column of one and the same class."""
    arms = []

    def flatten(n):
        if isinstance(n, (exp.Union, exp.Intersect, exp.Except)):
            flatten(n.this)
            flatten(n.expression)
        else:
            while isinstance(n, (exp.Paren, exp.Subquery)) and not n.args.get('alias'):
                n = n.this
            arms.append(n)
    flatten(q)
    if not all(isinstance(a, exp.Select) for a in arms):
        return None
    first = arms[0]
    pos = next((i for i, e in enumerate(first.expressions) if e.alias_or_name.lower() == name), None)
    if pos is None:
        return None
    classes = set()
    for a in arms:
        if pos >= len(a.expressions):
            return None
        body = _strip_parens(a.expressions[pos].this if isinstance(a.expressions[pos], exp.Alias)
                             else a.expressions[pos])
        k = _column_class(body, sources, by_table, schema, depth) if isinstance(body, exp.Column) else None
        if k is None:
            return None
        classes.add(k)
    return _combine_classes(classes)


def _combine_classes(classes):
    """The class of values drawn from columns of these classes, or None when two values
    could be equal without being identical (an integer and a real)."""
    kinds = set()
    for k in classes:
        if k is None:
            return None
        kinds |= set(k.split('+')) - {'null'}
    if {'integer', 'real'} <= kinds:
        return None
    return '+'.join(sorted(kinds)) or 'null'


def _def_class(d, cls):
    d = _strip_parens(d) if d is not None else None
    return cls.get(d.name.lower()) if isinstance(d, exp.Column) else None


def _proper_defs(name, defs):
    """The definitions of a name, without those that only refer to the name itself
    (`d.x` as an item, `x.c3 AS c3`): they say nothing about its values."""
    return [d for d in defs.get(name, [])
            if not (d is not None and isinstance(_strip_parens(d), exp.Column) and _strip_parens(d).name.lower() == name)]
