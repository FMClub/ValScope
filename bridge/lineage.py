"""A mutated value followed through a derived table (VLineage.v, Registry.wmutate_sound)."""
import sqlglot
from sqlglot import exp

from common import Unsupported, parse_sexp, _strip_parens
from collation_law import _sensitive_tree
from determinism import _check_deterministic
from sql_bridge import STATS, Translation, _mysql_population_names, _run_cli, _tree_key, _validated, canonical

# ---------------------------------------------------------------- lineage through a derived table
#
# SELECT d.k, SUM(d.s) FROM (value query) AS d [WHERE ...] [GROUP BY d.k] [HAVING ...]:
# the inner value query is mutated, and the outer query passes the relation of the mutated
# column on to the one item that reads it (VLineage.v, Registry.wmutate_sound).  The outer
# query is not re-printed: the mutant is the query as written with the body of the derived
# table replaced, so only the reading of the outer query (its term) is glue to be trusted;
# it is read again from every mutant and must be the same.

OUTER_AGGS = {exp.Sum: 'OSum', exp.Min: 'OMin', exp.Max: 'OMax', exp.Avg: 'OAvg', exp.Count: 'OCount'}


class Lineage:
    def __init__(self, sql, dialect='mysql', schema=None, exact_columns=None):
        self.dialect = dialect
        if dialect == 'mysql':
            sql = _mysql_population_names(sql)
        tree = sqlglot.parse_one(sql, read=dialect)
        _check_deterministic(tree)
        if not isinstance(tree, exp.Select):
            raise Unsupported('lineage: not a SELECT over a derived table')
        if tree.args.get('order') is not None and not (tree.args.get('limit') or tree.args.get('offset')):
            tree = tree.copy()
            tree.set('order', None)
        for key in ('joins', 'limit', 'offset', 'qualify', 'windows', 'sample', 'pivots', 'laterals', 'into', 'order'):
            if tree.args.get(key):
                raise Unsupported('lineage: %s in the outer query' % key)
        frm = tree.args.get('from_') or tree.args.get('from')
        if frm is None or not isinstance(frm.this, exp.Subquery) or not frm.this.alias:
            raise Unsupported('lineage: not a SELECT over a derived table')
        if frm.this.args.get('alias').columns:
            raise Unsupported('lineage: column list on the derived table')
        self.tree, self.alias = tree, frm.this.alias.lower()
        distinct = tree.args.get('distinct')
        if distinct is not None and (not isinstance(distinct, exp.Distinct) or distinct.args.get('on')):
            raise Unsupported('lineage: DISTINCT ON')
        self.distinct = distinct is not None
        w = tree.args.get('with_') or tree.args.get('with')
        prefix = (w.sql(dialect=dialect) + ' ') if w is not None else ''
        self.inner = Translation(prefix + frm.this.this.sql(dialect=dialect), dialect, kind='value', schema=schema,
                                 exact_columns=exact_columns)
        if self.inner.value_mask != ('one', False):
            raise Unsupported('lineage: DISTINCT, UNION, INTERSECT or EXCEPT in the derived table')
        names = [a.lower() for a in self.inner.item_alias_arms[0]]
        if len(set(names)) != len(names):
            raise Unsupported('lineage: the derived table has two columns of the same name')
        self.names = names
        self.term = self._outer(tree)

    def _cols(self, node):
        """The columns of the derived table that `node` reads (sorted positions)."""
        out = set()
        for n in ([node] if isinstance(node, exp.Column) else []) + list(node.find_all(exp.Column, exp.Star)):
            if isinstance(n, exp.Star) and isinstance(n.parent, exp.Count):
                continue                                 # COUNT(*): the number of rows
            if isinstance(n, exp.Star) or isinstance(n.this, exp.Star):
                raise Unsupported('lineage: * in the outer query')
            if not n.table:
                raise Unsupported('lineage: unqualified column %s in the outer query' % n.name)
            if n.table.lower() == self.alias:
                if n.name.lower() not in self.names:
                    raise Unsupported('lineage: unknown column %s' % n.sql())
                out.add(self.names.index(n.name.lower()))
            elif n.find_ancestor(exp.Select) is self.tree:
                raise Unsupported('lineage: column %s of another table' % n.sql())
        return sorted(out)

    def _plain(self, node):
        """The position of `node` if it is a column of the derived table, else None."""
        node = _strip_parens(node)
        if isinstance(node, exp.Column) and node.table and node.table.lower() == self.alias \
                and node.name.lower() in self.names:
            return self.names.index(node.name.lower())
        return None

    def _outer(self, tree):
        d = self.dialect
        where, group, having = tree.args.get('where'), tree.args.get('group'), tree.args.get('having')
        parts = list(tree.expressions) + [x.this for x in (where, having) if x is not None] + \
            (list(group.expressions) if group is not None else [])
        for part in parts:
            if part.find(exp.Window) is not None:
                raise Unsupported('lineage: window function in the outer query')
            if _sensitive_tree(part, d):
                # the inner query can pick another representative in the mutant
                raise Unsupported('lineage: the outer query distinguishes collation-equivalent values')

        def own_agg(n):
            if isinstance(n, (exp.Select, exp.Subquery)):
                return False
            return isinstance(n, exp.AggFunc) or any(own_agg(c) for c in n.iter_expressions())
        if group is not None:
            if any(group.args.get(k) for k in ('rollup', 'cube', 'grouping_sets', 'totals', 'all')):
                raise Unsupported('lineage: ROLLUP / CUBE / GROUPING SETS')
            keys = [self._plain(k) for k in group.expressions]
            if any(k is None for k in keys):
                raise Unsupported('lineage: a grouping key that is not a column of the derived table')
            mode = '(OGroup (%s))' % ' '.join(map(str, keys))
        elif any(own_agg(p) for p in list(tree.expressions) + ([having.this] if having is not None else [])):
            mode = '(OGlobal)'
        else:
            if having is not None:
                raise Unsupported('lineage: HAVING without aggregation')
            mode = '(OProj)'
        items = []
        for k, item in enumerate(tree.expressions):
            body = _strip_parens(item.this if isinstance(item, exp.Alias) else item)
            c = self._plain(body)
            if c is not None:
                items.append('(OCol %d)' % c)
                continue
            tag = OUTER_AGGS.get(type(body))
            arg = self._plain(body.this) if tag and isinstance(body.this, exp.Expression) else None
            if tag and arg is not None and len([v for v in body.args.values() if v]) == 1:
                items.append('(%s %d)' % (tag, arg))
            else:
                items.append('(OOpaque %d (%s))' % (k, ' '.join(map(str, self._cols(body)))))
        fcols = self._cols(where.this) if where is not None else []
        hcols = self._cols(having.this) if having is not None else []
        self.outer = '%s (F 0 (%s)) (H 0 (%s)) (%s)' % (mode, ' '.join(map(str, fcols)), ' '.join(map(str, hcols)),
                                                       ' '.join(items))
        # what the outer query is, for the comparison with a mutant: its term and its text
        # with the derived table emptied
        shell = tree.copy()
        (shell.args.get('from_') or shell.args.get('from')).this.set('this', exp.Select(expressions=[exp.Null()]))
        self.shell = _tree_key(shell)
        return '(W %s %s)' % (self.outer, self.inner.term)

    def with_inner(self, inner_sql):
        """The query as written, with the body of the derived table replaced."""
        tree = self.tree.copy()
        (tree.args.get('from_') or tree.args.get('from')).this.set('this', sqlglot.parse_one(inner_sql, read=self.dialect))
        return tree.sql(dialect=self.dialect)


