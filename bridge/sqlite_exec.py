"""Execute SQL on a chosen SQLite library (any version) through ctypes.

Python's own sqlite3 module is linked to one SQLite version.  To test old releases,
this module loads a shared library built from that release's amalgamation and calls
the C API directly.  The library path `None` means the SQLite that Python ships.
"""
import ctypes
import sqlite3

SQLITE_ROW, SQLITE_DONE = 100, 101
SQLITE_INTEGER, SQLITE_FLOAT, SQLITE_TEXT, SQLITE_BLOB, SQLITE_NULL = 1, 2, 3, 4, 5
PROGRESS = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)


class SQLiteLib:
    """One SQLite version loaded from a shared library, with one open database."""

    def __init__(self, lib_path, db_path, step_limit=20_000_000):
        self.last_collations = []
        if lib_path is None:
            self._py = sqlite3.connect(db_path, isolation_level=None)
            self.version = sqlite3.sqlite_version
            self.metadata = False
            return
        self._py = None
        lib = ctypes.CDLL(lib_path)
        self.lib = lib
        lib.sqlite3_libversion.restype = ctypes.c_char_p
        self.version = lib.sqlite3_libversion().decode()
        lib.sqlite3_open.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
        lib.sqlite3_prepare_v2.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
                                           ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_char_p)]
        lib.sqlite3_step.argtypes = [ctypes.c_void_p]
        lib.sqlite3_finalize.argtypes = [ctypes.c_void_p]
        lib.sqlite3_column_count.argtypes = [ctypes.c_void_p]
        lib.sqlite3_column_type.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.sqlite3_column_int64.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.sqlite3_column_int64.restype = ctypes.c_int64
        lib.sqlite3_column_double.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.sqlite3_column_double.restype = ctypes.c_double
        lib.sqlite3_column_text.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.sqlite3_column_text.restype = ctypes.c_void_p
        lib.sqlite3_column_blob.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.sqlite3_column_blob.restype = ctypes.c_void_p
        lib.sqlite3_column_bytes.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.sqlite3_errmsg.argtypes = [ctypes.c_void_p]
        lib.sqlite3_errmsg.restype = ctypes.c_char_p
        lib.sqlite3_exec.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p,
                                     ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p)]
        lib.sqlite3_progress_handler.argtypes = [ctypes.c_void_p, ctypes.c_int, PROGRESS, ctypes.c_void_p]
        # column metadata (only in libraries built with SQLITE_ENABLE_COLUMN_METADATA):
        # where a result column comes from, and that column's declared collation
        self.metadata = hasattr(lib, 'sqlite3_column_origin_name')
        if self.metadata:
            for name in ('sqlite3_column_database_name', 'sqlite3_column_table_name',
                         'sqlite3_column_origin_name'):
                getattr(lib, name).argtypes = [ctypes.c_void_p, ctypes.c_int]
                getattr(lib, name).restype = ctypes.c_char_p
            pp = ctypes.POINTER(ctypes.c_char_p)
            ip = ctypes.POINTER(ctypes.c_int)
            lib.sqlite3_table_column_metadata.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p,
                                                          ctypes.c_char_p, pp, pp, ip, ip, ip]
        self.db = ctypes.c_void_p()
        if lib.sqlite3_open(db_path.encode(), ctypes.byref(self.db)) != 0:
            raise RuntimeError('cannot open %s' % db_path)
        # abort runaway queries: the callback is called every 1000 VM steps
        self._budget = [0]
        limit = step_limit // 1000

        def progress(_):
            self._budget[0] += 1
            return 1 if self._budget[0] > limit else 0
        self._progress = PROGRESS(progress)
        lib.sqlite3_progress_handler(self.db, 1000, self._progress, None)

    def executescript(self, sql):
        if self._py is not None:
            self._py.executescript(sql)
            return
        err = ctypes.c_char_p()
        if self.lib.sqlite3_exec(self.db, sql.encode(), None, None, ctypes.byref(err)) != 0:
            raise RuntimeError(err.value.decode() if err.value else 'exec failed')

    def _collation(self, stmt, i):
        """The declared collation of the table column that result column i comes from
        ('BINARY', 'NOCASE', 'RTRIM', ...), or None when it is an expression or unknown."""
        if not self.metadata:
            return None
        lib = self.lib
        origin = lib.sqlite3_column_origin_name(stmt, i)
        if origin is None:
            return None
        dtype, coll = ctypes.c_char_p(), ctypes.c_char_p()
        a, b, c = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        rc = lib.sqlite3_table_column_metadata(self.db, lib.sqlite3_column_database_name(stmt, i),
                                               lib.sqlite3_column_table_name(stmt, i), origin,
                                               ctypes.byref(dtype), ctypes.byref(coll),
                                               ctypes.byref(a), ctypes.byref(b), ctypes.byref(c))
        return coll.value.decode().upper() if rc == 0 and coll.value else None

    def folds(self, collations_a, collations_b, fallback):
        """Folds (checker.py) for comparing results whose columns have these collations
        ('BINARY', 'NOCASE', 'RTRIM' or a combination such as 'NOCASE+RTRIM');
        `fallback` (the coarsest collation of the database) where one is unknown."""
        from checker import SQLiteFold
        known = {'BINARY', 'NOCASE', 'RTRIM'}
        out = []
        for a, b in zip(collations_a or [], collations_b or []):
            pa = set(a.split('+')) if a else None
            pb = set(b.split('+')) if b else None
            if not pa or not pb or not pa <= known or not pb <= known:
                out.append(fallback)
            else:
                parts = sorted((pa | pb) - {'BINARY'})
                out.append(SQLiteFold('+'.join(parts) or 'BINARY'))
        return out or fallback

    def _statement_collations(self, sql):
        """Collations of the result columns of one statement (prepared, not run)."""
        lib, stmt, tail = self.lib, ctypes.c_void_p(), ctypes.c_char_p()
        if lib.sqlite3_prepare_v2(self.db, sql.encode(), -1, ctypes.byref(stmt), ctypes.byref(tail)) != 0:
            return None
        try:
            return [self._collation(stmt, i) for i in range(lib.sqlite3_column_count(stmt))]
        finally:
            lib.sqlite3_finalize(stmt)

    def _query_collations(self, sql, reported):
        """The metadata of a compound query names the source column of its LEFTMOST arm
        only, but another arm can de-duplicate under a coarser collation (a DISTINCT over a
        NOCASE column), so the values of the result are determined only up to the
        coarsest collation of all arms.  For a compound at the top, every arm is prepared
        on its own and the collations are combined; when a compound is nested inside a
        derived table, a CTE or a subquery, the metadata is not used (None: the checker
        falls back to the coarsest collation of the database)."""
        try:
            import sqlglot
            from sqlglot import exp
            tree = sqlglot.parse_one(sql, read='sqlite')
        except Exception:
            return [None] * len(reported)
        setops = (exp.Union, exp.Intersect, exp.Except)
        top = tree
        arms = []

        def flatten(n):
            if isinstance(n, setops):
                flatten(n.left)
                flatten(n.right)
            else:
                arms.append(n)
        if isinstance(top, setops):
            flatten(top)
        chain = {id(n) for n in _chain(top, setops)}
        if any(isinstance(n, setops) and id(n) not in chain for n in tree.walk()):
            return [None] * len(reported)
        if not arms:
            return reported
        with_ = top.args.get('with')
        prefix = with_.sql(dialect='sqlite') + ' ' if with_ is not None else ''
        combined = None
        for arm in arms:
            cols = self._statement_collations(prefix + _strip_parens(arm).sql(dialect='sqlite'))
            if cols is None or len(cols) != len(reported):
                return [None] * len(reported)
            if combined is None:
                combined = [None if c is None else {c} for c in cols]
            else:
                combined = [None if a is None or c is None else a | {c} for a, c in zip(combined, cols)]
        return [None if c is None else ('+'.join(sorted(c - {'BINARY'})) or 'BINARY') for c in combined]

    def query(self, sql):
        """Rows of a SELECT as a list of tuples; raises on error or step limit."""
        if self._py is not None:
            cur = self._py.execute(sql)
            rows = [tuple(r) for r in cur.fetchall()]
            self.last_collations = [None] * len(cur.description or [])
            return rows
        lib, stmt, tail = self.lib, ctypes.c_void_p(), ctypes.c_char_p()
        self._budget[0] = 0
        if lib.sqlite3_prepare_v2(self.db, sql.encode(), -1, ctypes.byref(stmt), ctypes.byref(tail)) != 0:
            raise RuntimeError(lib.sqlite3_errmsg(self.db).decode())
        try:
            n = lib.sqlite3_column_count(stmt)
            self.last_collations = [self._collation(stmt, i) for i in range(n)]
            if self.metadata and any(w in sql.upper() for w in ('UNION', 'INTERSECT', 'EXCEPT')):
                self.last_collations = self._query_collations(sql, self.last_collations)
            rows = []
            while True:
                rc = lib.sqlite3_step(stmt)
                if rc == SQLITE_DONE:
                    return rows
                if rc != SQLITE_ROW:
                    raise RuntimeError(lib.sqlite3_errmsg(self.db).decode())
                row = []
                for i in range(n):
                    t = lib.sqlite3_column_type(stmt, i)
                    if t == SQLITE_INTEGER:
                        row.append(lib.sqlite3_column_int64(stmt, i))
                    elif t == SQLITE_FLOAT:
                        row.append(lib.sqlite3_column_double(stmt, i))
                    elif t == SQLITE_TEXT:
                        p, k = lib.sqlite3_column_text(stmt, i), lib.sqlite3_column_bytes(stmt, i)
                        row.append(ctypes.string_at(p, k).decode('utf-8', 'replace'))
                    elif t == SQLITE_BLOB:
                        p, k = lib.sqlite3_column_blob(stmt, i), lib.sqlite3_column_bytes(stmt, i)
                        row.append(ctypes.string_at(p, k) if k else b'')
                    else:
                        row.append(None)
                rows.append(tuple(row))
        finally:
            lib.sqlite3_finalize(stmt)


def _chain(top, setops):
    """The set operations of the compound at the top (not those nested in its arms)."""
    out = []

    def walk(n):
        if isinstance(n, setops):
            out.append(n)
            walk(n.left)
            walk(n.right)
    walk(top)
    return out


def _strip_parens(n):
    from sqlglot import exp
    while isinstance(n, (exp.Paren, exp.Subquery)) and n.args.get('alias') is None:
        n = n.this
    return n
