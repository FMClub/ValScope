# Campaign on SQLite: results

The verified mutators of this directory were run on four old SQLite releases. Every
violation below was found by this pipeline:

1. a random database is built;
2. a random query is generated;
3. the query is translated to an algebra term;
4. the verified mutator (Rocq, extracted) produces mutants, which are printed as SQL;
5. both queries are executed and the relation stated by the rule's theorem is checked.

Every violation was then re-checked from scratch by `bridge/confirm_sqlite.py`.

## Result

**51 distinct (original, mutant) query pairs violate the relation that the rule's theorem
guarantees; they come from 5 distinct SQLite bugs** (`results/sqlite-bisect.md`: each pair
is mapped to the commit that introduced and the commit that fixed it, and pairs with the
same commits are one bug). 37 pairs were found by the first campaign, 5 by a second
campaign run after the model was extended (strings, decimals, collations, opaque atoms), 2
by a third run after the audit fixes and 2 by the comparison of generator settings in the
fifth round, 3 by the seventh-round campaign, 1 by the eighth and 5 by the ninth; 1 pair was withdrawn in the fifth round
and 3 in the sixth (see "Withdrawn" and the sixth round below). All 51 are confirmed:

- the database of the seed was rebuilt by each SQLite library and both queries were run
  again;
- the violation reproduces on the version that reported it;
- the relation holds on SQLite 3.53.1, the version Python ships (for one pair it holds
  modulo the `NOCASE` collation, which is what the theorem states).

So the old releases return results that contradict each other, and a later release returns
results that are consistent with the theorem.

| | |
| --- | --- |
| SQLite versions tested | 3.26.0, 3.30.1, 3.31.1, 3.34.0 (reference: 3.53.1) |
| Databases (seeds) | about 590: 1-364, 401-429, 501-529, 601-662, 1001-1024, 1151-1178 |
| Queries generated | 142400 |
| Relation checks that passed | 9687625 |
| Violations recorded on all versions, before de-duplication | 228 |
| Distinct violating query pairs, confirmed | **37** (from 26 different databases) |
| Second campaign (`--focus --rich`, seeds 2001-2030, 60 queries per kind) | 3600 queries, 386891 checks passed, 17 violations = **5 new distinct pairs**, all confirmed |
| Third run (same seeds, after the audit fixes) | 3600 queries, 328852 checks passed, 24 violations = 6 distinct pairs, all confirmed; **2 new pairs** (seed 2009) |
| Fifth round: generator settings compared (seeds 3001-3020) | 3 x 1600 queries, 2 new confirmed pairs (seeds 3006, 3009), 1 pair outside the model (seed 3010) |
| Total confirmed pairs | **42** (1 pair withdrawn in the fifth round, 3 in the sixth; 5 distinct bugs, `results/sqlite-bisect.md`) |
| Negative control (`--flip`, 300 queries) | 1544 violations reported |

The rule of the mutation that exposed each pair:

| Rule | Pairs |
| --- | --- |
| `UNION->UNION-ALL` | 21 |
| `UNION-ALL->UNION` | 10 |
| `DISTINCT-add` | 6 |
| `EXCEPT->left` | 3 |
| `cond->TRUE` | 3 |
| `LEFT->INNER-JOIN` | 1 |
| `INNER->LEFT-JOIN` | 1 |
| `INTERSECT->operand` | 0 (1 withdrawn) |

The number of pairs of the first campaign violated on each version (a pair can be violated
on several):

| Version | Pairs |
| --- | --- |
| 3.26.0 | 33 |
| 3.30.1 | 29 |
| 3.31.1 | 31 |
| 3.34.0 | 31 |

All 45 come from set-semantic rules. The value-semantic and HAVING mutators did not find a
violation on these SQLite versions.

24 of the 37 pairs were found in focus mode (`--focus`: more compound queries, more
`DISTINCT`, more text and `COLLATE NOCASE` columns), which was added after the first 7 pairs
pointed in that direction.

## Root causes (partly analysed)

Root causes were not analysed for every pair, and the pairs were not reduced. There are most
likely only a few distinct causes, and most pairs share one of them.

