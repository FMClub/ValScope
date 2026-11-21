"""Determinism: the constructs whose result SQL does not determine (non-deterministic
functions, order-dependent aggregates, bare columns of a grouped query, window functions
that tell tied rows apart, LIMIT with ties).  Queries that use them are rejected."""
from sqlglot import exp

from common import Unsupported, _strip_parens

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
