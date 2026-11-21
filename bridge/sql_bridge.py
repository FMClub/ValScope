"""Bridge between SQL text and the verified mutators (cli/valscope_mutate).

    SQL text --sqlglot--> algebra term --valscope_mutate--> mutant terms --> SQL text

The mutators never look inside scalar expressions, table references or predicates
they do not analyse; they only copy them.  The bridge replaces each of them by a
numbered atom and puts the original SQL text back when printing.

How a query is encoded, and why the theorems apply to it (the theorems hold in every
world [db_t] that satisfies the laws of Semantics.v, so it suffices that SOME lawful
world gives the term the meaning of the SQL text):

- a stored table or an opaque derived table is (T i 1): in the world, each real row is
  one value that stands for the whole tuple, and its equivalence [veq] is the DBMS's
  equality of rows (with the column collations);
- a scalar expression that is not analysed is (EAtom n): its value is a function of the
  current row context (the concatenation of the rows of the joined inputs and of the
  outer queries), which is what [eatoms] provides;
- a predicate that is not analysed is (Atom n), a three-valued function of the context;
- a derived table or a CTE reference whose body is in the fragment is (Named i q):
  its rows are the rows of q, so it can be mutated inside;
- an arm of a set operation that is outside the fragment (aggregation, LIMIT, ...) is
  (QAtom i 1), an opaque query;
- LEFT JOIN pads with as many NULLs as the right input has columns in the encoding
  (1 for a table, the number of select items for a Named query);
- LIKE and REGEXP with a literal pattern of the analysed fragment are (Like e hex) and
  (Regex e hex); the character comparison (case-insensitivity) is the world's [ceq].

The laws demand that every operation respects the collation equivalence.  Where the
DBMS has operations that distinguish equivalent values (LENGTH('a ') vs LENGTH('a')
under a PAD SPACE collation, or 'a ' LIKE 'a'), SQL itself does not determine which
representative DISTINCT or UNION keep, and the result is not determined by the query;
the checker treats such differences explicitly (see checker.py).

This file is NOT verified.  Together with sqlglot it is the trusted base: the
theorems are about the algebra term, and the bridge is responsible for the term
meaning the same as the SQL text.  It is built to fail closed:

- every occurrence of an expression, predicate or table gets its own atom, so two
  occurrences with the same text but different meaning (alias shadowing) are never
  identified;
- anything outside the modelled fragment raises Unsupported; nothing is approximated;
- queries that use non-deterministic functions or user variables are rejected;
- `reprint` gives the SQL of the unmutated term, so a caller can check on the
  database that the translation preserved the query (see run_on_db.py).
"""
import collections
import os
import re
import subprocess

import sqlglot
from sqlglot import exp
from sqlglot.dialects.mysql import MySQL

# sqlglot prints `a REGEXP b` as REGEXP_LIKE(a, b), a MySQL 8 function that MariaDB
# does not have; print the operator, which both accept.
MySQL.Generator.TRANSFORMS[exp.RegexpLike] = lambda self, e: '(%s REGEXP %s)' % (
    self.sql(e, 'this'), self.sql(e, 'expression'))

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CLI = os.path.join(HERE, '..', 'cli', 'valscope_mutate')


class Unsupported(Exception):
    """The query (or a mutant) is outside the fragment the bridge can translate."""


CMP = {exp.EQ: 'eq', exp.NEQ: 'ne', exp.LT: 'lt', exp.LTE: 'le', exp.GT: 'gt', exp.GTE: 'ge'}
CMP_SQL = {'eq': '=', 'ne': '<>', 'lt': '<', 'le': '<=', 'gt': '>', 'ge': '>='}
SET_SQL = {'UnionAll': 'UNION ALL', 'Union': 'UNION', 'Intersect': 'INTERSECT', 'Except': 'EXCEPT',
           'IntersectAll': 'INTERSECT ALL', 'ExceptAll': 'EXCEPT ALL'}

# Scalar functions that are non-decreasing on all reals and never turn a non-NULL
# number into NULL.  LOG, LN and SQRT are excluded on purpose: they return NULL
# outside their domain, which would change NULL-ness.
MONO_FUNCS = [(getattr(exp, cls), name) for cls, name in
              (('Exp', 'EXP'), ('Floor', 'FLOOR'), ('Ceil', 'CEIL'), ('Round', 'ROUND'),
               ('Atan', 'ATAN'), ('Sign', 'SIGN')) if hasattr(exp, cls)]   # (Atan: sqlglot >= 27)

# In MySQL / MariaDB, VARIANCE, STD and STDDEV are the POPULATION aggregates.  Older sqlglot
# releases parse VARIANCE as the sample variance (the node of VAR_SAMP), so the names are
# rewritten before parsing to the unambiguous VAR_POP / STDDEV_POP (same meaning in MySQL).
MYSQL_POPULATION_ALIASES = {'VARIANCE': 'VAR_POP', 'STD': 'STDDEV_POP', 'STDDEV': 'STDDEV_POP'}


def _mysql_population_names(sql):
    try:
        tokens = sqlglot.tokenize(sql, read='mysql')
    except Exception:
        return sql
    out, last = [], 0
    for tok, nxt in zip(tokens, tokens[1:]):
        name = tok.text.upper()
        if name in MYSQL_POPULATION_ALIASES and nxt.text == '(' and sql[tok.start:tok.end + 1].upper() == name:
            out.append(sql[last:tok.start])
            out.append(MYSQL_POPULATION_ALIASES[name])
            last = tok.end + 1
    out.append(sql[last:])
    return ''.join(out)

# Functions whose value changes between two executions of the same query.
NONDETERMINISTIC = {
    'RAND', 'UUID', 'UUID_SHORT', 'NOW', 'SYSDATE', 'CURDATE', 'CURTIME', 'CURRENT_DATE',
    'CURRENT_TIME', 'CURRENT_TIMESTAMP', 'LOCALTIME', 'LOCALTIMESTAMP', 'UNIX_TIMESTAMP',
    'UTC_DATE', 'UTC_TIME', 'UTC_TIMESTAMP', 'CONNECTION_ID', 'LAST_INSERT_ID', 'FOUND_ROWS',
    'ROW_COUNT', 'SLEEP', 'BENCHMARK', 'GET_LOCK', 'RELEASE_LOCK', 'RANDOM_BYTES', 'USER',
    'CURRENT_USER', 'SESSION_USER', 'SYSTEM_USER', 'DATABASE', 'SCHEMA', 'VERSION',
    # SQLite
    'RANDOM', 'RANDOMBLOB', 'CHANGES', 'TOTAL_CHANGES', 'LAST_INSERT_ROWID',
}
NONDETERMINISTIC_NODES = (exp.Rand, exp.Uuid, exp.CurrentDate, exp.CurrentTime,
                          exp.CurrentTimestamp, exp.CurrentUser, exp.Parameter,
                          exp.SessionParameter, exp.Placeholder)


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


# Aggregates whose result depends on the order of the rows they read.
ORDER_DEPENDENT_AGGS = {'GROUP_CONCAT', 'STRING_AGG', 'LISTAGG', 'ARRAY_AGG', 'JSON_ARRAYAGG',
                        'JSON_OBJECTAGG', 'JSON_GROUP_ARRAY', 'JSON_GROUP_OBJECT', 'GROUPCONCAT',
                        'ARRAYAGG', 'JSONARRAYAGG', 'JSONOBJECTAGG', 'ANY_VALUE', 'ANYVALUE',
                        'FIRST_VALUE', 'LAST_VALUE'}


def _order_dependent_undetermined(node):
    """For an order-dependent aggregate: None if its ORDER BY determines the order
    (every aggregated expression is an ORDER BY key, so tied rows give the same value);
    otherwise the reason."""
    name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).upper().replace(' ', '')
    if name not in ORDER_DEPENDENT_AGGS:
        return None
    if name in ('ANY_VALUE', 'ANYVALUE'):
        return 'ANY_VALUE returns any row'
    arg = node.args.get('this')
    if isinstance(arg, exp.Order):
        keys = {_strip_parens(o.this).sql() for o in arg.expressions}
        values = [arg.this] if arg.this is not None else []
        if len(values) == 1 and isinstance(values[0], exp.Distinct):
            values = list(values[0].expressions)      # GROUP_CONCAT(DISTINCT x ORDER BY x)
        if values and all(_strip_parens(v).sql() in keys for v in values):
            return None
        return '%s with an ORDER BY that does not order its values' % name
    return '%s without ORDER BY: the order of the values is not determined' % name


def _bare_columns(select):
    """Columns of a grouped (or aggregated) SELECT, in the select list or in HAVING,
    that are neither grouping keys nor inside an aggregate: their value is taken from any
    row of the group.  A grouping key can name a select alias or a position (GROUP BY 1)."""
    group = select.args.get('group')
    items = list(select.expressions)
    having = select.args.get('having')
    def has_agg(n):
        # an aggregate of this SELECT, not one inside a subquery or a window
        if isinstance(n, (exp.Select, exp.Subquery, exp.Window)):
            return False
        return isinstance(n, exp.AggFunc) or any(has_agg(c) for c in n.iter_expressions())
    has_agg = any(has_agg(n) for n in items) or (having is not None and has_agg(having.this))
    if group is None and not has_agg:
        return []
    aliases = {i.alias.lower(): i.this for i in items if isinstance(i, exp.Alias)}
    keys = set()
    for k in (group.expressions if group else []):
        k = _strip_parens(k)
        if isinstance(k, exp.Literal) and not k.is_string and k.this.isdigit() and 0 < int(k.this) <= len(items):
            target = items[int(k.this) - 1]
            k = target.this if isinstance(target, exp.Alias) else target
        elif isinstance(k, exp.Column) and not k.table and k.name.lower() in aliases:
            keys.add(k.sql().lower())
            k = aliases[k.name.lower()]
        keys.add(_strip_parens(k).sql().lower())
    bare = []
    for item in items + ([having.this] if having is not None else []):
        body = item.this if isinstance(item, exp.Alias) else item
        if _strip_parens(body).sql().lower() in keys:
            continue

        def walk(n):
            if isinstance(n, exp.Window):
                # a window of a grouped query is evaluated per group: the arguments of its
                # function (SUM(SUM(x)) OVER ...: the inner SUM is an aggregate) and its
                # PARTITION BY / ORDER BY read the group, so a column there must be a key
                for c in n.this.iter_expressions():
                    walk(c)
                for e in n.args.get('partition_by') or []:
                    walk(e)
                if n.args.get('order') is not None:
                    walk(n.args['order'])
                return
            if isinstance(n, (exp.AggFunc, exp.Select, exp.Subquery)):
                return
            if _strip_parens(n).sql().lower() in keys:
                return          # a grouping key (also inside an expression: LN(c) + 3)
            if isinstance(n, exp.Column) and not isinstance(n.this, exp.Star):
                if _strip_parens(n).sql().lower() not in keys:
                    bare.append(n.sql())
                return
            for c in n.iter_expressions():
                walk(c)
        walk(body)
    return bare


