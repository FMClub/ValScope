# Open problems (status after the ninth round of the Rocq version)

> This repository has no issue tracker, so this document (submitted through a PR) collects
> the problems that are known and not solved, so that they can be reviewed together.
> Each item says where it comes from and what is missing. Items that are solved are not
> listed; see `issues/001-mutation-soundness-audit.md` (Progress) and PR #4 for those.

## A. The original Python implementation (branch `vanilla-python`)

These come from the audit in `issues/001-mutation-soundness-audit.md`. The implementation
fixes of PR #1 are merged; the design problems below are still open.

1. **Value-semantic propagation (audit problem 1), partly addressed.** Lineage is exact for
   derived tables, CTEs, `UNION ALL` and scalar subqueries in a select list. Subqueries in
   `WHERE` / `IN` / `EXISTS` and `DISTINCT` set operations still use the old heuristics, and
   rows are still paired by sorting.
2. **Python comparison semantics (problem 3).** Results are compared in Python, not with the
   DBMS's collation and type rules; values are rounded to two decimals.
3. **Preprocessing rewrites the query under test (problem 4).** `GROUP BY`, `LIMIT`,
   aggregates, window functions and outer joins are removed or rewritten before mutation,
   so those optimizer paths are not tested; 67 of 1801 executions failed because the
   rewritten query was invalid.
4. **Polarity refinements (problem 5).** `ALL` / `ANY`, the left input of a `LEFT JOIN` and
   aggregates over subqueries are skipped as "unknown polarity".
5. **Rule 26 and monotone functions (problem 6).** Rule 26 as written (`FUNC(c * k)`,
   `k > 0`) is unsound for negative `c`; there is no defined set of monotone functions.
6. **Repository consistency (problem 7).** The default configuration runs only the
   value-semantic mutator; `sql_generation/` has only `.pyc` files; `mutator/__pycache__`
   holds `.pyc` files without sources; `sqlglot` is not pinned.
7. **Rules 6, 13, 16 and the reverse of rule 1 are unreachable** in the Python code
   (registration always sets direction 1); `documents/mutation.md` lists mutators that do
   not exist (for example `AggM_AvgToMin`).

## B. The Rocq version (branch `main`, PR #4)

### Solved in the second round (kept here for reference)

- Values are now NULL, integers, rationals and strings; comparison, arithmetic, the
  collation equivalence used by DISTINCT and the set operations, LIKE / REGEXP character
  comparison and the opaque atoms are parameters of a world record with laws. The theorems
  hold for every lawful world; bags are compared modulo the collation.
- Rules 7 (`LIKE`) and 14 (`REGEXP`) are proved and plugged in.
- Derived tables and non-recursive CTEs are mutated inside; scalar subqueries, aggregated
  set-operation arms and unanalysed select items are opaque atoms instead of rejecting the
  query. 374 of the 870 sample queries of the Python generator are now accepted (6 of 511
  before).
- The checker compares modulo the database's real string equality (`WEIGHT_STRING` on
  MariaDB / MySQL, exact `NOCASE` / `RTRIM` on SQLite) instead of a fixed casefold.
- `HAVING` operands may take any value (integers, decimals, text).
- Review findings fixed: `(Col n)` encoding replaced by opaque expression atoms with a
  stated justification; LEFT JOIN padding uses the right input's width; exact comparison of
  integers and decimals; float noise in HAVING / set checks; select-alias references in
  value queries rejected; more nondeterminism rejected (SQLite `random()`, `'now'`, LIMIT
  without ORDER BY in subqueries); table functions with column arguments rejected; a lost
  server connection stops the run; errors are tallied instead of swallowed.

### B1. Coverage of SQL

1. Not modelled: window functions (except as opaque items of value queries when identical
   rows get identical values: without aggregation since the sixth round, over groups since
   the seventh), `FULL` / `NATURAL` / `USING` joins, a `RIGHT JOIN` that
   is not the first join, `LIMIT` at the top, recursive CTEs. (Since the fourth round:
   `INTERSECT ALL` / `EXCEPT ALL` and `IN` with a row constructor are modelled and proved,
   and a first `RIGHT JOIN` is translated as the swapped `LEFT JOIN`.) Unanalysed predicates
   and expressions are opaque atoms (sound, never mutated inside).
