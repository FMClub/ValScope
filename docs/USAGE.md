# Using the Rocq version of ValScope, end to end

This guide covers the whole process: preparing a machine, building and checking the proofs,
generating queries, and testing a database server, an SQLite file or old SQLite releases. It
also covers reading the results and adding a rule. Every step is a command that can be copied.
All paths are relative to the root of the repository (branch `main`).

**In a hurry:** after the installation of section 2, `scripts/demo.sh sqlite` runs everything
(proof check, build, tests, a test of a random SQLite database), and
`scripts/setup_mariadb.sh && scripts/demo.sh mariadb` does the same with MariaDB. The rest
of this guide explains each step and how to go further.

Contents

1. [What the tool does](#1-what-the-tool-does)
2. [Set up the environment](#2-set-up-the-environment)
3. [Build and check the proofs](#3-build-and-check-the-proofs)
4. [First steps without a database](#4-first-steps-without-a-database)
5. [Get queries to test](#5-get-queries-to-test)
6. [Test a MySQL-compatible server](#6-test-a-mysql-compatible-server)
7. [Test an SQLite database file](#7-test-an-sqlite-database-file)
8. [Run a differential campaign on old SQLite releases](#8-run-a-differential-campaign-on-old-sqlite-releases)
9. [Test any other database](#9-test-any-other-database)
10. [Read and triage the results](#10-read-and-triage-the-results)
11. [Add a mutation rule](#11-add-a-mutation-rule)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. What the tool does

ValScope finds logic bugs in database systems by metamorphic testing. It takes a query Q,
rewrites it into a mutant Q' whose result must stand in a known relation to Q's result,
runs both, and reports when the relation does not hold.

- **Set-semantic rules** change which rows are returned. The relation is bag inclusion:
  `Up` means every row of Q is also in Q' (with at least the same multiplicity), `Down`
  the other way round.
- **Value-semantic rules** change one select item. The rows of Q and Q' correspond one to
  one, agree outside the mutated column, and the mutated column satisfies a relation such
  as `Le` (the value does not decrease).
- **HAVING rules** mutate the HAVING predicate of a grouped query with the same predicate
  rules; the mutant returns a super-list (`Up`) or sub-list (`Down`) of the groups.

In this version every rule is a theorem proved in Rocq, and one generic engine, proved
sound for every list of rules, applies the rules inside whole queries. The proved engine
is extracted to OCaml (`cli/valscope_mutate`). A Python bridge translates SQL to the
engine's terms and back, runs the queries and checks the relations:

```
SQL text --(bridge/sql_bridge.py, sqlglot)--> algebra term
         --(cli/valscope_mutate, extracted from the proofs)--> mutant terms
         --(bridge/sql_bridge.py)--> mutant SQL
         --(run_on_db.py / campaign_sqlite.py: execute both)--> checker.py: does the relation hold?
```

The proofs cover the engine and the rules with respect to the SQL model in
`theories/Semantics.v`. The bridge, the command-line glue, sqlglot and the checker are not
verified; the README lists what each of them assumes.

## 2. Set up the environment

Tested on Ubuntu 24.04 with Coq 8.18.0, OCaml 4.14.1, Python 3.12 / 3.13, sqlglot 30.33.0,
pymysql 1.1, MariaDB 10.11.14 and SQLite 3.26.0 to 3.53.1.

### 2.1 Get the code

```bash
git clone https://github.com/FMClub/ValScope.git
```

```bash
cd ValScope
```

### 2.2 Rocq / Coq, OCaml and build tools

From the distribution (simplest):

```bash
sudo apt-get update && sudo apt-get install -y coq ocaml ocaml-findlib make gcc
```

Check the versions (Coq 8.18 or newer, OCaml 4.14 or newer):

```bash
coqc --version && ocamlfind ocamlopt -version
```

Alternatively with opam, if your distribution has an older Coq:

```bash
opam init -y && eval $(opam env) && opam install -y coq.8.18.0 ocamlfind
```

The development has not been built with Rocq 9.x; the theories use the `Coq` library names
(`From Coq Require Import ...`), which Rocq 9 still accepts with a deprecation warning.

### 2.3 Python packages

```bash
python3 -m pip install -r requirements.txt
```

(`requirements.txt` pins `sqlglot==30.33.0` and asks for `pymysql`.)

sqlglot changes its syntax tree between releases; the bridge was written for 30.33.0. Pin
it. `pymysql` is only needed to test MySQL-protocol servers.

### 2.4 A database to test (optional for the first steps)

**MariaDB or MySQL on the same machine:** `scripts/setup_mariadb.sh` (section 6.1) does the
following steps itself; by hand:

```bash
sudo apt-get install -y mariadb-server
```

```bash
sudo mkdir -p /run/mysqld && sudo chown mysql:mysql /run/mysqld
```

```bash
sudo nohup mariadbd-safe --port=3306 --bind-address=127.0.0.1 > /dev/null 2>&1 &
```

```bash
sudo mariadb -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '123456'; FLUSH PRIVILEGES;"
```

On a system with systemd, `sudo systemctl start mariadb` replaces the two `mariadbd-safe`
lines.

**SQLite:** nothing to install. Python's `sqlite3` module carries one SQLite version;
section 8 explains how to build old releases as shared libraries.

## 3. Build and check the proofs

```bash
make
```

This checks every proof in `theories/` and extracts the verified engine to
`extracted/valscope_core.ml`. It takes a few minutes. The output ends with three
`Print Assumptions` reports:

- `mutate_sound` (set-semantic mutator): `Closed under the global context`, that is, no
  axioms;
- `vmutate_sound` and `hmutate_sound` (value and HAVING mutators): the axioms of Coq's
  real-number library (`ClassicalDedekindReals.sig_not_dec`, `sig_forall_dec`,
  `functional_extensionality_dep`), because AVG divides and STDDEV takes a square root.

Any other axiom in that list means that a proof was left unfinished.

```bash
make cli
```

builds the command-line mutator `cli/valscope_mutate` from the extracted code.

```bash
make test
```

runs `bridge/test_bridge.py`: SQL to mutants to SQL, the encodings, the rejections and the
checkers, without a database. It must end with `0 failures`.

To start again from a clean tree:

```bash
make clean
```

## 4. First steps without a database

List the plugged-in rules (kind, direction or relation, name):

```bash
./cli/valscope_mutate --rules
```

Mutate one query with the set-semantic rules:

```bash
python3 bridge/sql_bridge.py "SELECT t.a FROM t WHERE t.b > 5 AND t.c LIKE 'a_c%'"
```

Each line shows the direction (`Up`: the mutant returns at least the rows of the
original; `Down`: at most), the rule and the mutant.

Mutate the select items of a grouped query (value rules) and its HAVING predicate:

```bash
python3 bridge/sql_bridge.py --value "SELECT t.g AS g, AVG(t.x) + 1 AS a, COUNT(DISTINCT t.y) AS n FROM t GROUP BY t.g HAVING SUM(t.x) > 10"
```

See the algebra term the engine works on:

```bash
python3 -c "import sys; sys.path.insert(0, 'bridge'); from sql_bridge import Translation; print(Translation(sys.argv[1]).term)" "SELECT t.a FROM t WHERE NOT EXISTS (SELECT u.x FROM u WHERE u.x < t.a)"
```

The engine itself reads one term per line and prints the mutants; the protocol is described
at the top of `cli/main.ml`:

```bash
echo "(Proj ((EAtom 0)) (Where (Cmp gt (EAtom 1) (Int 5)) (T 0 1)))" | ./cli/valscope_mutate
```

A query the bridge cannot translate faithfully is rejected with `Unsupported` and a reason
(for example `LIMIT`, window functions in the select list, `RIGHT JOIN`); it is never
approximated.

## 5. Get queries to test

The runners read a file with **one query per line**. Lines starting with `--` or `USE` are
skipped. There are three sources.

### 5.1 The fragment generator of this directory

`bridge/gen_fragment.py` generates random queries that use the features the mutators
analyse (joins, set operations, `EXISTS`, `IN`, `NOT`, comparisons, `IS NULL`, aggregates,
`GROUP BY`, `HAVING`).

```bash
python3 bridge/gen_fragment.py 400 7 > queries.sql
```

400 set-semantic queries with random seed 7, for the sample schema (tables `t1`, `t2`, `t3`).

```bash
python3 bridge/gen_fragment.py --value 500 11 > vqueries.sql
```

500 value queries (aggregates, `GROUP BY`, `HAVING`).

Options:

| Option | Effect |
| --- | --- |
| `--sqlite` | SQLite syntax (no parentheses around compound operands, no `VAR_SAMP`) |
| `--schema FILE.json` | use your own tables and numeric columns (below) |
| `--rich` | also opaque predicates (`BETWEEN`, `CAST`, `COLLATE`, ...) and derived tables |
| `--focus` | more set operations and `DISTINCT` |

For your own schema, write a JSON file that maps each table to its **numeric** columns; the
first column of each table is used in `EXISTS` subqueries:

```json
{"orders": ["id", "qty", "price"], "items": ["id", "order_id", "amount"]}
```

```bash
python3 bridge/gen_fragment.py --schema schema.json 400 1 > queries.sql
```

The numeric columns of a MySQL / MariaDB database can be listed with:

```bash
mariadb -uroot -p123456 -N -e "SELECT CONCAT(table_name, '.', column_name) FROM information_schema.columns WHERE table_schema = 'test' AND data_type IN ('tinyint','smallint','mediumint','int','bigint','decimal','float','double') ORDER BY table_name, ordinal_position"
```

and of an SQLite file with:

```bash
sqlite3 shop.db "SELECT m.name || '.' || p.name FROM sqlite_master m, pragma_table_info(m.name) p WHERE m.type = 'table' AND p.type IN ('INTEGER', 'INT', 'REAL', 'NUMERIC', 'DECIMAL', 'FLOAT', 'DOUBLE')"
```

### 5.2 Queries of the original Python generator

`data/python-generator-queries.sql` holds 870 queries produced by the original ValScope
generator for the sample database (one per line; the leading `USE test;` line is skipped).
They can be used as they are:

```bash
python3 bridge/run_on_db.py data/python-generator-queries.sql --port 3306 --user root --password 123456 --database test
```

To generate new ones, use the original implementation on branch `vanilla-python`, in a
separate worktree (it writes into its own `generated_sql/` directory):

```bash
git worktree add /tmp/valscope-vanilla vanilla-python
```

```bash
cd /tmp/valscope-vanilla && python3 -c "from generate_random_sql import Generate; Generate(subquery_depth=2, total_insert_statements=40, num_queries=500, query_type='default', use_database_tables=False, db_config={'host': '127.0.0.1', 'port': 3306, 'database': 'test', 'user': 'root', 'password': '123456'})"
```

This writes a new random database (`generated_sql/schema.sql`, `generated_sql/indexes.sql`)
and queries for it (`generated_sql/queries.sql`). Load the database and keep only the
query lines:

```bash
mariadb -uroot -p123456 < /tmp/valscope-vanilla/generated_sql/schema.sql
```

```bash
mariadb -uroot -p123456 test < /tmp/valscope-vanilla/generated_sql/indexes.sql
```

```bash
grep -E '^(SELECT|WITH|\()' /tmp/valscope-vanilla/generated_sql/queries.sql > py_queries.sql
```

About 40% of these queries are inside the fragment the bridge translates (374 of the 870
sample queries); the rest use `LIMIT` without `ORDER BY` in subqueries, `RIGHT JOIN`,
window functions, `SELECT DISTINCT` with aggregates and similar features, and are reported
as `unsupported`.

### 5.3 Your own queries

Any file with one `SELECT` per line works. Queries outside the fragment are counted as
`unsupported` and skipped.

## 6. Test a MySQL-compatible server

This covers MariaDB, MySQL, Percona Server, TiDB, OceanBase (MySQL mode), PolarDB-X and
any other server that speaks the MySQL protocol, local or remote.

### 6.1 Prepare a database

To use the sample database of the repository (tables `t1`, `t2`, `t3` with rows and
indexes, from `data/mariadb/`):

```bash
scripts/setup_mariadb.sh
```

It connects to `127.0.0.1:3306` as `root` with password `123456`, starts a local MariaDB
first if none answers, and (re)creates the database `test`. Another server:

```bash
HOST=db.example.internal PORT=3306 DB_USER=root PASSWORD=secret scripts/setup_mariadb.sh
```

To load the files by hand instead:

```bash
mariadb -uroot -p123456 < data/mariadb/schema.sql
```

```bash
mariadb -uroot -p123456 test < data/mariadb/indexes.sql
```

For your own database nothing needs to be loaded; generate queries for its schema
(section 5.1).

### 6.2 Run the set-semantic rules

```bash
python3 bridge/run_on_db.py queries.sql --host 127.0.0.1 --port 3306 --user root --password 123456 --database test --out violations.jsonl
```

For every query:

1. **Translation validation.** The query as written and the query re-printed from its
   algebra term are both executed; if they do not return the same rows, the query is not
   used and `TRANSLATION MISMATCH` is printed. This protects against bridge errors (and,
   occasionally, reveals a DBMS inconsistency between two equivalent queries).
2. Every mutant is executed and the relation of its rule is checked, modulo the equality of
   the database's collation (section 10.2).

### 6.3 Run the value-semantic and HAVING rules

```bash
python3 bridge/run_on_db.py vqueries.sql --value --host 127.0.0.1 --port 3306 --user root --password 123456 --database test --out violations.jsonl
```

### 6.4 Run a negative control

`--flip` expects the opposite relation for every mutant. A correct pipeline must then
report many violations; if it reports none, the checks are not doing anything.

```bash
python3 bridge/run_on_db.py queries.sql --flip --port 3306 --user root --password 123456 --database test
```

### 6.5 A remote or different server

Only the connection options change. For example TiDB on its default port:

```bash
python3 bridge/run_on_db.py queries.sql --host tidb.example.internal --port 4000 --user root --password '' --database test
```

The SQL dialect is MySQL for every server reached this way. If the server rejects a
construct (for example `INTERSECT` on older MySQL versions), the affected queries are
counted as `original_failed` or `mutant_failed`, never as violations.

### 6.6 A whole campaign

A loop over generator seeds, with all violations collected in one file:

```bash
for seed in $(seq 1 20); do python3 bridge/gen_fragment.py 300 $seed > q_$seed.sql; python3 bridge/run_on_db.py q_$seed.sql --port 3306 --password 123456 --database test --out violations.jsonl | tail -n 3; done
```

```bash
for seed in $(seq 101 120); do python3 bridge/gen_fragment.py --value 300 $seed > v_$seed.sql; python3 bridge/run_on_db.py v_$seed.sql --value --port 3306 --password 123456 --database test --out violations.jsonl | tail -n 3; done
```

## 7. Test an SQLite database file

Any SQLite file can be tested, with the SQLite that Python ships or with any SQLite
shared library.

```bash
python3 bridge/gen_fragment.py --sqlite --schema schema.json 400 1 > queries.sql
```

```bash
python3 bridge/run_on_db.py queries.sql --sqlite shop.db --out violations.jsonl
```

```bash
python3 bridge/gen_fragment.py --sqlite --schema schema.json --value 400 2 > vqueries.sql
```

```bash
python3 bridge/run_on_db.py vqueries.sql --value --sqlite shop.db --out violations.jsonl
```

With a particular SQLite library (section 8 shows how to build old releases):

```bash
python3 bridge/run_on_db.py queries.sql --sqlite shop.db --sqlite-lib /tmp/sqlite-libs/libsqlite3-3260000.so
```

The runner reads the `CREATE` statements of the file to find which collations the text
columns use (`NOCASE`, `RTRIM`) and compares results with that equality. For value queries
it first counts the rows where an aggregated expression holds text, and skips the query if
there are any (`non_numeric_input`): SQLite's `AVG` converts text to numbers while
`MIN`/`MAX` order text above all numbers, which is outside the numeric model.

## 8. Run a differential campaign on old SQLite releases

The campaign builds random databases, runs random queries and their mutants on several
SQLite releases, and re-checks each violation on the newest SQLite. A violation on an old
release that disappears on the newest one is a bug the newer release fixed; this is how the
42 confirmed pairs in `results/sqlite-campaign.md` were found.

### 8.1 Build old SQLite releases

`sqlite.org` is not always reachable; the script takes the amalgamations from the npm
package `sqlite3`, which bundles them (needs `npm` and `gcc`):

```bash
sudo apt-get install -y npm
```

```bash
bridge/build_old_sqlite.sh /tmp/sqlite-libs
```

It builds `libsqlite3-3260000.so` (3.26.0), `-3300100` (3.30.1), `-3310100` (3.31.1) and
`-3340000` (3.34.0), with `SQLITE_ENABLE_COLUMN_METADATA`: with it, SQLite reports for
every result column the table column it comes from, and the checker uses that column's
declared collation (section 10.2). Libraries built earlier without it are rebuilt. Any other
`libsqlite3.so` works too (without the metadata API the checker falls back to the coarsest
collation of the database); `python` stands for the SQLite that Python ships (no metadata).

### 8.2 Run the campaign

```bash
L=/tmp/sqlite-libs; python3 bridge/campaign_sqlite.py --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so --seeds 1-50 --queries 100 --out violations.jsonl
```

| Option | Effect |
| --- | --- |
| `--seeds A-B` | database seeds; each seed is a different random schema and data |
| `--queries N` | N set-semantic and N value queries per seed |
| `--focus` | more set operations, `DISTINCT`, text and `COLLATE NOCASE` columns |
| `--rich` | opaque predicates and derived tables |
| `--flip` | negative control |

Progress is printed to standard error after each seed; the summary and the per-rule
counts are printed at the end. Each violation is printed with the verdict on the newest
SQLite (`latest: ok` means fixed there) and appended to `violations.jsonl`.

### 8.3 Confirm the violations from scratch

```bash
L=/tmp/sqlite-libs; python3 bridge/confirm_sqlite.py violations.jsonl --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so > confirmed.md
```

This rebuilds each seed's database with every library, re-runs both queries and writes a
Markdown report. A pair is `confirmed` when it reproduces on the version that reported it
and the relation holds on the newest SQLite.

## 9. Test any other database

The runner talks to a target through a small class with two methods. To support another
DBMS (PostgreSQL, a JDBC-only system, an embedded engine), add a class to
`bridge/run_on_db.py` next to `MySQLTarget` and `SQLiteTarget`:

```python
class PostgresTarget:
    dialect = 'postgres'          # sqlglot dialect used to parse and print the queries

    def __init__(self, args):
        import psycopg2
        self.conn = psycopg2.connect(host=args.host, port=args.port, user=args.user,
                                     password=args.password, dbname=args.database)
        self.conn.autocommit = True
        self.name = 'exact'           # printed at the start of a run
        self.last_collations = []     # collation of each column of the last result

    def folds(self, collations_a, collations_b):
        """The equality of values when comparing two results (checker.py): one fold
        for all columns, or one per column."""
        return ExactFold()

    def run(self, sql):
        """(rows, column types or None), or (None, None) when the query fails."""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                return [tuple(r) for r in cur.fetchall()], None
        except Exception:
            return None, None
```

and select it with a new command-line flag where `target` is chosen in `main()`. Three
things must be checked for a new DBMS:

1. **The dialect.** The bridge prints mutants with sqlglot in `dialect`. The bridge was
   tested with `mysql` and `sqlite`; for another dialect, run the tests of
   `bridge/test_bridge.py` with that dialect and check that translation validation
   (section 6.2) passes on real queries.
2. **The equality of text values** (`folds`). If the database compares strings with a
   case- or accent-insensitive collation, return folds that map a string to its collation
   key, ideally one per result column from the driver's column metadata (see
   `MariaDBColumns` and `MariaDBFold`, which ask the server). With `ExactFold`, a correct
   result that only picks a different representative of equal strings would be reported as
   a violation.
3. **The monotone functions** used by rule 26 (`MONO_FUNCS` in `bridge/sql_bridge.py`) must
   be non-decreasing and must not turn a number into NULL in that DBMS.

## 10. Read and triage the results

### 10.1 The summary line

At the end of a run, `run_on_db.py` prints a dictionary of counters:

| Counter | Meaning |
| --- | --- |
| `queries` | lines read |
| `unsupported` | outside the fragment the bridge translates faithfully |
| `bridge_error` | the bridge failed on the query (listed under "most frequent errors") |
| `original_failed` | the query (or its re-printed form) failed on the database |
| `TRANSLATION_MISMATCH` | the query as written and as re-printed returned different rows |
| `supported` | queries that passed translation validation and were mutated |
| `mutants_not_printable` | mutants the bridge cannot print as SQL (dropped) |
| `mutants_roundtrip_rejected` | mutants whose printed SQL does not parse back to the term the verified engine produced (dropped; should be 0, anything else is a bridge bug) |
| `mutants_outside_model` | mutants that apply a collation-sensitive operation (`LENGTH`, `LIKE`, ...) to the output of a de-duplication; their result is not determined by SQL (dropped) |
| `mutant_failed` | mutants the database rejected (dropped) |
| `type_mismatch_skipped` | set mutants whose result column types differ from the original's |
| `approximate_group_key` | value queries grouped by FLOAT / DOUBLE (outside the model) |
| `non_numeric_input` | SQLite value queries over text (outside the model) |
| `checked_ok` | relation checks that passed |
| `collation` | passed modulo the collation, not exactly (section 10.2) |
| `incomparable` | value check on a column that is not numeric |
| `VIOLATIONS` | relation checks that failed |

Then `ok checks per rule` and the most frequent database errors.

### 10.2 Verdicts

- `ok`: the relation holds exactly.
- `collation`: the relation holds when strings are compared the way the database compares
  them, but not character by character. Example: a column with a case-insensitive
  collation holds `'a'` and `'A'`; `SELECT DISTINCT` must return one of them, and SQL does
  not say which. The original may return `'a'` and the mutant `'A'`. The theorem promises
  inclusion up to the database's equality, so this is not a violation. The equality is
  computed exactly, **per result column**:
  - MariaDB / MySQL: the connection sets `character_set_results = NULL`, so the server
    reports the real collation of every result column (also of expressions, derived tables
    and set operations); strings are compared by `WEIGHT_STRING` under that collation, with
    trailing spaces removed for PAD SPACE collations;
  - SQLite: the column metadata API gives the table column a result column comes from, and
    its declared collation (`NOCASE` folds only the 26 ASCII letters, `RTRIM` ignores
    trailing spaces). For an expression column, or with a library without the API, the
    coarsest collation of the database is used; that can miss a real case difference in
    such a column, but never reports a false one.
- `violation` (set rules): the mutant misses a row the relation requires (`Up`), or
  returns a row the original does not have (`Down`), even modulo the collation.
- Value rules: `row count a vs b`, `other columns changed`, `NULL-ness changed`, or
  `<relation> violated: ...`. The theorem says that the rows of the two results can be put
  in one-to-one correspondence so that corresponding rows agree outside the mutated column
  and satisfy the relation in it. The checker searches for such a correspondence
  (bipartite matching within each group of rows that agree outside the column) and reports
  a violation only when none exists.

### 10.3 Triage a violation

Each violation is printed with the original and the mutant, both as printed by the bridge
(re-printed form), and with `--out` also written as one JSON object per line (`rule`,
`expect`, `verdict`, `query`, `original`, `mutant`, row counts).

1. **Run both queries by hand** and compare the results:

   ```bash
   mariadb -uroot -p123456 test -e "ORIGINAL; MUTANT"
   ```

2. **Check that it is not a model gap.** The theorems hold for every *lawful* world
   (`Semantics.v`): operations must respect the collation equality, values are numbers,
   strings or NULL, there are no errors. A query whose result is not determined by SQL
   (a function that tells apart strings that the collation treats as equal, such as
   `LENGTH` after a `DISTINCT` on a PAD SPACE column) can produce a difference that is not
   a bug. The README lists the known gaps.
3. **Check other versions.** A violation that disappears on a newer release is most likely
   a bug fixed there (the SQLite campaign does this automatically).
4. **Reduce** the query by hand: remove joins, predicates and select items as long as the
   two queries still disagree.
5. **Record it.** In this repository, candidate bugs are written up as a Markdown document
   in `issues/` and submitted as a pull request (see `issues/` on `main` for examples).

## 11. Add a mutation rule

A rule is a rewrite plus a theorem. Example: `A INTERSECT B -> A` in
`theories/ExtraRules.v`.

1. Write the rewrite of the root of a query (or predicate, or select item). It returns the
   list of rewrites, empty when the rule does not apply.
2. Prove that each rewrite is a super-bag (`Up`) or sub-bag (`Down`) of its input, in
   every world (for value rules: that the values are related by one of the five
   relations).
3. Package rewrite and proof with `mk_qrule`, `mk_prule` or `mk_vrule`.
4. Add the rule to `pred_rules`, `query_rules` or `value_rules` in `theories/Registry.v`.
5. Rebuild and test:

   ```bash
   make && make cli && make test
   ```

The engine decides where the rule may fire (it flips the direction under `NOT` and in the
right operand of `EXCEPT`, and never enters the `ON` condition or the right input of a
`LEFT JOIN`), so the proof only reasons about the root. A rule cannot be registered without
its proof: the proof is a field of the rule record.

If the rule introduces a construct the bridge does not know (a new function, a new
operator), also extend the printer in `bridge/sql_bridge.py` (`_e_sql`, `_p_sql`,
`_q_sql`, `_a_sql`) and the S-expression parser and printer in `cli/main.ml`.

## 12. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `make` fails with `Unable to unify` or `not found` in a theory | Coq older than 8.18; install 8.18 (section 2.2). |
| `make cli` fails: `ocamlfind: command not found` | `sudo apt-get install -y ocaml-findlib` |
| `bridge/test_bridge.py` fails on many cases | wrong sqlglot version; `python3 -m pip install "sqlglot==30.33.0"` |
| `connection to the server lost ...; the run is stopped` | the server stopped (MariaDB is sometimes killed in idle containers); restart it (section 2.4) and run again |
| many `original_failed` with `near "(": syntax error` on SQLite | the queries were generated without `--sqlite` |
| `no such function: VAR_SAMP` on SQLite | the value queries were generated without `--sqlite` |
| `a GROUP BY clause is required before HAVING` on old SQLite | old releases reject HAVING without GROUP BY; these queries are skipped |
| `FUNCTION test.REGEXP_LIKE does not exist` | an old bridge version; update the branch (REGEXP is now printed as an operator) |
| everything `unsupported` | the queries use features outside the fragment; check one with the `Translation(...)` command of section 4 to see the reason |
| `--flip` reports 0 violations | no mutant was checked: look at `supported`, `mutant_failed` and the errors |
