# 007: SQLite compares a compound column with another collation than its derived table

Status: open, candidate (SQLite 3.53.1 and 3.54.1; found while reducing confirmed pair 38).
It may be intended behaviour; it is reported here because the two rules below disagree.

## Symptom

SQLite takes the collation of a compound column from **the left-most arm whose item has a
collating sequence** (`src/select.c`, `multiSelectCollSeq`: "The collating sequence for
the compound select is taken from the left-most term of the select that has a collating
sequence"). An expression such as `COALESCE(c1, 0)` has none, so the next arm's column
decides: `NOCASE` below.

When the same compound is a derived table, the derived table's column gets the
collation of the left-most arm only, and an expression without collation gives `BINARY`.
So the same `UNION ALL` de-duplicates `'a'` and `'A'` as equal in one query and as
different in the other.

## Reproduction

```sql
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE);
INSERT INTO t1 VALUES ('a'), ('A');
-- 1: the EXCEPT compares with NOCASE (the collation of the second arm)
SELECT COALESCE(c1, 0) AS k FROM t1 UNION ALL SELECT c1 FROM t1 EXCEPT SELECT 'zz';
-- 2: the same UNION ALL as a derived table: its column is BINARY
SELECT DISTINCT * FROM (SELECT COALESCE(c1, 0) AS k FROM t1 UNION ALL SELECT c1 FROM t1) AS d;
-- 3: the same, then the same EXCEPT
SELECT DISTINCT * FROM (SELECT COALESCE(c1, 0) AS k FROM t1 UNION ALL SELECT c1 FROM t1) AS d EXCEPT SELECT 'zz';
```

On SQLite 3.53.1 and 3.54.1, query 1 returns one row (`'a'`); queries 2 and 3 return two
(`'a'`, `'A'`). Query 3 differs from query 1 only by `SELECT DISTINCT * FROM (...)`
around the left operand of `EXCEPT`, which cannot add rows (rule `DISTINCT-add`).

## Consequence for ValScope

The model has one collation equivalence for the whole database, so it cannot describe
this. Since the sixth round the bridge computes, for SQLite, the item that decides the
collation of every compound column (`sql_bridge.sqlite_collation_sources`, following the
rule above, with `*` over a derived table resolved to the derived table's item, `BINARY`
for an expression), and drops a mutant that changes it (`mutants_outside_model`).
`reduce_sqlite.py --latest` keeps a reduction from drifting into this behaviour (it did
for pair 38 without it).
