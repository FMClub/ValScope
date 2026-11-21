"""Generate random queries inside the fragment the verified mutators support
(selection, projection, DISTINCT, inner/left joins, set operations, EXISTS, NOT).

    python3 bridge/gen_fragment.py N [SEED] > queries.sql            # set-semantic fragment
    python3 bridge/gen_fragment.py --value N [SEED] > queries.sql    # value queries (aggregates)
    add --sqlite for the SQLite databases of gen_sqlite_db.py
    add --value-ext for windows over groups, DISTINCT arms of a UNION ALL, INTERSECT / EXCEPT,
        an outer query over a derived value query
    add --sqlite-seed SEED (with --sqlite --value): only the numeric columns of that database
    add --schema FILE.json for another schema (see below)

By default the schema is the sample schema of the Python generator (tables t1, t2, t3).
With --schema, FILE.json maps each table to its numeric columns, for example
    {"orders": ["id", "qty", "price"], "items": ["id", "order_id", "amount"]}
The first column of each table is used by EXISTS subqueries.  Only numeric columns are
listed: the generator compares them with small integer constants."""
import json
import random
import sys

TABLES = {'t1': ['c1', 'c4'], 't2': ['c1', 'c2'], 't3': ['c1', 'c2', 'c3', 'c6', 'c7', 'c8']}
OPS = ['=', '<>', '<', '<=', '>', '>=']
CONSTS = [1, 5, 20, 50, 100, 1000, 5000]
SHIFTS = [5, 50, 500, 5000]
SQLITE = False
RICH = False      # opaque predicates and derived tables that stress the SQLite planner
FOCUS = False     # more compound queries and more DISTINCT
VALUE_EXT = False # value queries with windows over groups, a DISTINCT arm in a UNION ALL,
                  # INTERSECT / EXCEPT, an outer query over a derived value query (from side
                  # streams: off, the queries are those of earlier runs)
ALIAS = {}        # alias -> table


def tab(alias):
    """The table an alias was made for."""
    return ALIAS.get(alias, alias[:2])


def mk_alias(t, suffix):
    alias = t + suffix
    ALIAS[alias] = t
    return alias


def use_schema(path):
    """Use the tables and numeric columns of a JSON file instead of the sample schema."""
    with open(path) as f:
        schema = json.load(f)
    if not schema or not all(isinstance(c, list) and c for c in schema.values()):
        raise SystemExit('%s: expected {"table": ["column", ...], ...}' % path)
    TABLES.clear(); TABLES.update(schema)
    NUM.clear(); NUM.update(schema)


def use_sqlite():
    """Profile for the SQLite databases of gen_sqlite_db.py: all columns, small
    constants, SQLite compound syntax, only functions old SQLite versions have."""
    global SQLITE, CONSTS, SHIFTS, AGGS, MONO
    SQLITE = True
    cols = {'t1': ['c1', 'c4'], 't2': ['c1', 'c2', 'c3', 'c14', 'c15'],
            't3': ['c1', 'c2', 'c3', 'c6', 'c7', 'c8', 'c9']}
    TABLES.clear(); TABLES.update(cols)
    NUM.clear(); NUM.update(cols)
    CONSTS = [-1, 0, 1, 2, 3, 5, 7, 10]
    SHIFTS = [1, 2, 3]
    AGGS = ['SUM(%s)', 'MIN(%s)', 'MAX(%s)', 'AVG(%s)', 'COUNT(%s)', 'COUNT(DISTINCT %s)']
    MONO = ['ROUND']


def cmp_(rng, aliases):
    a = rng.choice(aliases)
    left = '%s.%s' % (a, rng.choice(TABLES[tab(a)]))
    if rng.random() < 0.35 and len(aliases) > 1:
        b = rng.choice(aliases)
        right = '%s.%s' % (b, rng.choice(TABLES[tab(b)]))
    else:
        right = str(rng.choice(CONSTS))
    return '%s %s %s' % (left, rng.choice(OPS), right)


def col_of(rng, aliases):
    a = rng.choice(aliases)
    return '%s.%s' % (a, rng.choice(TABLES[tab(a)]))


