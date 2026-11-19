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
import os
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
SET_SQL = {'UnionAll': 'UNION ALL', 'Union': 'UNION', 'Intersect': 'INTERSECT', 'Except': 'EXCEPT'}

# Scalar functions that are non-decreasing on all reals and never turn a non-NULL
# number into NULL.  LOG, LN and SQRT are excluded on purpose: they return NULL
# outside their domain, which would change NULL-ness.
MONO_FUNCS = [(exp.Exp, 'EXP'), (exp.Floor, 'FLOOR'), (exp.Ceil, 'CEIL'),
              (exp.Round, 'ROUND'), (exp.Atan, 'ATAN'), (exp.Sign, 'SIGN')]

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
        if isinstance(node, exp.Select) and node is not tree and \
                (node.args.get('limit') or node.args.get('offset')) and not node.args.get('order'):
            # which rows a LIMIT keeps is not determined without an ORDER BY
            raise Unsupported('LIMIT without ORDER BY in a subquery')


class Translation:
    """One SQL query translated to an algebra term, with its atom tables.

    kind is 'set' (set-semantic term, mutate with direction Up / Down) or
    'value' (value query, one select item is mutated)."""

    def __init__(self, sql, dialect='mysql', kind='set'):
        self.dialect = dialect
        self.kind = kind
        self.tables, self.aliases, self.exprs, self.preds = [], [], [], []
        self.item_alias, self.mono_ids = [], {}
        self.named, self.qatoms, self.ctes, self.opaque_items = [], [], {}, []
        tree = sqlglot.parse_one(sql, read=dialect)
        _check_deterministic(tree)
        tree = self._take_ctes(tree)
        self.term = self._query(tree) if kind == 'set' else self._value_query(tree)

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

    def _arm(self, node):
        """An operand of a set operation: translated if possible, else an opaque query."""
        snap = self._snapshot()
        try:
            return self._query(node)
        except Unsupported:
            self._restore(snap)
            inner = self._unwrap(node)
            if isinstance(inner, (exp.Union, exp.Intersect, exp.Except)) or not isinstance(inner, exp.Select):
                raise
            if any(isinstance(n, exp.Window) for n in inner.walk()) or inner.find(exp.Star) is not None:
                raise
            self.qatoms.append(self._text(inner))
            return '(QAtom %d 1)' % (len(self.qatoms) - 1)

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
            elif not distinct:
                raise Unsupported('INTERSECT ALL / EXCEPT ALL')
            else:
                tag = 'Intersect' if isinstance(node, exp.Intersect) else 'Except'
            return '(%s %s %s)' % (tag, self._arm(node.this), self._arm(node.expression))
        if isinstance(node, exp.Select):
            return self._select(node)
        raise Unsupported(type(node).__name__)

    def _column_count(self, node):
        """Number of select items of the leftmost SELECT, or None with a star."""
        node = self._unwrap(node)
        while isinstance(node, (exp.Union, exp.Intersect, exp.Except)):
            node = self._unwrap(node.this)
        if not isinstance(node, exp.Select) or any(item.find(exp.Star) is not None for item in node.expressions):
            return None
        return len(node.expressions)

    def _check_clauses(self, node, allowed=()):
        # (row locks, FOR UPDATE / LOCK IN SHARE MODE, do not change the result)
        for key in ('group', 'having', 'limit', 'offset', 'qualify', 'windows', 'with_', 'with',
                    'sample', 'pivots', 'laterals', 'distinct', 'into', 'hint', 'kind'):
            if key not in allowed and node.args.get(key):
                raise Unsupported(key)

    def _select(self, node):
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

    def _source(self, node):
        """FROM, JOINs and WHERE of a SELECT."""
        source = node.args.get('from_') or node.args.get('from')
        if source is None:
            raise Unsupported('SELECT without FROM')
        term, _ = self._table(source.this)
        for join in node.args.get('joins') or []:
            if join.args.get('using') or join.args.get('method'):
                raise Unsupported('USING / NATURAL join')
            side = str(join.args.get('side') or '').upper()
            kind = str(join.args.get('kind') or '').upper()
            right, width = self._table(join.this)
            on = self._pred(join.args['on']) if join.args.get('on') is not None else 'True'
            if side == 'LEFT':
                term = '(Left %d %s %s %s)' % (width, on, term, right)
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
        key_texts = {self._text(k) for k in keys}
        has_agg = any(item.find(exp.AggFunc) is not None for item in node.expressions)
        source = self._source(node)
        items = []
        for j, item in enumerate(node.expressions):
            body = item.this if isinstance(item, exp.Alias) else item
            if isinstance(body, exp.Star) or (isinstance(body, exp.Column) and isinstance(body.this, exp.Star)):
                raise Unsupported('* in a value query')
            self.item_alias.append(item.alias if isinstance(item, exp.Alias) and item.alias else 'c%d' % j)
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
        if any(isinstance(inner, exp.Window) for inner in node.walk()):
            raise Unsupported('window function in a select item')
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
        if key_texts is not None and self._text(node) not in key_texts:
            raise Unsupported('non-aggregated expression that is not a grouping key')
        return '(ACol %s)' % self._expr(node)

    # ------------------------------------------------------------ term -> SQL
    def to_sql(self, term):
        tree = parse_sexp(term) if isinstance(term, str) else term
        if tree[0] in ('VProj', 'VGroup', 'VGlobal'):
            return self._v_sql(tree)
        return self._q_sql(tree)

    def type_probe(self):
        """For a value query: (sql, number_of_keys).  The query returns no rows; its
        columns are the grouping keys followed by every row-level expression used in
        the select items, so a caller can inspect their types."""
        keys, items, _, source = self._v_parts(parse_sexp(self.term))
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
        is inside the model only when it returns 0."""
        keys, items, _, source = self._v_parts(parse_sexp(self.term))
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
                elif t and t[0] in ('Exists', 'In'):
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
        cols = ', '.join('%s AS %s' % (self._a_sql(a), self.item_alias[j]) for j, a in enumerate(items))
        sql = 'SELECT %s FROM %s' % (cols, self._from_sql(source))
        if where:
            sql += ' WHERE ' + where
        if keys:
            sql += ' GROUP BY ' + ', '.join(self._e_sql(k) for k in keys)
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


def _run_cli(term, cli):
    out = subprocess.run([cli], input=term + '\n', capture_output=True, text=True, check=True).stdout
    lines = []
    for line in out.splitlines():
        if line == 'END':
            break
        if line.startswith('ERROR'):
            raise Unsupported(line)
        lines.append(line.split('\t'))
    return lines


def mutate_sql(sql, cli=DEFAULT_CLI, dialect='mysql'):
    """Set-semantic mutation.

    Returns (reprinted_original, [(direction, rule, mutant_sql), ...], skipped).
    direction is 'Up' (the mutant returns a super-bag) or 'Down' (a sub-bag).
    `skipped` counts mutants the bridge cannot print as SQL."""
    tr = Translation(sql, dialect, kind='set')
    mutants, skipped = [], 0
    for direction, rule, term in _run_cli(tr.term, cli):
        try:
            mutants.append((direction, rule, tr.to_sql(term)))
        except Unsupported:
            skipped += 1
    return tr.reprint(), mutants, skipped


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


def mutate_value(sql, cli=DEFAULT_CLI, dialect='mysql', translation=None):
    """Like mutate_value_sql, with two more components: the result of
    Translation.type_probe, and the mutants of the HAVING predicate as
    (direction, rule, mutant_sql).  For those, 'Up' means the mutant returns the
    same rows and possibly more, 'Down' a subset."""
    tr = Translation(sql, dialect, kind='value')
    if translation is not None:
        translation.append(tr)
    mutants, having_mutants, skipped = [], [], 0
    for fields in _run_cli(tr.term, cli):
        try:
            if len(fields) == 4:
                relation, rule, column, term = fields
                mutants.append((relation, rule, int(column), tr.to_sql(term)))
            else:
                direction, rule, term = fields
                having_mutants.append((direction, rule, tr.to_sql(term)))
        except Unsupported:
            skipped += 1
    return tr.reprint(), mutants, skipped, tr.type_probe(), having_mutants


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
