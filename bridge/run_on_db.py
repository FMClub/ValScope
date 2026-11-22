"""Run the verified mutators on a file of SQL queries against an existing database.

    # a MySQL-protocol server (MySQL, MariaDB, Percona, TiDB, OceanBase, PolarDB, ...)
    python3 bridge/run_on_db.py QUERIES.sql [--value] --host H --port P --user U --password W --database D

    # an SQLite database file, with the SQLite that Python ships or with a given library
    python3 bridge/run_on_db.py QUERIES.sql [--value] --sqlite FILE.db [--sqlite-lib libsqlite3.so]

QUERIES.sql has one query per line (lines starting with `--` and `USE` are skipped).
For every query in the supported fragment:
1. translation validation: the query as written and the query re-printed from its
   algebra term must return the same bag of rows; otherwise the bridge did not
   preserve the query and it is not used;
2. each mutant is executed and the relation promised by its rule is checked
   (bag inclusion, or with --value the value relation on the mutated column),
   modulo the equality of the database's collation (see checker.py).

A violation is a candidate DBMS bug, or a gap between the SQL model and the DBMS.
With --out, violations are also written as JSON lines.
"""
import argparse
import collections
import json
import os
import re
import sys
from types import SimpleNamespace as types_ns

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sql_bridge  # noqa: E402
from sql_bridge import mutate_sql, mutate_value, Unsupported  # noqa: E402
from checker import check_inclusion, check_value, comparable_types, MariaDBColumns, mariadb_fold, sqlite_fold  # noqa: E402


ERRORS = collections.Counter()
# messages of errors that are the server's own fault, not the query's: the first query of each
INTERNAL_ERROR = re.compile(r"can't find column|internal error|assertion|unexpected|index out of range|"
                            r"runtime error|nil pointer|lost connection", re.IGNORECASE)
INTERNAL = {}
# PolarDB-X starts every message with '[request id][host:port][database]': not part of the error
REQUEST_ID = re.compile(r'^(\[[^\]]*\])+\s*')


