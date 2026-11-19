"""Generate random queries inside the fragment the verified mutators support
(selection, projection, DISTINCT, inner/left joins, set operations, EXISTS, NOT).

    python3 bridge/gen_fragment.py N [SEED] > queries.sql            # set-semantic fragment
    python3 bridge/gen_fragment.py --value N [SEED] > queries.sql    # value queries (aggregates)
    add --sqlite for the SQLite databases of gen_sqlite_db.py

The schema is the sample schema of the Python generator (tables t1, t2, t3 with
integer columns c1, c2 present in all three)."""
import random
import sys

TABLES = {'t1': ['c1', 'c4'], 't2': ['c1', 'c2'], 't3': ['c1', 'c2', 'c3', 'c6', 'c7', 'c8']}
OPS = ['=', '<>', '<', '<=', '>', '>=']
CONSTS = [1, 5, 20, 50, 100, 1000, 5000]
SHIFTS = [5, 50, 500, 5000]
SQLITE = False
RICH = False      # opaque predicates and derived tables that stress the SQLite planner
FOCUS = False     # more compound queries and more DISTINCT


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
    left = '%s.%s' % (a, rng.choice(TABLES[a[:2]]))
    if rng.random() < 0.35 and len(aliases) > 1:
        b = rng.choice(aliases)
        right = '%s.%s' % (b, rng.choice(TABLES[b[:2]]))
    else:
        right = str(rng.choice(CONSTS))
    return '%s %s %s' % (left, rng.choice(OPS), right)


def col_of(rng, aliases):
    a = rng.choice(aliases)
    return '%s.%s' % (a, rng.choice(TABLES[a[:2]]))


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
            return '%s.%s IS NULL' % (a, rng.choice(TABLES[a[:2]]))
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
        alias = t + 'i%d' % rng.randint(0, 99)
        inner = pred(rng, [alias], depth - 1, outer=tuple(aliases) + tuple(outer))
        return '%s.%s %sIN (SELECT %s.%s FROM %s AS %s WHERE %s)' % (
            a, rng.choice(TABLES[a[:2]]), 'NOT ' if rng.random() < 0.5 else '',
            alias, rng.choice(TABLES[t]), t, alias, inner)
    t = rng.choice(list(TABLES))
    alias = t + 's%d' % rng.randint(0, 99)
    inner = pred(rng, [alias], depth - 1, outer=tuple(aliases) + tuple(outer))
    return '%sEXISTS (SELECT %s.c1 FROM %s AS %s WHERE %s)' % (
        'NOT ' if rng.random() < 0.5 else '', alias, t, alias, inner)


def from_item(rng, t, alias):
    """A table, or (RICH) a derived table over it that exposes the same columns."""
    if not (RICH and rng.random() < 0.3):
        return '%s AS %s' % (t, alias)
    cols = ', '.join('x.%s AS %s' % (c, c) for c in TABLES[t])
    inner = 'SELECT %s%s FROM %s AS x' % ('DISTINCT ' if rng.random() < 0.3 else '', cols, t)
    if rng.random() < 0.6:
        inner += ' WHERE ' + pred(rng, ['x'] if False else [t + 'x'], 1).replace(t + 'x.', 'x.')
    if rng.random() < 0.3:
        inner += ' UNION ALL SELECT %s FROM %s AS x' % (cols, t)
    return '(%s) AS %s' % (inner, alias)


def select(rng, ncols):
    t = rng.choice(list(TABLES))
    aliases = [t + 'a']
    sql_from = from_item(rng, t, t + 'a')
    for i in range(rng.choice([0, 0, 1, 1, 2])):
        u = rng.choice(list(TABLES))
        alias = u + 'bcd'[i]
        kind = rng.choice(['INNER JOIN', 'INNER JOIN', 'LEFT JOIN'] + (['CROSS JOIN'] if RICH else []))
        if kind == 'CROSS JOIN':
            sql_from += ' CROSS JOIN %s' % from_item(rng, u, alias)
        else:
            sql_from += ' %s %s ON %s' % (kind, from_item(rng, u, alias), pred(rng, aliases + [alias], 1))
        aliases.append(alias)
    items = []
    for i in range(ncols):
        a = rng.choice(aliases)
        c = '%s.%s' % (a, rng.choice(TABLES[a[:2]]))
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
        op = rng.choice(['UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT'])
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
    ualias = u + 'h%d' % rng.randint(0, 99)
    return '%s %sIN (SELECT %s.%s FROM %s AS %s WHERE %s)' % (
        rng.choice(['COUNT(%s)', 'MIN(%s)', 'MAX(%s)']) % scalar(rng, alias, t),
        'NOT ' if rng.random() < 0.5 else '', ualias, rng.choice(TABLES[u]), u, ualias,
        pred(rng, [ualias], 1))


def value_query(rng):
    t = rng.choice(list(NUM))
    alias = t + 'a'
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
        keys = ['%s.%s' % (alias, c) for c in rng.sample(NUM[t], rng.randint(1, 2))]
        if rng.random() < 0.4:
            keys = ['%s %% %d' % (keys[0], rng.choice([2, 3, 5]))]   # few, larger groups
        items = keys + [agg_item(rng, alias, t) for _ in range(n)]
        group = ' GROUP BY ' + ', '.join(keys)
    having = ''
    if shape >= 0.25 and rng.random() < 0.5:
        having = ' HAVING ' + having_pred(rng, alias, t, 2)
    cols = ', '.join('%s AS k%d' % (item, i) for i, item in enumerate(items))
    return 'SELECT %s FROM %s AS %s%s%s%s' % (cols, t, alias, where, group, having)


if __name__ == '__main__':
    if '--sqlite' in sys.argv:
        use_sqlite()
    if '--rich' in sys.argv:
        RICH = True
    if '--focus' in sys.argv:
        FOCUS = True
    args = [a for a in sys.argv[1:] if a not in ('--value', '--sqlite', '--rich', '--focus')]
    n = int(args[0])
    rng = random.Random(int(args[1]) if len(args) > 1 else 0)
    for _ in range(n):
        print(value_query(rng) if '--value' in sys.argv else query(rng))