def opaque_pred(rng, aliases):
    """A predicate the model does not analyse: it becomes one opaque atom, which the
    theorems allow because they hold for any deterministic predicate."""
    c = col_of(rng, aliases)
    k = rng.choice(CONSTS)
    forms = [
        "%s LIKE '%s%%'" % (c, rng.choice(['1', 'a', 'A', '0', ''])),
        "%s GLOB '%s*'" % (c, rng.choice(['1', 'a', '0'])),
        '%s BETWEEN %d AND %d' % (c, k, k + rng.choice([0, 1, 3])),
        '%s IN (%s)' % (c, ', '.join(str(rng.choice(CONSTS)) for _ in range(rng.randint(1, 3)))),
        "%s IN ('%d', %d)" % (c, k, rng.choice(CONSTS)),
        '%s IS %s' % (c, rng.choice([str(k), 'NULL', col_of(rng, aliases)])),
        '%s IS NOT %s' % (c, rng.choice([str(k), 'NULL', col_of(rng, aliases)])),
        "CAST(%s AS TEXT) = '%d'" % (c, k),
        'CAST(%s AS INTEGER) = %d' % (c, k),
        "%s = '%d'" % (c, k),
        "%s COLLATE NOCASE = '%s'" % (c, rng.choice(['a', 'A', 'b'])),
        'abs(%s) > %d' % (c, abs(k)),
        '%s + 0 = %d' % (c, k),
        "%s || '' = '%d'" % (c, k),
        'coalesce(%s, %d) > %d' % (c, k, rng.choice(CONSTS)),
        'likely(%s > %d)' % (c, k),
        '(%s > %d) = 1' % (c, k),
    ]
    return rng.choice(forms)


def pred(rng, aliases, depth, outer=()):
    if RICH and rng.random() < 0.3:
        return opaque_pred(rng, list(aliases) + list(outer))
    r = rng.random()
    if depth <= 0 or r < 0.35:
        if rng.random() < 0.15:
            a = rng.choice(aliases)
            return '%s.%s IS NULL' % (a, rng.choice(TABLES[tab(a)]))
        return cmp_(rng, list(aliases) + list(outer))
    if r < 0.55:
        return '(%s AND %s)' % (pred(rng, aliases, depth - 1, outer), pred(rng, aliases, depth - 1, outer))
    if r < 0.70:
        return '(%s OR %s)' % (pred(rng, aliases, depth - 1, outer), pred(rng, aliases, depth - 1, outer))
    if r < 0.80:
        return 'NOT (%s)' % pred(rng, aliases, depth - 1, outer)
    if r < 0.90:
        a = rng.choice(aliases)
        t = rng.choice(list(TABLES))
        alias = mk_alias(t, 'i%d' % rng.randint(0, 99))
        if not SQLITE and rng.random() < 0.25 and len(TABLES[tab(a)]) > 1 and len(TABLES[t]) > 1:
            # (a, b) IN (SELECT x, y ...): row comparison
            inner = pred(rng, [alias], depth - 1, outer=tuple(aliases) + tuple(outer))
            c1, c2 = rng.sample(TABLES[tab(a)], 2)
            d1, d2 = rng.sample(TABLES[t], 2)
            return '(%s.%s, %s.%s) %sIN (SELECT %s.%s, %s.%s FROM %s AS %s WHERE %s)' % (
                a, c1, a, c2, 'NOT ' if rng.random() < 0.5 else '', alias, d1, alias, d2, t, alias, inner)
        inner = pred(rng, [alias], depth - 1, outer=tuple(aliases) + tuple(outer))
        return '%s.%s %sIN (SELECT %s.%s FROM %s AS %s WHERE %s)' % (
            a, rng.choice(TABLES[tab(a)]), 'NOT ' if rng.random() < 0.5 else '',
            alias, rng.choice(TABLES[t]), t, alias, inner)
    t = rng.choice(list(TABLES))
    alias = mk_alias(t, 's%d' % rng.randint(0, 99))
    inner = pred(rng, [alias], depth - 1, outer=tuple(aliases) + tuple(outer))
    return '%sEXISTS (SELECT %s.%s FROM %s AS %s WHERE %s)' % (
        'NOT ' if rng.random() < 0.5 else '', alias, TABLES[t][0], t, alias, inner)


