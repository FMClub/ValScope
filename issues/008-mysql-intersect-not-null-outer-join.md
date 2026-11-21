# 008: MySQL INTERSECT matches a NOT NULL column with the NULL of an outer join

Status: open, candidate (MySQL 8.4.13: minimal case; MySQL 9.7.4: only the larger case on
the sample database, see below; MariaDB 10.11.14 and 11.8.9 are correct). Found by `scripts/demo.sh mariadb` on MySQL with N=300 (rule `DISTINCT-add`).

## Minimal case (`data/mysql/intersect-min.sql`, variant B)

```sql
CREATE TABLE t1 (c1 INT PRIMARY KEY, c4 INT);
CREATE TABLE t2 (c1 INT PRIMARY KEY, c2 INT NOT NULL);
INSERT INTO t1 VALUES (8811, 13);
INSERT INTO t2 VALUES (9623, 3704);
(SELECT t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1))
INTERSECT ALL
(SELECT t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (0));
```

The left arm is `(3704, 13, 9623)`, the right arm `(NULL, 13, NULL)`: the intersection is
empty. MySQL 8.4.13 returns 1 row (the left one) when `t2.c2` is declared `NOT NULL`, and
no row when it is nullable (variant A). The `k0` column of the right arm is `NULL` only
because of the outer join (`t1.c1` is a primary key): MySQL seems to take the column's
`NOT NULL` property, or that of the left arm, for the result of the outer join when it
compares the rows of the two arms.

| Variant (`data/mysql/intersect-min.sql`) | MySQL 8.4.13 | MySQL 9.7.4 | MariaDB 10.11.14 |
| --- | --- | --- | --- |
| A: `t2.c2 INT` (nullable) | 0 | 0 | 0 |
| B: `t2.c2 INT NOT NULL` | **1** | 0 | 0 |
| C: B with `AUTO_INCREMENT` keys | **1** | 0 | 0 |
| D: the column definitions of the sample tables | **1** | 0 | 0 |

On MySQL 9.7.4 the minimal case is correct, but the larger case on the full sample database
(`data/mysql/intersect-all-variants.sql`) still returns the 4 rows of `A`, now even at the
top level: the defect is still reachable there, through another plan. There the original
and the mutant are both wrong in the same way, so the pair is consistent and ValScope does
not see it on 9.7.4 (a metamorphic relation compares two queries, not a query with the
right answer); the parts of the query (`A`, `B UNION ALL C`) show that the result is wrong.
It cannot be reduced by `bridge/reduce_mysql.py` there for the same reason.

The steps that led here: `bridge/reduce_mysql.py` reduced the pair found by the demo on
MySQL 8.4 (query 750 -> 197 characters, rows 14 / 13 -> 1 / 1, 77 secondary indexes -> 0),
and the variants of the column definitions isolated `NOT NULL`.

## History of the analysis




## Symptom

`A INTERSECT ALL (B UNION ALL C)` returns no row: `A` has 4 rows with `k0 = 8811`, and
`B UNION ALL C` has none. On MySQL 8.4.13 the same query as the derived table of
`SELECT DISTINCT * FROM (...)` returns exactly those 4 rows of `A`, which are not in the
intersection. `SELECT DISTINCT` cannot add rows, so one of the two results is wrong; the
parts show that it is the second. MariaDB 10.11.14 returns no row for both.

```
original  0 rows
mutant    4 rows: (8811, 37, 815), (8811, 60, 815), (8811, 78, 815), (8811, 81, 815)
```

## Queries

Original:

```sql
(SELECT t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON t1b.c1 <= 5000 WHERE t1b.c1 >= 1000) INTERSECT ALL ((SELECT t2b.c2 AS k0, t2b.c2 AS k1, t3a.c1 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c2 = 5) AND (t3a.c7 > 5000) WHERE ((t3a.c3 < t2b.c2) OR (t2b.c2 = 1)) OR (EXISTS (SELECT t2s87.c1 FROM t2 AS t2s87 WHERE t2s87.c2 >= t2s87.c2))) UNION ALL (SELECT t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (t1a.c4 IS NULL) AND (t1a.c4 = 20) WHERE ((t1b.c4 >= t1a.c4) OR (t1b.c4 IS NULL)) OR (t1a.c4 <> 20)))
```