class MySQLTarget:
    """A server that speaks the MySQL protocol."""
    dialect = 'mysql'
    APPROXIMATE_TYPES = {4, 5}      # pymysql FIELD_TYPE.FLOAT, FIELD_TYPE.DOUBLE
    DECIMAL_TYPES = {0, 246}        # pymysql FIELD_TYPE.DECIMAL, FIELD_TYPE.NEWDECIMAL
    SINGLE = 4
    # client errors that mean the server is gone, not that the query is wrong
    CONNECTION_LOST = {2003, 2006, 2013, 2055}

    def __init__(self, args):
        import pymysql
        self.pymysql = pymysql
        self.conn = pymysql.connect(host=args.host, port=args.port, user=args.user, password=args.password,
                                    database=args.database, charset='utf8mb4', autocommit=True)
        # (a column that is neither grouped nor aggregated would take its value from any row
        # of the group; the bridge rejects such queries.  ONLY_FULL_GROUP_BY is not set:
        # MariaDB's also rejects determined expressions such as LN(c) + 3 with GROUP BY LN(c).)
        # the collation of every result column, reported by the server (checker.py)
        self.columns = MariaDBColumns(self.conn, mariadb_fold(self.conn, args.database))
        self.name = 'per result column (server metadata)'
        self.trusted_collations = self._metadata_reports_collations()
        if not self.trusted_collations:
            self.name = 'the coarsest collation of the database (the server does not report collations of result columns)'
        self.last_collations = []
        self.last_arm_mix = set()
        self.last_mixed_columns = set()
        # table -> columns, for printing DISTINCT around a join (sql_bridge._join_columns)
        with self.conn.cursor() as cur:
            cur.execute('SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS '
                        'WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION', (args.database,))
            self.schema = {}
            for t, c in cur.fetchall():
                t, c = (x.decode() if isinstance(x, bytes) else x for x in (t, c))
                self.schema.setdefault(t, []).append('`%s`' % c if not c.isidentifier() else c)
            # columns of an integer type in every table that has them (collation law)
            cur.execute('SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS '
                        'WHERE TABLE_SCHEMA = %s', (args.database,))
            exact, other, by_table = set(), set(), {}
            for t, c, ty in cur.fetchall():
                t, c, ty = (x.decode() if isinstance(x, bytes) else x for x in (t, c, ty))
                if ty.lower() in ('tinyint', 'smallint', 'mediumint', 'int', 'integer', 'bigint'):
                    exact.add(c.lower())
                    by_table[(t.lower(), c.lower())] = 'integer'
                else:
                    other.add(c.lower())
            from sql_bridge import ExactColumns
            self.exact = ExactColumns({c: 'integer' for c in exact - other})
            self.exact.by_table = by_table

    def folds(self, collations_a, collations_b):
        return self.columns.folds(collations_a, collations_b)

    def run(self, sql):
        """(rows, column types), or (None, None) when the query fails.  The collations
        of the result columns are left in self.last_collations."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                rows = list(cur.fetchall())
                self.last_collations = [self.columns.name(f.charsetnr) for f in cur._result.fields]
                types = [d[1] for d in cur.description]
                self.last_scales = [d[5] for d in cur.description]
            self.last_arm_mix = set()
            self.last_mixed_columns = set()
            compound = any(w in sql.upper() for w in ('UNION', 'INTERSECT', 'EXCEPT'))
            if compound:
                # also when the collations are not trusted: the arms' types are (last_arm_mix)
                self.last_collations = self._compound_collations(sql, self.last_collations)
            if not self.trusted_collations:
                text = [n != 'binary' for n in self.last_collations]
                self.last_collations = [MariaDBColumns.COARSEST if t else 'binary' for t in text]
                if compound and any(text) and any(w in sql.upper() for w in ('INTERSECT', 'EXCEPT')):
                    # the arms' collations are unknown: which rows match may depend on the
                    # representative a de-duplication kept (as for 'collations' above)
                    self.last_arm_mix.add('collations')
            return rows, types
        except self.pymysql.err.MySQLError as e:
            code = e.args[0] if e.args else None
            if code in self.CONNECTION_LOST or isinstance(e, self.pymysql.err.InterfaceError):
                sys.exit('connection to the server lost (%s); the run is stopped' % (e,))
            message = REQUEST_ID.sub('', str(e.args[1] if len(e.args) > 1 else e))
            ERRORS['%s %s' % (code, message[:70])] += 1
            if INTERNAL_ERROR.search(message) and message not in INTERNAL:
                INTERNAL[message] = sql        # a valid query the server cannot run (issues/017)
            return None, None
        except (ValueError, TypeError, UnicodeDecodeError, OverflowError) as e:
            # the driver could not convert a value the server sent (PolarDB-X): the query is
            # counted as failed, and the connection, left in the middle of a result, is opened
            # again with the session setting the column metadata depends on
            ERRORS['driver: %s %s' % (type(e).__name__, str(e)[:60])] += 1
            if 'driver: ' + type(e).__name__ not in INTERNAL:
                INTERNAL['driver: ' + type(e).__name__] = sql
            self.conn.close()
            self.conn.connect()
            with self.conn.cursor() as cur:
                cur.execute('SET character_set_results = NULL')
            return None, None

    def _metadata_reports_collations(self):
        """Whether the server reports the collation of a result column in its metadata.
        TiDB (v7.5, v8.5) reports utf8mb4_bin for every text column whatever its collation
        (scripts/probe_collations.py); the checker would then compare 'a' and 'A' of a
        case-insensitive column as different strings.  Checked on two literals."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT _utf8mb4'a' COLLATE utf8mb4_general_ci, _utf8mb4'a' COLLATE utf8mb4_bin")
                cur.fetchall()
                got = [self.columns.name(f.charsetnr) for f in cur._result.fields]
        except self.pymysql.err.MySQLError:
            return True
        return got == ['utf8mb4_general_ci', 'utf8mb4_bin']

    NUMERIC_CODES = {0, 1, 2, 3, 4, 5, 8, 9, 13, 16, 246}     # pymysql FIELD_TYPE: integers, DECIMAL, FLOAT, DOUBLE, YEAR, BIT

    def _compound_collations(self, sql, names):
        """The server reports for a compound column the collation it derives from all
        arms (MariaDB: that of the first arm in practice), but an arm can de-duplicate
        under a coarser collation (DISTINCT over a _ci column) and keep either of two
        equivalent strings.  Per column the coarsest of the arms' collations is used;
        for a compound nested in a derived table or a CTE, the coarsest collation of the
        database (MariaDBColumns.COARSEST).

        Two things about the arms make a result that no fold repairs; they are left in
        self.last_arm_mix for arm_mix_verdict():
        - 'types': a column is a number in one arm and text or a date in another.  The
          server turns the numbers into text, and how ('5' or '5.00', '0' or '0.00') depends
          on which arms it combines first and on whether an arm is materialized (a
          DISTINCT), which a mutation changes;
        - 'collations': an INTERSECT or EXCEPT compares a column that has a case-insensitive
          collation in one arm and another collation in another arm.  When the arm
          de-duplicates ('a' or 'A' is kept) and the comparison is made under the finer
          collation, WHICH rows match depends on the representative."""
        coarsest = [MariaDBColumns.COARSEST] * len(names)
        try:
            import sqlglot
            from sqlglot import exp
            tree = sqlglot.parse_one(sql, read='mysql')
        except Exception:
            return coarsest
        setops = (exp.Union, exp.Intersect, exp.Except)
        chain, arms = [], []

        def flatten(n):
            while isinstance(n, (exp.Paren, exp.Subquery)) and not n.alias and isinstance(n.this, setops + (exp.Paren, exp.Subquery)):
                n = n.this
            if isinstance(n, setops):
                chain.append(id(n))
                flatten(n.left)
                flatten(n.right)
            else:
                arms.append(n)
        flatten(tree)
        # a compound inside a derived table or a CTE: its arms are not probed, so the
        # collations are the coarsest; the arms of the compound at the top still are
        nested = any(isinstance(n, setops) and id(n) not in chain for n in tree.walk())
        compares = any(isinstance(n, (exp.Intersect, exp.Except)) and id(n) in chain for n in tree.walk())
        if not chain:
            return coarsest if nested else names
        with_ = tree.args.get('with')
        prefix = with_.sql(dialect='mysql') + ' ' if with_ is not None else ''
        combined = [{n} for n in names]
        codes = [set() for _ in names]
        for arm in arms:
            while isinstance(arm, (exp.Paren, exp.Subquery)) and arm.args.get('alias') is None:
                arm = arm.this
            probe = '%sSELECT * FROM (%s) AS vs_arm LIMIT 0' % (prefix, arm.sql(dialect='mysql'))
            cache = self.__dict__.setdefault('_arm_cache', {})
            if probe not in cache:      # the same arm recurs in the original and its mutants
                try:
                    with self.conn.cursor() as cur:
                        cur.execute(probe)
                        cur.fetchall()
                        cache[probe] = [(self.columns.name(f.charsetnr), f.type_code) for f in cur._result.fields]
                except self.pymysql.err.MySQLError:
                    cache[probe] = None
            got = cache[probe]
            if got is None:
                return coarsest
            if len(got) != len(names):
                return coarsest
            for c, f, (g, code) in zip(combined, codes, got):
                c.add(g)
                f.add(code)
        out = []
        for i, f in enumerate(codes):
            numbers = f & self.NUMERIC_CODES
            # 6: the type of a bare NULL.  16: BIT, which the servers do not print as a
            # number (issues/005 is found through such a compound and must stay visible)
            if numbers - {16} and f - numbers - {6}:
                self.last_arm_mix.add('types')
                self.last_mixed_columns.add(i)
        for c in combined:
            insensitive = [n for n in c if n and ('_ci' in n or '_ai' in n)]
            if compares and insensitive and len({n for n in c if n != 'binary'}) > 1:
                self.last_arm_mix.add('collations')
            if len(c) == 1:
                out.append(next(iter(c)))
            elif len(insensitive) == 1 and all(n and n.endswith('_bin') or n == 'binary' or n in insensitive
                                               for n in c):
                out.append(insensitive[0])      # one coarse collation over exact ones
            else:
                out.append(MariaDBColumns.COARSEST)
        return coarsest if nested else out


