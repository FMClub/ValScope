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
# VALSCOPE_MUTATE selects another mutator with the same interface: one extracted from a
# development which adds rules of a class of worlds (README, "A rule of one dialect").
DEFAULT_CLI = os.environ.get('VALSCOPE_MUTATE') or os.path.join(HERE, '..', 'cli', 'valscope_mutate')


from common import Unsupported, parse_sexp, _strip_parens
from collation_law import (ExactColumns, _alias_sources, _column_class, _exact_names, compared_selections,
                           outside_collation_law)
from determinism import _check_deterministic, _window_undetermined
from printer import Printer, join_arms_out

# the public names of the bridge (some are defined in the modules above)
__all__ = ['DEFAULT_CLI', 'ExactColumns', 'STATS', 'Translation', 'Unsupported', 'canonical', 'mutate_sql',
           'mutate_value', 'mutate_value_sql', 'outside_collation_law', 'parse_sexp', 'sqlite_collation_sources']


CMP = {exp.EQ: 'eq', exp.NEQ: 'ne', exp.LT: 'lt', exp.LTE: 'le', exp.GT: 'gt', exp.GTE: 'ge'}

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


class Translation(Printer):
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
        # without outer parentheses: the printer adds its own around an atom, and a
        # re-printed query that is translated again would collect one more level each time
        return self._unparen(node).sql(dialect=self.dialect)

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

    def _parse_one_table_arms(self, node, alias):
        """(term, width) of a set operation whose arms are all `SELECT [DISTINCT] * FROM X AS
        alias [WHERE p]` over one source X; None if it is anything else."""
        node = self._unwrap(node)
        if isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            if any(node.args.get(key) for key in ('limit', 'offset', 'with_', 'with', 'order')):
                return None
            distinct = node.args.get('distinct')
            if isinstance(node, exp.Union):
                tag = 'Union' if distinct else 'UnionAll'
            else:
                tag = ('Intersect' if isinstance(node, exp.Intersect) else 'Except') + ('' if distinct else 'All')
            left, right = self._parse_one_table_arms(node.this, alias), self._parse_one_table_arms(node.expression, alias)
            if left is None or right is None or left[1] != right[1] or left[2] != right[2]:
                return None
            return '(%s %s %s)' % (tag, left[0], right[0]), left[1], left[2]
        if not isinstance(node, exp.Select):
            return None
        src = node.args.get('from_') or node.args.get('from')
        if src is None or not self._star_only(node) or not self._bare(node, allowed=('where',)) \
                or src.this.alias_or_name != alias or isinstance(src.this, exp.Subquery) \
                or (isinstance(node.args.get('distinct'), exp.Distinct) and node.args['distinct'].args.get('on')):
            return None
        source = self._text(src.this)
        term, width = self._table(src.this)
        if node.args.get('where') is not None:
            term = '(Where %s %s)' % (self._pred(node.args['where'].this), term)
        if node.args.get('distinct'):
            term = '(Distinct %s)' % term
        return term, width, source

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
            if isinstance(self._unwrap(body), (exp.Union, exp.Intersect, exp.Except)):
                # ((SELECT * FROM X AS a WHERE p) UNION ALL (SELECT * FROM X AS a WHERE q)) AS a:
                # a set operation whose arms all read the one table X, under its name (the
                # printer writes a set operation in a FROM position this way)
                snap = self._snapshot()
                try:
                    arms = self._parse_one_table_arms(body, alias)
                except Unsupported:
                    arms = None
                if arms is not None:
                    return arms[0], arms[1]
                self._restore(snap)
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

    @staticmethod
    def _unparen(node):
        while isinstance(node, exp.Paren):
            node = node.this
        return node

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
            # without outer parentheses: the printer adds its own around an atom
            keys = [self._unparen(k) for k in group.expressions]
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


_CLI = {}          # path -> running valscope_mutate process