2. Value mutation applies to the select items of a `SELECT` or of the arms of a `UNION ALL`
   (`VUnion.v`, fourth round). Tenth round: a mutated value is followed through one derived
   table when the outer query reads the column in exactly one item, as the column or under
   `SUM` / `MIN` / `MAX` / `AVG` (`VLineage.v`, `wmutate_sound`; `gen_fragment.py --value-ext`
   generates such queries). The 870 Python-generator queries gain nothing from it: their
   outer queries join, or read the column twice (as a key and under an aggregate).
   Since the sixth round, value queries with `SELECT DISTINCT` and `UNION`s of value
   queries are proved (`VDistinct.v`: a cover in both directions) and used: 280 of the 870
   Python-generator queries are translated for the value rules (136 before, 69 before the
   fourth round). Window functions in value queries are accepted as opaque items when
   identical rows get identical values and the window names qualified columns only. Top-level
   `INTERSECT` / `EXCEPT` of value queries have no relation for the value rules. Seventh
   round: a `UNION` whose arms are `SELECT DISTINCT`, windows over groups (`tmutate_frame`),
   `SELECT DISTINCT` / `UNION` as a part of a `UNION ALL` (`tmutate_mask_sound`) and the
   HAVING rules inside `INTERSECT` / `EXCEPT` (`VSet.v`, `shmutate_sound`) are accepted:
   322 of the 870 Python-generator queries for the value and HAVING rules on MariaDB
   (`run_on_db.py --value`; 215 before this round). Still out: `INTERSECT` / `EXCEPT`
   operands with float sums, `INTERSECT ALL` / `EXCEPT ALL` of value queries, `LIMIT`
   without `ORDER BY` (106 queries, not determined).
3. Some set-semantic mutants cannot be printed: `DISTINCT` around a join that is an operand
   of another join, or around a join of derived tables (91 of about 9000 mutants on 200
   generated queries; 480 before the fourth round, when `DISTINCT` around any join was
   unprintable). Printing `DISTINCT` around a join of base tables needs the schema.
4. `LIMIT` in a subquery is accepted only when its result is determined (every output
   column ordered, or one input row). The Python generator emits `LIMIT` without `ORDER BY`
   inside subqueries (106 of 870
   sample queries). Their result is not determined, so the Rocq version rejects them; the
   Python tool mutates them, which can produce false alarms there.

### B2. Gap between the model and real DBMSs

1. **Laws of the world (partly solved).** The theorems assume that every operation respects
   the collation equivalence. Since the third round the bridge rejects (or drops mutants
   with) operations that break it above a de-duplication (`outside_collation_law`). Since
   the sixth round a function counts as respecting the equivalence only if it is on an
   explicit list (`RESPECTING_FUNCS`); every other function, known to sqlglot or not, is
   treated as breaking it. Open: the check is
   static, so it also rejects queries whose data cannot actually hit the problem (2 of the
   44 SQLite pairs fall under it, and their data was checked by hand: the affected
   columns hold integers only).
2. **Several collations in one database (mostly solved).** The checker now uses the
   collation of each result column: reported by MariaDB / MySQL, and by SQLite through its
   column metadata for columns that come from a table. Open: SQLite expression columns
   and Python's built-in SQLite (no metadata API) fall back to the coarsest collation.
2b. **Collation of set operations (found in the fifth round).** SQLite compares a compound
   with the collations of its leftmost arm, and MySQL derives them from the arms; the model
   has one equivalence. A rule that changes the leftmost arm (`INTERSECT->operand`) can
   change the equality an enclosing UNION uses. Such mutants are now dropped
   (`changes_compound_collation`), and one confirmed pair was withdrawn. In the sixth round
   the checker also stopped trusting SQLite's column metadata for compounds (it describes
   the leftmost arm only): the collations of all arms are combined, which withdrew two
   more pairs. The criterion
   compares select lists syntactically; a world with per-operation collations would
   cover this case in the model itself.
