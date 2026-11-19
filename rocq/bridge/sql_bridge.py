"""Bridge between SQL text and the verified mutators (cli/valscope_mutate).

    SQL text --sqlglot--> algebra term --valscope_mutate--> mutant terms --> SQL text

The mutators never look inside scalar expressions, table references or predicates
they do not analyse; they only copy them.  The bridge replaces each of them by a
numbered atom and puts the original SQL text back when printing.

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


class Translation:
    """One SQL query translated to an algebra term, with its atom tables.

    kind is 'set' (set-semantic term, mutate with direction Up / Down) or
    'value' (value query, one select item is mutated)."""

    def __init__(self, sql, dialect='mysql', kind='set'):
        self.dialect = dialect
        self.kind = kind
        self.tables, self.aliases, self.exprs, self.preds = [], [], [], []
        self.item_alias, self.mono_ids = [], {}
        tree = sqlglot.parse_one(sql, read=dialect)
        _check_deterministic(tree)
        self.term = self._query(tree) if kind == 'set' else self._value_query(tree)

    # ------------------------------------------------------------ SQL -> term
    def _text(self, node):
        return node.sql(dialect=self.dialect)

    def _expr(self, node):
        # one atom per occurrence: never identify two occurrences by their text
        self.exprs.append(self._text(node))
        return '(Col %d)' % (len(self.exprs) - 1)

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
            return '(%s %s %s)' % (tag, self._query(node.this), self._query(node.expression))
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
        for key in ('group', 'having', 'limit', 'offset', 'qualify', 'windows', 'with_', 'with',
                    'locks', 'sample', 'pivots', 'laterals', 'distinct', 'into', 'hint', 'kind'):
            if key not in allowed and node.args.get(key):
                raise Unsupported(key)

    def _select(self, node):
        self._check_clauses(node, allowed=('distinct',))
        for item in node.expressions:
            for inner in item.walk():
                if isinstance(inner, (exp.AggFunc, exp.Window, exp.Select)):
                    raise Unsupported('aggregate, window or subquery in the select list')
                if isinstance(inner, exp.Anonymous):
                    raise Unsupported('unknown function in the select list')
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
        return term

    def _table(self, node):
        if isinstance(node, exp.Table) or (isinstance(node, exp.Subquery) and node.alias):
            # a derived table is kept as an opaque table: it is not mutated
            self.tables.append(self._text(node))
            self.aliases.append(node.alias_or_name)
            return '(T %d 0)' % (len(self.tables) - 1)
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
            saved = (len(self.tables), len(self.exprs), len(self.preds))
            try:
                return '(Exists %s)' % self._query(node.this)
            except Unsupported:
                # roll back the atoms of the failed attempt and keep it opaque
                del self.tables[saved[0]:], self.aliases[saved[0]:]
                del self.exprs[saved[1]:], self.preds[saved[2]:]
        if isinstance(node, exp.In) and node.args.get('query') is not None \
                and not isinstance(node.this, exp.Tuple) and node.this.find(exp.Select) is None:
            saved = (len(self.tables), len(self.exprs), len(self.preds))
            try:
                sub = self._unwrap(node.args['query'])
                if self._column_count(sub) != 1:
                    raise Unsupported('IN subquery with several columns')
                left = self._expr(node.this)
                return '(In %s %s)' % (left, self._query(sub))
            except Unsupported:
                del self.tables[saved[0]:], self.aliases[saved[0]:]
                del self.exprs[saved[1]:], self.preds[saved[2]:]
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
        for inner in node.walk():
            if isinstance(inner, (exp.Window, exp.Select, exp.Anonymous)):
                raise Unsupported('window, subquery or unknown function in a select item')
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
        if type(node) in simple:
            return '(%s %s)' % (simple[type(node)], self._agg_arg(node))
        if isinstance(node, exp.Add):
            return '(AAdd %s %s)' % (self._item(node.this, key_texts), self._item(node.expression, key_texts))
        if isinstance(node, exp.Mul):
            return '(AMul %s %s)' % (self._item(node.this, key_texts), self._item(node.expression, key_texts))
        for cls, name in MONO_FUNCS:
            if type(node) is cls and len([v for v in node.args.values() if v is not None]) == 1:
                fid = self.mono_ids.setdefault(name, len(self.mono_ids))
                return '(AMono %d %s)' % (fid, self._item(node.this, key_texts))
        if node.find(exp.AggFunc) is not None:
            raise Unsupported('aggregate %s is not modelled' % type(node.find(exp.AggFunc)).__name__)
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
                if t and t[0] == 'Col':
                    atoms.append(t)
                else:
                    for x in t[1:]:
                        collect(x)
        collect(items)
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
        if tag == 'Col':
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
        raise Unsupported('predicate %s' % tag)

    def _single_table(self, f):
        """The only table atom below f, or None."""
        found = []

        def walk(t):
            if isinstance(t, list):
                if t and t[0] == 'T':
                    found.append(int(t[1]))
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
        if tag in ('Inner', 'Left'):
            on, left, right = (f[1], f[2], f[3]) if tag == 'Inner' else (f[2], f[3], f[4])
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
            if idx is not None and inner[0] == 'T':
                sql = 'SELECT %s* FROM %s' % ('DISTINCT ' if distinct else '', self.tables[idx])
                if where:
                    sql += ' WHERE ' + where
                return '(%s) AS %s' % (sql, self.aliases[idx])
        raise Unsupported('%s in FROM position' % tag)

    def _q_sql(self, q):
        tag = q[0]
        if tag in SET_SQL:
            return '(%s) %s (%s)' % (self._q_sql(q[1]), SET_SQL[tag], self._q_sql(q[2]))
        distinct, items, where = False, '*', None
        if q[0] == 'Distinct':
            distinct, q = True, q[1]
        if q[0] == 'Proj':
            # select-list atoms keep their exact text (it may end in "AS alias")
            items, q = ', '.join(self.exprs[int(e[1])] if e[0] == 'Col' else self._e_sql(e)
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


def mutate_value(sql, cli=DEFAULT_CLI, dialect='mysql'):
    """Like mutate_value_sql, with two more components: the result of
    Translation.type_probe, and the mutants of the HAVING predicate as
    (direction, rule, mutant_sql).  For those, 'Up' means the mutant returns the
    same rows and possibly more, 'Down' a subset."""
    tr = Translation(sql, dialect, kind='value')
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
