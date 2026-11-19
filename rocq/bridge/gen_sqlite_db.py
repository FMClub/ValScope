"""Create a random SQLite test database with the schema the query generator uses.

    python3 bridge/gen_sqlite_db.py OUT.db SEED

Tables t1, t2, t3 with the column names of the MariaDB sample schema.  Values are
small (so that joins and comparisons match often), with NULLs, duplicates and a few
negative numbers.  The schema varies with the seed: column affinities, COLLATE
NOCASE, WITHOUT ROWID, plain / unique / partial / expression indexes, ANALYZE.
These are the features that the SQLite query planner treats specially.
"""
import random
import sqlite3
import sys

COLUMNS = {'t1': ['c1', 'c4'], 't2': ['c1', 'c2', 'c3', 'c14', 'c15'],
           't3': ['c1', 'c2', 'c3', 'c6', 'c7', 'c8', 'c9']}


def value(rng, kind):
    if rng.random() < 0.15:
        return 'NULL'
    v = rng.choice([0, 1, 1, 2, 2, 3, 4, 5, 7, 10, -1, -3])
    if kind == 'REAL' and rng.random() < 0.4:
        return repr(v + rng.choice([0.5, 0.25, 0.0]))
    if kind == 'TEXT' and rng.random() < 0.3:
        return "'%s'" % rng.choice(['a', 'A', 'b', 'x', ' 1', '01', ''])
    if kind in ('TEXT', '') and rng.random() < 0.3:
        return "'%d'" % v          # a number stored as text
    return str(v)


def statements(seed):
    """The CREATE / INSERT / CREATE INDEX / ANALYZE statements for one seed."""
    rng = random.Random(seed)
    stmts = []
    kinds = {}
    for t, cols in COLUMNS.items():
        defs = []
        for c in cols:
            kind = rng.choice(['INTEGER', 'INTEGER', 'INTEGER', 'REAL', 'TEXT', ''])
            kinds[(t, c)] = kind
            coll = ' COLLATE NOCASE' if kind == 'TEXT' and rng.random() < 0.5 else ''
            defs.append('%s %s%s' % (c, kind, coll))
        without_rowid = rng.random() < 0.25
        if without_rowid:
            defs.append('rid INTEGER PRIMARY KEY')
        stmts.append('CREATE TABLE %s (%s)%s;' % (t, ', '.join(defs), ' WITHOUT ROWID' if without_rowid else ''))
        for i in range(rng.randint(4, 12)):
            vals = [value(rng, kinds[(t, c)]) for c in cols]
            if without_rowid:
                vals.append(str(i))
            stmts.append('INSERT INTO %s VALUES (%s);' % (t, ', '.join(vals)))
    for i in range(rng.randint(2, 8)):
        t = rng.choice(list(COLUMNS))
        cols = rng.sample(COLUMNS[t], rng.randint(1, min(3, len(COLUMNS[t]))))
        if rng.random() < 0.2:
            cols[0] = '(%s + 1)' % cols[0] if rng.random() < 0.5 else '(%s %% 3)' % cols[0]
        where = ''
        if rng.random() < 0.3:
            c = rng.choice(COLUMNS[t])
            where = rng.choice([' WHERE %s IS NOT NULL' % c, ' WHERE %s > 1' % c, ' WHERE %s <> 0' % c])
        unique = 'UNIQUE ' if rng.random() < 0.15 else ''
        stmts.append('CREATE %sINDEX i%d ON %s (%s)%s;' % (unique, i, t, ', '.join(cols), where))
    if rng.random() < 0.5:
        stmts.append('ANALYZE;')
    return stmts


def build(db, seed):
    """Create the tables in `db` (a sqlite_exec.SQLiteLib).  Statements that fail
    (a UNIQUE index over duplicate data) are skipped.  Returns the statements used."""
    used = []
    for s in statements(seed):
        try:
            db.executescript(s)
            used.append(s)
        except Exception:      # RuntimeError from ctypes, sqlite3.Error from Python's module
            pass
    return used


if __name__ == '__main__':
    con = sqlite3.connect(sys.argv[1])
    for s in statements(int(sys.argv[2])):
        try:
            con.execute(s)
            print(s)
        except sqlite3.Error:
            pass
    con.commit()
