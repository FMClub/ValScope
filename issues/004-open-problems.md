# Open problems (status after the SQLite campaign)

> This repository has no issue tracker, so this document (submitted through a PR) collects
> the problems that are known and not solved, so that they can be reviewed together.
> Each item says where it comes from and what is missing. Items that are solved are not
> listed; see `issues/001-mutation-soundness-audit.md` (Progress) and PR #4 for those.

## A. The Python implementation on `main`

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

## B. The Rocq version (branch `claude/rocq-core`, PR #4)

### B1. Coverage of SQL

1. Not modelled: `LIKE` / `REGEXP` as analysed predicates (rules 7 and 14), scalar
   subqueries, CTEs, window functions, `IN` with a row constructor, `RIGHT` / `FULL` /
   `NATURAL` / `USING` joins, `INTERSECT ALL` / `EXCEPT ALL`, `LIMIT`.
   Unanalysed predicates are kept as opaque atoms (sound, but never mutated inside).
2. Derived tables are opaque to the bridge: they are carried through but not mutated.
3. Value mutation applies to the select items of one top-level `SELECT`; a mutated value is
   not followed through derived tables or `UNION ALL`.
4. About 10% of the set-semantic mutants cannot be printed as SQL (`DISTINCT` around a join)
   and are dropped.
5. Of 511 queries from the Python generator, only 6 are inside the fragment. The campaigns
   use separate generators (`rocq/bridge/gen_fragment.py`), so the Rocq version does not yet
   test the queries the original tool produces.

### B2. Gap between the model and real DBMSs

1. **Values.** The model has integers and NULL with exact arithmetic. Real columns hold
   decimals, floats and (in SQLite) text in any column. Consequences seen in practice:
   - SQLite: `AVG` converts text to a number while `MIN` / `MAX` order text above every
     number, so `AVG -> MAX`, `MIN -> MAX` and `MAX -> MIN` fail on columns holding text.
     Handled by `numeric_probe` (the query is skipped); the theorems themselves do not
     cover dynamic typing.
   - MariaDB: grouping by `FLOAT` / `DOUBLE` expressions gives a plan-dependent number of
     groups. Handled by rejecting such queries.
   - Floating-point aggregates differ in their last bits between plans; handled by a
     tolerance and by rounded row keys.
2. **Collation.** The model compares strings exactly. Under `COLLATE NOCASE`, `DISTINCT`
   and set operations may keep a different representative; the checker classifies a
   difference that disappears up to case and trailing spaces as `collation`, not as a
   violation. This is a heuristic.
3. **HAVING operands** take integer or NULL values in the model; real-valued aggregates are
   not literally covered.
4. **Axioms.** The value-semantic part depends on the three axioms of Coq's `Reals`
   library. The set-semantic part uses none.

### B3. Trusted, unverified parts

1. The SQL bridge (`bridge/sql_bridge.py`), the command-line parser and printer
   (`cli/main.ml`), sqlglot and Rocq's extraction. Translation validation (the query as
   written and the query re-printed from its term must return the same rows) checks the
   original, not the mutants: a printing error in a mutant is not caught by it (one such
   error, a missing parenthesis, was found by running against MariaDB and fixed).
2. The checker (`bridge/checker.py`): row matching by sorting within groups is justified
   informally; tolerances are chosen by hand; the `collation` classification (a difference
   that disappears up to case and trailing spaces is not counted) is a heuristic and could
   hide a real violation.
3. The list of monotone SQL functions (`EXP`, `FLOOR`, `CEIL`, `ROUND`, `ATAN`, `SIGN`;
   `ROUND` only on SQLite) is an assumption of the bridge.
4. After extraction the proofs are erased; OCaml code could build an unproved rule record.

### B4. Tooling

1. Built and tested with Coq 8.18.0 and OCaml 4.14.1 only; not built with Rocq 9.
2. The checker re-runs every query once per mutant; there is no result cache and no
   test-case reduction, so violations are reported with the full generated query.

## C. Testing real DBMSs

1. **Candidate MariaDB bugs not reported upstream** (PR #2: `HAVING MAX(enum) <> n`
   depends on the select list; PR #5: `HAVING COUNT(x) IN (subquery)` finds no match).
   Both were reproduced on MariaDB 10.11.14 only; other versions, MySQL, Percona, TiDB,
   OceanBase and PolarDB were not tested; causes not analysed.
2. **MariaDB `GROUP BY` on DOUBLE** (see B2.1): plan-dependent number of groups; not
   analysed and not checked against the documentation.
3. **SQLite: 37 confirmed violations, causes mostly not analysed.** The Rocq version found
   37 distinct query pairs on SQLite 3.26.0 to 3.34.0 that violate the relation of their
   rule and are consistent on SQLite 3.53.1 (`rocq/results/sqlite-campaign.md` on branch
   `claude/rocq-core`). Open:
   - root causes: one is analysed (the `DISTINCT` of a compound arm is ignored under `UNION`
     when the column is `COLLATE NOCASE`); the `DISTINCT-add` pairs and the pairs that fail
     on 3.31.1 only are not;
   - the pairs are not reduced to minimal test cases, not grouped by root cause, and not
     mapped to SQLite tickets or check-ins;
   - "confirmed" means inconsistent on the old version and consistent on 3.53.1; it does
     not establish which of the two old results is wrong;
   - only the four releases bundled in npm packages could be built (`sqlite.org` is not
     reachable).
4. **Value-semantic and HAVING mutators found nothing on SQLite.** All 37 pairs come from
   set-semantic rules. On SQLite the value rules are restricted (no `VAR_SAMP` /
   `STDDEV_SAMP`, `ROUND` as the only monotone function) and many queries are skipped by
   `numeric_probe`; whether the value side can find SQLite bugs at all is open.
5. **Generator tuning is manual.** The focus mode (more compounds, `DISTINCT`, text and
   `COLLATE NOCASE` columns) was added after looking at the first violations and found 24
   of the 37 pairs. There is no feedback-driven or coverage-driven generation.
6. No other DBMS (MySQL, TiDB, OceanBase, Percona, PolarDB, PostgreSQL) was run.

## D. Environment

1. The local MariaDB server is stopped from time to time when the container is idle and
   must be restarted; a campaign that runs during such a stop records failures, not
   violations.
2. `sqlite.org` and `usenix.org` are blocked by the network policy. The OSDI 2026 paper was
   never read, so none of the conclusions has been compared with the paper's definitions.
