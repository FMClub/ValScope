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

Rocq 9 works as well (checked in CI with Rocq 9.2 from opam: `opam install rocq-prover
ocamlfind`). The theories use the `Coq` library names (`From Coq Require Import ...`), which
Rocq 9 accepts with a deprecation warning; the Makefile and `demo.sh` use `rocq makefile` and
`rocq c` when `coq_makefile` and `coqc` are not installed.

### 2.3 Python packages

```bash
python3 -m pip install -r requirements.txt
```

(`requirements.txt` pins `sqlglot==30.33.0` and asks for `pymysql`.)

sqlglot changes its syntax tree between releases. The bridge tests pass with sqlglot 26.33
to 30.33; `requirements.txt` pins 30.33.0, and `scripts/demo.sh` warns outside that range.
`pymysql` is only needed to test MySQL-protocol servers.

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
(for example `LIMIT` whose kept rows are not determined, window functions in the select
list, `FULL JOIN`); it is never approximated.

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
| `--value-ext` | value queries (with `--value`) with windows over groups, a `SELECT DISTINCT` arm in a `UNION ALL`, `INTERSECT` / `EXCEPT`, an outer query over a derived value query; from side streams, so without it the queries of a seed stay those of earlier runs |

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

About a third of these queries are inside the fragment the bridge translates (307 of the
870 sample queries for the set rules, 138 for the value rules); the rest use `LIMIT` whose
kept rows are not determined, window functions, `SELECT DISTINCT` with aggregates and
similar features, and are reported as `unsupported`.

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
first if none answers (with `sudo` when not run as root), and (re)creates the database
`test`. If that database already has tables it asks first; without a terminal it refuses
unless `YES=1` is set. Another server or database name:

```bash
HOST=db.example.internal PORT=3306 DB_USER=root PASSWORD=secret DATABASE=vs_test scripts/setup_mariadb.sh
```

```bash
DATABASE=vs_test scripts/demo.sh mariadb
```

The script reports the index statements of `data/mariadb/indexes.sql` it skips: the file
collects several runs of the original generator, so 155 definitions are duplicates
(`ERROR 1061`), and 9 indexes exceed MariaDB's key length of 3072 bytes (`ERROR 1071`).

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
   occasionally, reveals a DBMS inconsistency between two equivalent queries: `issues/010`
   was found this way). With `--out`, the pair is recorded with the rule `TRANSLATION`
   (the query as written, the query re-printed), and `reduce_mysql.py` reduces it like a
   violation.
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

### 6.6b A campaign over random databases

`scripts/demo.sh` and section 6.6 test one database. `bridge/campaign_mysql.py` builds a
random database per seed (`bridge/gen_mysql_db.py`: random column types, NULLs,
duplicates, a primary key, random indexes; the database `vs_campaign` is dropped and
created for every seed), generates queries for it and checks them with `run_on_db.py`:

```bash
python3 bridge/campaign_mysql.py --seeds 1-40 --queries 40 --focus --value-ext --host 127.0.0.1 --port 3306 --user root --password 123456 --out violations.jsonl
```

There is no reference release, so every violation is a candidate, to be classified by a
person. `scripts/triage_mysql.py` does the mechanical part:

```bash
python3 scripts/triage_mysql.py violations.jsonl --port 3306 --password 123456 --out-dir triage
```

For every pair it rebuilds the database of the seed and judges the pair again, judges it
without the secondary indexes (a pair that needs an index depends on the access path),
reduces it (`reduce_mysql.py --build-seed`, section 6.7) into `triage/pair-N.sql`, and
prints a table of the pairs grouped by the shape of the reduced query (names and constants
removed). Pairs of one shape are very likely one defect. The steps are also available
alone: `bridge/recheck_mysql.py violations.jsonl ... [--no-indexes] [--out still.jsonl]`
and `reduce_mysql.py`. To look at a pair by hand:
`python3 bridge/gen_mysql_db.py SEED | mysql --force DATABASE` (`--force`: a UNIQUE index on
a column with duplicates fails, as it does in the campaign, and the client must go on).
The campaigns so far are in `results/mariadb-campaign.md`.

### 6.7 Reduce a violation found on a server

```bash
python3 bridge/reduce_mysql.py out/violations.jsonl --pair 1 --host 127.0.0.1 --port 3306 --user root --password 123456 --database test
```

The pair (a line of `--out`, or `--key KEY` with a key of `scripts/check_violations.py`) is
reduced like an SQLite pair (section 8.5): the query step by step, re-running the verified
mutator, then the data, deleting rows one by one in a copy of the tables (database
`vs_reduce`, dropped at the end), then the secondary indexes, dropping each one and adding
it back when the pair is no longer violated without it. It prints a script: `CREATE TABLE` and `INSERT`
statements for the remaining rows, the original and the mutant. For a pair of
`campaign_mysql.py`, `--build-seed` first builds `--database` from the seed of the pair.

