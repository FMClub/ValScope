"""The records of SQLite pairs, their databases and their verdicts: one place for the tools that
replay recorded pairs (confirm_sqlite.py, bisect_sqlite.py, reduce_sqlite.py,
scripts/replay_reduced_sqlite.py, scripts/record_sqlite_pairs.py).

A record (a line of results/sqlite-*.jsonl or of campaign_sqlite.py --out) has the two
queries ('original', 'mutant'), the relation ('expect': 'Up', 'Down' or 'REL col N'),
'distinct' (a cover check, VDistinct.v), and its database: either 'database', the statements
of a reduced pair (a list, or the text of one in older files), or 'seed' and 'focus', for
gen_sqlite_db.py.
"""
import ast
import json
import os

from checker import judge, sqlite_fold
from gen_sqlite_db import build
from sqlite_exec import SQLiteLib


def read(*paths):
    """The records of these JSON-lines files, in order; a missing file has none."""
    out = []
    for path in paths:
        if os.path.exists(path):
            with open(path) as f:
                out += [json.loads(line) for line in f if line.strip()]
    return out


def statements_of(rec):
    """The statements of a reduced pair's database, or None for a pair of a seed."""
    d = rec.get('database')
    if d is None:
        return None
    return ast.literal_eval(d) if isinstance(d, str) else list(d)


def focus_of(rec):
    return rec.get('focus') in (True, 'True')


def fresh(lib, path):
    """An empty database file at `path`, opened with the library `lib` (None: Python's)."""
    if path != ':memory:' and os.path.exists(path):
        os.remove(path)
    return SQLiteLib(lib, path)


def build_for(db, rec, compat=False, strict=False):
    """Create the database of the record in `db`; returns the statements that succeeded.
    compat: tables without WITHOUT ROWID (releases before 3.8.2).  strict: a statement of
    a reduced pair that fails raises (the pair would run on another database) instead of
    being skipped; the statements of a seed are always skipped on failure, as in a campaign."""
    stmts = statements_of(rec)
    if stmts is None:
        return build(db, rec['seed'], focus_of(rec), compat=compat)
    used = []
    for st in stmts:
        if compat:
            st = st.replace(') WITHOUT ROWID;', ');')
        try:
            db.executescript(st)
            used.append(st)
        except Exception:
            if strict:
                raise
    return used


def database(lib, path, rec, compat=False, strict=False):
    """(db, statements used) for the record, in a fresh file."""
    db = fresh(lib, path)
    return db, build_for(db, rec, compat=compat, strict=strict)


def verdict(db, rec, used, original=None, mutant=None, expect=None):
    """(verdict, original rows, mutant rows) of the record's pair on `db`, built from `used`.
    The queries and the relation can be replaced (a reduction tries variants).  A query
    that fails gives ('error: ...', None, None).  Strings are compared with the collation
    of each result column where the library reports it, else the coarsest of the schema."""
    original = rec['original'] if original is None else original
    mutant = rec['mutant'] if mutant is None else mutant
    try:
        base = db.query(original)
        collations = db.last_collations
        res = db.query(mutant)
    except Exception as e:
        return 'error: %s' % e, None, None
    fold = db.folds(collations, db.last_collations, sqlite_fold(used))
    v = judge(expect or rec['expect'], base, res, fold=fold, cover=bool(rec.get('distinct')), strict_types=True)
    return v, base, res