- **`DISTINCT` of a compound arm under `COLLATE NOCASE`.** This explains most of the
  `UNION`, `UNION ALL` and `EXCEPT` pairs. It was analysed on seed 1004:
  - Column `t1.c1` is `TEXT COLLATE NOCASE` and holds both `'a'` and `'A'`.
  - The arm `SELECT DISTINCT t1a.c1, t1a.c1 ...` returns one of them when run alone or
    under `UNION ALL`.
  - Under `UNION`, SQLite 3.26.0 returns both rows: the arm's own `DISTINCT` is not
    applied, and the de-duplication uses the compound's collation instead. So `A UNION B`
    returns a row that `A UNION ALL B` does not have.
  - SQLite 3.53.1 returns one row in both cases.
- **`DISTINCT-add` returning more rows.** A table replaced by `SELECT DISTINCT * FROM table`
  returns more rows than the original on 3.26.0 and on 3.34.0. Not analysed; a guess is the
  affinity of the columns of a materialised subquery.
- **Violations on 3.31.1 only.** The `LEFT->INNER-JOIN` and `cond->TRUE` violations occur on
  3.31.1 alone. Not analysed.

The pairs were not mapped to SQLite tickets or check-ins.

## What was ruled out

The campaign first reported violations of `AVG->MAX`, `MIN->MAX` and `MAX->MIN` that also
occur on SQLite 3.53.1. They are not DBMS bugs but a gap between the model and SQLite:

- an SQLite column can hold text;
- `AVG` converts text to a number;
- `MIN` and `MAX` order text above every number.

Such queries are now skipped by `numeric_probe`. A bug that made the probe miss the first
select item was found and fixed on the way. None of the 37 pairs is of this kind; all 37
are consistent on 3.53.1.

## Collation

The theorems promise inclusion modulo the database's equality of values. Since the second
campaign, the checker computes that equality exactly from the declared collations: `BINARY`,
`NOCASE` (the 26 ASCII letters only) and `RTRIM` (trailing spaces). A result that is
included only modulo that equality is classified as `collation` and is not a violation. The
first campaign used a fixed approximation instead (case folding and trailing spaces on every
column). All 37 pairs of the first campaign were re-checked with the exact equality and all
are still confirmed.

## Re-checks after the third round

The checker and bridge were tightened again (round-trip validation of every mutant, the
collation-law check, determined `LIMIT` only, per-column collations from SQLite's column
metadata, exact correspondence search in value checks). The libraries were rebuilt with
`SQLITE_ENABLE_COLUMN_METADATA`. All 42 pairs were re-confirmed with these changes.