2c. **Arms of a compound that differ in type or collation on MySQL-protocol servers (round
   9).** Two shapes gave false alarms and are now judged `incomparable` / `collation`
   instead of a violation (`MySQLTarget.last_arm_mix`): a column that is a number in one arm
   and text or a date in another (the text of a number, `'0'` or `'0.00'`, depends on which
   arms meet first and on whether an arm is materialized; `BIT` is excepted, so that
   issue 005 stays visible), and an INTERSECT / EXCEPT over arms with a `_ci` and another collation (which
   rows match depends on the representative a `DISTINCT` kept). The arms at the top level are probed also when one of them holds a compound in a
   derived table (six of the twelve pairs of the first MySQL 9 campaign were of that
   kind). Open: a compound that is itself inside a derived table is not probed, and a real
   bug in a compound with such mixed arms is no longer reported.
3. **Character-by-character LIKE / REGEXP.** Collations with contractions or expansions
   (`'ss' = 'ß'`) are not covered.
4. **Approximate numbers.** FLOAT / DOUBLE arithmetic is not exact; grouping keys of these
   types are rejected (MariaDB), and results are compared with a tolerance.
5. **SQLite dynamic typing.** Value queries whose aggregated inputs hold text are skipped
   (`numeric_probe`); the model reads text as non-numeric, while SQLite's `AVG` converts it.
6. **Axioms.** The value-semantic part depends on the three axioms of Coq's `Reals`
   library. The set-semantic part uses none.

### B3. Trusted, unverified parts

1. The SQL bridge (`bridge/sql_bridge.py`), the command-line parser and printer
   (`cli/main.ml`), sqlglot and Rocq's extraction. Since the third round every printed
   mutant is round-trip validated (parsed back and compared with the engine's term), so a
   printing error is caught; the parser and sqlglot are still trusted (the round trip uses
   them on both sides).
2. The checker: value checks now search for a one-to-one correspondence (bipartite
   matching), which is what the theorem states; tolerances for floats are chosen by hand.
3. The list of monotone SQL functions is an assumption of the bridge.
4. After extraction the proofs are erased. (Since the fifth round the rule types are
   abstract in the interface the front end is compiled against, and a test checks that a
   forged rule does not compile; the extracted code and the extraction stay trusted.)
5. Only the `mysql` and `sqlite` dialects of sqlglot were tested.
6. **MySQL refuses value mutants of a grouping expression (round 10).** For
   `SELECT (t.c % 2) AS k0, ... GROUP BY (t.c % 2)` the rule `expr->expr+k` gives
   `((t.c % 2) + 3) AS k0`. MariaDB accepts it; MySQL 8.4 and 9.7 answer error 1055
   (ONLY_FULL_GROUP_BY does not see that the item is a function of the grouping
   expression). These mutants are counted as `mutant_failed` and not checked on MySQL: 166
   of about 36000 in the campaign of CI. Printing them as a query over a derived table
   would make MySQL accept them, but it would also change the plan under test.

### B4. Tooling

1. Since the fifth round, GitHub Actions checks the proofs with Coq 8.18 and with Rocq 9.2
   (opam; it no longer ships `coq_makefile`, which the build now handles) and runs the tests
   and end-to-end runs on SQLite and MariaDB 10.11. The bridge
   tests pass with sqlglot 26.33 to 30.33.
2. The command-line mutator now runs as one long-lived process, and the round trip
   caches atom syntax trees (2.7 times faster).
3. Sixth round: `bridge/reduce_sqlite.py` reduces a recorded SQLite pair, re-running the
   verified mutator after every step (so the reduced pair is still covered by the theorem
   of its rule), and `bridge/bisect_sqlite.py` finds the fixing and introducing commits in
   the SQLite history. CI also runs MySQL 8.4.
4. Later in the sixth round: the reducer keeps the bisection boundaries of a pair
   (`--boundaries`), reduces databases (`--sql`), value and HAVING pairs, and MySQL pairs
   (`bridge/reduce_mysql.py`); CI fails on any violation outside `data/ci-baseline/`, and
   runs the candidate scripts on MariaDB 11 and MySQL 9 as well.

## C. Testing real DBMSs

1. **Candidate MariaDB bugs not reported upstream:** PR #2 (`HAVING MAX(enum) <> n` depends
   on the select list), PR #5 (`HAVING COUNT(x) IN (subquery)` finds no match; reproduced
   again in this round), PR #8 (new: `MIN` / `MAX` of a `BIT` column return decimal text
   without `GROUP BY`), `issues/006` (new in the sixth round: a `BIT(8)` scalar subquery
   under a loose index scan returns 255). Reproduced on MariaDB 10.11.14; on MySQL 8.4.13
   (CI) the minimal cases of 005 and 006 give the correct results, so both are specific to
   MariaDB. Percona Server and TiDB: item 1d; OceanBase and PolarDB-X: item 1e; causes
   not analysed.
