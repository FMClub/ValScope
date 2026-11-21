# 006: MariaDB returns 255 for a BIT(8) scalar subquery under a loose index scan

Status: open (MariaDB 10.11.14, found by `scripts/demo.sh mariadb`, rule `DISTINCT-add`).

## Symptom

A scalar subquery that returns a `BIT(8)` value is evaluated once per group of an outer
`GROUP BY`. When the outer `GROUP BY` uses a loose index scan (`EXPLAIN` shows
"Using index for group-by") and the result goes through a derived table and a `UNION ALL`
with a string, every row holds `255` instead of the value of the subquery (`14` below).

Without the loose index scan (drop the key `ky`), or without the `UNION ALL`, the rows
hold `14`.  The query that found the problem wraps the left arm of the union in
`SELECT DISTINCT * FROM (...)`: the original returned `14` (the plan used no loose scan for
it), the mutant `255`, so the mutant had rows the original does not have.

This is not the text encoding of issue 005: `255` is not any encoding of `0x0E`, and the
subquery returns `14` when it is evaluated on its own.

## Reproduction

```sql
DROP DATABASE IF EXISTS vs_bit2; CREATE DATABASE vs_bit2; USE vs_bit2;
CREATE TABLE b (x BIT(8));
INSERT INTO b VALUES (14), (19);
CREATE TABLE g (k INT PRIMARY KEY, y INT, UNIQUE KEY ky (k, y));
INSERT INTO g VALUES (1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8);
-- loose index scan for the GROUP BY, then DISTINCT, then a union with a string
SELECT x FROM (SELECT DISTINCT * FROM (SELECT (SELECT x FROM b ORDER BY x LIMIT 1) AS x FROM g GROUP BY g.k) d) u
UNION ALL SELECT 'a';
-- the same without DISTINCT
SELECT x FROM (SELECT * FROM (SELECT (SELECT x FROM b ORDER BY x LIMIT 1) AS x FROM g GROUP BY g.k) d) u
UNION ALL SELECT 'a';
DROP DATABASE vs_bit2;
```

Output on MariaDB 10.11.14:

```
x
255
a
x
255   (8 rows)
a
```

Expected `14` in place of every `255`.

## Original pair

```sql
-- original: 28 rows, the left arm holds 14
(SELECT GROUP_CONCAT(yjg85.c2 ORDER BY yjg85.c2 SEPARATOR ',') AS col_1,
        (SELECT s127.c12 AS subq_col FROM t2 AS s127 ORDER BY s127.c12 ASC LIMIT 1) AS col_2
 FROM t1 AS yjg85 GROUP BY yjg85.c1 ORDER BY yjg85.c1 DESC)
UNION ALL (SELECT xro13.c2 AS col_1, 62 AS col_2 FROM t1 AS xro13)
-- mutant (DISTINCT-add, must be a sub-bag): the left arm holds 255
(SELECT DISTINCT * FROM (... the same left arm ...) AS vs_d2)
UNION ALL (SELECT xro13.c2 AS col_1, 62 AS col_2 FROM t1 AS xro13)
```

`t1` has the key `idx_t1_pk_c4 (c1, c4)`, which the plan uses for the loose scan;
`t2.c12` is `BIT(8)` (`data/mariadb/`).

## MySQL

On MySQL 8.4.13 (CI job `mysql`), the reproduction above returns `14` on every row, as
expected: the problem is specific to MariaDB.

## Newer versions (CI job `candidates-newer-servers`, sixth round)

MariaDB 11.8.9 returns `255` on every row: still present. MySQL 9.7.4 returns `14`.

## Upstream

A web search of the MariaDB bug tracker (jira.mariadb.org) for this symptom (BIT scalar subquery under a loose index scan) found no matching report.
The search was by keywords over titles only; the tracker itself is not reachable from the
development environment. Not reported upstream.
