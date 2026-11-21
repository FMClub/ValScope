# 009: MariaDB returns the AVG of the last group for every row under SELECT DISTINCT

Status: open, candidate (MariaDB 10.11.14; found by `scripts/demo.sh mariadb`, value rule
`expr->expr+k` / `expr->expr*k` on a `SELECT DISTINCT` value query, sixth round).

## Symptom

```sql
SELECT DISTINCT g + 0 AS k, MAX(x) * 2 AS m, AVG(g) AS a FROM t GROUP BY g;
```

returns `a = 3` (the value of the last group) on every row; without `DISTINCT` it returns
`1, 2, 3`. The groups are different anyway, so `DISTINCT` must not change anything. All
three parts are needed: an expression over the grouping key (`g + 0`; plain `g` is
correct), an expression over another aggregate (`MAX(x) * 2`; plain `MAX(x)` is correct),
and `AVG` (`SUM` is correct).

## Reproduction

`data/mariadb/avg-distinct.sql` (also run by CI on MariaDB and MySQL):

```sql
-- issues/009: AVG under SELECT DISTINCT with an expression over the grouping key and over another aggregate
DROP DATABASE IF EXISTS vs_avg; CREATE DATABASE vs_avg; USE vs_avg;
CREATE TABLE t (g INT, x INT);
INSERT INTO t VALUES (1, 10), (2, 20), (3, 30);
-- reference, without DISTINCT: a = 1, 2, 3
SELECT 'no DISTINCT' AS q, g + 0 AS k, MAX(x) * 2 AS m, AVG(g) AS a FROM t GROUP BY g;
-- the same with DISTINCT (the groups are distinct anyway): a must still be 1, 2, 3
SELECT DISTINCT g + 0 AS k, MAX(x) * 2 AS m, AVG(g) AS a FROM t GROUP BY g;
-- variants
SELECT DISTINCT g AS k, MAX(x) * 2 AS m, AVG(g) AS a FROM t GROUP BY g;
SELECT DISTINCT g + 0 AS k, MAX(x) AS m, AVG(g) AS a FROM t GROUP BY g;
SELECT DISTINCT g + 0 AS k, MAX(x) * 2 AS m, SUM(g) AS a FROM t GROUP BY g;
SELECT DISTINCT g + 0 AS k, MIN(x) + 1 AS m, AVG(x) AS a FROM t GROUP BY g;
DROP DATABASE vs_avg;
```

Output on MariaDB 10.11.14:

```
no DISTINCT  1  20  1.0000 / 2  40  2.0000 / 3  60  3.0000
DISTINCT     1  20  3.0000 / 2  40  3.0000 / 3  60  3.0000    <- wrong
DISTINCT g          AVG correct
DISTINCT MAX(x)     AVG correct
DISTINCT ... SUM(g) correct
DISTINCT MIN(x)+1, AVG(x): 30.0000 on every row              <- wrong
```

## The pair that found it

```sql
-- original (value query under DISTINCT, VDistinct.v)
SELECT DISTINCT t1a.c4 AS k0, (MAX(t1a.c1) * 2) AS k1, AVG((t1a.c4 - 500)) AS k2 FROM t1 AS t1a GROUP BY t1a.c4
-- mutant (expr->expr+k on k0: every k0 grows by 3, the rest must stay)
SELECT DISTINCT (t1a.c4 + 3) AS k0, (MAX(t1a.c1) * 2) AS k1, AVG((t1a.c4 - 500)) AS k2 FROM t1 AS t1a GROUP BY t1a.c4
```

In the mutant every row has `k2 = -415`, the value of the last group.
