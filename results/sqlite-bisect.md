# SQLite violations mapped to commits

`bridge/bisect_sqlite.py results/sqlite-confirmed.jsonl --introduced --src SQLITE_GIT_CLONE`
checked each of the 43 confirmed pairs on SQLite built from its source history
(https://github.com/sqlite/sqlite, first-parent history, about 20 s per build, builds cached):

- **fixed by**: the first commit after the reporting release on which the relation of the
  rule holds again (the pair is good on 3.54.1, the newest release tag);
- **introduced by**: the first commit on which the pair is bad, after the newest older
  release on which it is good.

Pairs with the same (introducing, fixing) commits are counted as one bug: different
commits, different bugs. 43 pairs give **7 distinct bugs**. Every boundary found is exact
(the two commits are adjacent in the first-parent history); 13 verdicts per fix, 7 to 37
per introduction; 179 commits were built. Two pairs were withdrawn in this round (`results/sqlite-withdrawn.jsonl`,
false alarms of the collation check), so the numbering is that of the current
`results/sqlite-confirmed.md`.

| Bug | Pairs | Introduced by | Fixed by | Fix first released in | Rules |
| --- | --- | --- | --- | --- | --- |
| 1 | #1, #2, #3, #4, #5, #6, #7, #8, #9, #12, #13, #15, #21, #22, #25, #30, #35, #36, #41, #42, #43 | before version-3.8.2 (bad on every older release that could be judged) | `9b7005feeae1` 2026-01-25 Always use the sort-and-merge algorithm for EXCEPT, INTERSEC | version-3.52.0 | EXCEPT->left, UNION->UNION-ALL, UNION-ALL->UNION |
| 2 | #10, #11, #14, #16, #17, #18, #19, #20, #23, #24, #31 | `9ed1dfa802c2` 2008-01-02 Minor optimizations for sub-selects in EXISTS(...) expressio | `9b7005feeae1` 2026-01-25 Always use the sort-and-merge algorithm for EXCEPT, INTERSEC | version-3.52.0 | EXCEPT->left, UNION->UNION-ALL, UNION-ALL->UNION |
| 3 | #26, #29 | `f8f76d672b78` 2020-01-08 Simplification of the logic in the constant-propagation opti | `fdfd45aef3c8` 2020-02-13 Fix problems in the constant propagation optimization that w | version-3.32.0 | LEFT->INNER-JOIN, cond->TRUE |
| 4 | #27, #28 | `fad4dd0fd182` 2020-09-30 Improved query optimization for multi-column indexes where t | `16cd8b96d3e2` 2021-01-27 Fix an issue with IN operator optimization introduced by che | version-3.35.0 | DISTINCT-add, cond->TRUE |
| 5 | #32, #33, #34, #37, #40 | `8dc570b6afac` 2016-06-08 Prefer to use partial indexes for full table scans when that | `8f2b1e4c909d` 2019-05-11 Do not assume that "x IS NOT ?" implies "x NOT NULL" when co | version-3.29.0 | DISTINCT-add, UNION->UNION-ALL |
| 6 | #38 | `49ad330d677f` 2010-08-13 Do not apply the flattening optimization if the sub-query is | `9b7005feeae1` 2026-01-25 Always use the sort-and-merge algorithm for EXCEPT, INTERSEC | version-3.52.0 | DISTINCT-add |
| 7 | #39 | before version-3.8.2 (bad on every older release that could be judged) | `e69ba68363ed` 2020-12-19 Allow UNION ALL sub-queriesto be flattened even if the paren | version-3.35.0 | UNION->UNION-ALL |

## The bugs

Three groups share the fixing commit `9b7005feeae1fd6267f0b52161998ce2d75335e2` (2026-01-25,
3.52.0: "Always use the sort-and-merge algorithm for EXCEPT, INTERSECT, and UNION, even if
there is no ORDER BY clause"). That commit replaced the code path of compound operators
without `ORDER BY`; the three groups became wrong at different commits, so by the rule
above they are different bugs that one rewrite removed.

1. **Compound operators without `ORDER BY`, introduction unknown** (21 pairs; `UNION`,
   `UNION ALL`, `EXCEPT`). Fixed by `9b7005feeae1`. Bad on every release back to 3.8.2;
   the 5 releases before it could not be judged, so the introducing commit is not known
   (it may be one of the commits of bugs 2 and 6).
2. **`EXISTS` subqueries drop `DISTINCT`** (11 pairs). Introduced by
   `9ed1dfa802c24fc678f6ca11e4616b4edc414fed` (2008-01-02, 3.5.5, "Minor optimizations for
   sub-selects in EXISTS(...) expressions: Discard any DISTINCT or ORDER BY clauses and do
   not calculate any column values"), fixed by `9b7005feeae1`.
3. **Constant propagation** (pairs 26, 29: `LEFT->INNER-JOIN`, `cond->TRUE`). Introduced by
   `f8f76d672b78b77e7d79ebaf0e9ab55c8bb0b14d` (2020-01-08, 3.31.0, "Simplification of the
   logic in the constant-propagation optimization"), fixed by
   `fdfd45aef3c8ed91278f4bddff6b421472e49f10` (2020-02-13, 3.32.0, SQLite ticket
   `1dcb4d44964846ad`).
4. **IN operator on multi-column indexes (`OP_SeekScan`)** (pairs 27, 28: `DISTINCT-add`,
   `cond->TRUE`). Introduced by `fad4dd0fd1826c08f3f04c81b77d51dcb7f1c661` (2020-09-30,
   3.34.0), fixed by `16cd8b96d3e2cb80e169beee529307d0f0fdf51c` (2021-01-27, 3.35.0,
   ticket `ee51301f316c09e9`).
5. **Partial indexes and `x IS NOT ?`** (pairs 32, 33, 34, 37, 40: `DISTINCT-add`,
   `UNION->UNION-ALL`). Introduced by `8dc570b6afac593f029a67640ab916278af1ca65`
   (2016-06-08, 3.14.0, "Prefer to use partial indexes for full table scans when that is
   possible"), fixed by `8f2b1e4c909df912209c34816ae33bf31cbb20b8` (2019-05-11, 3.29.0,
   ticket `8025674847`: "Do not assume that "x IS NOT ?" implies "x NOT NULL" when
   considering partial indexes").
6. **Flattening of a `DISTINCT` subquery** (pair 38, `DISTINCT-add`). Introduced by
   `49ad330d677f613964c53d4ff2b5790dac59d5a4` (2010-08-13, 3.7.1, "Do not apply the
   flattening optimization if the sub-query is DISTINCT. Fix for [e4b8a2ba6e]"), fixed by
   `9b7005feeae1`.
7. **`UNION ALL` subquery in a join** (pair 39, `UNION->UNION-ALL`). The first good commit
   is `e69ba68363ed3802881a9b09c4a3661fc9368756` (2020-12-19, 3.35.0, "Allow UNION ALL
   sub-queries to be flattened even if the parent query is a join"). This is an
   optimisation, not a fix: it changes the plan so that the wrong result no longer shows,
   and the underlying defect may still be reachable with other queries. Bad back to 3.8.2;
   the introducing commit is not known.

## Caveats

- The fixing commit is the first commit on which the pair is good. When that commit
  changes the plan rather than the faulty code (bug 7), it marks the end of the symptom
  for this pair, not necessarily of the bug.
- One bug can be reached through several rules and pairs (bug 1: four rules). Two
  different bugs could in principle be fixed by one commit; they would then count as one.
- For bugs 1 and 7, the 5 releases before the oldest bad one could not be judged (they do
  not build with the current toolchain, or the database or the queries fail on them), so
  their introducing commits are not known. Bug 1 may therefore be the same as bug 2 or 6.
- Several bugs can share a fixing commit (bugs 1, 2 and 6): one rewrite removed them.

## Reproduce

```
git clone --filter=blob:none --no-checkout https://github.com/sqlite/sqlite sqlite-src
python3 bridge/bisect_sqlite.py results/sqlite-confirmed.jsonl --introduced --src sqlite-src --out bisect.jsonl > bisect.md
```

Building needs gcc, make and tclsh. Per-pair results: `results/sqlite-bisect.jsonl`.