def _lineage_mutants(sql, cli, dialect, schema, exact_columns):
    """(Lineage, [(relation, rule, column, mutant_sql), ...]) for a SELECT over a derived
    value query; raises Unsupported when the query has no such reading."""
    lin = Lineage(sql, dialect, schema, exact_columns)
    if _validated(lin.inner, lin.inner.term, 'value') is None:
        raise Unsupported('lineage: the derived table does not survive the round trip')
    out = []
    for fields in _run_cli(lin.term, cli):
        relation, rule, column, wterm = fields
        inner_term = parse_sexp(wterm)[-1]
        try:
            inner_sql = _validated(lin.inner, inner_term, 'value')
        except Unsupported:
            continue
        if inner_sql is None:
            continue
        text = lin.with_inner(inner_sql)
        # the mutant, read again, is the same outer query over the mutated inner term
        try:
            back = Lineage(text, dialect, schema, exact_columns)
        except Exception:
            STATS['lineage_roundtrip_rejected'] += 1
            continue
        if back.outer != lin.outer or back.shell != lin.shell or back.names != lin.names or \
                canonical(back.inner, back.inner.lift(parse_sexp(back.inner.term))) != \
                canonical(lin.inner, lin.inner.lift(inner_term)):
            STATS['lineage_roundtrip_rejected'] += 1
            continue
        out.append((relation, rule, int(column), text))
    return lin, out