def _cli_process(cli):
    p = _CLI.get(cli)
    if p is None or p.poll() is not None:
        p = subprocess.Popen([cli], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        _CLI[cli] = p
    return p


_CLASS_RULES = {}


def _class_rules(cli):
    """The names of the rules of `cli` that are sound in a class of worlds only (rules
    proved against the semantics of one dialect); none for a mutator without such rules
    or without the option."""
    if cli not in _CLASS_RULES:
        try:
            listed = subprocess.run([cli, '--class-rules'], capture_output=True, text=True, timeout=30)
            names = set(listed.stdout.split('\n')) - {''} if listed.returncode == 0 else set()
        except (OSError, subprocess.SubprocessError):
            names = set()
        _CLASS_RULES[cli] = names
    return _CLASS_RULES[cli]


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
    # a select list or WHERE over a UNION ALL of joins is printed inside the arms (printer.join_arms_out)
    return canonical(tr, join_arms_out(tree)) == canonical(back, join_arms_out(back.lift(parse_sexp(back.term))))


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
            arm = leftmost(x)
            out.add(_join_source(tr, arm) or canonical(tr, arm))
        for y in x[1:]:
            walk(y)
    walk(t)
    return out


def _join_source(tr, x):
    """An inner join of tables, without its ON conditions: `SELECT *` over it has the
    columns of the tables whatever the conditions are.  None for anything else."""
    if isinstance(x, list) and x and x[0] == 'T':
        return canonical(tr, x)
    if isinstance(x, list) and x and x[0] == 'Inner':
        a, b = _join_source(tr, x[2]), _join_source(tr, x[3])
        return None if a is None or b is None else ('Join', a, b)
    return None


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
                return _join_source(tr, x) or canonical(tr, x)
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


def _one_table_compounds(tr, t):
    """The tables (canonical), or inner joins of tables without their conditions, such that
    some maximal tree of set operations in t has for arms that source alone, or DISTINCT
    and WHERE over it."""
    out = set()

    def leaves(x, acc):
        if isinstance(x, list) and x and x[0] in SET_TAGS:
            leaves(x[1], acc)
            leaves(x[2], acc)
            return
        if isinstance(x, list) and x and x[0] == 'Distinct':
            x = x[1]
        if isinstance(x, list) and x and x[0] == 'Where':
            x = x[2]
        acc.append(_join_source(tr, x))

    def walk(x, inside):
        if not isinstance(x, list) or not x:
            return
        if isinstance(x[0], list):
            for y in x:
                walk(y, False)
            return
        is_set = x[0] in SET_TAGS
        if is_set and not inside:
            acc = []
            leaves(x, acc)
            if None not in acc and len(set(acc)) == 1:
                out.add(acc[0])
        for y in x[1:]:
            walk(y, is_set)
    walk(t, False)
    return out


def changes_compound_collation(tr, original, mutant):
    """Does the mutant give a set operation a leftmost arm that no set operation of the
    original has (MySQL / MariaDB: arms of several select lists that no set operation of
    the original has)?  Then the collation that set operation compares with can change (the
    left arm's column may be NOCASE where the old one was BINARY), which the model, with
    one collation equivalence for the whole database, does not describe."""
    o_t = parse_sexp(original) if isinstance(original, str) else original
    m_t = parse_sexp(mutant) if isinstance(mutant, str) else mutant
    new_leftmost = _leftmost_arms(tr, m_t) - _leftmost_arms(tr, o_t)
    if tr.dialect == 'sqlite':
        return bool(new_leftmost)       # SQLite: the leftmost arm decides
    # MySQL / MariaDB: all arms decide.  A set operation all of whose arms have one select
    # list (`t WHERE c1 UNION ALL t WHERE c2`) derives for each column the collation that
    # the select list alone has, so it changes nothing, new as it may be.
    arm_sets = _arm_sets(tr, m_t)
    if any(len(arms) > 1 for arms in arm_sets - _arm_sets(tr, o_t)):
        return True
    uniform = {next(iter(arms)) for arms in arm_sets if len(arms) == 1} & _one_table_compounds(tr, m_t)
    if any(len(arms) == 1 and not arms <= uniform for arms in arm_sets - _arm_sets(tr, o_t)):
        return True                     # one select list over several tables
    return bool(new_leftmost - uniform)


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
    class_rules = _class_rules(cli)
    compared = compared_selections(tr, tr.term) if class_rules else None
    for direction, rule, term in _run_cli(tr.term, cli):
        if changes_compound_collation(tr, tr.term, term):
            STATS['outside_model'] += 1
            continue
        if rule in class_rules and compared_selections(tr, term) != compared:
            STATS['outside_model'] += 1     # see compared_selections
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
    # value mutants of a derived table, seen through the outer query (VLineage.v)
    from lineage import _lineage_mutants      # (lineage imports this module)
    try:
        lin, extra = _lineage_mutants(sql, cli, dialect, schema, exact_columns)
    except Unsupported:
        lin, extra = None, []
    if extra:
        tr.lineage = lin
        for m in extra:
            tr.cover_by_text[m[3]] = lin.distinct          # SELECT DISTINCT outside: a cover
        mutants.extend(extra)
        STATS['lineage_mutants'] += len(extra)
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