def from_item(rng, t, alias):
    """A table, or (RICH) a derived table over it that exposes the same columns."""
    if not (RICH and rng.random() < 0.3):
        return '%s AS %s' % (t, alias)
    cols = ', '.join('x.%s AS %s' % (c, c) for c in TABLES[t])
    inner = 'SELECT %s%s FROM %s AS x' % ('DISTINCT ' if rng.random() < 0.3 else '', cols, t)
    if rng.random() < 0.6:
        inner += ' WHERE ' + pred(rng, [mk_alias(t, 'x')], 1).replace(t + 'x.', 'x.')
    if rng.random() < 0.3:
        inner += ' UNION ALL SELECT %s FROM %s AS x' % (cols, t)
    return '(%s) AS %s' % (inner, alias)


def select(rng, ncols):
    t = rng.choice(list(TABLES))
    aliases = [mk_alias(t, 'a')]
    sql_from = from_item(rng, t, t + 'a')
    for i in range(rng.choice([0, 0, 1, 1, 2])):
        u = rng.choice(list(TABLES))
        alias = mk_alias(u, 'bcd'[i])
        kind = rng.choice(['INNER JOIN', 'INNER JOIN', 'LEFT JOIN'] + (['CROSS JOIN'] if RICH else []))
        if kind == 'CROSS JOIN':
            sql_from += ' CROSS JOIN %s' % from_item(rng, u, alias)
        else:
            sql_from += ' %s %s ON %s' % (kind, from_item(rng, u, alias), pred(rng, aliases + [alias], 1))
        aliases.append(alias)
    items = []
    for i in range(ncols):
        a = rng.choice(aliases)
        c = '%s.%s' % (a, rng.choice(TABLES[tab(a)]))
        if RICH and rng.random() < 0.2:
            c = rng.choice(['%s + 0', 'CAST(%s AS INTEGER)', "%s || ''", 'abs(%s)', 'coalesce(%s, 0)']) % c
        items.append('%s AS k%d' % (c, i))
    sql = 'SELECT %s%s FROM %s' % ('DISTINCT ' if rng.random() < (0.5 if FOCUS else 0.3) else '',
                                   ', '.join(items), sql_from)
    if rng.random() < 0.85:
        sql += ' WHERE ' + pred(rng, aliases, 2)
    return sql


def query(rng, depth=2):
    ncols = rng.randint(1, 3)

    def go(d):
        if d <= 0 or rng.random() < (0.2 if FOCUS else 0.55):
            return select(rng, ncols)
        # INTERSECT ALL / EXCEPT ALL: MySQL 8.0.31+, MariaDB 10.5+; not in SQLite
        op = rng.choice(['UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT'] +
                        ([] if SQLITE else ['INTERSECT ALL', 'EXCEPT ALL']))
        if SQLITE:
            # SQLite does not allow parentheses around compound operands; compounds
            # are left-associative, so build a left-deep chain
            return '%s %s %s' % (go(d - 1), op, select(rng, ncols))
        return '(%s) %s (%s)' % (go(d - 1), op, go(d - 1))
    return go(depth)


# ---- value queries: one SELECT with aggregates over integer and decimal columns ----
NUM = {'t1': ['c1', 'c4'], 't2': ['c1', 'c2', 'c3', 'c14', 'c15'], 't3': ['c1', 'c2', 'c3', 'c6', 'c7', 'c8', 'c9']}
AGGS = ['SUM(%s)', 'MIN(%s)', 'MAX(%s)', 'AVG(%s)', 'COUNT(%s)', 'COUNT(DISTINCT %s)',
        'VAR_SAMP(%s)', 'STDDEV_SAMP(%s)']
MONO = ['FLOOR', 'CEIL', 'ROUND', 'EXP', 'ATAN', 'SIGN']


def scalar(rng, alias, t):
    c = '%s.%s' % (alias, rng.choice(NUM[t]))
    r = rng.random()
    if r < 0.45:
        return c
    if r < 0.75:      # shifted so that values, sums and averages can be negative
        return '%s - %d' % (c, rng.choice(SHIFTS))
    if r < 0.85:      # small values, so that variances below and above 1 both occur
        return '%s %% %d' % (c, rng.choice([2, 3]))
    return '%s.%s + %s.%s' % (alias, rng.choice(NUM[t]), alias, rng.choice(NUM[t]))


