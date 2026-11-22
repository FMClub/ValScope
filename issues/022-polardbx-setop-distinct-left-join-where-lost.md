# Candidate PolarDB-X bug: in an INTERSECT / EXCEPT arm, `(SELECT DISTINCT * FROM u) LEFT JOIN u ... WHERE b.x IN (subquery)` loses its WHERE

Status: open, candidate (PolarDB-X `polardbx/polardb-x:latest`, `5.6.29-PXC-5.4.19-SNAPSHOT`;
MySQL 9 and MariaDB 10.11.14 are correct). Found by the second campaign on PolarDB-X
(`--focus --value-ext`, seeds 1-10) in round 19: seed 7, rule `DISTINCT-add`. Not reported
upstream.

## Summary

`data/polardbx/distinct-derived.sql`, queries B9-B16:

```sql
CREATE TABLE u (a DECIMAL(10,2), b DECIMAL(10,2));          -- no key, a duplicate row
INSERT INTO u VALUES (1, 5), (1, 5), (2, 2), (NULL, 0);
CREATE TABLE l (k0 INT, k1 INT, rid INT PRIMARY KEY);
INSERT INTO l VALUES (3, NULL, 0), (NULL, NULL, 1), (9, NULL, 2), (4, 7, 3), (1, NULL, 4), (2, NULL, 5);
CREATE TABLE r (x INT, y INT, rid INT PRIMARY KEY);
INSERT INTO r VALUES (5, 6, 0);

-- the right arm is empty: b.a is NULL (ON (0)), and NULL IN (...) is not true
(SELECT l.k0, l.k1 FROM l) INTERSECT
(SELECT a.a AS k0, b.a AS k1 FROM (SELECT DISTINCT * FROM u) AS a LEFT JOIN u AS b ON (0)
 WHERE (b.a, b.b) IN (SELECT r.x, r.y FROM r));
-- expected: no row.  PolarDB-X: (NULL, NULL) (1, NULL) (2, NULL)
```

| Query | Expected | PolarDB-X | MySQL 9, MariaDB 10.11 |
| --- | --- | --- | --- |
| B9 the right arm alone | none | none | none |
| B10 `l EXCEPT arm`, arm on `u` | the 6 rows of `l` | the 6 rows | the 6 rows |
| B11 `l EXCEPT arm`, arm on `(SELECT DISTINCT * FROM u)` | the 6 rows | **3 rows** (without the `(a, NULL)` of `u`) | the 6 rows |
| B12 `l INTERSECT arm` (above) | none | **3 rows** | none |
| B13 B12 with `b.a IN (SELECT r.x FROM r)` | none | **3 rows** | none |
| B14 B13 with `INNER JOIN u AS b ON (0)` | none | none | none |
| B15 B13 without the join, `a.b IN (SELECT r.x ...)` | (1, NULL) | (1, NULL) | (1, NULL) |
| B16 B13 with `LEFT JOIN u AS b ON (1 = 1)` | none | **3 rows** | none |
| B3, B4 B11 / B12 with a table that has a primary key | as B10 / none | right | right |

The arm alone is right (B9), and so is the same arm in a `UNION ALL` (`data/polardbx/distinct-except-seed7.sql`, E3).
Inside an `INTERSECT` or `EXCEPT`, the arm returns `(a.a, NULL)` for every row of `u`: the
rows of the `LEFT JOIN` without its `WHERE b.a IN (subquery)`. It needs the `DISTINCT` to do
something (a table without a key; with a primary key it is right, B3 / B4), a `LEFT JOIN`
(B14), and the `IN` subquery on the column of the outer-joined side (with `b.c1 = 5` it is
right, E10 of the seed-7 script). A guess: when a set operation is planned as a join of its
arms, the semi-join of the `IN` is pushed into the `LEFT JOIN` as a condition of its `ON`,
where a failed match keeps the row with NULLs instead of removing it. Not checked against the
source.

The campaign pair on its database: `data/polardbx/distinct-add-seeds.sql` (seed 7, D7 / D8)
and the variants E1-E11 of `data/polardbx/distinct-except-seed7.sql`. These variants also show
that PolarDB-X compares a `VARCHAR` with a `DECIMAL` arm as numbers (`'01'` equals `1.00`,
E5), where MySQL compares them as strings; that is a difference of type derivation, not this
issue.

## Limitations

- One PolarDB-X image (`latest`, 5.4.19 snapshot), all-in-one container.
- The PolarDB-X tracker was not searched.