Mutant (`DISTINCT-add`, must return a sub-bag of the original):

```sql
SELECT DISTINCT * FROM ((SELECT t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON t1b.c1 <= 5000 WHERE t1b.c1 >= 1000) INTERSECT ALL ((SELECT t2b.c2 AS k0, t2b.c2 AS k1, t3a.c1 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c2 = 5) AND (t3a.c7 > 5000) WHERE ((t3a.c3 < t2b.c2) OR (t2b.c2 = 1)) OR (EXISTS (SELECT t2s87.c1 FROM t2 AS t2s87 WHERE t2s87.c2 >= t2s87.c2))) UNION ALL (SELECT t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (t1a.c4 IS NULL) AND (t1a.c4 = 20) WHERE ((t1b.c4 >= t1a.c4) OR (t1b.c4 IS NULL)) OR (t1a.c4 <> 20)))) AS vs_d1
```

## Variants

`data/mysql/intersect-all-variants.sql` runs the parts and the variants; CI runs it on
MySQL in the job `mysql`. Results on MySQL 8.4.13 (MariaDB 10.11.14: 0 everywhere):

| Query | Rows |
| --- | --- |
| `A`, rows with `k0 = 8811` | 4 |
| `B UNION ALL C`, rows with `k0 = 8811` | 0 |
| 1. `A INTERSECT ALL (B UNION ALL C)` | 0 |
| 2. `SELECT DISTINCT * FROM (1)` | 4 |
| 3. `SELECT COUNT(*) FROM (1)` (no DISTINCT) | 4 |
| 4. `SELECT DISTINCT * FROM (A INTERSECT (B UNION ALL C))` | 4 |
| 5. `A INTERSECT ALL (SELECT * FROM (B UNION ALL C))`, in a derived table | 4 |

So the DISTINCT does not matter: as soon as the `INTERSECT` (with or without ALL) is
evaluated as a derived table, the 4 rows of `A` with `k0 = 8811` are returned although no
row of the right operand has `k0 = 8811`. At the top level the result is empty, as it
should be. The database is the sample database of `scripts/setup_mariadb.sh` (on
MySQL 8.4, 165 index statements of `data/mariadb/indexes.sql` are skipped).

## MySQL 9.7.4 (CI job `candidates-newer-servers`)

On MySQL 9.7.4 the **top-level** `A INTERSECT ALL (B UNION ALL C)` also returns the 4 rows of
`A` (variant 1), as do variants 2 to 4; only variant 5 (a derived right arm) returns 0. So
on 9.7.4 the intersection is wrong without any derived table: rows of the left operand
that do not occur in the right operand are returned. MariaDB 11.8.9: 0 everywhere.

## Reduced (bridge/reduce_mysql.py on MySQL 8.4.13, CI)

The query reduces to two `LEFT JOIN`s of one row each; the right arm has `NULL` in two of
its three columns, so the intersection is empty:

```sql
(SELECT t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1))
INTERSECT ALL
(SELECT t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (0))
```

`data/mysql/intersect-min.sql` runs it on two plain tables with one row each (CI: MySQL 8.4
and 9). MariaDB 10.11.14 returns no row for every form.

With two plain tables (`data/mysql/intersect-min.sql`: one row each, no secondary index)
the reduced query is correct on MySQL 8.4.13 and 9.7.4. So the problem needs the schema of
the sample database (its secondary indexes or column types); `bridge/reduce_mysql.py`
now also drops the secondary indexes that are not needed (CI job `mysql`, step "Reduce the
pair of issue 008").

## Upstream

A web search of the MySQL bug tracker (bugs.mysql.com) for this symptom (INTERSECT with the NULL of an outer join) found no matching report.
The search was by keywords over titles only; the tracker itself is not reachable from the
development environment. Not reported upstream.