def _same_under(mask, t, u):
    """VDistinct.v, same_under: the terms t and u are equal in the parts under DISTINCT."""
    if mask == ('one', True):
        return t == u
    if mask[0] == 'union' and t[0] == 'VUnionAll' and u[0] == 'VUnionAll':
        return _same_under(mask[1], t[1], u[1]) and _same_under(mask[2], t[2], u[2])
    return True


def _mask_any(mask):
    """Is some part of the value query under DISTINCT?"""
    return mask[1] is True if mask[0] == 'one' else _mask_any(mask[1]) or _mask_any(mask[2])


# window functions whose value is the same for identical rows (peers): no row numbers, no
# offsets into the partition, the default frame (RANGE ... CURRENT ROW includes the peers)
DETERMINED_WINDOWS = {'RANK', 'DENSE_RANK', 'PERCENT_RANK', 'CUME_DIST', 'COUNT', 'SUM', 'MIN', 'MAX', 'AVG'}


def _window_undetermined(w):
    f = w.this
    if not isinstance(f, (exp.Func, exp.Anonymous)) or w.args.get('alias'):
        # WINDOW w AS (...), OVER w, or SUM(...) FILTER (...) OVER (...): the frame is not
        # in this node
        return 'a named window or FILTER (not modelled)'
    name = (f.name if isinstance(f, exp.Anonymous) else f.sql_name()).upper()
    if name not in DETERMINED_WINDOWS:
        return 'window function %s (its value can differ between identical rows)' % name
    spec = w.args.get('spec')
    if spec is not None and str(spec.args.get('kind') or '').upper() == 'ROWS':
        return 'window frame in ROWS (it can differ between identical rows)'
    if any(isinstance(a, exp.Distinct) for a in f.iter_expressions()):
        return 'DISTINCT in a window function'
    return None


def _check_deterministic(tree):
    for node in tree.walk():
        if isinstance(node, NONDETERMINISTIC_NODES):
            raise Unsupported('non-deterministic: %s' % type(node).__name__)
        if isinstance(node, (exp.Anonymous, exp.Func)):
            name = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).upper()
            if name in NONDETERMINISTIC:
                raise Unsupported('non-deterministic function %s' % name)
            # date('now'), datetime('now', ...): the current time (SQLite)
            if any(isinstance(a, exp.Literal) and a.is_string and a.this.strip().lower() == 'now'
                   for a in node.iter_expressions()):
                raise Unsupported("non-deterministic: %s('now')" % name)
        if isinstance(node, exp.Window):
            # anywhere in the query (a derived table, a subquery): ROW_NUMBER, LAG,
            # FIRST_VALUE, a ROWS frame, ... can give different values to tied rows in two plans
            why = _window_undetermined(node)
            if why:
                raise Unsupported('non-deterministic: ' + why)
        if isinstance(node, (exp.Anonymous, exp.AggFunc)) and not isinstance(node.parent, exp.Window):
            why = _order_dependent_undetermined(node)
            if why:
                raise Unsupported('non-deterministic: ' + why)
        if isinstance(node, exp.Select):
            bare = _bare_columns(node)
            if bare:
                # the value of a column that is neither grouped nor aggregated comes from
                # any row of its group (MySQL without ONLY_FULL_GROUP_BY, SQLite)
                aliases = {i.alias.lower() for i in node.expressions if isinstance(i, exp.Alias)}
                if '.' not in bare[0] and bare[0].strip('`"').lower() in aliases:
                    raise Unsupported('HAVING refers to the select alias %s (not modelled)' % bare[0])
                raise Unsupported('non-deterministic: %s is neither grouped nor aggregated' % bare[0])
        if isinstance(node, (exp.Select, exp.Union, exp.Intersect, exp.Except)) and node is not tree \
                and (node.args.get('limit') or node.args.get('offset')):
            why = _limit_undetermined(node)
            if why:
                raise Unsupported('LIMIT in a subquery: %s' % why)


def _limit_undetermined(node):
    """None if the rows a LIMIT / OFFSET keeps are determined by the query; otherwise
    the reason.  Among rows that tie under ORDER BY the DBMS keeps any, so the result is
    determined only when tied rows are identical in every output column: every output
    column must be an ORDER BY key.  A single-row input (an aggregate without GROUP BY)
    is also determined."""
    order = node.args.get('order')
    first = node
    while isinstance(first, (exp.Union, exp.Intersect, exp.Except)):
        first = first.this
        while isinstance(first, exp.Subquery):
            first = first.this
    if not isinstance(first, exp.Select):
        return 'output columns unknown'
    if isinstance(node, exp.Select) and not node.args.get('group') and \
            any(item.find(exp.AggFunc) for item in node.expressions) and \
            not any(item.find(exp.Window) for item in node.expressions):
        return None                          # exactly one row
    if order is None:
        return 'no ORDER BY'
    if any(isinstance(i, exp.Star) or (isinstance(i, exp.Column) and isinstance(i.this, exp.Star))
           for i in first.expressions):
        return 'SELECT * with ORDER BY (columns unknown)'
    keys = set()
    for o in order.expressions:
        k = o.this
        if isinstance(k, exp.Literal) and not k.is_string:       # ORDER BY 2
            idx = int(k.this) - 1
            if 0 <= idx < len(first.expressions):
                keys.add(('pos', idx))
        else:
            keys.add(('expr', _strip_parens(k).sql()))
            if isinstance(k, exp.Column) and not k.table:
                keys.add(('alias', k.name.lower()))
    for i, item in enumerate(first.expressions):
        body = item.this if isinstance(item, exp.Alias) else item
        alias = item.alias.lower() if isinstance(item, exp.Alias) and item.alias else None
        if ('pos', i) in keys or ('expr', _strip_parens(body).sql()) in keys or \
                (alias and ('alias', alias) in keys) or \
                (isinstance(body, exp.Column) and ('alias', body.name.lower()) in keys and not body.table):
            continue
        return 'ORDER BY does not cover the output column %s, so ties are kept arbitrarily' % item.sql()[:40]
    return None


def _strip_parens(node):
    """A copy of the expression without parentheses (they do not change its meaning
    in a syntax tree)."""
    return node.copy().transform(lambda n: n.this if isinstance(n, exp.Paren) else n)


