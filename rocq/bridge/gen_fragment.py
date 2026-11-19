"""Generate random queries inside the fragment the verified mutators support
(selection, projection, DISTINCT, inner/left joins, set operations, EXISTS, NOT).

    python3 bridge/gen_fragment.py N [SEED] > queries.sql

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
    if r < 0.82:
        return 'NOT (%s)' % pred(rng, aliases, depth - 1, outer)
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


if __name__ == '__main__':
    n = int(sys.argv[1])
    rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 0)
    for _ in range(n):
        print(query(rng))
