# Open problems (status after the second round of the Rocq version)

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

1. Not modelled: window functions, `FULL` / `NATURAL` / `USING` joins, a `RIGHT JOIN` that
   is not the first join, `LIMIT` at the top, recursive CTEs. (Since the fourth round:
   `INTERSECT ALL` / `EXCEPT ALL` and `IN` with a row constructor are modelled and proved,
   and a first `RIGHT JOIN` is translated as the swapped `LEFT JOIN`.) Unanalysed predicates
   and expressions are opaque atoms (sound, never mutated inside).
2. Value mutation applies to the select items of a `SELECT` or of the arms of a `UNION ALL`
   (`VUnion.v`, fourth round); a mutated value is not followed through derived tables.
   Value queries with `SELECT DISTINCT` are rejected. 138 of the 870 Python-generator
   queries are used by the value rules (69 before the fourth round).
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
   with) operations that break it above a de-duplication (`outside_collation_law`). Open:
   the list of such operations is maintained by hand and may be incomplete; the check is
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
   (`changes_compound_collation`), and one confirmed pair was withdrawn. The criterion
   compares select lists syntactically; a world with per-operation collations would
   cover this case in the model itself.
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

### B4. Tooling

1. Since the fifth round, GitHub Actions checks the proofs with Coq 8.18 and with Rocq 9.2
   (opam; it no longer ships `coq_makefile`, which the build now handles) and runs the tests
   and end-to-end runs on SQLite and MariaDB 10.11. The bridge
   tests pass with sqlglot 26.33 to 30.33.
2. The command-line mutator now runs as one long-lived process, and the round trip
   caches atom syntax trees (2.7 times faster). There is still no test-case reduction.

## C. Testing real DBMSs

1. **Candidate MariaDB bugs not reported upstream:** PR #2 (`HAVING MAX(enum) <> n` depends
   on the select list), PR #5 (`HAVING COUNT(x) IN (subquery)` finds no match; reproduced
   again in this round), PR #8 (new: `MIN` / `MAX` of a `BIT` column return decimal text
   without `GROUP BY`). All were reproduced on MariaDB 10.11.14 only; other versions,
   MySQL, Percona, TiDB, OceanBase and PolarDB were not tested; causes not analysed.
2. **MariaDB `GROUP BY` on DOUBLE**: plan-dependent number of groups; not analysed.
3. **SQLite: 45 confirmed violations (1 withdrawn), causes mostly not analysed.** 37 from the first
   campaign (all re-confirmed with the exact collation check), 5 from a second campaign
   with the extended model and 2 from a third run after the audit fixes
   (`results/sqlite-campaign.md`). Open:
   - root causes: one is analysed (the `DISTINCT` of a compound arm is ignored under `UNION`
     when the column is `COLLATE NOCASE`); the others are not;
   - the pairs are not reduced, not grouped by root cause, and not mapped to SQLite tickets;
   - "confirmed" means inconsistent on the old version and consistent on 3.53.1; it does
     not establish which of the two old results is wrong;
   - the second campaign also saw 4 translation mismatches on the old releases only
     (`CROSS JOIN` versus `INNER JOIN ... ON 1 = 1`), not counted and not analysed;
   - only the four releases bundled in npm packages could be built.
4. **Value-semantic and HAVING mutators found nothing on SQLite**; whether the value side
   can find SQLite bugs at all is open.
5. **Generator tuning (partly solved).** `--adaptive` chooses the generator settings per
   database seed by coverage features and violations (UCB1). The arms are only the four
   existing settings; the generator's probabilities themselves are not learned, and a
   20-seed comparison does not show a clear winner.
6. No DBMS outside MariaDB and SQLite was run. The runner can now reach any MySQL-protocol
   server and any SQLite file, and documents how to add another DBMS
   (`docs/USAGE.md`, section 9), but no PostgreSQL target exists.

## D. Environment

1. The local MariaDB server is stopped from time to time when the container is idle and
   must be restarted; a campaign that runs during such a stop records failures, not
   violations.
2. `sqlite.org` and `usenix.org` are blocked by the network policy. The OSDI 2026 paper was
   never read, so none of the conclusions has been compared with the paper's definitions.