class Translation:
    """One SQL query translated to an algebra term, with its atom tables.

    kind is 'set' (set-semantic term, mutate with direction Up / Down) or
    'value' (value query, one select item is mutated)."""

    def __init__(self, sql, dialect='mysql', kind='set', schema=None, exact_columns=None):
        self.dialect = dialect
        # table name (lower case) -> column names; optional, used to print DISTINCT around
        # a join (see _join_columns)
        self.schema = {k.lower(): v for k, v in (schema or {}).items()}
        self.kind = kind
        self.tables, self.aliases, self.exprs, self.preds = [], [], [], []
        self.item_alias, self.mono_ids = [], {}
        self.item_alias_arms = []           # the column aliases of each arm of a value query
        self.named, self.qatoms, self.ctes, self.opaque_items = [], [], {}, []
        self._law_cache = {}
        if dialect == 'mysql':
            sql = _mysql_population_names(sql)
        tree = sqlglot.parse_one(sql, read=dialect)
        _check_deterministic(tree)
        if tree.args.get('order') is not None and not (tree.args.get('limit') or tree.args.get('offset')):
            # ORDER BY of the whole query, without LIMIT: the bag of rows is the same without
            # it (it may name a select alias, which a value mutant changes)
            tree = tree.copy()
            tree.set('order', None)
        self.exact_columns = exact_columns
        self._exact_names = _exact_names(tree, exact_columns, self.schema)
        self._sources = _alias_sources(tree)
        tree = self._take_ctes(tree)
        # a value query under DISTINCT, or a UNION of value queries (VDistinct.v): the
        # mutants are those of the query without it, and the check is a cover
        self.value_distinct, self.value_cover, self.value_mask = False, False, ('one', False)
        self.cover_by_text = {}             # value mutant SQL -> is its check a cover?
        self.term = self._query(tree) if kind == 'set' else self._value_top(tree, top=True)
        why = outside_collation_law(self, self.term)
        if why:
            raise Unsupported('outside the model: ' + why)

    def cover_for(self, mutant_sql):
        """Is the value mutant checked by a cover (VDistinct.v) rather than a one-to-one
        correspondence?  Only when the mutation lies in a part under DISTINCT."""
        return self.cover_by_text.get(mutant_sql, self.value_cover)

    # ------------------------------------------------------------ SQL -> term
    def _text(self, node):
        return node.sql(dialect=self.dialect)

    def _expr(self, node):
        # one atom per occurrence: never identify two occurrences by their text
        self.exprs.append(self._text(node))
        return '(EAtom %d)' % (len(self.exprs) - 1)

    def _take_ctes(self, tree):
        """Non-recursive CTEs are inlined: each reference becomes a derived table."""
        w = tree.args.get('with_') or tree.args.get('with')
        if w is None:
            return tree
        if w.args.get('recursive'):
            raise Unsupported('recursive CTE')
        tree = tree.copy()
        tree.set('with_' if 'with_' in tree.args else 'with', None)
        for sub in tree.find_all(exp.Select):
            if sub.args.get('with_') or sub.args.get('with'):
                raise Unsupported('nested WITH')

        def inline(node):
            # every reference to a CTE, also inside atoms that are kept as text,
            # becomes a derived table with the CTE's body
            if isinstance(node, exp.Table) and not node.args.get('db') and node.name.lower() in self.ctes:
                alias = node.alias_or_name
                return exp.Subquery(this=self.ctes[node.name.lower()].copy(),
                                    alias=exp.TableAlias(this=exp.to_identifier(alias)))
            return node
        for cte in w.expressions:
            if cte.args.get('alias') is not None and cte.args['alias'].columns:
                raise Unsupported('CTE with a column list')
            # a CTE may refer to the CTEs before it
            self.ctes[cte.alias_or_name.lower()] = cte.this.copy().transform(inline)
        return tree.transform(inline)

    def _snapshot(self):
        return [len(x) for x in (self.tables, self.aliases, self.exprs, self.preds,
                                 self.named, self.qatoms)]

    def _restore(self, snap):
        for lst, n in zip((self.tables, self.aliases, self.exprs, self.preds,
                           self.named, self.qatoms), snap):
            del lst[n:]

    def _opaque_query(self, node):
        """An opaque query (QAtom) for a SELECT the model does not analyse."""
        inner = self._unwrap(node)
        if isinstance(inner, (exp.Union, exp.Intersect, exp.Except)) or not isinstance(inner, exp.Select):
            raise Unsupported('opaque query that is not a single SELECT')
        if any(isinstance(n, exp.Window) for n in inner.walk()) or inner.find(exp.Star) is not None:
            raise Unsupported('opaque query with a window function or *')
        self.qatoms.append(self._text(inner))
        return '(QAtom %d 1)' % (len(self.qatoms) - 1)

    def _arm(self, node):
        """An operand of a set operation: translated if possible, else an opaque query."""
        snap = self._snapshot()
        try:
            return self._query(node)
        except Unsupported:
            self._restore(snap)
            return self._opaque_query(node)

    def _unwrap(self, node):
        while isinstance(node, (exp.Subquery, exp.Paren)):
            if isinstance(node, exp.Subquery) and node.alias:
                raise Unsupported('aliased subquery as a query')
            node = node.this
        return node

    def _query(self, node):
        node = self._unwrap(node)
        if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            for key in ('limit', 'offset', 'with_', 'with'):
                if node.args.get(key):
                    raise Unsupported('%s on a set operation' % key)
            distinct = node.args.get('distinct')
            if isinstance(node, exp.Union):
                tag = 'Union' if distinct else 'UnionAll'
            else:
                tag = 'Intersect' if isinstance(node, exp.Intersect) else 'Except'
                if not distinct:
                    tag += 'All'                # INTERSECT ALL / EXCEPT ALL (bag semantics)
            return '(%s %s %s)' % (tag, self._arm(node.this), self._arm(node.expression))
        if isinstance(node, exp.Select):
            return self._select(node)
        raise Unsupported(type(node).__name__)

    def _column_count(self, node):
        """Number of select items of the leftmost SELECT, or None with a star."""
        node = self._unwrap(node)
        while isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            node = self._unwrap(node.this)
        if isinstance(node, exp.Select) and self._star_only(node) and self._bare(node):
            src = node.args.get('from_') or node.args.get('from')
            if src is not None and isinstance(src.this, exp.Subquery):
                return self._column_count(src.this.this)       # SELECT * FROM (q): the columns of q
        if not isinstance(node, exp.Select) or any(item.find(exp.Star) is not None for item in node.expressions):
            return None
        return len(node.expressions)

    def _check_clauses(self, node, allowed=()):
        # (row locks, FOR UPDATE / LOCK IN SHARE MODE, do not change the result)
        for key in ('group', 'having', 'limit', 'offset', 'qualify', 'windows', 'with_', 'with',
                    'sample', 'pivots', 'laterals', 'distinct', 'into', 'hint', 'kind'):
            if key not in allowed and node.args.get(key):
                raise Unsupported(key)

    @staticmethod
    def _star_only(node):
        return len(node.expressions) == 1 and (
            isinstance(node.expressions[0], exp.Star) or
            (isinstance(node.expressions[0], exp.Column) and isinstance(node.expressions[0].this, exp.Star)))

    @staticmethod
    def _bare(node, allowed=()):
        """A SELECT with only a FROM item (and the clauses in `allowed`)."""
        return all(not node.args.get(k) for k in ('where', 'joins', 'group', 'having', 'limit', 'offset',
                                                   'qualify', 'windows', 'with_', 'with', 'laterals')
                   if k not in allowed)

    def _select(self, node):
        source = node.args.get('from_') or node.args.get('from')
        distinct = node.args.get('distinct')
        if source is not None and isinstance(source.this, exp.Subquery) and self._star_only(node) \
                and self._bare(node) and not (isinstance(distinct, exp.Distinct) and distinct.args.get('on')):
            # SELECT [DISTINCT] * FROM (q) AS a: the rows of q (the printer writes DISTINCT
            # around a set operation this way, and SQLite compound operands too)
            body = source.this.this
            snap = self._snapshot()
            try:
                inner = self._query(body)
            except Unsupported:
                self._restore(snap)
                inner = self._opaque_query(body)
            return '(Distinct %s)' % inner if distinct else inner
        group = node.args.get('group')
        if group is not None and self.schema and not node.args.get('having') and self._group_is_distinct(node):
            # SELECT [DISTINCT] items FROM j WHERE p GROUP BY <every column of j>: DISTINCT
            # around the join
            self._check_clauses(node, allowed=('group', 'distinct'))
            if isinstance(distinct, exp.Distinct) and distinct.args.get('on'):
                raise Unsupported('DISTINCT ON')
            term = self._source(node)
            items = ' '.join(self._expr(item) for item in node.expressions)
            term = '(Proj (%s) (Distinct %s))' % (items, term)
            return '(Distinct %s)' % term if distinct else term
        self._check_clauses(node, allowed=('distinct',))
        for item in node.expressions:
            # an aggregate or a window function depends on the whole input, not on the
            # row; a scalar subquery is an ordinary (correlated) expression of the row
            outside = [n for n in item.walk(prune=lambda n: isinstance(n, exp.Select))
                       if not isinstance(n, exp.Select)]
            if any(isinstance(n, (exp.AggFunc, exp.Window)) for n in outside):
                raise Unsupported('aggregate or window function in the select list')
        term = self._source(node)
        # ORDER BY does not change the bag of rows and is dropped
        items = ' '.join(self._expr(item) for item in node.expressions)
        term = '(Proj (%s) %s)' % (items, term)
        if node.args.get('distinct'):
            if isinstance(node.args['distinct'], exp.Distinct) and node.args['distinct'].args.get('on'):
                raise Unsupported('DISTINCT ON')
            term = '(Distinct %s)' % term
        return term

    def _group_is_distinct(self, node):
        """Does the GROUP BY list every column of the FROM tables (all base tables of the
        schema), with no aggregate or window in the select list?"""
        for item in node.expressions:
            # aggregates inside a scalar subquery are computed per row; only those of
            # this SELECT itself matter
            outside = [n for n in item.walk(prune=lambda n: isinstance(n, exp.Select))
                       if not isinstance(n, exp.Select)]
            if any(isinstance(n, (exp.AggFunc, exp.Window)) for n in outside):
                return False
        group = node.args['group']
        if any(group.args.get(k) for k in ('rollup', 'cube', 'grouping_sets', 'totals', 'all')):
            return False
        source = node.args.get('from_') or node.args.get('from')
        items = [source.this] + [j.this for j in node.args.get('joins') or []]
        cols = []
        for item in items:
            if not isinstance(item, exp.Table) or not isinstance(item.this, exp.Identifier) \
                    or item.name.lower() not in self.schema:
                return False
            cols += ['%s.%s' % (item.alias_or_name, c) for c in self.schema[item.name.lower()]]
        keys = [_strip_parens(k).sql(dialect=self.dialect).lower() for k in group.expressions]
        return len(node.args.get('joins') or []) > 0 and sorted(keys) == sorted(c.lower() for c in cols)

    def _source(self, node):
        """FROM, JOINs and WHERE of a SELECT."""
        source = node.args.get('from_') or node.args.get('from')
        if source is None:
            raise Unsupported('SELECT without FROM')
        term, first_width = self._table(source.this)
        for k, join in enumerate(node.args.get('joins') or []):
            if join.args.get('using') or join.args.get('method'):
                raise Unsupported('USING / NATURAL join')
            side = str(join.args.get('side') or '').upper()
            kind = str(join.args.get('kind') or '').upper()
            right, width = self._table(join.this)
            on = self._pred(join.args['on']) if join.args.get('on') is not None else 'True'
            if side == 'LEFT':
                term = '(Left %d %s %s %s)' % (width, on, term, right)
            elif side == 'RIGHT' and kind in ('', 'OUTER'):
                # a RIGHT JOIN b ON p returns the rows of b LEFT JOIN a ON p, with the columns
                # in the other order: fine when the select list names its columns, and when
                # a is a single FROM item (later joins would need nested parentheses)
                if k > 0:
                    raise Unsupported('RIGHT JOIN after another join')
                if any(isinstance(i, exp.Star) or (isinstance(i, exp.Column) and isinstance(i.this, exp.Star))
                       for i in node.expressions):
                    raise Unsupported('RIGHT JOIN with SELECT *')
                term = '(Left %d %s %s %s)' % (first_width, on, right, term)
            elif side == '' and kind in ('', 'INNER', 'CROSS'):
                term = '(Inner %s %s %s)' % (on, term, right)
            else:
                raise Unsupported('%s %s join' % (side, kind))
        if node.args.get('where') is not None:
            term = '(Where %s %s)' % (self._pred(node.args['where'].this), term)
        return term

    def _table(self, node):
        """A FROM item: (term, number of columns in the encoding)."""
        body, alias = None, None
        if isinstance(node, exp.Subquery) and node.alias:
            body, alias = node.this, node.alias
        if body is not None:
            if isinstance(node, exp.Subquery) and node.args['alias'].columns:
                raise Unsupported('derived table with a column list')
            src = body.args.get('from_') or body.args.get('from') if isinstance(body, exp.Select) else None
            if src is not None and self._star_only(body) and self._bare(body, allowed=('where',)) \
                    and src.this.alias_or_name == alias \
                    and not (isinstance(body.args.get('distinct'), exp.Distinct)
                             and body.args['distinct'].args.get('on')):
                # (SELECT [DISTINCT] * FROM X AS a [WHERE p]) AS a: the rows of X, filtered
                # and de-duplicated, under the same name (the printer writes DISTINCT and
                # WHERE in a FROM position this way)
                term, width = self._table(src.this)
                if body.args.get('where') is not None:
                    term = '(Where %s %s)' % (self._pred(body.args['where'].this), term)
                if body.args.get('distinct'):
                    term = '(Distinct %s)' % term
                return term, width
            width = self._column_count(body)
            if width is not None:
                snap = self._snapshot()
                try:
                    inner = self._query(body)
                    self.named.append(alias)
                    return '(Named %d %s)' % (len(self.named) - 1, inner), width
                except Unsupported:
                    self._restore(snap)
            # kept as an opaque table: it is not mutated inside
            self.tables.append(self._text(node))
            self.aliases.append(alias)
            return '(T %d 1)' % (len(self.tables) - 1), 1
        if isinstance(node, exp.Table):
            if node.args.get('joins') or node.args.get('laterals'):
                raise Unsupported('nested join')
            if not isinstance(node.this, exp.Identifier) and node.this.find(exp.Column) is not None:
                # json_each(t.c): a table that depends on another FROM item (a lateral
                # join); a table of the model does not depend on the row context
                raise Unsupported('table function with column arguments')
            self.tables.append(self._text(node))
            self.aliases.append(node.alias_or_name)
            return '(T %d 1)' % (len(self.tables) - 1), 1
        raise Unsupported('FROM item %s' % type(node).__name__)

    def _pattern(self, node):
        """The text of a string-literal pattern, or None."""
        if isinstance(node, exp.Literal) and node.is_string:
            return node.this
        return None

    def _pred(self, node):
        if isinstance(node, exp.Paren):
            return self._pred(node.this)
        if node.args.get('negate'):
            # sqlglot writes `x NOT LIKE p`, `x NOT IN (...)`, ... as the node with negate=True
            positive = node.copy()
            positive.set('negate', None)
            return '(Not %s)' % self._pred(positive)
        if isinstance(node, exp.And):
            return '(And %s %s)' % (self._pred(node.this), self._pred(node.expression))
        if isinstance(node, exp.Or):
            return '(Or %s %s)' % (self._pred(node.this), self._pred(node.expression))
        if isinstance(node, exp.Not):
            return '(Not %s)' % self._pred(node.this)
        if isinstance(node, exp.Boolean):
            return 'True' if node.this else 'False'
        if isinstance(node, exp.EQ) and all(isinstance(x, exp.Literal) and not x.is_string
                                            for x in (node.this, node.expression)) \
                and node.this.this == '1' and node.expression.this in ('0', '1'):
            # the printer writes TRUE as 1 = 1 and FALSE as 1 = 0
            return 'True' if node.expression.this == '1' else 'False'
        if type(node) in CMP and node.this.find(exp.Select) is None \
                and node.expression.find(exp.Select) is None:
            return '(Cmp %s %s %s)' % (CMP[type(node)], self._expr(node.this), self._expr(node.expression))
        if isinstance(node, exp.Is) and isinstance(node.expression, exp.Null) \
                and node.this.find(exp.Select) is None:
            return '(IsNull %s)' % self._expr(node.this)
        if isinstance(node, exp.Like) and node.this.find(exp.Select) is None:
            pat = self._pattern(node.expression)
            # a backslash is an escape character in MySQL / MariaDB patterns
            if pat is not None and '\\' not in pat and pat.isprintable() and pat.isascii():
                return '(Like %s%s)' % (self._expr(node.this), ' ' + pat.encode().hex() if pat else '')
        if isinstance(node, exp.RegexpLike) and node.this.find(exp.Select) is None \
                and not node.args.get('flag'):
            pat = self._pattern(node.expression)
            if pat is not None and _regex_in_fragment(pat):
                return '(Regex %s%s)' % (self._expr(node.this), ' ' + pat.encode().hex() if pat else '')
        if isinstance(node, exp.Exists) and isinstance(node.this, exp.Select):
            snap = self._snapshot()
            try:
                return '(Exists %s)' % self._query(node.this)
            except Unsupported:
                # roll back the atoms of the failed attempt and keep it opaque
                self._restore(snap)
        if isinstance(node, exp.In) and node.args.get('query') is not None \
                and isinstance(node.this, exp.Tuple) and node.this.find(exp.Select) is None:
            # (e1, ..., en) IN (subquery): row comparison (Semantics.int3)
            snap = self._snapshot()
            try:
                sub = self._unwrap(node.args['query'])
                if self._column_count(sub) != len(node.this.expressions):
                    raise Unsupported('row IN with a different number of columns')
                left = ' '.join(self._expr(e) for e in node.this.expressions)
                return '(InT (%s) %s)' % (left, self._query(sub))
            except Unsupported:
                self._restore(snap)
        if isinstance(node, exp.In) and node.args.get('query') is not None \
                and not isinstance(node.this, exp.Tuple) and node.this.find(exp.Select) is None:
            snap = self._snapshot()
            try:
                sub = self._unwrap(node.args['query'])
                if self._column_count(sub) != 1:
                    raise Unsupported('IN subquery with several columns')
                left = self._expr(node.this)
                return '(In %s %s)' % (left, self._query(sub))
            except Unsupported:
                self._restore(snap)
        # anything else is an opaque predicate: it can only be replaced as a whole
        self.preds.append(self._text(node))
        return '(Atom %d)' % (len(self.preds) - 1)

    # ---------------------------------------------------- value queries
    def _value_top(self, node, top=False):
        """A value query, or a UNION ALL of value queries with the same number of columns
        (VUnion.v: one arm is mutated, the other arms' rows stay as they are).  SELECT
        DISTINCT, or a UNION (without ALL), is DISTINCT over the same term; it can be the
        whole query or any part of a UNION ALL (VDistinct.v: meval, a mask over the UNION
        ALL; Translation.value_mask).  Sets self.value_mask at the top."""
        if top and isinstance(self._unwrap(node), (exp.Intersect, exp.Except)):
            # INTERSECT / EXCEPT of value queries (VSet.v): set semantics, HAVING mutants only
            term = self._set_part(node)
            # the server compares rows exactly: an item that can round differently in two
            # plans (SUM / AVG / VAR / STDDEV of floats, a function, an opaque item) could
            # make a row enter or leave the result without a bug
            # (a function of one row is computed the same way in every plan; an aggregate
            # that adds floats is not)
            # A SUM or AVG of integers is exact: its argument reads only columns that hold
            # integers on this database and uses + - * % only.
            def rounding(t):
                if not isinstance(t, list) or not t:
                    return None
                if isinstance(t[0], str) and t[0] in ('AVar', 'AStd'):
                    return t[0]
                if isinstance(t[0], str) and t[0] in ('ASum', 'AAvg') and not self._integer_expr(t[1]):
                    return t[0]
                for x in t:
                    r = rounding(x)
                    if r:
                        return r
                return None
            tag = rounding(parse_sexp(term))
            if tag:
                raise Unsupported('%s in an operand of INTERSECT / EXCEPT (rounding)' % tag)
            for text in self.opaque_items:
                if re.search(r'\b(SUM|AVG|VAR\w*|VARIANCE|STD\w*)\s*\(', text, re.I):
                    raise Unsupported('an opaque sum in an operand of INTERSECT / EXCEPT (rounding)')
            self.value_mask, self.value_distinct, self.value_cover = ('set',), True, True
            return term
        term, mask = self._value_part(node)
        if top:
            self.value_mask = mask
            self.value_distinct = mask == ('one', True)          # the whole result
            self.value_cover = _mask_any(mask)                   # a cover check, not Forall2
        return term

    def _integer_expr(self, e):
        """Is the expression term e integer arithmetic over columns that hold only integers
        (or NULL) on the database under test?"""
        by_table = getattr(self.exact_columns, 'by_table', None) or {}
        try:
            tree = sqlglot.parse_one(self._e_sql(e), read=self.dialect)
        except Exception:
            return False
        for n in tree.walk():
            if isinstance(n, exp.Column):
                if _column_class(n, self._sources, by_table, self.schema) != 'integer':
                    return False
            elif isinstance(n, exp.Literal):
                if not n.is_int:
                    return False
            elif not isinstance(n, (exp.Add, exp.Sub, exp.Mul, exp.Mod, exp.Neg, exp.Paren, exp.Identifier,
                                    exp.TableAlias)):
                return False
        return True

    def _set_part(self, node):
        node = self._unwrap(node)
        if isinstance(node, (exp.Intersect, exp.Except)):
            if not node.args.get('distinct'):
                raise Unsupported('%s ALL of value queries' % type(node).__name__.upper())
            for key in ('limit', 'offset', 'with_', 'with', 'order'):
                if node.args.get(key):
                    raise Unsupported('%s on an INTERSECT / EXCEPT of value queries' % key)
            return '(%s %s %s)' % ('SInter' if isinstance(node, exp.Intersect) else 'SExcept',
                                   self._set_part(node.this), self._set_part(node.expression))
        # an operand: under set semantics a DISTINCT or UNION inside it does not matter, and
        # it is printed as the UNION ALL of its arms
        return self._value_part(node)[0]

    def _value_part(self, node):
        node = self._unwrap(node)
        if isinstance(node, exp.Union) and node.args.get('distinct'):
            arms = []

            def flatten(n):
                n = self._unwrap(n)
                if isinstance(n, exp.Union) and n.args.get('distinct'):
                    for key in ('limit', 'offset', 'with_', 'with', 'order'):
                        if n.args.get(key):
                            raise Unsupported('%s on a UNION of value queries' % key)
                    flatten(n.this)
                    flatten(n.expression)
                elif isinstance(n, exp.Select) and isinstance(n.args.get('distinct'), exp.Distinct) \
                        and not n.args['distinct'].args.get('on'):
                    # DISTINCT of an arm is redundant under UNION: dedup(dedup(a) ++ b) = dedup(a ++ b)
                    n = n.copy()
                    n.set('distinct', None)
                    arms.append(n)
                else:
                    arms.append(n)
            flatten(node)
            terms = [self._value_part(a)[0] for a in arms]       # under DISTINCT: inner masks do not matter
            out = terms[0]
            for t in terms[1:]:
                out = '(VUnionAll %s %s)' % (out, t)
            return out, ('one', True)
        if isinstance(node, exp.Select) and isinstance(node.args.get('distinct'), exp.Distinct) \
                and not node.args['distinct'].args.get('on'):
            node = node.copy()
            node.set('distinct', None)
            return self._value_query(node), ('one', True)
        if isinstance(node, exp.Union) and not node.args.get('distinct'):
            for key in ('limit', 'offset', 'with_', 'with'):
                if node.args.get(key):
                    raise Unsupported('%s on a UNION ALL of value queries' % key)
            (left, ml), (right, mr) = self._value_part(node.this), self._value_part(node.expression)
            mask = ('one', False) if ml == mr == ('one', False) else ('union', ml, mr)
            return '(VUnionAll %s %s)' % (left, right), mask
        return self._value_query(node), ('one', False)

    def _value_arms(self, tree):
        """The value queries of a (possibly UNION ALL) value term, left to right."""
        if tree[0] in ('VUnionAll', 'SInter', 'SExcept'):
            return self._value_arms(tree[1]) + self._value_arms(tree[2])
        return [tree]

    def _value_query(self, node):
        node = self._unwrap(node)
        if not isinstance(node, exp.Select):
            raise Unsupported('value mutation needs a plain SELECT')
        self._check_clauses(node, allowed=('group', 'having'))
        group = node.args.get('group')
        keys = []
        if group is not None:
            if any(group.args.get(k) for k in ('rollup', 'cube', 'grouping_sets', 'totals', 'all')):
                raise Unsupported('ROLLUP / CUBE / GROUPING SETS')
            keys = list(group.expressions)
        self._check_alias_references(node)
        key_texts = {_strip_parens(k).sql(dialect=self.dialect) for k in keys}
        def agg_outside_window(n):
            if isinstance(n, (exp.Window, exp.Select, exp.Subquery)):
                return False
            return isinstance(n, exp.AggFunc) or any(agg_outside_window(c) for c in n.iter_expressions())
        has_agg = any(agg_outside_window(item) for item in node.expressions)
        source = self._source(node)
        items, aliases = [], []
        self.item_alias_arms.append(aliases)
        for j, item in enumerate(node.expressions):
            body = item.this if isinstance(item, exp.Alias) else item
            if isinstance(body, exp.Star) or (isinstance(body, exp.Column) and isinstance(body.this, exp.Star)):
                raise Unsupported('* in a value query')
            self.item_alias.append(item.alias if isinstance(item, exp.Alias) and item.alias else 'c%d' % j)
            aliases.append(self.item_alias[-1])
            items.append(self._item(body, key_texts if (keys or has_agg) else None))
        # HAVING is an ordinary predicate; its operands (aggregate expressions) are atoms
        having = 'True'
        if node.args.get('having') is not None:
            if not (keys or has_agg):
                raise Unsupported('HAVING without aggregation')
            having = self._pred(node.args['having'].this)
        if keys:
            key_terms = ' '.join(self._expr(k) for k in keys)
            return '(VGroup (%s) (%s) %s %s)' % (key_terms, ' '.join(items), having, source)
        if has_agg:
            return '(VGlobal (%s) %s %s)' % (' '.join(items), having, source)
        return '(VProj (%s) %s)' % (' '.join(items), source)

    def _check_alias_references(self, node):
        """A value mutant changes a select item; if WHERE, GROUP BY, HAVING or ORDER BY
        refer to it through its alias, they would change with it, and the rows of the
        mutant would no longer correspond to the rows of the original."""
        aliases = set()
        for item in node.expressions:
            if isinstance(item, exp.Alias) and item.alias:
                body = item.this
                if not (isinstance(body, exp.Column) and body.name.lower() == item.alias.lower()):
                    aliases.add(item.alias.lower())
        for key in ('where', 'group', 'having', 'order'):
            clause = node.args.get(key)
            if clause is None:
                continue
            for col in clause.find_all(exp.Column):
                if not col.table and col.name.lower() in aliases:
                    raise Unsupported('%s refers to the select alias %s' % (key.upper(), col.name))

    def _agg_arg(self, node):
        arg = node.this
        if isinstance(arg, exp.Distinct) or arg is None:
            raise Unsupported('DISTINCT inside %s' % type(node).__name__)
        if arg.find(exp.Select) is not None or arg.find(exp.AggFunc) is not None:
            raise Unsupported('subquery or nested aggregate')
        return self._expr(arg)

    def _item(self, node, key_texts):
        """key_texts is None for a query without aggregation; otherwise the texts of
        the grouping keys (a non-aggregated expression must be one of them)."""
        if isinstance(node, exp.Paren):
            return self._item(node.this, key_texts)
        windows = [inner for inner in node.walk() if isinstance(inner, exp.Window)]
        if windows and not isinstance(node, (exp.Add, exp.Mul)):
            # (a sum or product is split first, so that a mutant `window + k` of the engine
            # parses back to its term; the window is then the opaque operand)
            # In a query without aggregation (each row its own group) a window function
            # whose value is the same for identical rows is, for the given database and
            # the unchanged input of the query, a function of the row: an opaque item
            # (Value.v: magg), copied and never mutated.  Value mutations change only select
            # items, so the original and the mutant see the same windows.  Not with
            # aggregation: a HAVING mutant changes the groups a window ranges over.
            # In a grouped query the window ranges over the groups that survive HAVING.
            # A value mutant keeps the keys, the HAVING predicate and the source of every
            # arm (Registry.v: tmutate_frame), so it sees the same groups and the window is
            # again an opaque item; a HAVING mutant changes the groups, so a query with a
            # window gets no HAVING mutants (mutate_value).
            self.has_window = True
            why = None
            for w in windows:
                why = why or _window_undetermined(w)
                # MariaDB / MySQL resolve an unqualified name in PARTITION BY / ORDER BY of a
                # window to a select alias first: the window would read a (mutated) item
                spec = w.args.get('partition_by') or []
                order = w.args.get('order')
                names = [c for e in list(spec) + ([order] if order is not None else [])
                         for c in e.find_all(exp.Column) if not c.table]
                if names:
                    why = why or 'unqualified column %s in a window (it can name a select alias)' % names[0].name
            if why:
                raise Unsupported(why)
            self.opaque_items.append(self._text(node))
            return '(AOpaque %d)' % (len(self.opaque_items) - 1)
        if isinstance(node, exp.Literal) and node.is_int:
            return '(AConst %s)' % node.this
        if isinstance(node, exp.Neg) and isinstance(node.this, exp.Literal) and node.this.is_int:
            return '(AConst -%s)' % node.this.this
        if isinstance(node, exp.Count):
            arg = node.this
            if isinstance(arg, exp.Star):
                return '(ACount (Int 1))'
            if isinstance(arg, exp.Distinct):
                if len(arg.expressions) != 1 or arg.expressions[0].find(exp.Select) is not None:
                    raise Unsupported('COUNT(DISTINCT a, b)')
                return '(ACountD %s)' % self._expr(arg.expressions[0])
            return '(ACount %s)' % self._agg_arg(node)
        simple = {exp.Sum: 'ASum', exp.Min: 'AMin', exp.Max: 'AMax', exp.Avg: 'AAvg',
                  exp.Variance: 'AVar', exp.StddevSamp: 'AStd'}
        if type(node) in simple and node.this is not None and not isinstance(node.this, exp.Distinct) \
                and node.this.find(exp.Select) is None and node.this.find(exp.AggFunc) is None:
            return '(%s %s)' % (simple[type(node)], self._agg_arg(node))
        if isinstance(node, exp.Add):
            return '(AAdd %s %s)' % (self._item(node.this, key_texts), self._item(node.expression, key_texts))
        if isinstance(node, exp.Mul):
            return '(AMul %s %s)' % (self._item(node.this, key_texts), self._item(node.expression, key_texts))
        for cls, name in MONO_FUNCS:
            if type(node) is cls and len([v for v in node.args.values() if v is not None]) == 1:
                fid = self.mono_ids.setdefault(name, len(self.mono_ids))
                return '(AMono %d %s)' % (fid, self._item(node.this, key_texts))
        if node.find(exp.AggFunc) is not None or (key_texts is not None and node.find(exp.Select) is not None):
            # a function of the group that is not analysed: copied, never mutated
            self.opaque_items.append(self._text(node))
            return '(AOpaque %d)' % (len(self.opaque_items) - 1)
        if key_texts is not None and _strip_parens(node).sql(dialect=self.dialect) not in key_texts:
            raise Unsupported('non-aggregated expression that is not a grouping key')
        return '(ACol %s)' % self._expr(node)

    # ------------------------------------------------------------ term -> SQL
    # ------------------------------------------------ DISTINCT around a join
    def _join_columns(self, j):
        """All columns of the joined base tables of j, qualified by their aliases, or None
        if a table is not a base table of the known schema."""
        if not isinstance(j, list) or not j:
            return None
        if j[0] == 'T':
            tree = _cached_parse(self._law_cache, self.tables[int(j[1])], self.dialect, 'table')
            if tree is None:
                return None
            node = (tree.args.get('from_') or tree.args.get('from')).this
            if not isinstance(node, exp.Table) or not isinstance(node.this, exp.Identifier):
                return None
            cols = self.schema.get(node.name.lower())
            return ['%s.%s' % (node.alias_or_name, c) for c in cols] if cols else None
        if j[0] == 'Inner':
            a, b = self._join_columns(j[2]), self._join_columns(j[3])
        elif j[0] == 'Left':
            a, b = self._join_columns(j[3]), self._join_columns(j[4])
        else:
            return None
        return a + b if a is not None and b is not None else None

    # ------------------------------------------------ lifting correlated filters
    def _qualifiers(self, x):
        """Table qualifiers used by the atoms of x, minus the aliases x defines itself."""
        used, defined = set(), set()

        def walk(t):
            if not isinstance(t, list) or not t:
                return
            if isinstance(t[0], list):
                for y in t:
                    walk(y)
                return
            tag = t[0]
            if tag in ('EAtom', 'Atom'):
                text = (self.exprs if tag == 'EAtom' else self.preds)[int(t[1])]
                tree = _cached_parse(self._law_cache, text, self.dialect)
                if tree is None:
                    used.add(None)
                    return
                inner = {n.alias_or_name for n in tree.find_all(exp.Table, exp.Subquery)}
                defined.update(inner)
                used.update(c.table for c in tree.find_all(exp.Column) if c.table)
            elif tag == 'T':
                defined.add(self.aliases[int(t[1])])
            elif tag == 'Named':
                defined.add(self.named[int(t[1])])
            for y in t[1:]:
                walk(y)
        walk(x)
        return used - defined

    def lift(self, t):
        """Distinct(Where p X), X a table, as the input of a projection or a filter, with p
        referring to tables outside X (a correlated subquery): rewritten to
        Where p (Distinct X), and merged with an enclosing filter.  Same rows modulo the
        collation (Approx.compat: p gives equal truth values on equivalent rows); SQL can
        print it, while a derived table cannot see the outer tables."""
        if not isinstance(t, list) or not t or isinstance(t[0], list):
            return [self.lift(y) for y in t] if isinstance(t, list) else t
        t = [t[0]] + [self.lift(y) for y in t[1:]]
        if t[0] == 'Where' and isinstance(t[2], list) and t[2][0] == 'Distinct':
            # a filter above DISTINCT around a join is moved below it (same rows modulo the
            # collation, by Approx.compat), so that it is printed as one WHERE ... GROUP BY
            inner = t[2][1]
            if isinstance(inner, list) and inner[0] == 'Where' and inner[2][0] in ('Inner', 'Left'):
                return ['Distinct', ['Where', ['And', inner[1], t[1]], inner[2]]]
            if isinstance(inner, list) and inner[0] in ('Inner', 'Left'):
                return ['Distinct', ['Where', t[1], inner]]
        if t[0] in ('Proj', 'Where'):
            x = t[2]
            if isinstance(x, list) and x[0] == 'Distinct' and isinstance(x[1], list) and x[1][0] == 'Where' \
                    and isinstance(x[1][2], list) and x[1][2][0] in ('T', 'Named'):
                p, inner = x[1][1], x[1][2]
                alias = (self.aliases if inner[0] == 'T' else self.named)[int(inner[1])]
                if self._qualifiers(p) - {alias}:
                    lifted = ['Where', p, ['Distinct', inner]]
                    if t[0] == 'Where':
                        return ['Where', ['And', t[1], p], ['Distinct', inner]]
                    return ['Proj', t[1], lifted]
        return t

    def to_sql(self, term):
        tree = parse_sexp(term) if isinstance(term, str) else term
        tree = self.lift(tree)
        if tree[0] in ('SInter', 'SExcept'):
            self._arm = 0
            return self._st_sql(tree)
        if tree[0] in ('VProj', 'VGroup', 'VGlobal', 'VUnionAll'):
            self._arm = 0
            return self._vt_sql(tree)
        return self._q_sql(tree)

    def _st_sql(self, t):
        """SQL of an INTERSECT / EXCEPT of value terms (VSet.v); an operand that is not one
        is a UNION ALL of value queries, printed without DISTINCT."""
        if t[0] not in ('SInter', 'SExcept'):
            return self._vt_sql(t, ('one', False))
        op = 'INTERSECT' if t[0] == 'SInter' else 'EXCEPT'
        left, right = self._st_sql(t[1]), self._st_sql(t[2])
        if self.dialect == 'sqlite':
            if t[2][0] in ('SInter', 'SExcept', 'VUnionAll'):
                raise Unsupported('SQLite: a compound right operand of %s' % op)
            return '%s %s %s' % (left, op, right)
        return '(%s) %s (%s)' % (left, op, right)

    def _vt_sql(self, t, mask=None):
        """SQL of a value term; `mask` (VDistinct.v: mask) says which parts are under DISTINCT."""
        mask = self.value_mask if mask is None else mask
        if mask[0] == 'union' and t[0] == 'VUnionAll':
            return self._compound_sql('UNION ALL', t, self._vt_sql(t[1], mask[1]), self._vt_sql(t[2], mask[2]))
        return self._arms_sql(t, mask == ('one', True))

    def _arms_sql(self, t, distinct):
        """SQL of a UNION ALL of arms; under DISTINCT, SELECT DISTINCT for one arm and UNION
        (DISTINCT over their UNION ALL) for several."""
        if t[0] != 'VUnionAll':
            sql = self._v_sql(t)
            if distinct:
                assert sql.startswith('SELECT ')
                sql = 'SELECT DISTINCT ' + sql[len('SELECT '):]
            return sql
        return self._compound_sql('UNION' if distinct else 'UNION ALL', t,
                                  self._arms_sql(t[1], False), self._arms_sql(t[2], False))

    def _compound_sql(self, op, t, left, right):
        if self.dialect == 'sqlite':
            # no parentheses around compound operands in SQLite; compounds are
            # left-associative, so a compound right operand becomes a derived table
            if t[2][0] == 'VUnionAll':
                right = 'SELECT * FROM (%s)' % right
            return '%s %s %s' % (left, op, right)
        return '(%s) %s (%s)' % (left, op, right)

    def type_probe(self):
        """For a value query: (sql, number_of_keys) of its first arm (see type_probes)."""
        return self.type_probes()[0]

    def type_probes(self):
        """For a value query: one (sql, number_of_keys) per arm.  The query returns no
        rows; its columns are the grouping keys followed by every row-level expression
        used in the select items, so a caller can inspect their types."""
        return [self._type_probe_arm(v) for v in self._value_arms(parse_sexp(self.term))]

    def _type_probe_arm(self, v):
        keys, items, _, source = self._v_parts(v)
        atoms = []

        def collect(t):
            if isinstance(t, list):
                if t and t[0] == 'EAtom':
                    atoms.append(t)
                else:
                    for x in t[1:]:
                        collect(x)
        for item in items:          # a list of items, not a tagged node
            collect(item)
        where = None
        if source[0] == 'Where':
            where, source = self._p_sql(source[1]), source[2]
        cols = [self._e_sql(k) for k in keys] + [self._e_sql(a) for a in atoms]
        # also the plain columns inside those expressions: `c % 2` is DOUBLE even
        # when c is a single-precision FLOAT
        seen = set()
        for atom in atoms:
            try:
                tree_ = sqlglot.parse_one(self.exprs[int(atom[1])], read=self.dialect)
            except Exception:
                continue
            for column in tree_.find_all(exp.Column):
                text = self._text(column)
                if text not in seen:
                    seen.add(text)
                    cols.append(text)
        if not cols:
            return None, 0
        sql = 'SELECT %s FROM %s' % (', '.join(cols), self._from_sql(source))
        return sql + (' WHERE ' + where if where else '') + ' LIMIT 0', len(keys)

    def numeric_probe(self):
        """SQLite only.  The value model computes with numbers, but an SQLite column can
        hold text in any row, and aggregates then follow SQLite's own rules (AVG converts
        text to a number, MAX orders text above every number).  This query counts the
        rows where an expression used in a select item is text or a blob; a value query
        is inside the model only when it returns 0.  For a UNION ALL, the counts of the
        arms are added."""
        probes = [p for p in (self._numeric_probe_arm(v) for v in self._value_arms(parse_sexp(self.term))) if p]
        if not probes:
            return None
        return probes[0] if len(probes) == 1 else 'SELECT ' + ' + '.join('(%s)' % p for p in probes)

    def _numeric_probe_arm(self, v):
        keys, items, _, source = self._v_parts(v)
        atoms = []

        def collect(t):
            if isinstance(t, list):
                if t and t[0] == 'EAtom':
                    atoms.append(self._e_sql(t))
                else:
                    for x in t[1:]:
                        collect(x)
        for node in list(items) + list(keys):     # lists of items / keys, not tagged nodes
            collect(node)
        if not atoms:
            return None
        where = None
        if source[0] == 'Where':
            where, source = self._p_sql(source[1]), source[2]
        bad = ' OR '.join("typeof(%s) IN ('text', 'blob')" % a for a in atoms)
        cond = '(%s)' % bad if where is None else '(%s) AND (%s)' % (where, bad)
        return 'SELECT COUNT(*) FROM %s WHERE %s' % (self._from_sql(source), cond)

    def reprint(self):
        """SQL of the unmutated term: the query the mutants are compared with."""
        return self.to_sql(self.term)

    @staticmethod
    def _atom_text(text):
        """An atom is put back into a context it was not written in (a mutant may
        multiply it, compare it, ...), so anything that is not a plain name or
        number is parenthesised."""
        plain = text.replace('.', '').replace('_', '').replace('`', '')
        return text if plain.isalnum() else '(%s)' % text

    def _e_sql(self, e):
        tag = e[0]
        if tag == 'EAtom':
            return self._atom_text(self.exprs[int(e[1])])
        if tag == 'Int':
            return e[1]
        if tag == 'Null':
            return 'NULL'
        if tag in ('Add', 'Mul'):
            return '(%s %s %s)' % (self._e_sql(e[1]), '+' if tag == 'Add' else '*', self._e_sql(e[2]))
        raise Unsupported('expression %s' % tag)

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
        if tag == 'In':
            return '%s IN (%s)' % (self._e_sql(p[1]), self._q_sql(p[2]))
        if tag == 'InT':
            return '(%s) IN (%s)' % (', '.join(self._e_sql(e) for e in p[1]), self._q_sql(p[2]))
        if tag == 'Atom':
            return '(%s)' % self.preds[int(p[1])]
        if tag in ('Like', 'Regex'):
            pat = bytes.fromhex(p[2]).decode() if len(p) > 2 else ''
            return '%s %s %s' % (self._e_sql(p[1]), 'LIKE' if tag == 'Like' else 'REGEXP', _quote(pat))
        raise Unsupported('predicate %s' % tag)

    def _single_table(self, f):
        """The only table atom below f, or None."""
        found = []

        def walk(t):
            if isinstance(t, list):
                if t and t[0] in ('T', 'Named'):
                    found.append((t[0], int(t[1])))
                    return
                elif t and t[0] in ('Exists', 'In', 'InT'):     # tables of subqueries do not count
                    return
                else:
                    for x in t[1:]:
                        walk(x)
        walk(f)
        return found[0] if len(found) == 1 else None

    def _from_sql(self, f, nested=False):
        tag = f[0]
        if tag == 'T':
            return self.tables[int(f[1])]
        if tag == 'Named':
            return '(%s) AS %s' % (self._q_sql(f[2]), self.named[int(f[1])])
        if tag in ('Inner', 'Left'):
            on, left, right = (f[1], f[2], f[3]) if tag == 'Inner' else (f[2], f[3], f[4])
            if tag == 'Inner' and on == 'True':
                # CROSS JOIN, not INNER JOIN ... ON 1 = 1: the same rows, and in SQLite it also
                # keeps the join order that the query as written asks for
                text = '%s CROSS JOIN %s' % (self._from_sql(left), self._from_sql(right, nested=True))
            else:
                text = '%s %s JOIN %s ON %s' % (self._from_sql(left), 'INNER' if tag == 'Inner' else 'LEFT',
                                               self._from_sql(right, nested=True), self._p_sql(on))
            return '(%s)' % text if nested else text
        if tag in ('Distinct', 'Where'):
            # DISTINCT / WHERE over one table can be printed as a derived table that
            # keeps the table's alias, so qualified references outside stay valid
            idx = self._single_table(f)
            distinct, where, inner = False, None, f
            if inner[0] == 'Distinct':
                distinct, inner = True, inner[1]
            if inner[0] == 'Where':
                where, inner = self._p_sql(inner[1]), inner[2]
            if idx is not None and inner[0] in ('T', 'Named') and (inner[0], int(inner[1])) == idx:
                alias = self.aliases[idx[1]] if idx[0] == 'T' else self.named[idx[1]]
                sql = 'SELECT %s* FROM %s' % ('DISTINCT ' if distinct else '', self._from_sql(inner))
                if where:
                    sql += ' WHERE ' + where
                return '(%s) AS %s' % (sql, alias)
        raise Unsupported('%s in FROM position' % tag)

    def _q_sql(self, q):
        tag = q[0]
        if tag == 'QAtom':
            text = self.qatoms[int(q[1])]
            return 'SELECT * FROM (%s) AS qa%s' % (text, q[1]) if self.dialect == 'sqlite' else text
        if tag == 'Named':
            return self._q_sql(q[2])
        if tag in SET_SQL:
            if self.dialect == 'sqlite' and tag in ('IntersectAll', 'ExceptAll'):
                raise Unsupported('SQLite has no %s' % SET_SQL[tag])
            if self.dialect == 'sqlite':
                # no parentheses around compound operands in SQLite; compounds are
                # left-associative, so a compound right operand becomes a derived table
                right = self._q_sql(q[2])
                if q[2][0] in SET_SQL:
                    right = 'SELECT * FROM (%s)' % right
                return '%s %s %s' % (self._q_sql(q[1]), SET_SQL[tag], right)
            return '(%s) %s (%s)' % (self._q_sql(q[1]), SET_SQL[tag], self._q_sql(q[2]))
        distinct, items, where = False, '*', None
        if q[0] == 'Distinct':
            distinct, q = True, q[1]
            if q[0] in SET_SQL or q[0] in ('QAtom', 'Distinct'):
                # DISTINCT around a query that is not a single SELECT
                self.derived = getattr(self, 'derived', 0) + 1
                return 'SELECT DISTINCT * FROM (%s) AS vs_d%d' % (self._q_sql(q), self.derived)
        if q[0] == 'Proj':
            # select-list atoms keep their exact text (it may end in "AS alias")
            items, q = ', '.join(self.exprs[int(e[1])] if e[0] == 'EAtom' else self._e_sql(e)
                                 for e in q[1]), q[2]
            if q[0] == 'Distinct':
                # DISTINCT around a join: GROUP BY every column of the joined tables keeps
                # one row per distinct joined row, which is what the projection then reads
                inner, pred = q[1], None
                if inner[0] == 'Where':
                    pred, inner = inner[1], inner[2]
                cols = self._join_columns(inner) if inner[0] in ('Inner', 'Left') else None
                if cols:
                    sql = 'SELECT %s%s FROM %s' % ('DISTINCT ' if distinct else '', items, self._from_sql(inner))
                    if pred is not None:
                        sql += ' WHERE ' + self._p_sql(pred)
                    return sql + ' GROUP BY ' + ', '.join(cols)
        if q[0] == 'Where':
            where, q = self._p_sql(q[1]), q[2]
        sql = 'SELECT %s%s FROM %s' % ('DISTINCT ' if distinct else '', items, self._from_sql(q))
        return sql + (' WHERE ' + where if where else '')

    def _a_sql(self, a):
        tag = a[0]
        if tag == 'ACol':
            return self._e_sql(a[1])
        if tag == 'AConst':
            return a[1]
        names = {'ACount': 'COUNT(%s)', 'ACountD': 'COUNT(DISTINCT %s)', 'ASum': 'SUM(%s)',
                 'AMin': 'MIN(%s)', 'AMax': 'MAX(%s)', 'AAvg': 'AVG(%s)',
                 'AVar': 'VAR_SAMP(%s)', 'AStd': 'STDDEV_SAMP(%s)'}
        if tag in names:
            return names[tag] % self._e_sql(a[1])
        if tag in ('AAdd', 'AMul'):
            return '(%s %s %s)' % (self._a_sql(a[1]), '+' if tag == 'AAdd' else '*', self._a_sql(a[2]))
        if tag == 'AMono':
            name = [n for n, i in self.mono_ids.items() if i == int(a[1])][0]
            return '%s(%s)' % (name, self._a_sql(a[2]))
        if tag == 'AOpaque':
            return self._atom_text(self.opaque_items[int(a[1])])
        raise Unsupported('select item %s' % tag)

    @staticmethod
    def _v_parts(v):
        """(keys, items, having, source) of a value query term."""
        if v[0] == 'VGroup':
            return v[1], v[2], v[3], v[4]
        if v[0] == 'VGlobal':
            return [], v[1], v[2], v[3]
        return [], v[1], 'True', v[2]

    def _v_sql(self, v):
        keys, items, having, source = self._v_parts(v)
        where = None
        if source[0] == 'Where':
            where, source = self._p_sql(source[1]), source[2]
        aliases = self.item_alias_arms[min(getattr(self, '_arm', 0), len(self.item_alias_arms) - 1)]
        self._arm = getattr(self, '_arm', 0) + 1
        cols = ', '.join('%s AS %s' % (self._a_sql(a), aliases[j]) for j, a in enumerate(items))
        sql = 'SELECT %s FROM %s' % (cols, self._from_sql(source))
        if where:
            sql += ' WHERE ' + where
        if keys:
            sql += ' GROUP BY ' + ', '.join(self._e_sql(k) for k in keys)
        if having != 'True' and not keys and self.dialect == 'sqlite' and getattr(self, 'wrap_global_having', False):
            # SQLite before 3.39 rejects HAVING without GROUP BY.  The aggregate query (one
            # row) keeps that row exactly when the predicate is TRUE, which is a WHERE on
            # the predicate's value computed as an extra column (_validated: the standard
            # form is the one checked by the round trip; test_bridge runs both forms)
            outer = ', '.join('vs_g.%s' % aliases[j] for j in range(len(items)))
            return 'SELECT %s FROM (%s, (%s) AS vs_h%s) AS vs_g WHERE vs_g.vs_h' % (
                outer, sql[:len('SELECT ') + len(cols)], self._p_sql(having), sql[len('SELECT ') + len(cols):])
        if having != 'True':
            sql += ' HAVING ' + self._p_sql(having)
        return sql