The second campaign was then run again with the same seeds (2001-2030, `--focus --rich`,
60 queries per kind): 24 violations, 6 distinct pairs, all fixed in 3.53.1 and confirmed
from scratch; no translation mismatch (4 before). Of the 5 pairs of the previous run, 2
reappear with the same text, 2 (seed 2011) reappear with a different printed mutant (a join
with condition TRUE is now printed as `CROSS JOIN`), and 1 (seed 2022, #41) is now rejected
by the collation-law check. 2 pairs are new (seed 2009: `INNER->LEFT-JOIN`, `cond->TRUE`).

Two pairs (#37, seed 515, and #41, seed 2022) apply `GLOB` or `||` to a column of a
`SELECT DISTINCT` derived table, which the collation-law check now rejects statically. In
both databases the affected column (`t2.c3`, `t3.c3`) holds integers only, so the
representative kept by `DISTINCT` cannot change the result; the two pairs remain valid.

## Withdrawn: a collation change hidden in a set operation (fifth round)

A comparison of generator settings (seeds 3001-3020) reported a pair that also violates its
relation on SQLite 3.53.1. Analysis (seed 3010, `INTERSECT->operand`):

- The original `A INTERSECT B UNION C` is `(A INTERSECT B) UNION C`; the mutant is
  `B UNION C`. In the model the mutant contains the original.
- SQLite compares the rows of a compound with the collations of its **leftmost** arm. In the
  original that is `A`, whose column 2 is an `INTEGER` column (BINARY): the UNION keeps both
  `'B'` and `'b'` coming from `C`. In the mutant the leftmost arm is `B`, whose column 2 is
  `TEXT COLLATE NOCASE`: the UNION keeps only one of them.
- The rule changes the equality that the enclosing UNION uses. The model has one collation
  equivalence for the whole database, so this case is outside it: not a bug.

Since then the bridge drops every mutant that gives a set operation a leftmost select list
that no set operation of the original has (`changes_compound_collation`, counted as
`mutants_outside_model`). All 44 confirmed pairs were re-checked with SQLite's column
metadata: only one, #40 of the earlier list (seed 2011, `INTERSECT->operand`), has result
columns whose collations differ between original and mutant (BINARY -> NOCASE). Its
violation can be explained by the same gap, so it is withdrawn. The other 43 have the same
column collations on both sides and remain confirmed.

## Fourth round (same seeds again)

After the P1 changes (types compared by family, correlated filters lifted out of
`DISTINCT`, `DISTINCT` around a join printed with `GROUP BY`, `RIGHT JOIN`, `UNION ALL` of
value queries, `INTERSECT ALL` / `EXCEPT ALL`, row `IN`), seeds 2001-2030 were run once
more: 329928 checks passed (328852 before), 3766 mutants unprintable (4310 before), 24
violations = the same 6 distinct pairs, all fixed in 3.53.1; no translation mismatch. All
44 confirmed pairs were re-confirmed with the new checker.

## The second campaign

Run with the extended model and bridge: opaque expressions as `EAtom`, analysed `LIKE`,
derived tables mutated inside, opaque set-operation arms, the exact collation check, and
`DISTINCT` around set operations printed as a derived table.

```bash
L=/tmp/sqlite-libs; python3 bridge/campaign_sqlite.py --focus --rich --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so --seeds 2001-2030 --queries 60 --out violations2.jsonl
```

- 17 violations, 5 distinct pairs (seeds 2004, 2011, 2022), all fixed in 3.53.1.
- 4 translation mismatches, all on seed 2010 and only on the old releases: the query as
  written (with `CROSS JOIN`) and the re-printed query (then with `INNER JOIN ... ON 1 = 1`)
  returned different rows on 3.26.0 to 3.34.0. The bridge now prints `CROSS JOIN` again.
  (Analysed in the ninth round: the rows differ only in `'B'` / `'b'`, the representative of
  a `DISTINCT` over a `NOCASE` column, which depends on the join order; `CROSS JOIN` fixes
  the join order in SQLite. Not an inconsistency modulo the collation.)
- 2964 value queries skipped because an aggregated input held text (`non_numeric_input`).

## Reproduce

```bash
bridge/build_old_sqlite.sh /tmp/sqlite-libs
```

```bash
L=/tmp/sqlite-libs; python3 bridge/campaign_sqlite.py --focus --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so --seeds 1001-1024 --queries 100 --out violations.jsonl
```

```bash
L=/tmp/sqlite-libs; python3 bridge/confirm_sqlite.py results/sqlite-confirmed.jsonl --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so
```

`results/sqlite-confirmed.md` is the output of the last command. For every pair it has the
queries, the first rows of both results and the verdict on each version.
`results/sqlite-confirmed.jsonl` holds the 51 pairs as data; `results/sqlite-withdrawn.jsonl`
the withdrawn ones with the reasons. `results/sqlite-reduced.md` has the pairs reduced by
`bridge/reduce_sqlite.py`, and `results/sqlite-bisect.md` the commits of each bug.

## Limitations

- The campaign ran on four old releases (from npm packages: `sqlite.org` is not reachable).
  The bisection (sixth round) builds SQLite from its git history on GitHub instead.
- "Confirmed" means inconsistent on the old version and consistent on 3.53.1. It does not
  prove which of the two results on the old version is the wrong one.
- The 51 pairs come from 5 bugs, identified by their introducing and fixing commits; three
  fixes name an SQLite ticket. A fixing commit can be a plan change that hides the symptom
  (bug 5).

## Sixth round: commits, reduction, three withdrawals

- `bridge/bisect_sqlite.py` mapped every pair to the commit that fixed it and, where an
  older release is good on the same database, the commit that introduced it.
- `bridge/reduce_sqlite.py --boundaries` reduced all 42 pairs, query and database (460 -> 123
  characters, 33 -> 6 statements), keeping each pair's verdicts on the commits around its
  fix and its introduction, so a reduced pair shows the same bug (`results/sqlite-reduced.md`,
  scripts in `results/sqlite-repro/`). Bisected again, the reduced pairs give the same
  commits, and the introducing commits the full databases could not reach (they needed
  `WITHOUT ROWID`): 5 distinct bugs (`results/sqlite-bisect.md`).
- Pair 38 of the previous numbering was withdrawn: its mutant wraps the leftmost arm of a
  compound, whose column is `COALESCE(...)` without a collation, in a derived table, which
  changes the collation the compound compares with (issues/007).
- Two pairs (former numbers 42 and 43, seed 2009) were withdrawn. The bisection found them
  still "violated" on every release up to 3.54.1. The difference is only which of `'A'` /
  `'a'` a `DISTINCT` over a `NOCASE` column keeps, in the third arm of a `UNION ALL`;
  SQLite's column metadata describes the leftmost arm only (`BINARY`), so the checker
  compared that column exactly. The checker now combines the collations of all arms of a
  compound and does not use the metadata when a compound is nested in a derived table; with
  it, both pairs hold on every release and the others stay confirmed.

## Seventh round: a new campaign (seeds 4001-4030)

After the sixth round the generator gained `DISTINCT` and `UNION` over value queries, and the
bridge the cover check for them. A new campaign ran on the same four releases:

```bash
L=/tmp/sqlite-libs; python3 bridge/campaign_sqlite.py --focus --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so --seeds 4001-4030 --queries 40 --out violations.jsonl
```

- 2400 queries, 262868 checks passed, 12 violations: 3 new distinct pairs (seeds 4004 and
  4028, all `UNION-ALL->UNION`), all consistent on 3.53.1, so all confirmed (pairs 43 to 45).
- Bisected on their full databases they give the fixing commit `9b7005f`; reduced with
  `--boundaries` and bisected again, the introducing commit `9ed1dfa`: all three are bug 1.
  The campaign found no new SQLite bug.
- The value and HAVING rules again found nothing on SQLite. (The window items of the
  generator were added after this campaign started, so it did not exercise them.)

## Eighth round: the extended value queries (seeds 5001-5030)

The value side now covers windows over groups, `SELECT DISTINCT` arms of a `UNION ALL` and
the HAVING rules inside `INTERSECT` / `EXCEPT`; `gen_fragment.py --value-ext` generates
such queries, and SQLite prints `HAVING` without `GROUP BY` in a form the old releases
accept (before, every HAVING mutant of an ungrouped aggregate failed on them).

```bash
L=/tmp/sqlite-libs; python3 bridge/campaign_sqlite.py --focus --value-ext --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so --seeds 5001-5030 --queries 40 --out violations.jsonl
```

- 2400 queries, 257784 checks passed (5556 of them HAVING checks), 4 violations = 1 new
  distinct pair (seed 5023, `UNION->UNION-ALL`, a set rule), consistent on 3.53.1: pair 46.
- Bisected on its full database it gives the fixing commit `9b7005f`; reduced with
  `--boundaries` (679 -> 113 characters) and bisected again, the introducing commit
  `9ed1dfa`: bug 1 again. No new SQLite bug.
- The value and HAVING rules, with the new shapes, found nothing on SQLite. On MariaDB
  10.11.14, 1200 `--value-ext` value queries found 20 violations, all of the shape of
  `issues/009` (now also with `STDDEV_SAMP`).

## Ninth round: value queries over numeric columns (seeds 6001-6030)

In the eighth round 2208 of the 4800 value-query runs (46%) were skipped as
`non_numeric_input`: the generator drew aggregated columns from all columns, and many of
them hold text. The campaign now draws them from the columns declared `INTEGER` or `REAL`
in the seed's schema (`--any-column` restores the old queries).

```bash
L=/tmp/sqlite-libs; python3 bridge/campaign_sqlite.py --focus --value-ext --libs $L/libsqlite3-3260000.so $L/libsqlite3-3300100.so $L/libsqlite3-3310100.so $L/libsqlite3-3340000.so --seeds 6001-6030 --queries 40 --out violations.jsonl
```

- 2400 queries, 292896 checks passed, no run skipped as non-numeric: 44836 value checks
  (19636 in the eighth round) and 11888 HAVING checks (5556).
- 20 violations = 5 new distinct pairs (seeds 6004, 6009, 6026, 6027), all set rules
  (`UNION-ALL->UNION`, `UNION->UNION-ALL`, `EXCEPT->left`), all consistent on 3.53.1: pairs
  47 to 51. Bisected, reduced with `--boundaries` (5 of 5) and bisected again: introduced by
  `9ed1dfa`, fixed by `9b7005f`, so all are bug 1. No new SQLite bug.
- The value and HAVING rules found nothing on SQLite, now with more than twice the checks
  and no skipped queries: the earlier explanation "half of the value queries were not
  checked" is ruled out.

