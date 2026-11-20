# SQLite violations mapped to commits

The 43 confirmed pairs were first reduced (`bridge/reduce_sqlite.py --latest --sql`): the
query and the database are made small while the pair stays violated on the reporting
release and the relation still holds on 3.54.1, the newest release, so the reduced pair
shows the same fixed bug (`results/sqlite-reduced.md`, scripts in `results/sqlite-repro/`).
42 pairs are reduced; pair 40 is kept as it is. Six reduced pairs coincide (3 = 4, 6 = 7,
33 = 34), so 40 distinct pairs were bisected.

`bridge/bisect_sqlite.py --introduced --compat` then checked each pair on SQLite built
from its source history (https://github.com/sqlite/sqlite, first-parent history):

- **fixed by**: the first commit after the reporting release on which the relation holds;
- **introduced by**: the first commit on which the pair is bad, after the newest older
  release on which it is good.

A verdict counts only on the same database as on the reporting release (every statement
that succeeds there must succeed). Pairs with the same (introducing, fixing) commits are
one bug: different commits, different bugs. **The 43 pairs give 7 distinct bugs** (6 if
the approximation for bug 1 below is accepted). Every boundary is exact: the two commits
are adjacent in the first-parent history.

| Bug | Pairs | Introduced by | Fixed by | Fix first released in | Rules |
| --- | --- | --- | --- | --- | --- |
| 1 | #1, #2, #3, #4, #5, #6, #7, #8, #9, #12, #13, #15, #21, #22, #25, #30, #35, #36, #39, #41, #42, #43 | before version-3.8.2 (bad on every older release that could be judged); without WITHOUT ROWID (approximation): `9ed1dfa802c2` 2008-01-02 Minor optimizations for sub-selects in EXISTS(...) | `9b7005feeae1` 2026-01-25 Always use the sort-and-merge algorithm for EXCEPT, INTERSEC | version-3.52.0 | EXCEPT->left, UNION->UNION-ALL, UNION-ALL->UNION |
| 2 | #10, #11, #14, #16, #17, #18, #19, #20, #23, #24, #31 | `9ed1dfa802c2` 2008-01-02 Minor optimizations for sub-selects in EXISTS(...) expressio | `9b7005feeae1` 2026-01-25 Always use the sort-and-merge algorithm for EXCEPT, INTERSEC | version-3.52.0 | EXCEPT->left, UNION->UNION-ALL, UNION-ALL->UNION |
| 3 | #26, #29 | `f8f76d672b78` 2020-01-08 Simplification of the logic in the constant-propagation opti | `fdfd45aef3c8` 2020-02-13 Fix problems in the constant propagation optimization that w | version-3.32.0 | LEFT->INNER-JOIN, cond->TRUE |
| 4 | #27 | `fad4dd0fd182` 2020-09-30 Improved query optimization for multi-column indexes where t | `16cd8b96d3e2` 2021-01-27 Fix an issue with IN operator optimization introduced by che | version-3.35.0 | cond->TRUE |
| 5 | #28 | `beb22d086bae` 2020-10-22 Minor tweaks to query planning weights so that when STAT4 is | `16cd8b96d3e2` 2021-01-27 Fix an issue with IN operator optimization introduced by che | version-3.35.0 | DISTINCT-add |
| 6 | #32, #33, #34, #37, #40 | `8dc570b6afac` 2016-06-08 Prefer to use partial indexes for full table scans when that | `8f2b1e4c909d` 2019-05-11 Do not assume that "x IS NOT ?" implies "x NOT NULL" when co | version-3.29.0 | DISTINCT-add, UNION->UNION-ALL |
| 7 | #38 | `49ad330d677f` 2010-08-13 Do not apply the flattening optimization if the sub-query is | `9b7005feeae1` 2026-01-25 Always use the sort-and-merge algorithm for EXCEPT, INTERSEC | version-3.52.0 | DISTINCT-add |

## The bugs

Bugs 1, 2 and 7 share the fixing commit `9b7005feeae1fd6267f0b52161998ce2d75335e2`
(2026-01-25, 3.52.0: "Always use the sort-and-merge algorithm for EXCEPT, INTERSECT, and
UNION, even if there is no ORDER BY clause"), a rewrite of compound operators without
`ORDER BY`; they became wrong at different commits.

1. **Compound operators, introduction not judged exactly** (22 pairs; `UNION`, `UNION ALL`,
   `EXCEPT`). The databases of these pairs need `WITHOUT ROWID` (SQLite 3.8.2+), and every
   release back to 3.8.2 is bad. On the same databases without `WITHOUT ROWID` (an
   approximation, `--compat`) the introducing commit is `9ed1dfa802c2`, the one of bug 2:
   bug 1 is most likely bug 2.
2. **`EXISTS` subqueries drop `DISTINCT`** (11 pairs). Introduced by
   `9ed1dfa802c24fc678f6ca11e4616b4edc414fed` (2008-01-02, 3.5.5, "Minor optimizations for
   sub-selects in EXISTS(...) expressions: Discard any DISTINCT or ORDER BY clauses and do
   not calculate any column values"), fixed by `9b7005feeae1`.
3. **Constant propagation** (pairs 26, 29). Introduced by
   `f8f76d672b78b77e7d79ebaf0e9ab55c8bb0b14d` (2020-01-08, 3.31.0), fixed by
   `fdfd45aef3c8ed91278f4bddff6b421472e49f10` (2020-02-13, 3.32.0, SQLite ticket
   `1dcb4d44964846ad`).
4. **IN operator on multi-column indexes (`OP_SeekScan`)** (pair 27). Introduced by
   `fad4dd0fd1826c08f3f04c81b77d51dcb7f1c661` (2020-09-30, 3.34.0), fixed by
   `16cd8b96d3e2cb80e169beee529307d0f0fdf51c` (2021-01-27, 3.35.0, ticket `ee51301f316c09e9`).
5. **The same fix, another introducing commit** (pair 28). Introduced by
   `beb22d086bae` (2020-10-22, "Minor tweaks to query planning weights so that when STAT4
   is enabled ..."), fixed by `16cd8b96d3e2`. The introducing commit changes plan weights:
   it probably exposes the code of bug 4 to this query. By the rule it is another bug.
6. **Partial indexes and `x IS NOT ?`** (pairs 32, 33, 34, 37, 40). Introduced by
   `8dc570b6afac593f029a67640ab916278af1ca65` (2016-06-08, 3.14.0), fixed by
   `8f2b1e4c909df912209c34816ae33bf31cbb20b8` (2019-05-11, 3.29.0, ticket `8025674847`).
7. **Flattening of a `DISTINCT` subquery** (pair 38). Introduced by
   `49ad330d677f613964c53d4ff2b5790dac59d5a4` (2010-08-13, 3.7.1, "Do not apply the
   flattening optimization if the sub-query is DISTINCT. Fix for [e4b8a2ba6e]"), fixed by
   `9b7005feeae1`.

## What changed in the sixth round

- The previous result (5, then 7 bugs) was computed on the full databases, and older
  releases that could not create some index were judged on another database. With the
  same-database rule, and on the reduced pairs (whose few statements old releases can run),
  the groups are the ones above.
- An earlier reduction of pair 38 drifted to a behaviour that 3.54.1 shares (issues/007);
  `--latest` prevents that.

## Caveats

- The fixing commit is the first commit on which the pair is good. A commit that changes
  the plan rather than the faulty code ends the symptom for the pair, not necessarily the
  bug; likewise an introducing commit can expose an older defect (bug 5).
- Several bugs can share a fixing commit (bugs 1, 2, 7): one rewrite removed them.

## Reproduce

```
git clone --filter=blob:none --no-checkout https://github.com/sqlite/sqlite sqlite-src
python3 bridge/reduce_sqlite.py results/sqlite-confirmed.jsonl --lib 3.26.0=LIB --lib 3.30.1=LIB --lib 3.31.1=LIB --lib 3.34.0=LIB --latest LIB-3.54.1 --out reduced.jsonl --sql repro
python3 bridge/bisect_sqlite.py reduced.jsonl --introduced --compat --src sqlite-src --out bisect.jsonl > bisect.md
```

(`reduced.jsonl` lacks the unreduced pair 40; append its line from
`results/sqlite-confirmed.jsonl`.) Building needs gcc, make and tclsh. Per-pair results:
`results/sqlite-bisect.jsonl`.
