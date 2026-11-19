"""Generate random queries inside the fragment the verified mutators support
(selection, projection, DISTINCT, inner/left joins, set operations, EXISTS, NOT).

    python3 bridge/gen_fragment.py N [SEED] > queries.sql            # set-semantic fragment
    python3 bridge/gen_fragment.py --value N [SEED] > queries.sql    # value queries (aggregates)

The schema is the sample schema of the Python generator (tables t1, t2, t3 with
integer columns c1, c2 present in all three)."""
import random
import sys

TABLES = {'t1': ['c1', 'c4'], 't2': ['c1', 'c2'], 't3': ['c1', 'c2', 'c3', 'c6', 'c7', 'c8']}
OPS = ['=', '<>', '<', '<=', '>', '>=']


def cmp_(rng, aliases):
    a = rng.choice(aliases)
    left = '%s.%s' % (a, rng.choice(TABLES[a[:2]]))
    if rng.random() < 0.35 and len(aliases) > 1:
        b = rng.choice(aliases)
        right = '%s.%s' % (b, rng.choice(TABLES[b[:2]]))
    else:
        right = str(rng.choice([1, 5, 20, 50, 100, 1000, 5000]))
    return '%s %s %s' % (left, rng.choice(OPS), right)


def pred(rng, aliases, depth, outer=()):
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


def select(rng, ncols):
    t = rng.choice(list(TABLES))
    aliases = [t + 'a']
    sql_from = '%s AS %sa' % (t, t)
    for i in range(rng.choice([0, 0, 1, 1, 2])):
        u = rng.choice(list(TABLES))
        alias = u + 'bcd'[i]
        kind = rng.choice(['INNER JOIN', 'INNER JOIN', 'LEFT JOIN'])
        sql_from += ' %s %s AS %s ON %s' % (kind, u, alias, pred(rng, aliases + [alias], 1))
        aliases.append(alias)
    items = []
    for i in range(ncols):
        a = rng.choice(aliases)
        items.append('%s.%s AS k%d' % (a, rng.choice(TABLES[a[:2]]), i))
    sql = 'SELECT %s%s FROM %s' % ('DISTINCT ' if rng.random() < 0.3 else '', ', '.join(items), sql_from)
    if rng.random() < 0.85:
        sql += ' WHERE ' + pred(rng, aliases, 2)
    return sql


def query(rng, depth=2):
    ncols = rng.randint(1, 3)

    def go(d):
        if d <= 0 or rng.random() < 0.55:
            return select(rng, ncols)
        op = rng.choice(['UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT'])
        return '(%s) %s (%s)' % (go(d - 1), op, go(d - 1))
    return go(depth)


# ---- value queries: one SELECT with aggregates over integer and decimal columns ----
NUM = {'t1': ['c1', 'c4'], 't2': ['c1', 'c2', 'c3', 'c14', 'c15'], 't3': ['c1', 'c2', 'c3', 'c6', 'c7', 'c8', 'c9']}
AGGS = ['SUM(%s)', 'MIN(%s)', 'MAX(%s)', 'AVG(%s)', 'COUNT(%s)', 'COUNT(DISTINCT %s)',
        'VAR_SAMP(%s)', 'STDDEV_SAMP(%s)']


def scalar(rng, alias, t):
    c = '%s.%s' % (alias, rng.choice(NUM[t]))
    r = rng.random()
    if r < 0.45:
        return c
    if r < 0.75:      # shifted so that values, sums and averages can be negative
        return '%s - %d' % (c, rng.choice([5, 50, 500, 5000]))
    if r < 0.85:      # small values, so that variances below and above 1 both occur
        return '%s %% %d' % (c, rng.choice([2, 3]))
    return '%s.%s + %s.%s' % (alias, rng.choice(NUM[t]), alias, rng.choice(NUM[t]))


def agg_item(rng, alias, t):
    item = rng.choice(AGGS) % scalar(rng, alias, t)
    r = rng.random()
    if r < 0.15:
        item = '%s + %d' % (item, rng.randint(1, 9))
    elif r < 0.25:
        item = '%s(%s)' % (rng.choice(['FLOOR', 'CEIL', 'ROUND', 'EXP', 'ATAN', 'SIGN']),
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
        right = str(rng.choice([0, 1, 2, 10, 100, 1000, 5000]))
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
    args = [a for a in sys.argv[1:] if a != '--value']
    n = int(args[0])
    rng = random.Random(int(args[1]) if len(args) > 1 else 0)
    for _ in range(n):
        print(value_query(rng) if '--value' in sys.argv else query(rng))