REGEX_SPECIAL = set('^$.?*+()[]{}|\\')


def _regex_in_fragment(pat):
    """The analysed fragment of regular expressions: optional ^, then literal
    characters or '.', each optionally followed by ?, * or +, then optional $."""
    if not (pat.isascii() and pat.isprintable()):
        return False
    body = pat[1:] if pat.startswith('^') else pat
    body = body[:-1] if body.endswith('$') else body
    i = 0
    while i < len(body):
        c = body[i]
        if c in REGEX_SPECIAL and c != '.':
            return False
        i += 1
        if i < len(body) and body[i] in '?*+':
            i += 1
    return True


def _quote(text):
    return "'%s'" % text.replace("'", "''")


_CLI = {}          # path -> running valscope_mutate process


def _cli_process(cli):
    p = _CLI.get(cli)
    if p is None or p.poll() is not None:
        p = subprocess.Popen([cli], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        _CLI[cli] = p
    return p


def _run_cli(term, cli):
    """The mutants the verified engine prints for one term.  The command-line mutator
    reads one term per line and answers with lines ended by END, so one process serves
    all queries; it is restarted if it dies."""
    for attempt in (1, 2):
        p = _cli_process(cli)
        try:
            p.stdin.write(term.replace('\n', ' ') + '\n')
            p.stdin.flush()
            lines = []
            while True:
                line = p.stdout.readline()
                if line == '':
                    raise BrokenPipeError('mutator exited')
                line = line.rstrip('\n')
                if line == 'END':
                    break
                lines.append(line)
            break
        except (BrokenPipeError, OSError):
            _CLI.pop(cli, None)
            if attempt == 2:
                raise
    out = []
    for line in lines:
        if line.startswith('ERROR'):
            raise Unsupported(line)
        out.append(line.split('\t'))
    return out


# ---------------------------------------------------------------- round-trip validation
#
# The printer (term -> SQL) is not verified.  Every printed query is therefore parsed
# back into a term, and the two terms must be equal up to the numbering of atoms: an
# atom is identified by the syntax tree of its SQL text (without parentheses, which do
# not change the meaning of a tree).  A mutant whose printed SQL does not mean the
# term the verified engine produced is dropped, and counted in STATS.

STATS = collections.Counter()


def _tree_key(node):
    """A hashable, parenthesis-free description of a syntax tree."""
    if isinstance(node, exp.Paren):
        return _tree_key(node.this)
    if isinstance(node, exp.Subquery) and not node.args.get('alias') and \
            not any(node.args.get(k) for k in ('order', 'limit', 'offset')):
        return _tree_key(node.this)           # (SELECT ...) without alias: parentheses only
    if isinstance(node, exp.Expression):
        return (type(node).__name__,
                tuple((k, _tree_key(v)) for k, v in sorted(node.args.items())
                      if v is not None and v != [] and v is not False))
    if isinstance(node, list):
        return tuple(_tree_key(x) for x in node)
    return str(node)


_KEY_CACHE = {}


def _parse_key(text, dialect, wrap=None):
    """The tree key of an SQL text (cached: the same atom occurs in every mutant)."""
    k = (text, dialect, wrap)
    if k not in _KEY_CACHE:
        if len(_KEY_CACHE) > 200000:
            _KEY_CACHE.clear()
        _KEY_CACHE[k] = _parse_key_uncached(text, dialect, wrap)
    return _KEY_CACHE[k]


def _parse_key_uncached(text, dialect, wrap=None):
    try:
        if wrap == 'table':
            tree = sqlglot.parse_one('SELECT * FROM ' + text, read=dialect)
            tree = (tree.args.get('from_') or tree.args.get('from')).this
        else:
            tree = sqlglot.parse_one(text, read=dialect)
        return _tree_key(tree)
    except Exception:
        return ('text', ' '.join(text.split()))


_TREE_CACHE = {}


def _parse_cached(text, dialect):
    k = (text, dialect)
    if k not in _TREE_CACHE:
        if len(_TREE_CACHE) > 200000:
            _TREE_CACHE.clear()
        _TREE_CACHE[k] = sqlglot.parse_one(text, read=dialect)
    return _TREE_CACHE[k]


def _expr_tree(tr, e):
    """The syntax tree that an expression term stands for."""
    tag = e[0]
    if tag == 'EAtom':
        return _parse_cached(tr.exprs[int(e[1])], tr.dialect)
    if tag == 'Int':
        return exp.Literal.number(int(e[1]))
    if tag == 'Null':
        return exp.Null()
    if tag in ('Add', 'Mul'):
        cls = exp.Add if tag == 'Add' else exp.Mul
        return cls(this=_expr_tree(tr, e[1]), expression=_expr_tree(tr, e[2]))
    raise Unsupported('expression %s' % tag)


def canonical(tr, t):
    """The term t of translation tr, with every atom replaced by its syntax tree."""
    if isinstance(t, str):
        return t
    if t and isinstance(t[0], list):            # a list of terms (select items, row IN, ...)
        return tuple(canonical(tr, x) for x in t)
    tag, d = t[0], tr.dialect
    if tag == 'EAtom':
        return ('E', _parse_key(tr.exprs[int(t[1])], d))
    if tag in ('Int', 'Null', 'Add', 'Mul'):
        try:
            return ('E', _tree_key(_expr_tree(tr, t)))
        except Exception:
            return ('Etext', tr._e_sql(t))
    if tag == 'Atom':
        return ('Atom', _parse_key(tr.preds[int(t[1])], d))
    if tag == 'T':
        return ('T', _parse_key(tr.tables[int(t[1])], d, 'table'))
    if tag == 'QAtom':
        return ('QAtom', _parse_key(tr.qatoms[int(t[1])], d))
    if tag == 'Named':
        return ('Named', tr.named[int(t[1])].lower(), canonical(tr, t[2]))
    if tag == 'AOpaque':
        return ('AOpaque', _parse_key(tr.opaque_items[int(t[1])], d))
    if tag == 'AMono':
        name = [n for n, i in tr.mono_ids.items() if i == int(t[1])][0]
        return ('AMono', name, canonical(tr, t[2]))
    if tag in ('Proj', 'VProj', 'VGroup', 'VGlobal'):
        return (tag,) + tuple(tuple(canonical(tr, x) for x in a) if isinstance(a, list) and
                              (not a or isinstance(a[0], list)) else canonical(tr, a) for a in t[1:])
    return (tag,) + tuple(canonical(tr, x) for x in t[1:])


def _roundtrip_ok(tr, term, sql, kind):  # noqa: C901
    """Does the SQL text `sql`, printed from `term`, parse back to the same term?"""
    tree = tr.lift(parse_sexp(term) if isinstance(term, str) else term)
    if tree[0] == 'QAtom' and tr.dialect != 'sqlite':
        # the whole mutant is one opaque query (e.g. INTERSECT->operand): it is printed
        # as its own text
        return _parse_key(sql, tr.dialect) == canonical(tr, tree)[1]
    try:
        back = Translation(sql, tr.dialect, kind=kind, schema=tr.schema, exact_columns=tr.exact_columns)
    except Exception:
        return False
    if getattr(back, 'value_mask', None) != getattr(tr, 'value_mask', None):
        return False
    return canonical(tr, tree) == canonical(back, back.lift(parse_sexp(back.term)))


SET_TAGS = ('Union', 'UnionAll', 'Intersect', 'Except', 'IntersectAll', 'ExceptAll')


def _leftmost_arms(tr, t):
    """The select list of the leftmost arm (canonical) of every set operation in t.  SQLite
    compares the rows of a compound with the collations of its leftmost arm's columns,
    and MySQL derives them from the arms; the model uses one equivalence everywhere."""
    out = set()

    def leftmost(x):
        """The select list of the leftmost arm: it determines the columns and so their
        collations (DISTINCT, WHERE and derived tables in between do not change them)."""
        while isinstance(x, list) and x:
            if x[0] in SET_TAGS or x[0] == 'Distinct':
                x = x[1]
            elif x[0] in ('Where', 'Named'):
                x = x[2]
            elif x[0] == 'Proj':
                return ['Items'] + [e for e in x[1]]
            else:
                return x
        return x

    def walk(x):
        if not isinstance(x, list) or not x:
            return
        if isinstance(x[0], list):
            for y in x:
                walk(y)
            return
        if x[0] in SET_TAGS:
            out.add(canonical(tr, leftmost(x)))
        for y in x[1:]:
            walk(y)
    walk(t)
    return out


def _arm_sets(tr, t):
    """For every maximal tree of set operations in t, the set of the select lists of its
    arms (canonical).  MySQL / MariaDB derive the collation of a compound column from all
    arms, so removing or replacing an arm can change it."""
    out = set()

    def items(x):
        while isinstance(x, list) and x:
            if x[0] == 'Distinct':
                x = x[1]
            elif x[0] in ('Where', 'Named'):
                x = x[2]
            elif x[0] == 'Proj':
                return canonical(tr, ['Items'] + list(x[1]))
            else:
                return canonical(tr, x)
        return canonical(tr, x)

    def leaves(x, acc):
        if isinstance(x, list) and x and x[0] in SET_TAGS:
            leaves(x[1], acc)
            leaves(x[2], acc)
        else:
            acc.add(items(x))

    def walk(x, inside):
        if not isinstance(x, list) or not x:
            return
        if isinstance(x[0], list):
            for y in x:
                walk(y, False)
            return
        is_set = x[0] in SET_TAGS
        if is_set and not inside:
            acc = set()
            leaves(x, acc)
            out.add(frozenset(acc))
        for y in x[1:]:
            walk(y, is_set)
    walk(t, False)
    return out


def changes_compound_collation(tr, original, mutant):
    """Does the mutant give a set operation a leftmost arm that no set operation of the
    original has?  Then the collation that set operation compares with can change (the
    left arm's column may be NOCASE where the old one was BINARY), which the model, with
    one collation equivalence for the whole database, does not describe."""
    o_t = parse_sexp(original) if isinstance(original, str) else original
    m_t = parse_sexp(mutant) if isinstance(mutant, str) else mutant
    if _leftmost_arms(tr, m_t) - _leftmost_arms(tr, o_t):
        return True                     # SQLite: the leftmost arm decides
    if tr.dialect != 'sqlite' and _arm_sets(tr, m_t) - _arm_sets(tr, o_t):
        return True                     # MySQL / MariaDB: all arms decide
    return False


def sqlite_collation_sources(sql):
    """For every compound of an SQLite query: per column, the item that decides its
    collation.  SQLite takes it from the left-most arm whose item has a collating sequence
    (select.c, multiSelectCollSeq): a column (also of a derived table, so * counts) or a
    COLLATE; an expression such as COALESCE(c, 0) has none and passes it on to the next
    arm.  Returns a set of tuples (one per compound) of item texts."""
    try:
        tree = sqlglot.parse_one(sql, read='sqlite')
    except Exception:
        return None
    setops = (exp.Union, exp.Intersect, exp.Except)
    out = set()

    def arms(n, acc):
        if isinstance(n, setops):
            arms(n.this, acc)
            arms(n.expression, acc)
        else:
            while isinstance(n, (exp.Paren, exp.Subquery)) and not n.args.get('alias'):
                n = n.this
            acc.append(n)

    def resolve(arm, i):
        """The item that gives column i of a select its collation, as text, or None when it
        has none.  * over one derived table is the item of the derived table: its
        column has the collation of that item, BINARY when the item has none (and a
        derived compound takes it from its leftmost arm only)."""
        item = arm.expressions[i] if len(arm.expressions) > i else None
        if item is None:
            return None
        body = _strip_parens(item.this if isinstance(item, exp.Alias) else item)
        if isinstance(body, exp.Star) or (isinstance(body, exp.Column) and isinstance(body.this, exp.Star)):
            src = arm.args.get('from') or arm.args.get('from_')
            sub = src.this if src is not None else None
            if isinstance(sub, exp.Subquery) and not arm.args.get('joins') and len(arm.expressions) == 1:
                inner = sub.this
                while isinstance(inner, setops):
                    inner = inner.this
                while isinstance(inner, (exp.Paren, exp.Subquery)) and not inner.args.get('alias'):
                    inner = inner.this
                if isinstance(inner, exp.Select):
                    got = resolve(inner, i)
                    return got if got is not None else 'BINARY (derived column)'
            return '*'
        if isinstance(body, (exp.Column, exp.Collate)):
            return body.sql(dialect='sqlite')
        return None

    for n in tree.walk():
        if isinstance(n, setops) and not isinstance(n.parent, setops):
            acc = []
            arms(n, acc)
            if not all(isinstance(a, exp.Select) for a in acc):
                out.add(('?',))
                continue
            width = max(len(a.expressions) for a in acc)     # an arm can be * over a derived table
            src = []
            for i in range(width):
                pick = next((r for r in (resolve(a, i) for a in acc) if r is not None), None)
                src.append('-' if pick is None else pick)
            out.add(tuple(src))
    return out


def _validated(tr, term, kind):
    """The SQL of `term`, or None if it does not survive the round trip or is outside
    the collation law."""
    if outside_collation_law(tr, term) or \
            outside_collation_law(tr, tr.lift(parse_sexp(term) if isinstance(term, str) else term)):
        STATS['outside_model'] += 1
        return None
    sql = tr.to_sql(term)
    if _roundtrip_ok(tr, term, sql, kind):
        if tr.dialect == 'sqlite':
            tr.wrap_global_having = True     # the form old SQLite releases accept
            try:
                sql = tr.to_sql(term)
            finally:
                tr.wrap_global_having = False
        return sql
    STATS['roundtrip_rejected'] += 1
    return None


def mutate_sql(sql, cli=DEFAULT_CLI, dialect='mysql', schema=None, exact_columns=None):
    """Set-semantic mutation.

    Returns (reprinted_original, [(direction, rule, mutant_sql), ...], skipped).
    direction is 'Up' (the mutant returns a super-bag) or 'Down' (a sub-bag).
    `skipped` counts mutants the bridge cannot print as SQL."""
    tr = Translation(sql, dialect, kind='set', schema=schema, exact_columns=exact_columns)
    original = _validated(tr, tr.term, 'set')
    if original is None:
        raise Unsupported('the re-printed query does not parse back to its term')
    mutants, skipped, seen = [], 0, set()
    for direction, rule, term in _run_cli(tr.term, cli):
        if changes_compound_collation(tr, tr.term, term):
            STATS['outside_model'] += 1
            continue
        try:
            text = _validated(tr, term, 'set')
            if text is not None and dialect == 'sqlite':
                # a compound column whose collation now comes from another arm or item
                src_o, src_m = sqlite_collation_sources(original), sqlite_collation_sources(text)
                if src_o is None or src_m is None or src_m - src_o:
                    STATS['outside_model'] += 1
                    continue
        except Unsupported as e:
            if str(e).startswith('SQLite has no'):
                STATS['not_in_dialect'] += 1     # INTERSECT ALL / EXCEPT ALL: no SQL for SQLite
            else:
                skipped += 1
            continue
        if text is not None and (direction, text) not in seen:
            seen.add((direction, text))        # two rules can give the same SQL
            mutants.append((direction, rule, text))
    return original, mutants, skipped


def mutate_value_sql(sql, cli=DEFAULT_CLI, dialect='mysql'):
    """Value-semantic mutation of one select item of a plain SELECT.

    Returns (reprinted_original, [(relation, rule, column, mutant_sql), ...], skipped).
    The rows of the mutant correspond one to one to the rows of the original, agree
    outside `column`, and inside it satisfy `relation`:
      Le / Ge    the value does not decrease / increase
      AwayZero   a value >= 0 does not decrease, a value <= 0 does not increase
      TowardOne  a value <= 1 does not decrease, a value >= 1 does not increase
      AwayOne    a value >= 1 does not decrease, a value <= 1 does not increase
    NULL corresponds to NULL."""
    return mutate_value(sql, cli, dialect)[:3]


def mutate_value(sql, cli=DEFAULT_CLI, dialect='mysql', translation=None, schema=None, exact_columns=None):
    """Like mutate_value_sql, with two more components: the result of
    Translation.type_probe, and the mutants of the HAVING predicate as
    (direction, rule, mutant_sql).  For those, 'Up' means the mutant returns the
    same rows and possibly more, 'Down' a subset."""
    tr = Translation(sql, dialect, kind='value', schema=schema, exact_columns=exact_columns)
    if translation is not None:
        translation.append(tr)
    original = _validated(tr, tr.term, 'value')
    if original is None:
        raise Unsupported('the re-printed query does not parse back to its term')
    mutants, having_mutants, skipped = [], [], 0
    for fields in _run_cli(tr.term, cli):
        try:
            text = _validated(tr, fields[-1], 'value')
        except Unsupported:
            skipped += 1
            continue
        if text is None:
            continue
        if len(fields) == 4:
            relation, rule, column, _ = fields
            # outside the DISTINCT parts the rows correspond one to one (tmutate_mask_plain_sound)
            tr.cover_by_text[text] = tr.value_cover and not _same_under(
                tr.value_mask, parse_sexp(tr.term), parse_sexp(fields[-1]))
            mutants.append((relation, rule, int(column), text))
        else:
            direction, rule, _ = fields
            if getattr(tr, 'has_window', False):
                STATS['having_with_window'] += 1     # the window would range over other groups
                continue
            if tr.value_cover and not tr.value_distinct:
                # DISTINCT on a part of a UNION ALL only: no theorem for HAVING mutants
                STATS['having_partial_distinct'] += 1
                continue
            having_mutants.append((direction, rule, text))
    return original, mutants, skipped, tr.type_probe(), having_mutants


if __name__ == '__main__':
    import sys
    args = [a for a in sys.argv[1:] if a != '--value']
    if '--value' in sys.argv:
        original, mutants, skipped, _, having_mutants = mutate_value(args[0])
        print('original:', original)
        for relation, rule, column, text in mutants:
            print('%-9s col %d  %-24s %s' % (relation, column, rule, text))
        for direction, rule, text in having_mutants:
            print('%-9s HAVING %-24s %s' % (direction, rule, text))
    else:
        original, mutants, skipped = mutate_sql(args[0])
        print('original:', original)
        for direction, rule, text in mutants:
            print('%-4s %-20s %s' % (direction, rule, text))
    print('(%d mutants not printable as SQL)' % skipped)