### 6.8 Known violations in CI

`scripts/check_violations.py out/violations.jsonl data/ci-baseline/mariadb.txt` fails when a
run reports a violation that is not listed (key: rule and a hash of the two queries); CI
runs it after every end-to-end run. A new violation is either a DBMS bug to record in
`issues/` (then its key goes into the baseline) or a false alarm of the tool to fix.
`scripts/check_violations.py --keys FILE` prints the keys of a run. The key hashes the printed
SQL, so a change of how the bridge prints queries (or of the generator) changes the keys
of known violations: the run then reports them as new, and the baseline is updated from
`--keys` after checking that they are the known ones.

A bug that many generated queries hit is listed by signature instead: a baseline line
`sig:NAME` names a predicate of `scripts/check_violations.py` (`SIGNATURES`) on the record,
for example `mariadb-distinct-avg` for `issues/009` (a value rule, `SELECT DISTINCT` in a
grouped query with `AVG` or `STDDEV`, verdict "other columns changed"). The script prints
how many violations each signature matched. A signature must be narrow: it hides every
violation that satisfies it.

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
`MIN`/`MAX` order text above all numbers, which is outside the numeric model. Since the
ninth round the campaign generates value queries over the columns declared `INTEGER` or
`REAL` in the seed's schema, so this no longer happens (it skipped 46% of the value-query
runs before); `--any-column` gives the earlier queries.

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
| `--adaptive` | choose plain / `--focus` / `--rich` / both per database seed by coverage feedback (section 8.4) |
| `--latest LIB.so` | the reference library a violation is re-checked on (default: the SQLite that Python ships). Use a build of the newest release: a bug that Python's SQLite still has is otherwise filed as "also in latest" (bug 5 of `results/sqlite-bisect.md`) |
| `--value-ext` | the value queries of `gen_fragment.py --value-ext` (windows over groups, DISTINCT arms of a `UNION ALL`, `INTERSECT` / `EXCEPT`) |
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

### 8.4 Coverage-guided generation (`--adaptive`)

The four generator settings differ only in fixed probabilities and in the random database:

| Setting | Database (`gen_sqlite_db.py`) | Queries (`gen_fragment.py`) |
| --- | --- | --- |
| plain | column types INTEGER 3/6, REAL 1/6, TEXT 1/6, none 1/6; a TEXT value is a word 30% of the time (`'a'`, `'A'`, `'b'`, `'x'`, `' 1'`, `'01'`, `''`) | a SELECT is a set operation 45% of the time per level; `SELECT DISTINCT` 30% |
| `--focus` | TEXT 2/6 and untyped 1/6 of the columns; a TEXT value is a word 50% of the time, `'B'` added; half of the TEXT columns are `COLLATE NOCASE` in every setting | set operation 80% per level; `SELECT DISTINCT` 50% |
| `--rich` | as plain | in addition: 30% of the predicates are opaque (`LIKE`, `GLOB`, `BETWEEN`, `CAST`, `COLLATE NOCASE =`, `IS`, `coalesce`, `likely`, ...); 30% of the FROM items are derived tables (some with `DISTINCT`, `WHERE`, `UNION ALL`); `CROSS JOIN`; 20% of the select items are wrapped (`+ 0`, `CAST`, `\|\| ''`, `abs`, `coalesce`) |
| `--focus --rich` | as `--focus` | both |

The original Python generator (branch `vanilla-python`) works the same way: its behaviour is
set by fixed arguments (`query_type`, `subquery_depth`, `num_queries`,
`total_insert_statements`) and 41 fixed probabilities in the code; it keeps the generated
queries that execute without an error and has no feedback. `--adaptive` adds a feedback
loop on top of the fixed settings; the probabilities themselves are not learned.