def agg_item(rng, alias, t):
    item = rng.choice(AGGS) % scalar(rng, alias, t)
    r = rng.random()
    if r < 0.15:
        item = '%s + %d' % (item, rng.randint(1, 9))
    elif r < 0.25:
        item = '%s(%s)' % (rng.choice(MONO),
                           'COUNT(%s)' % scalar(rng, alias, t) if rng.random() < 0.5 else item)
        if item.startswith('EXP'):
            item = 'ATAN' + item[3:]          # EXP overflows on large aggregates
    elif r < 0.30:
        item = '%s * %d' % (item, rng.randint(2, 4))
    return item


def having_pred(rng, alias, t, depth):
    r = rng.random()
    if depth <= 0 or r < 0.45:
        left = rng.choice(AGGS[:6]) % scalar(rng, alias, t)
        right = str(rng.choice(CONSTS if SQLITE else [0, 1, 2, 10, 100, 1000, 5000]))
        if rng.random() < 0.2:
            right = rng.choice(AGGS[:5]) % scalar(rng, alias, t)
        return '%s %s %s' % (left, rng.choice(OPS), right)
    if r < 0.65:
        return '(%s AND %s)' % (having_pred(rng, alias, t, depth - 1), having_pred(rng, alias, t, depth - 1))
    if r < 0.80:
        return '(%s OR %s)' % (having_pred(rng, alias, t, depth - 1), having_pred(rng, alias, t, depth - 1))
    if r < 0.90:
        return 'NOT (%s)' % having_pred(rng, alias, t, depth - 1)
    u = rng.choice(list(TABLES))
    ualias = mk_alias(u, 'h%d' % rng.randint(0, 99))
    return '%s %sIN (SELECT %s.%s FROM %s AS %s WHERE %s)' % (
        rng.choice(['COUNT(%s)', 'MIN(%s)', 'MAX(%s)']) % scalar(rng, alias, t),
        'NOT ' if rng.random() < 0.5 else '', ualias, rng.choice(TABLES[u]), u, ualias,
        pred(rng, [ualias], 1))


def _value_query_base(rng):
    t = rng.choice(list(NUM))
    alias = mk_alias(t, 'a')
    where = ''
    if rng.random() < 0.6:
        where = ' WHERE ' + pred(rng, [alias], 1)
    shape = rng.random()
    n = rng.randint(1, 4)
    if shape < 0.25:      # no aggregation
        items = [scalar(rng, alias, t) for _ in range(n)]
        group = ''
    elif shape < 0.45:    # aggregates without GROUP BY
        items = [agg_item(rng, alias, t) for _ in range(n)]
        group = ''
    else:                 # GROUP BY
        keys = ['%s.%s' % (alias, c) for c in rng.sample(NUM[t], min(len(NUM[t]), rng.randint(1, 2)))]
        if rng.random() < 0.4:
            keys = ['%s %% %d' % (keys[0], rng.choice([2, 3, 5]))]   # few, larger groups
        items = keys + [agg_item(rng, alias, t) for _ in range(n)]
        group = ' GROUP BY ' + ', '.join(keys)
    having = ''
    if shape >= 0.25 and rng.random() < 0.5:
        having = ' HAVING ' + having_pred(rng, alias, t, 2)
        if SQLITE and not group:
            # SQLite before 3.39 rejects HAVING without GROUP BY; the predicate is still
            # drawn, so the queries after this one stay those of earlier runs
            having = ''
    if shape < 0.25:
        # 30%: a window function whose value is the same for identical rows (an opaque item
        # of the value query); from a random stream of its own, so the main stream is unchanged
        side = random.Random('window:%s:%s:%s' % (t, where, ','.join(items)))
        if side.random() < 0.3:
            p, o = side.choice(NUM[t]), side.choice(NUM[t])
            items = items + [side.choice([
                'RANK() OVER (PARTITION BY %s.%s ORDER BY %s.%s)' % (alias, p, alias, o),
                'DENSE_RANK() OVER (ORDER BY %s.%s)' % (alias, o),
                'SUM(%s.%s) OVER (PARTITION BY %s.%s)' % (alias, o, alias, p),
                'COUNT(*) OVER (PARTITION BY %s.%s)' % (alias, p),
                'MAX(%s.%s) OVER (PARTITION BY %s.%s ORDER BY %s.%s)' % (alias, o, alias, p, alias, o)])]
    if VALUE_EXT and group:
        # 30%: a window over the groups (VUnion.v: tmutate_frame), over keys and aggregates
        side = random.Random('gwindow:%s:%s:%s' % (t, where, ','.join(items)))
        if side.random() < 0.3:
            o = side.choice(NUM[t])
            items = items + [side.choice([
                'RANK() OVER (ORDER BY MAX(%s.%s))' % (alias, o),
                'DENSE_RANK() OVER (ORDER BY %s)' % keys[0],
                'COUNT(*) OVER ()',
                'MAX(MIN(%s.%s)) OVER (PARTITION BY %s %% 2)' % (alias, o, keys[0])])]
    cols = ', '.join('%s AS k%d' % (item, i) for i, item in enumerate(items))
    return 'SELECT %s FROM %s AS %s%s%s%s' % (cols, t, alias, where, group, having)