class SQLiteTarget:
    """An SQLite database file."""
    dialect = 'sqlite'

    def __init__(self, args):
        from sqlite_exec import SQLiteLib
        if not os.path.exists(args.sqlite):
            sys.exit('no such database file: %s' % args.sqlite)
        self.db = SQLiteLib(args.sqlite_lib, args.sqlite)
        schema = [r[0] for r in self.db.query("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")]
        # the coarsest collation of the database, for columns whose collation is unknown
        self.fallback = sqlite_fold(schema)
        self.name = 'per result column where SQLite reports it, else %s' % self.fallback.name
        self.last_collations = []
        self.schema = sqlite_schema(self.db)
        self.exact = sqlite_exact_columns(self.db, self.schema)

    def folds(self, collations_a, collations_b):
        return self.db.folds(collations_a, collations_b, self.fallback)

    def run(self, sql):
        try:
            rows = self.db.query(sql)
            self.last_collations = self.db.last_collations
            return rows, None
        except Exception as e:      # RuntimeError (ctypes library) or sqlite3.Error
            ERRORS[str(e)[:70]] += 1
            return None, None


def sqlite_schema(db):
    """table -> columns of an SQLite database (sqlite_exec.SQLiteLib)."""
    schema = {}
    for (t,) in db.query("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
        schema[t] = [r[1] for r in db.query("PRAGMA table_info('%s')" % t.replace("'", "''"))]
    return schema


def sqlite_exact_columns(db, schema):
    """Column name -> storage classes, for the columns whose equivalent values are identical
    in every table that has them (sql_bridge._exact_names); `by_table` per (table, column).
    A column qualifies when it does not mix integers with reals (1 = 1.0), holds no -0.0, and
    holds text only under the BINARY collation (NOCASE and RTRIM make 'a' = 'A', 'a' = 'a ').
    The value is the set of storage classes, as a sorted text ('integer', 'integer+text', ...)."""
    import re
    collations = {}
    for name, sql in db.query("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"):
        body = sql[sql.index('(') + 1:sql.rindex(')')]
        for part in body.split(','):
            m = re.match(r'\s*"?(\w+)"?\s', part + ' ')
            if m:
                c = re.search(r'COLLATE\s+(\w+)', part, re.I)
                collations[(name.lower(), m.group(1).lower())] = c.group(1).upper() if c else 'BINARY'
    classes, by_table = {}, {}
    for t, cols in schema.items():
        for c in cols:
            qt, qc = t.replace('"', '""'), c.replace('"', '""')
            kinds = {r[0] for r in db.query('SELECT DISTINCT typeof("%s") FROM "%s" WHERE "%s" IS NOT NULL'
                                             % (qc, qt, qc))}
            k = None
            ok = not {'integer', 'real'} <= kinds and \
                ('text' not in kinds or collations.get((t.lower(), c.lower()), 'BINARY') == 'BINARY') and \
                not ('real' in kinds and db.query("SELECT 1 FROM \"%s\" WHERE typeof(\"%s\") = 'real' AND \"%s\" = 0 "
                                                   "AND CAST(\"%s\" AS TEXT) LIKE '-%%' LIMIT 1" % (qt, qc, qc, qc)))
            if ok:
                k = '+'.join(sorted(kinds)) or 'null'
            classes.setdefault(c.lower(), set()).add(k)
            if k is not None:
                by_table[(t.lower(), c.lower())] = k
    from sql_bridge import ExactColumns
    out = ExactColumns({c: next(iter(ks)) for c, ks in classes.items() if len(ks) == 1 and None not in ks})
    out.by_table = by_table
    return out


FLIP_VALUE = {'Le': 'Ge', 'Ge': 'Le', 'TowardOne': 'AwayOne', 'AwayOne': 'TowardOne'}


def collation_can_explain(base, res):
    """Whether the difference between two results can come from which representative a
    de-duplication kept: some row that is in one result and not in the other (as a multiset)
    has a string that another string can be equal to under a case- or accent-insensitive,
    PAD SPACE collation (a letter, a trailing space, a non-ASCII character).  A difference
    in rows of numbers or digits alone cannot (round 18: the TiDB pair of seed 6)."""
    a, b = collections.Counter(base), collections.Counter(res)
    for row in (a - b) + (b - a):
        for v in row:
            if isinstance(v, (bytes, bytearray)):
                try:
                    v = bytes(v).decode('utf-8')
                except UnicodeDecodeError:
                    return True
            if isinstance(v, str) and (v != v.rstrip() or not v.isascii()
                                       or any(c.isalpha() for c in v)):
                return True
    return False


def arm_mix_verdict(verdict, *mixes):
    """A violation of a compound whose INTERSECT / EXCEPT compares mixed collations is
    'collation' (MySQLTarget._compound_collations); `mixes` are the last_arm_mix of the
    original and of the mutant.  (Mixed types are handled by rejudge, per column.)"""
    if verdict in ('ok', 'incomparable', 'collation'):
        return verdict
    return 'collation' if any('collations' in (m or ()) for m in mixes) else verdict


STEP_OF_INEXACT = re.compile(r'\b(FLOOR|CEIL|CEILING|ROUND|TRUNCATE|SIGN)\s*\(\s*\(*\s*(VAR_SAMP|VAR_POP|VARIANCE|STDDEV\w*|STD)\s*\(',
                             re.IGNORECASE)


def step_columns(sql):
    """The result columns that are a step function of a variance or a standard deviation in
    some arm of the query: binary floats summed in the order of the plan, so that
    CEIL(1.0000000000000002) is 2 where CEIL(1.0) is 1 (a pair of the campaign on MySQL 9)."""
    if not STEP_OF_INEXACT.search(sql):
        return set()
    try:
        import sqlglot
        from sqlglot import exp
        tree = sqlglot.parse_one(sql, read='mysql')
    except Exception:
        return set()
    out, todo = set(), [tree]
    while todo:
        n = todo.pop()
        if isinstance(n, (exp.Union, exp.Intersect, exp.Except)):
            todo += [n.left, n.right]
        elif isinstance(n, (exp.Paren, exp.Subquery)) and not n.alias:
            todo.append(n.this)
        elif isinstance(n, exp.Select):
            out |= {i for i, e in enumerate(n.expressions) if STEP_OF_INEXACT.search(e.sql(dialect='mysql'))}
    return out


def _soften(rows, mixed, steps):
    """The rows with the columns a server may render differently made comparable: in a
    `mixed` column (a number in one arm, text in another) a text that is a number is that
    number ('5' and '5.00' are 5); a `steps` column is dropped (NULL)."""
    from decimal import Decimal, InvalidOperation
    out = []
    for row in rows:
        r = list(row)
        for i in mixed:
            v = r[i]
            if isinstance(v, (bytes, bytearray)):
                try:
                    v = bytes(v).decode('utf-8')
                except UnicodeDecodeError:
                    continue
            if isinstance(v, str):
                try:
                    r[i] = Decimal(v.strip())
                except InvalidOperation:
                    pass
        for i in steps:
            r[i] = None
        out.append(tuple(r))
    return out


def _is_set(rows):
    try:
        return len(set(rows)) == len(rows)
    except TypeError:
        return False


def _unique(rows):
    out, seen = [], set()
    for r in rows:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def rejudge(verdict, check, base, res, mixed=(), steps=(), column=None):
    """A violation judged again with the columns of `mixed` and `steps` made comparable
    (_soften): 'incomparable' if it holds then, the violation itself otherwise.  `check`
    judges two results; `column` (a value check) is never dropped.  This replaces two rules
    that turned a whole pair 'incomparable' and hid issues 012 and 013 (round 16)."""
    steps = set(steps) - {column}
    if verdict in ('ok', 'incomparable', 'collation') or not (mixed or steps):
        return verdict
    soft_base, soft_res = _soften(base, mixed, steps), _soften(res, mixed, steps)
    if column is None and mixed and _is_set(base) and _is_set(res):
        # both results are sets, and the server de-duplicated by the text it wrote: rows that
        # differ only in how a number is written ('0', '0.00') were kept apart in one result
        # and merged in the other (the TiDB and MySQL 9 pair of seed 7, round 18)
        soft_base, soft_res = _unique(soft_base), _unique(soft_res)
    again = check(soft_base, soft_res)
    if again not in ('ok', 'collation'):
        return verdict
    for i in steps:
        # a step function moves by one step at a boundary, not more: the sorted values of
        # the column differ by at most 1, one by one
        a = sorted(float(r[i]) for r in base if r[i] is not None)
        b = sorted(float(r[i]) for r in res if r[i] is not None)
        if len(a) != len(b) or any(abs(x - y) > 1 + 1e-9 for x, y in zip(a, b)):
            return verdict
    return 'incomparable'


def printed_decimals(target, column, base_types, types, base_scales, rows=(), scales=None):
    """The number of decimals after which the mutated column may differ by one unit, or
    None.  The server rounds a binary float printed with a fixed number of decimals, and a
    DECIMAL (the result of a division: AVG) to its scale; when the two results round at
    different places the relation holds only up to one unit of the coarser one.  (Two
    DECIMALs of one scale are rounded alike, and rounding is monotone: no tolerance.)
    `scales` are those of the mutant (default: target.last_scales), `base_scales` those of the original.
    `rows`: the two results; a number of decimals is used only if the values of the result
    that reports it have no more (TiDB reports 0 decimals for an unrounded STDDEV_SAMP)."""
    if scales is None:
        scales = getattr(target, 'last_scales', None)
    if types is None or not base_scales or not scales:
        return None
    pair, both = {base_types[column], types[column]}, (base_scales[column], scales[column])
    printed = [d for d in both if d is not None and d < 31]
    if pair & set(target.APPROXIMATE_TYPES):
        d = min(printed) if printed else None
    elif pair <= set(getattr(target, 'DECIMAL_TYPES', ())) and len(set(printed)) == 2:
        d = min(printed)
    else:
        return None
    for scale, result in zip(both, rows):
        if scale != d:
            continue            # the other result is not rounded there; its values may have more
        for row in result or ():
            v = row[column]
            if isinstance(v, float) and abs(v - round(v, d)) > 1e-9 * max(1.0, abs(v)):
                return None
    return d


def capture(target, sql):
    """Run `sql` and keep what a judgement needs of its result, or None if it failed."""
    rows, types = target.run(sql)
    if rows is None:
        return None
    return types_ns(rows=rows, types=types, collations=list(getattr(target, 'last_collations', [])),
                    scales=getattr(target, 'last_scales', None), mix=set(getattr(target, 'last_arm_mix', None) or ()),
                    mixed=set(getattr(target, 'last_mixed_columns', ())))


def judge_results(target, base, res, expect, cover=False, single=False, sql=None):
    """The verdict on two captured results (capture()) for the relation `expect`: 'Up' / 'Down'
    (set inclusion), 'Same' (the translation check: both), or 'REL col N' (a value relation on
    column N).  'ok', 'collation', 'incomparable', 'type_mismatch', or a violation.  `single`:
    the query reads single-precision inputs; `sql`: the original, for its step-function
    columns.  run_on_db.py, recheck_mysql.py and reduce_mysql.py all judge with this."""
    fold = target.folds(base.collations, res.collations)
    strict = target.dialect == 'sqlite'           # the numeric probe passed (see main)
    if ' col ' in expect:
        relation, _, column = expect.split()
        column = int(column)
        loose = single or (res.types is not None and target.SINGLE in (base.types[column], res.types[column]))
        decimals = printed_decimals(target, column, base.types, res.types, base.scales, (base.rows, res.rows),
                                    res.scales)

        def check(b, r):
            return check_value(relation, column, b, r, single_precision=loose, fold=fold,
                               output_decimals=decimals, cover=cover, strict_types=strict)
    else:
        column = None
        if expect != 'Same' and comparable_types(base.types, res.types, base.rows, res.rows):
            return 'type_mismatch'
        directions = ('Up', 'Down') if expect == 'Same' else (expect,)

        def check(b, r):
            verdicts = [check_inclusion(d, b, r, fold) for d in directions]
            bad = [v for v in verdicts if v not in ('ok', 'collation')]
            return bad[0] if bad else ('collation' if 'collation' in verdicts else 'ok')
    verdict = check(base.rows, res.rows)
    if collation_can_explain(base.rows, res.rows):
        verdict = arm_mix_verdict(verdict, base.mix, res.mix)
    return rejudge(verdict, check, base.rows, res.rows, base.mixed | res.mixed,
                   step_columns(sql) if sql else set(), column)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('queries', help='file with one SQL query per line')
    ap.add_argument('--value', action='store_true', help='value-semantic and HAVING mutation')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=3306)
    ap.add_argument('--user', default='root')
    ap.add_argument('--password', default='')
    ap.add_argument('--database', default='test')
    ap.add_argument('--sqlite', metavar='FILE.db', help='test this SQLite database file instead of a server')
    ap.add_argument('--sqlite-lib', metavar='LIB.so', default=None,
                    help='SQLite shared library to use (default: the one Python ships)')
    ap.add_argument('--out', metavar='FILE.jsonl', help='append the violations to this file')
    ap.add_argument('--show-failed', type=int, default=0, metavar='N',
                    help='print the first N mutants that the DBMS refused although it ran the original')
    ap.add_argument('--flip', action='store_true',
                    help='negative control: expect the opposite relation (must report violations)')
    args = ap.parse_args()
    target = SQLiteTarget(args) if args.sqlite else MySQLTarget(args)
    print('comparing modulo collation: %s' % target.name)
    out = open(args.out, 'a') if args.out else None
    st, by_rule = collections.Counter(), collections.Counter()
    for line in open(args.queries, encoding='utf-8'):
        sql = line.strip().rstrip(';')
        if not sql or sql.upper().startswith(('USE ', '--')):
            continue
        st['queries'] += 1
        trs = []
        try:
            if args.value:
                original, mutants, skipped, probe, having_mutants = mutate_value(
                    sql, dialect=target.dialect, translation=trs, schema=target.schema, exact_columns=target.exact)
                mutants = mutants + having_mutants
            else:
                original, mutants, skipped = mutate_sql(sql, dialect=target.dialect, schema=target.schema,
                                                        exact_columns=target.exact)
        except Unsupported:
            st['unsupported'] += 1
            continue
        except Exception as e:
            st['bridge_error'] += 1
            ERRORS['bridge: %s %s' % (type(e).__name__, str(e)[:60])] += 1
            continue
        single = False
        probes = trs[0].type_probes() if args.value else []
        if args.value and target.dialect == 'mysql' and any(p[0] for p in probes):
            # The model computes with exact numbers.
            # - FLOAT / DOUBLE grouping keys: the server may compare rounded or unrounded
            #   values depending on the plan, so the number of groups is not determined;
            #   such queries are outside the model.
            # - single-precision inputs: results are compared with a looser tolerance.
            failed = approximate = False
            for probe_sql, nkeys in probes:          # one probe per arm of a UNION ALL
                if probe_sql is None:
                    continue
                _, probe_types = target.run(probe_sql)
                if probe_types is None:
                    failed = True
                    break
                approximate |= any(t in target.APPROXIMATE_TYPES for t in probe_types[:nkeys])
                single |= target.SINGLE in probe_types
            if failed:
                st['original_failed'] += 1
                continue
            if approximate:
                st['approximate_group_key'] += 1
                continue
        if args.value and target.dialect == 'sqlite':
            # an SQLite column can hold text in any row; aggregates then follow SQLite's
            # own rules, outside the model (see Translation.numeric_probe)
            count_sql = trs[0].numeric_probe()
            if count_sql is not None:
                count, _ = target.run(count_sql)
                if count is None or count[0][0] != 0:
                    st['non_numeric_input'] += 1
                    continue
        written = capture(target, sql)
        base = capture(target, original)
        if written is None or base is None:
            st['original_failed'] += 1
            continue
        if judge_results(target, written, base, 'Same') not in ('ok', 'collation', 'incomparable'):
            st['TRANSLATION_MISMATCH'] += 1
            print('TRANSLATION MISMATCH\n  written  : %s\n  reprinted: %s' % (sql, original))
            if out and not args.flip:
                # recorded like a violation: the re-printed query means the same (the bridge
                # only drops parentheses, ORDER BY without LIMIT, ...), so different rows are
                # a DBMS bug or a bridge bug; reduce_mysql.py reduces such a pair too
                out.write(json.dumps({'rule': 'TRANSLATION', 'expect': 'Same', 'verdict': 'translation mismatch',
                                      'value': bool(args.value), 'query': sql, 'original': sql, 'mutant': original,
                                      'original_rows': len(written.rows), 'mutant_rows': len(base.rows)}) + '\n')
                out.flush()
            continue
        st['supported'] += 1
        st['mutants_not_printable'] += skipped
        for mutant in mutants:
            text = mutant[-1]
            res = capture(target, text)
            if res is None:
                st['mutant_failed'] += 1
                if st['mutant_failed'] <= args.show_failed:     # the dialect of the printer, or of the server?
                    print('MUTANT FAILED (%s)\n  original: %s\n  mutant  : %s' % (mutant[1], original, text))
                continue
            cover = False
            if args.value and len(mutant) == 4:
                relation, rule, column, _ = mutant
                if args.flip:
                    if relation not in FLIP_VALUE:
                        continue
                    relation = FLIP_VALUE[relation]
                cover = bool(trs) and trs[0].cover_for(text)
                label = '%s col %d' % (relation, column)
            else:
                # set-semantic mutant, or a mutant of the HAVING predicate
                direction, rule, _ = mutant
                if args.value:
                    rule = 'HAVING ' + rule
                if args.flip:
                    direction = 'Down' if direction == 'Up' else 'Up'
                label = direction
            verdict = judge_results(target, base, res, label, cover=cover, single=single, sql=original)
            if verdict == 'type_mismatch':
                st['type_mismatch_skipped'] += 1
                continue
            if verdict == 'ok':
                st['checked_ok'] += 1
                by_rule[rule] += 1
            elif verdict in ('incomparable', 'collation'):
                st[verdict] += 1
            else:
                st['VIOLATIONS'] += 1
                if not args.flip:
                    print('VIOLATION %s %s (%s)\n  original: %s\n  mutant  : %s'
                          % (label, rule, verdict, original, text))
                    if out:
                        out.write(json.dumps({'rule': rule, 'expect': label, 'verdict': verdict, 'distinct': cover,
                                              'single': single, 'query': sql, 'original': original, 'mutant': text,
                                              'original_rows': len(base.rows), 'mutant_rows': len(res.rows)}) + '\n')
                        out.flush()
    # mutants whose printed SQL did not parse back to the term of the verified engine
    if sql_bridge.STATS['not_in_dialect']:
        # rules whose operator the dialect lacks (SQLite: INTERSECT ALL, EXCEPT ALL)
        st['mutants_not_in_dialect'] = sql_bridge.STATS['not_in_dialect']
    if sql_bridge.STATS['roundtrip_rejected']:
        st['mutants_roundtrip_rejected'] = sql_bridge.STATS['roundtrip_rejected']
    # mutants that apply a collation-sensitive operation above a de-duplication
    if sql_bridge.STATS['outside_model']:
        st['mutants_outside_model'] = sql_bridge.STATS['outside_model']
    print(dict(st))
    print('ok checks per rule:', dict(by_rule))
    if ERRORS:
        print('most frequent errors:')
        for msg, n in ERRORS.most_common(10):
            print('  %6d  %s' % (n, msg))
    for message, sql in INTERNAL.items():
        print('INTERNAL ERROR: %s\n  query: %s' % (message[:300], sql))


if __name__ == '__main__':
    main()
