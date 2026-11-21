"""Random databases for campaigns on MySQL-protocol servers (MariaDB, MySQL, ...).

    python3 bridge/gen_mysql_db.py SEED > database.sql        # the statements, for any client

A UNIQUE index is asked for at random and fails when its column has duplicates; build()
skips it, and a client must go on after the error too (`mysql --force`), or the statements
after it are lost and the database is not the one of the campaign.

One seed gives one database: the tables t1, t2, t3 of gen_fragment.py with random column
types (integers, decimals, doubles, text with a case-insensitive or a binary collation,
dates), 5 to 30 rows with NULLs and many duplicates, an optional primary key, random
single-column, composite and unique indexes.  These are the features a query planner
treats specially; the databases are small so that results can be read by hand.

`numeric_columns(seed)` gives, per table, the columns whose type is exact and numeric:
value queries (aggregates) read only those (see campaign_mysql.py).
"""
import random
import sys

COLUMNS = {'t1': ['c1', 'c4'], 't2': ['c1', 'c2', 'c3', 'c14', 'c15'],
           't3': ['c1', 'c2', 'c3', 'c6', 'c7', 'c8', 'c9']}
KINDS = ['INT', 'INT', 'INT', 'BIGINT', 'DECIMAL(10,2)', 'DECIMAL(10,2)', 'DOUBLE',
         'VARCHAR(20) COLLATE utf8mb4_general_ci', 'VARCHAR(20) COLLATE utf8mb4_bin', 'DATE']
EXACT_NUMERIC = ('INT', 'BIGINT', 'DECIMAL(10,2)')
KINDS_OF = {}       # (table, column) -> type, of the last call of statements()


def value(rng, kind):
    if rng.random() < 0.15:
        return 'NULL'
    v = rng.choice([0, 1, 1, 2, 2, 3, 4, 5, 7, 10, -1, -3])
    if kind.startswith('DECIMAL') and rng.random() < 0.4:
        return '%s' % (v + rng.choice([0.5, 0.25, 0.75]))
    if kind == 'DOUBLE' and rng.random() < 0.4:
        return repr(v + rng.choice([0.5, 0.25, 0.1]))
    if kind.startswith('VARCHAR'):
        if rng.random() < 0.6:
            return "'%s'" % rng.choice(['a', 'A', 'b', 'B', 'x', ' 1', '01', '', 'a '])
        return "'%d'" % v
    if kind == 'DATE':
        return "'2024-%02d-%02d'" % (rng.choice([1, 1, 2, 12]), rng.choice([1, 1, 15, 28]))
    return str(v)


def statements(seed):
    """The CREATE TABLE / INSERT / CREATE INDEX / ANALYZE statements for one seed."""
    rng = random.Random('mysql-db:%d' % seed)
    stmts, kinds = [], {}
    for t, cols in COLUMNS.items():
        defs = []
        for c in cols:
            kinds[(t, c)] = rng.choice(KINDS)
            defs.append('%s %s' % (c, kinds[(t, c)]))
        pk = rng.random() < 0.3
        if pk:
            defs.append('rid INT PRIMARY KEY')
        stmts.append('CREATE TABLE %s (%s) ENGINE=InnoDB' % (t, ', '.join(defs)))
        rows = []
        for i in range(rng.randint(5, 30)):
            vals = [value(rng, kinds[(t, c)]) for c in cols]
            if pk:
                vals.append(str(i))
            rows.append('(%s)' % ', '.join(vals))
        stmts.append('INSERT INTO %s VALUES %s' % (t, ', '.join(rows)))
    for i in range(rng.randint(2, 8)):
        t = rng.choice(list(COLUMNS))
        cols = rng.sample(COLUMNS[t], rng.randint(1, min(3, len(COLUMNS[t]))))
        unique = 'UNIQUE ' if rng.random() < 0.15 else ''       # fails on duplicates: then skipped
        stmts.append('CREATE %sINDEX i%d ON %s (%s)' % (unique, i, t, ', '.join(cols)))
    for t in COLUMNS:
        stmts.append('ANALYZE TABLE %s' % t)
    KINDS_OF.clear()
    KINDS_OF.update(kinds)
    return stmts


def numeric_columns(seed):
    """table -> the columns with an exact numeric type (INT, BIGINT, DECIMAL) for this seed."""
    statements(seed)
    return {t: [c for c in cols if KINDS_OF[(t, c)] in EXACT_NUMERIC] for t, cols in COLUMNS.items()}


def build(cursor, database, seed):
    """Drop and create `database` and run the statements of the seed; returns the statements
    that succeeded (a UNIQUE index on duplicates fails and is skipped)."""
    cursor.execute('DROP DATABASE IF EXISTS `%s`' % database)
    cursor.execute('CREATE DATABASE `%s`' % database)
    cursor.execute('USE `%s`' % database)
    used = []
    for s in statements(seed):
        try:
            cursor.execute(s)
            cursor.fetchall()
            used.append(s)
        except Exception:
            pass
    return used


if __name__ == '__main__':
    for s in statements(int(sys.argv[1])):
        print(s + ';')