def value_query(rng):
    """A value query; 20% of them under SELECT DISTINCT and 10% a UNION of two value
    queries (VDistinct.v).  That choice and the second arm come from a random stream
    seeded by the query text, so the main stream (and every recorded seed) is unchanged."""
    sql = _value_query_base(rng)
    side = random.Random('value-distinct:' + sql)
    x = side.random()
    if x < 0.2:
        return 'SELECT DISTINCT ' + sql[len('SELECT '):]
    if x < 0.3:
        width = sql.count(' AS k')
        for _ in range(20):
            arm = _value_query_base(side)
            if arm.count(' AS k') == width:
                return '%s UNION %s' % (sql, arm)
    if VALUE_EXT:
        # 15%: a SELECT DISTINCT arm next to a plain one (VDistinct.v: meval), 20%: INTERSECT /
        # EXCEPT of two value queries (VSet.v); from a side stream of their own
        ext = random.Random('value-ext:' + sql)
        y = ext.random()
        if y < 0.35:
            width = sql.count(' AS k')
            for _ in range(20):
                arm = _value_query_base(ext)
                if arm.count(' AS k') == width and ' OVER ' not in arm:
                    if y < 0.15:
                        return '%s UNION ALL SELECT DISTINCT %s' % (sql, arm[len('SELECT '):])
                    return '%s %s %s' % (sql, ext.choice(['INTERSECT', 'EXCEPT']), arm)
        elif y < 0.55 and ' OVER ' not in sql:
            # 20%: the value query as a derived table under an outer query that projects,
            # groups or aggregates its columns (VLineage.v): a mutated inner value is
            # followed to the outer result
            width = sql.count(' AS k')
            cols = ['d.k%d' % i for i in range(width)]
            shape = ext.random()
            agg = lambda c: '%s(%s)' % (ext.choice(['SUM', 'MIN', 'MAX', 'AVG']), c)
            if shape < 0.35 or width == 1:
                items = cols[::-1] if shape < 0.2 else [agg(c) for c in cols]
                where = ' WHERE d.k0 IS NOT NULL' if shape < 0.1 and width > 1 else ''
                group = ''
            else:
                items = [cols[0]] + [agg(c) for c in cols[1:]]
                where, group = '', ' GROUP BY d.k0'
            return 'SELECT %s FROM (%s) AS d%s%s' % (', '.join('%s AS c%d' % (x, i) for i, x in enumerate(items)),
                                                    sql, where, group)
    return sql


if __name__ == '__main__':
    if '--sqlite' in sys.argv:
        use_sqlite()
    if '--rich' in sys.argv:
        RICH = True
    if '--focus' in sys.argv:
        FOCUS = True
    if '--value-ext' in sys.argv:
        VALUE_EXT = True
    argv = sys.argv[1:]
    if '--sqlite-seed' in argv:
        # value queries over the columns declared INTEGER or REAL in the database of
        # gen_sqlite_db.py for this seed (a value query that aggregates text is skipped)
        import gen_sqlite_db
        i = argv.index('--sqlite-seed')
        num = {t: c for t, c in gen_sqlite_db.numeric_columns(int(argv[i + 1]), FOCUS).items() if c}
        if num:
            NUM.clear()
            NUM.update(num)
        del argv[i:i + 2]
    if '--schema' in argv:
        i = argv.index('--schema')
        use_schema(argv[i + 1])
        del argv[i:i + 2]
    args = [a for a in argv if a not in ('--value', '--sqlite', '--rich', '--focus', '--value-ext')]
    n = int(args[0])
    rng = random.Random(int(args[1]) if len(args) > 1 else 0)
    for _ in range(n):
        print(value_query(rng) if '--value' in sys.argv else query(rng))
