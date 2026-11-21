# SQLite violations mapped to commits

**The 64 confirmed pairs come from 6 distinct SQLite bugs.** Pairs with the same
(introducing, fixing) commits are one bug; different commits, different bugs. Every
boundary is exact (two adjacent commits of the first-parent history).

How it was computed:

1. `bridge/bisect_sqlite.py --introduced --compat` bisected every confirmed pair on SQLite
   built from its source history (https://github.com/sqlite/sqlite), on the same database
   as on the reporting release (a commit on which a statement of the database fails is not
   judged). Result: `results/sqlite-bisect-original.jsonl`.
2. `bridge/reduce_sqlite.py --boundaries results/sqlite-bisect-original.jsonl --latest ... --sql`
   reduced every pair, query and database, keeping it bad on the reporting release, on
   the last bad commit and on the introducing commit, and good on the fixing commit, on the
   last good commit and on 3.54.1: a reduced pair shows the same bug as its pair. The
   reduced databases also drop `WITHOUT ROWID` where the pair allows it, so releases
   before 3.8.2 can judge them (`results/sqlite-reduced.md`, `results/sqlite-repro/`).
3. The reduced pairs were bisected again (`results/sqlite-bisect.jsonl`). Their commits
   equal those of their pairs wherever the original bisection found them, and the
   introducing commits that the full databases could not reach are now found.

Three reduced pairs coincide (3 = 4, 6 = 7, 33 = 34). Pairs 43 to 45 come from the seventh-round campaign (seeds 4001-4030) and were reduced and bisected the same way: all three are bug 1, as are pair 46 (eighth-round campaign, seed 5023) and pairs 47 to 51 (ninth round, seeds 6001-6030). Pairs 52 to 60 (tenth round, seeds 7001-7030) were recorded by `scripts/record_sqlite_pairs.py`, which runs these steps.

| Bug | Pairs | Introduced by | Fixed by | Fix first released in | Rules |
| --- | --- | --- | --- | --- | --- |
| 1 | #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20, #21, #22, #23, #24, #25, #30, #31, #35, #36, #40, #41, #42, #43, #44, #45, #46, #47, #48, #49, #50, #51, #55, #56, #57, #58, #59, #60 | `9ed1dfa802c2` 2008-01-02 Minor optimizations for sub-selects in EXISTS(...) expressio | `9b7005feeae1` 2026-01-25 Always use the sort-and-merge algorithm for EXCEPT, INTERSEC | version-3.52.0 | EXCEPT->left, UNION->UNION-ALL, UNION-ALL->UNION |
| 2 | #26, #29 | `f8f76d672b78` 2020-01-08 Simplification of the logic in the constant-propagation opti | `fdfd45aef3c8` 2020-02-13 Fix problems in the constant propagation optimization that w | version-3.32.0 | LEFT->INNER-JOIN, cond->TRUE |
| 3 | #27, #28, #52 | `fad4dd0fd182` 2020-09-30 Improved query optimization for multi-column indexes where t | `16cd8b96d3e2` 2021-01-27 Fix an issue with IN operator optimization introduced by che | version-3.35.0 | DISTINCT-add, cond->TRUE |
| 4 | #32, #33, #34, #37, #39 | `8dc570b6afac` 2016-06-08 Prefer to use partial indexes for full table scans when that | `8f2b1e4c909d` 2019-05-11 Do not assume that "x IS NOT ?" implies "x NOT NULL" when co | version-3.29.0 | DISTINCT-add, UNION->UNION-ALL |
| 5 | #38 | `9ed1dfa802c2` 2008-01-02 Minor optimizations for sub-selects in EXISTS(...) expressio | `e69ba68363ed` 2020-12-19 Allow UNION ALL sub-queriesto be flattened even if the paren | version-3.35.0 | UNION->UNION-ALL |
| 6 | #53, #54, #61, #62, #63, #64 | `f78dcd1b960e` 2016-09-07 Add support for row-value comparisons, including IN operator | `3bc026df6eef` 2026-07-29 Avoid apply an affinity to a register that might be the resu | version-3.54.0 | COUNT->COUNT-DISTINCT, COUNT-DISTINCT->COUNT, HAVING cond->TRUE, expr->expr*k, expr->expr+k |

## The bugs

1. **`EXISTS` subqueries drop `DISTINCT`, shown by compound operators** (47 pairs; `UNION`,
   `UNION ALL`, `EXCEPT`, `DISTINCT`). Introduced by `9ed1dfa802c24fc678f6ca11e4616b4edc414fed`
   (2008-01-02, 3.5.5, "Minor optimizations for sub-selects in EXISTS(...) expressions:
   Discard any DISTINCT or ORDER BY clauses and do not calculate any column values"), fixed
   by `9b7005feeae1fd6267f0b52161998ce2d75335e2` (2026-01-25, 3.52.0, "Always use the
   sort-and-merge algorithm for EXCEPT, INTERSECT, and UNION, even if there is no ORDER BY
   clause").
2. **Constant propagation** (pairs 26, 29). Introduced by
   `f8f76d672b78b77e7d79ebaf0e9ab55c8bb0b14d` (2020-01-08, 3.31.0), fixed by
   `fdfd45aef3c8ed91278f4bddff6b421472e49f10` (2020-02-13, 3.32.0, SQLite ticket
   `1dcb4d44964846ad`).
3. **IN operator on multi-column indexes (`OP_SeekScan`)** (pairs 27, 28, 52). Introduced by
   `fad4dd0fd1826c08f3f04c81b77d51dcb7f1c661` (2020-09-30, 3.34.0), fixed by
   `16cd8b96d3e2cb80e169beee529307d0f0fdf51c` (2021-01-27, 3.35.0, ticket `ee51301f316c09e9`).
4. **Partial indexes and `x IS NOT ?`** (pairs 32, 33, 34, 37, 39). Introduced by
   `8dc570b6afac593f029a67640ab916278af1ca65` (2016-06-08, 3.14.0), fixed by
   `8f2b1e4c909df912209c34816ae33bf31cbb20b8` (2019-05-11, 3.29.0, ticket `8025674847`).
5. **`UNION ALL` subquery in a join** (pair 38). Introduced by `9ed1dfa802c2` like bug 1,
   but its first good commit is `e69ba68363ed3802881a9b09c4a3661fc9368756` (2020-12-19,
   3.35.0, "Allow UNION ALL sub-queries to be flattened even if the parent query is a
   join"), an optimisation that changes the plan: by the rule it is another bug, and it
   may be the defect of bug 1 that this plan change hides for this pair.
6. **Affinity applied to an aggregate's register** (pairs 53, 54, 61, 62, 63, 64; found by the HAVING rule
   `cond->TRUE` and by four value rules). `HAVING COUNT(x) IN (SELECT text_column ...)` converts the register that
   holds `COUNT(x)` to text for the comparison, and the select list then returns the text:

   ```sql
   CREATE TABLE t (a, b INTEGER); INSERT INTO t VALUES (1, 2), (1, 2), (2, 2);
   CREATE TABLE s (v TEXT);       INSERT INTO s VALUES ('2');
   SELECT typeof(COUNT(a)), COUNT(a) FROM t GROUP BY a HAVING COUNT(a) IN (SELECT v FROM s);
   -- 3.26.0, 3.34.0, 3.53.1: text, '2'      3.54.1: integer, 2
   ```

   Introduced by `f78dcd1b960ebf135ec7860dd4fed592e5d3fc7e` (2016-09-07, 3.15.0, "Add support
   for row-value comparisons, including IN operators"), fixed by
   `3bc026df6eef2397ea0968404037e1b15d34955d` (2026-07-29, 3.54.0, "Avoid apply an affinity to
   a register that might be the result of a TK_AGG_COLUMN expression, as it might be reused";
   the commit names a bug report of the same day). The SQLite that Python 3.13 ships
   (3.53.1) has the bug; `MAX(b)` in place of `COUNT(a)` shows it too.

## What changed in the sixth round

- Earlier reductions kept a pair violated on its release and (later) good on 3.54.1, but
  not its commits: two reduced pairs had another fixing or introducing commit than their
  pair, and the grouping showed 7 bugs. With the boundaries kept, the 5 groups above.
- Three pairs were withdrawn in the sixth round as outside the model (collations of
  compounds, `results/sqlite-withdrawn.jsonl`, issues/007).

## Caveats

- A fixing commit is the first commit on which the pair is good; a plan change can end the
  symptom without fixing the defect (bug 5). An introducing commit can expose older code.
- Several bugs can share a commit (bugs 1 and 5 share the introducing commit).

## Reproduce

```
git clone --filter=blob:none --no-checkout https://github.com/sqlite/sqlite sqlite-src
python3 bridge/bisect_sqlite.py results/sqlite-confirmed.jsonl --introduced --compat --src sqlite-src --out original.jsonl
python3 bridge/reduce_sqlite.py results/sqlite-confirmed.jsonl --lib 3.26.0=LIB ... --latest LIB-3.54.1 --boundaries original.jsonl --src sqlite-src --out reduced.jsonl --sql repro
python3 bridge/bisect_sqlite.py reduced.jsonl --introduced --src sqlite-src --out bisect.jsonl > bisect.md
```

Building needs gcc, make and tclsh.
