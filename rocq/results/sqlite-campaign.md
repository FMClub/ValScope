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

**37 distinct (original, mutant) query pairs violate the relation that the rule's theorem
guarantees.** All 37 are confirmed:

- the database of the seed was rebuilt by each SQLite library and both queries were run
  again;
- the violation reproduces on the version that reported it;
- the relation holds on SQLite 3.53.1, the version Python ships.

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
| Negative control (`--flip`, 300 queries) | 1544 violations reported |

The rule of the mutation that exposed each pair:

| Rule | Pairs |
| --- | --- |
| `UNION->UNION-ALL` | 19 |
| `UNION-ALL->UNION` | 9 |
| `DISTINCT-add` | 4 |
| `EXCEPT->left` | 2 |
| `cond->TRUE` | 2 |
| `LEFT->INNER-JOIN` | 1 |

The number of pairs violated on each version (a pair can be violated on several):

| Version | Pairs |
| --- | --- |
| 3.26.0 | 33 |
| 3.30.1 | 29 |
| 3.31.1 | 31 |
| 3.34.0 | 31 |

All 37 come from set-semantic rules. The value-semantic and HAVING mutators did not find a
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

A difference that disappears when strings are compared up to case and trailing spaces is
classified as `collation` and is not counted as a violation.

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
`results/sqlite-confirmed.jsonl` holds the 37 pairs as data.

## Limitations

- Only four old releases were tested. `sqlite.org` was not reachable, so the sources come
  from npm packages.
- "Confirmed" means inconsistent on the old version and consistent on 3.53.1. It does not
  prove which of the two results on the old version is the wrong one.
- The 37 pairs most likely share a few root causes; only one cause is analysed, and the
  test cases are not reduced.
