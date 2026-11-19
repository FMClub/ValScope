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
        if lib_path is None:
            self._py = sqlite3.connect(db_path, isolation_level=None)
            self.version = sqlite3.sqlite_version
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

    def query(self, sql):
        """Rows of a SELECT as a list of tuples; raises on error or step limit."""
        if self._py is not None:
            return [tuple(r) for r in self._py.execute(sql).fetchall()]
        lib, stmt, tail = self.lib, ctypes.c_void_p(), ctypes.c_char_p()
        self._budget[0] = 0
        if lib.sqlite3_prepare_v2(self.db, sql.encode(), -1, ctypes.byref(stmt), ctypes.byref(tail)) != 0:
            raise RuntimeError(lib.sqlite3_errmsg(self.db).decode())
        try:
            n = lib.sqlite3_column_count(stmt)
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
