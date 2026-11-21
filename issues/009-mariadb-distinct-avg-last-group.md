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

## Another query of the same shape

`gen_fragment.py --value 200 2` gives a second pair: an expression over the grouping key
(the mutant's `t3a.c7 + 3`), an expression over another aggregate (`SIGN(COUNT(...))`) and
`AVG`, under `SELECT DISTINCT ... GROUP BY ... HAVING ...`:

```sql
SELECT DISTINCT t3a.c7 AS k0, COUNT(t3a.c2) AS k1, AVG(t3a.c2) AS k2, SIGN(COUNT((t3a.c9 % 3))) AS k3
FROM t3 AS t3a GROUP BY t3a.c7 HAVING ...
```

`bridge/reduce_mysql.py` reduces the first pair to 2 rows of `t1`.

## Newer versions and MySQL (CI, sixth round)

MariaDB 11.8.9 returns `3.0000` on every row (and `30.0000` for the last variant): still
present. MySQL 8.4.13 and 9.7.4 return `1, 2, 3` (and `10, 20, 30`): correct, the problem
is specific to MariaDB.

## Also STDDEV_SAMP (seventh round)

A run of 1200 generated value queries with `--value-ext` on MariaDB 10.11.14 found 20
violations, all of this shape (`SELECT DISTINCT`, an expression over a grouping key, and an
aggregate that is computed at the end). Most use `AVG`; two use only `VAR_SAMP` and
`STDDEV_SAMP`, and there `STDDEV_SAMP` of the last group is copied into every row:

```sql
-- the sample database of scripts/setup_mariadb.sh
SELECT DISTINCT (t2a.c1 % 2) + 3 AS k0, VAR_SAMP(t2a.c1) + 6 AS k1, STDDEV_SAMP(t2a.c1 + t2a.c15) AS k2
FROM t2 AS t2a WHERE t2a.c2 > 50 GROUP BY (t2a.c1 % 2);
-- (3, 3329079.0667, 3207.22949395), (4, 10310799.9048, 3207.22949395)
-- without DISTINCT, or with the key itself as k0: k2 = 1841.46421693 for the first group
```

`data/mariadb/avg-distinct.sql` has a self-contained `STDDEV_SAMP` variant.

## Upstream

MDEV-9445 "Wrong result for a grouping query with DISTINCT" (confirmed, open) is very
likely the same defect: its reproducer `SELECT DISTINCT (COUNT(*) + 1) AS c FROM t1 GROUP BY a`
returns one row on MariaDB 10.11.14 (checked here; three groups with counts 2, 1, 3 give
the single row 3 instead of 3, 2, 4). In both cases an expression over an aggregate, or an
aggregate computed at the end, is evaluated once for the last group under `SELECT DISTINCT`.
The ticket was found by a web search and not read in full; nothing was reported upstream.