1a. **MariaDB `AVG` under `SELECT DISTINCT`** (`issues/009`, sixth round, found by the DISTINCT
   value queries): the `AVG` of the last group on every row; still present in MariaDB
   11.8.9, not in MySQL. Issues 005 and 006 are also still present in MariaDB 11.8.9.
1d. **Percona Server and TiDB (rounds 13-15).** Percona Server 8.4.11 shows issues 008 and 015
   as MySQL 8.4 does. TiDB v7.5.1 and v8.5.3 have three candidates of their own:
   `issues/016` (`NOT IN` with a condition on the outer row returns every row twice),
   `issues/017` (an internal error on `SELECT DISTINCT` with an `OR` after `ANALYZE`) and
   `issues/018` (a `UNION` of a `DECIMAL` and a `DOUBLE` arm rounds the `DOUBLE`). On TiDB the
   tool itself was wrong at first: TiDB reports `utf8mb4_bin` for every text column of a
   result and 0 decimals for unrounded floats (round 14). Open: the TiDB tracker was not
   searched for any of the three.
1e. **OceanBase and PolarDB-X (round 19).** OceanBase CE 4.4.2.1 has one candidate,
   `issues/023` (`SUM(x - k)` next to `SUM(x)` and `COUNT(DISTINCT x)` is computed as
   `SUM(x) - k * COUNT(DISTINCT x)`), behind 27 of the 33 pairs of its two campaigns; the
   other 6 were false alarms of the checker (a nested `UNION` de-duplicated in the outer
   collation, as MySQL 9 does; fixed). PolarDB-X 5.4.19 has four (024 in round 20): `issues/020` (a constant
   false `HAVING` of a global aggregate ignored in an `INTERSECT` / `EXCEPT` arm), `issues/021`
   (a correlated `IN` over a DISTINCT derived table NULL where its subquery is empty) and
   `issues/022` (an `INTERSECT` / `EXCEPT` arm with a DISTINCT derived table and a `LEFT JOIN`
   loses its `WHERE ... IN (subquery)`). The tool needed changes first: `--no-set-all`
   (OceanBase refuses `INTERSECT ALL` / `EXCEPT ALL`), no `WEIGHT_STRING` and untrusted result
   collations on PolarDB-X, request ids in its error messages, driver errors, `DELETE` without
   `WHERE` forbidden, and a server wait that requires DDL. Open: the trackers were not
   searched directly (round 20: a web search found no PolarDB-X report and one OceanBase lead,
   #1964); one release of each, in its all-in-one container. With `--tidb --no-group-window`
   (round 20) 15% of the generated queries still fail on PolarDB-X, not 45%: mostly
   `AssertionError: Do not support RexSubQuery` and `IllegalArgumentException` of its optimizer;
   that campaign also found `issues/024` (the parentheses of a `UNION` on the right of a
   `UNION ALL` dropped).
1c. **MariaDB over random databases (round 8 of `docs/JOURNAL.md`).** `bridge/campaign_mysql.py`
   (40 databases, 3200 queries) gave 123 violating pairs on 10.11.14, all classified
   (`results/mariadb-campaign.md`): 110 are issue 009, which turns out to be a family
   (`SELECT DISTINCT` over a grouped query: wrong aggregate values, NULLs, missing rows),
   and two are new candidates: `issues/012` (`number IN (SELECT date ...)` FALSE instead of
   NULL with an index) and `issues/013` (DECIMAL `-0.00` in `GROUP BY`). Issue 009 hides
   whatever else such queries might show, so round 9 ran a second campaign without
   `SELECT DISTINCT` in value queries (50 databases, 4000 queries, 37 pairs): no new defect;
   issues 003, 010, 012 and 013 again, three of them in new forms, and five false alarms of
   the tool, fixed. MySQL 8.4.13 in CI (12 databases): no violation. Open: MySQL refused
   166 mutants in that run (reported from the next run on); larger MySQL campaigns need a
   local server, which this environment does not have. Round 10: the rich generator, made
   to write MySQL spelling, found `issues/014` on its first run (the subquery cache keys a
   `_ci` outer column while the subquery compares under `_bin`; rows appear or disappear
   with the order of the table). CI now also runs the campaign on MariaDB 11.4, 11.8 and
   MySQL 9. Round 11: two workflows started by hand run a campaign
   (`.github/workflows/campaign.yml`) or one script (`sql.yml`) on any server image. The
   first campaign on MySQL 9.7.4 found `issues/015` (a LEFT JOIN loses its inner side; a
   regression of MySQL 8.0, present in 8.0.46, 8.4.13 and 9.7.4), and the one on MariaDB
   11.8.9 showed that the 11.x fix of issue 003 is partial.
1b. **MySQL 8.4.13 (CI, sixth round)**: the Python-generator run reports one `DISTINCT-add`
   violation on the `MIN(BIT)` query that also shows issue 005 on MariaDB: the original
   returns the decimal text `'14'`, the mutant the bit value `0x0E` (`issues/005`, section
   MySQL). CI prints the rows of every violation. With 300 generated queries per kind,
   MySQL also shows `issues/008`: INTERSECT matches a `NOT NULL` column with the `NULL` of an
   outer join (reduced to two one-row tables on MySQL 8.4.13; on 9.7.4 only the larger case
   reproduces).
2. **MariaDB `GROUP BY` on DOUBLE (analysed in the ninth round, `issues/011`).** Only columns
   with display decimals (`DOUBLE(M,D)`, `FLOAT(M,D)`) are affected: a plain `GROUP BY` groups by
   the value rounded to the declared decimals, the same `GROUP BY` with `COUNT(DISTINCT)` or
   `GROUP_CONCAT` by the unrounded double. Reproduced with four rows.
3. **SQLite: 64 confirmed violations from 5 distinct bugs (4 withdrawn).** 37 pairs from
   the first campaign, 5 from a second campaign with the extended model, 2 from a third run
   after the audit fixes, 2 from the fifth round, 3 from the seventh-round campaign, 1 from
   the eighth, 5 from the ninth (all nine bug 1) and 13 from the tenth (6 bug 1, 1 bug 3, 6 the
   new bug 5), minus 1 pair withdrawn in the fifth
   round and 3 in the sixth (`results/sqlite-campaign.md`). Solved in the sixth round:
   - every pair is mapped to the SQLite commits that introduced and fixed it
     (`bridge/bisect_sqlite.py`, `results/sqlite-bisect.md`); pairs with the same commits
     are one bug. Three of the fixing commits name an SQLite ticket
     (`1dcb4d44964846ad`, `ee51301f316c09e9`, `8025674847`);
   - all 64 pairs are reduced, query and database, keeping their verdicts on the commits
     around the fix and the introduction (`bridge/reduce_sqlite.py --boundaries`); the
     reduced pairs give the same commits and every introducing commit (the reduced
     databases no longer need `WITHOUT ROWID`).
   Closed since:
   - (tenth round) pair 38, counted as a bug of its own because its first good commit is
     the UNION ALL flattening of 3.35.0, is bug 1: with the query flattener switched off
     (`bisect_sqlite.py --optimizations-off 0x1`) it stays violated until the fix of bug 1.
     Six groups of commits became 5 bugs, and the affinity bug found by the HAVING rule is
     now number 5;
   - (closed in the ninth round) the 4 translation mismatches of the second campaign
     (`CROSS JOIN` versus `INNER JOIN ... ON 1 = 1`, seed 2010) were reproduced: the results
     differ only in `'B'` versus `'b'`, the representative a `SELECT DISTINCT` over a
     `NOCASE` column keeps in one arm of a compound. SQLite does not reorder a `CROSS JOIN`,
     so the two spellings get different join orders on 3.26.0 to 3.34.0. Not a bug: the
     comparison of that time was exact for compounds; the present one (collations of all
     arms combined) accepts the pair.
4. **The value side on SQLite (solved for HAVING in the tenth round).** The value and
   HAVING rules found nothing in the first nine rounds. Two things were in the way: until
   the ninth round 46% of the value-query runs were skipped (aggregated text columns), and
   the reference was the SQLite that Python ships (3.53.1), so a bug that it still has was
   filed as "also in latest". In the tenth round (numeric columns, 3.54.1 as the reference)
   the HAVING rule `cond->TRUE` found bug 5: `HAVING COUNT(x) IN (SELECT text_column ...)`
   turns the `COUNT(x)` of the select list into text (3.15.0 to 3.53.x). The value rules proper saw the
   same bug but filed it as "incomparable" (text in the mutated column on one side); with
   `strict_types` they report it (pairs 61 to 64). Open: no SQLite bug so far is visible
   ONLY to a value rule.
5. **Generator tuning (partly solved).** `--adaptive` chooses the generator settings per
   database seed by coverage features and violations (UCB1). The arms are only the four
   existing settings; the generator's probabilities themselves are not learned, and a
   20-seed comparison does not show a clear winner.
6. No DBMS outside MariaDB, MySQL 8.4 (CI only) and SQLite was run. The runner can reach any MySQL-protocol
   server and any SQLite file, and documents how to add another DBMS
   (`docs/USAGE.md`, section 9), but no PostgreSQL target exists.

1f. **MySQL 8.4.13 under the rules of SQLMRLab's bridge (audits 15 to 23 of the bridge).**
   Rules proved in `SqlFull.v` and exported as a mutator are judged on the integer fragment
   (`collation_law.integer_fragment`). The audits compared the server with an evaluator of
   the fragment (some 165,000 queries) and found eight candidates, `issues/025` to `032`.
   Three of them (`026` to `028`) are excluded from the fragment and a text with `!!` (`025`) is
   not translated, so that a campaign does not report them again; the others are left in and are reported when met (README of the
   bridge in SQLMRLab, "What the server does on the fragment is still its own"). The
   checker's own faults found by the same audits are fixed (`bridge/sql_bridge.py`
   `_same_names`, `_check_read_as_written`; `run_on_db.py` `_mixes_precision`); what is still
   open there: the name checks and the re-print check are necessary conditions found by
   audits, not proofs; a mutant `SELECT DISTINCT * FROM (...)` over two items of one name is
   refused by the server (error 1060) and not judged; outside the fragment a set operation
   with a correlated operand is never judged.

## D. Environment

1. The local MariaDB server is stopped from time to time when the container is idle and
   must be restarted; a campaign that runs during such a stop records failures, not
   violations.
2. `sqlite.org` and `usenix.org` are blocked by the network policy. The OSDI 2026 paper was
   never read, so none of the conclusions has been compared with the paper's definitions.
