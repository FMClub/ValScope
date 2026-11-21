# Candidate MariaDB bug: `number IN (SELECT date_column ...)` is FALSE instead of NULL when the subquery has a NULL and the column is indexed

Status: open, candidate (MariaDB 10.11.14; found by `bridge/campaign_mysql.py`, seeds 26 and
27, rules `cond->TRUE`, `cmp-weaken` and `DISTINCT-add`: 5 pairs). Not reported upstream.
CI runs the reproducer on every server.

## Summary

`x IN (subquery)` is NULL, never FALSE, when no value of the subquery equals `x` and the
subquery returns a NULL; `x NOT IN (subquery)` then selects no row. When `x` is a number
(`DOUBLE`, `INT`, `DECIMAL`), the subquery column is a `DATE` or `DATETIME` and that column
has an index, MariaDB returns FALSE for some `x`, and `NOT IN` returns rows. Without the
index the result is NULL for every `x`. A query result must not depend on an index.

## Minimal reproducer

`data/mariadb/in-date-index-null.sql`:

```sql
CREATE TABLE t (x DOUBLE);
CREATE TABLE s (v DATE);
INSERT INTO t VALUES (0), (1), (-3), (NULL);
INSERT INTO s VALUES ('2024-01-01'), (NULL);

SELECT x, x IN (SELECT v FROM s) FROM t ORDER BY x;           -- NULL for every x
SELECT COUNT(*) FROM t WHERE x NOT IN (SELECT v FROM s);      -- 0

CREATE INDEX si ON s (v);
SELECT x, x IN (SELECT v FROM s) FROM t ORDER BY x;           -- 0 for x = -3 and x = 1 (NULL for 0 and NULL)
SELECT COUNT(*) FROM t WHERE x NOT IN (SELECT v FROM s);      -- 2
```

| `x` type | subquery column | without index | with index |
| --- | --- | --- | --- |
| `DOUBLE`, `INT`, `DECIMAL(10,2)` | `DATE`, `DATETIME` | NULL, NULL, NULL | NULL, **0, 0** (for 0, 1, -3) |
| `DOUBLE` | `INT`, `VARCHAR(10)` | NULL | NULL |
| `INT` | `INT` | NULL | NULL |

## How it was found

Seed 26 of the random databases (`bridge/gen_mysql_db.py`): `t1.c1` is a `DATE` with an
index and one NULL, `t1.c4` a `DOUBLE`. The original had
`NOT (t1a.c4 IN (SELECT t1i48.c1 FROM t1 AS t1i48 WHERE t1i48.c1 IS NULL))` in a join
condition and returned no row; the mutant of `cond->TRUE` (the inner `WHERE` replaced by
`1 = 1`) must return a subset (`Down`) and returned 276 rows. `bridge/recheck_mysql.py
--no-indexes` showed that the five pairs hold when the secondary indexes are dropped.

## Limitations

- MariaDB 10.11.14 only (locally); the CI log shows MySQL and the newer MariaDB releases.
- Comparing a number with a `DATE` converts one of them; which conversion the index
  lookup uses was not analysed. Whatever it is, a NULL in the subquery cannot give FALSE.
- Not checked against the MariaDB bug tracker.