Every campaign counts **coverage features**: a pair (rule, the set of constructs of the
original query's term, such as `Union`, `Distinct`, `Left`, `Like`). A feature counts when
that rule was checked on a query of that shape. With `--adaptive`, the generator settings
(plain, `--focus`, `--rich`, both) are chosen for each database seed by a UCB1 bandit.
The reward is the new features per query, plus a large bonus for each new violating pair:

```bash
L=/tmp/sqlite-libs; python3 bridge/campaign_sqlite.py --adaptive --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so --seeds 3001-3020 --queries 40 --out violations.jsonl
```

Each seed's line on standard error names the chosen arm, and the final summary gives how
often each arm was chosen and its mean reward. On seeds 3001-3020 (1600 queries each):

| Setting | Checks passed | Coverage features | Violating pairs |
| --- | --- | --- | --- |
| plain | 127,896 | 6,412 | 0 |
| `--focus --rich` (fixed) | 149,100 | 8,127 | 1 |
| `--adaptive` (chose `focus` 12 times) | 152,372 | 7,608 | 2 (+1 outside the model) |

Twenty seeds are too few to call a winner. The adaptive run found the most violating
pairs and passed the most checks; the fixed best setting covered more features.

### 8.5 Reduce a violation

```bash
L=/tmp/sqlite-libs; python3 bridge/reduce_sqlite.py violations.jsonl --lib 3.26.0=$L/libsqlite3-3260000.so --lib 3.34.0=$L/libsqlite3-3340000.so --latest NEWEST.so --out reduced.jsonl --sql repro
```

For every set-semantic pair, the original query is simplified one step at a time: a
compound is replaced by one of its arms, an `AND` / `OR` by an operand, `NOT p` by `p`, a
clause (`WHERE`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`, `DISTINCT`), a join or a select
item is removed (in a compound, the same column from every arm), a subquery predicate or a
comparison is replaced by `1` or `0`. After each step the verified mutator runs again on
the smaller query, and the step is kept only if a mutant of the same rule and direction
still violates the relation on the library of the reporting version (`--lib VERSION=PATH`,
or a bare `PATH` for all pairs). So the reduced pair is again one the engine produced, and
the theorem of its rule still applies. `--pair N` reduces only pair N (1-based). The
reduced pairs are printed and, with `--out`, written in the input format with the
original pair under `reduced_from`.

- `--latest LIB` (a library of the newest release, for example one built by
  `bisect_sqlite.py`): a step is kept only if the relation still HOLDS there. Without it,
  a reduction can drift from the bug of the pair (fixed since) to some other behaviour that
  the newest release shares; with it, the reduced pair shows the same fixed bug.
- `--boundaries ORIGINAL.jsonl --src SQLITE_GIT_CLONE`: the bisection of the original pairs
  (`bisect_sqlite.py --introduced --out`). A step is kept only if the pair stays violated
  on the last bad commit and on the introducing commit, and not violated on the fixing
  commit and on the last good commit, on the same database. So the reduced pair shows the
  same bug, which `--latest` alone does not guarantee (the fixing commit could change).
- Value and HAVING pairs (`kind` `value` / `having`) are reduced too, with the same
  relation and column, and the cover check for DISTINCT value queries.
- `--sql DIR`: the database is reduced as well (rows, indexes and `ANALYZE` are removed,
  first in chunks, then one by one, while the reduced pair stays violated), and
  `DIR/pair-N.sql` is a self-contained reproduction: the statements, then the original and
  the mutant. The record gets a `database` field with the statements.

### 8.6 Map violations to SQLite commits (distinct bugs)

```bash
git clone --filter=blob:none --no-checkout https://github.com/sqlite/sqlite sqlite-src
```

```bash
python3 bridge/bisect_sqlite.py violations.jsonl --introduced --src sqlite-src --cache bisect-cache --out bisect.jsonl > bisect.md
```

SQLite is built from its source history (gcc, make and tclsh are needed; about 20 s per
commit, cached in `--cache`). For each pair:

1. the pair must be bad on the reporting release (`--old`, default the release in the
   record) and good on `--new` (default: the newest release tag); the first-parent history
   between them is bisected for the first good commit, the **fixing commit**. If the pair
   is bad on `--new` too, it is reported as a live bug.
2. with `--introduced`, older release tags are tried (doubling steps back, then one
   release at a time) until one is good; the commits between that release and the next
   bad one are bisected for the first bad commit, the **introducing commit**.

Commits that do not build or on which a query fails are skipped (their neighbours are
tested), and so are commits on which the database of the pair is not the same: every
statement that succeeds on the reporting release must succeed there too (an old release
without `WITHOUT ROWID`, partial or expression indexes would otherwise run the queries on
another database). A reduced pair (`reduce_sqlite.py --sql`) brings its own few
statements, so older releases can judge it more often. With `--compat`, a pair whose
introducing commit is not found is tried again on its database without `WITHOUT ROWID`;
that result is an approximation and is reported as such. The result says whether a
boundary is exact (two adjacent commits). `bisect.md`
groups the pairs: **pairs with the same introducing and fixing commits are one bug,
different commits are different bugs.** The fixing commit is the first commit on which the
pair is good; when it is an optimisation that changes the plan, it ends the symptom of the
pair rather than fixing the defect.

### 8.7 Record new pairs, and replay the recorded ones

`scripts/record_sqlite_pairs.py` runs sections 8.3, 8.6 and 8.5 for the pairs of a campaign
file that `results/` does not have yet, and then appends them to the result files and
regenerates the reports:

```bash
scripts/record_sqlite_pairs.py violations.jsonl --lib 3.26.0=$L/libsqlite3-3260000.so --lib 3.30.1=$L/libsqlite3-3300100.so --lib 3.31.1=$L/libsqlite3-3310100.so --lib 3.34.0=$L/libsqlite3-3340000.so --latest sqlite-src/../bisect-cache/libsqlite3-NEWEST.so --src sqlite-src --work record-work
```

`--latest` is a library of the newest release (bisect_sqlite.py builds one into its cache).
The script stops, without touching `results/`, when a pair is not confirmed (reproduced
on its release, consistent on the newest), cannot be reduced or bisected; run again with
the same `--work`, it reuses the steps that are done. It prints a note when a pair has
commits that no recorded bug has: the entry in "The bugs" of `results/sqlite-bisect.md`
is then written by hand.

`scripts/replay_reduced_sqlite.py --lib 3.26.0=... [--latest ...]` replays every reduced
pair of `results/` on the release that reported it, where it must still be violated (and
on `--latest`, where it must hold). CI runs it: a change of the checker or of the
execution layer that hides a known bug fails there.

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
        self.schema = {}              # table -> columns (information_schema), optional
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
  - compounds: a compound column gets the coarsest collation of its arms (SQLite: each arm
    prepared on its own; MariaDB / MySQL: each arm run with `LIMIT 0`, cached), because an
    arm can de-duplicate under a coarser collation than the one the server reports for the
    whole compound; a compound nested in a derived table or a CTE is compared with the
    coarsest collation of the database.
- `violation` (set rules): the mutant misses a row the relation requires (`Up`), or
  returns a row the original does not have (`Down`), even modulo the collation.
- Value rules: `row count a vs b`, `other columns changed`, `NULL-ness changed`, or
  `<relation> violated: ...`. The theorem says that the rows of the two results can be put
  in one-to-one correspondence so that corresponding rows agree outside the mutated column
  and satisfy the relation in it. The checker searches for such a correspondence
  (bipartite matching within each group of rows that agree outside the column) and reports
  a violation only when none exists.
- Value rules on `SELECT DISTINCT` (or a `UNION` of value queries): after DISTINCT the rows
  no longer correspond one to one. The theorem (`VDistinct.v`, `tmutate_distinct_sound`)
  states a cover in both directions: every row of each result agrees outside the mutated
  column with a row of the other result and satisfies the relation with it. The checker
  checks exactly that. The same holds when only some arms of a `UNION ALL` are under
  DISTINCT (`tmutate_mask_sound`); a mutant that changes only arms outside the DISTINCT
  parts keeps the one-to-one check (`tmutate_mask_plain_sound`; `Translation.cover_for`).
- Value rules through a derived table (`VLineage.v`, `wmutate_sound`): for a `SELECT` over
  one derived value query, the mutants of the derived table are also used; the checked
  column is the outer item that reads the mutated column. The check is the same
  correspondence (a cover under an outer `SELECT DISTINCT`).
- HAVING rules on a top-level `INTERSECT` / `EXCEPT` of value queries (`VSet.v`,
  `shmutate_sound`): inclusion of the sets of rows, with the direction flipped in the
  right operand of `EXCEPT`; the checker's inclusion check applies as it is (the results
  have no duplicates).
- What is rejected before any check, and why (determinism, the collation law): README,
  "How the bridge fails closed". The collation law looks at the data of the database
  under test: an operation that reads only columns whose equivalent values are identical
  (SQLite: no mix of integers and reals, no `-0.0`, text only under `BINARY`; MySQL:
  integer columns), followed through derived tables and CTEs, is not rejected.

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
| `a GROUP BY clause is required before HAVING` on old SQLite | a query written with HAVING but no GROUP BY fails on releases before 3.39 (the bridge prints its own queries and mutants without it) |
| `FUNCTION test.REGEXP_LIKE does not exist` | an old bridge version; update the branch (REGEXP is now printed as an operator) |
| everything `unsupported` | the queries use features outside the fragment; check one with the `Translation(...)` command of section 4 to see the reason |
| `database test has N tables; set YES=1 ...` | `setup_mariadb.sh` would drop an existing database; set `YES=1`, or use another `DATABASE=` |
| `missing: ...` from `demo.sh` | a tool or Python package is not installed; the message gives the install command |
| `warning: sqlglot X` | sqlglot outside the tested range 26.33 to 30.33; `python3 -m pip install -r requirements.txt` |
| `--flip` reports 0 violations | no mutant was checked: look at `supported`, `mutant_failed` and the errors |
