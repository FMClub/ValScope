# Candidate PolarDB-X bug: a correlated `IN` over a DISTINCT table is NULL where its subquery is empty

Status: open, candidate (PolarDB-X `polardbx/polardb-x:latest`, `5.6.29-PXC-5.4.19-SNAPSHOT`;
MySQL 9 and MariaDB 10.11.14 are correct). Found by the second campaign on PolarDB-X
(`--focus --value-ext`, seeds 1-10) in round 19: seed 3, rule `DISTINCT-add` (a table of a
subquery replaced by `(SELECT DISTINCT * FROM it)`). Not reported upstream.

## Summary

`data/polardbx/distinct-derived.sql`, queries A1-A7:

```sql
CREATE TABLE t (a INT, b INT, rid INT PRIMARY KEY);
INSERT INTO t VALUES (3, NULL, 0), (NULL, 1, 1), (4, 2, 2);

-- for the row (3, NULL), t.b <= 10 is unknown: the subquery is empty and the IN is 0
SELECT t.a, t.a IN (SELECT s.b FROM (SELECT DISTINCT * FROM t) AS s WHERE t.b <= 10) FROM t;
-- expected: (3, 0) (NULL, NULL) (4, NULL).  PolarDB-X: (3, NULL) (NULL, NULL) (4, NULL)
```

| Query | Row (3, NULL): expected | PolarDB-X | MySQL 9, MariaDB 10.11 |
| --- | --- | --- | --- |
| A1 subquery on `t` | 0 | 0 | 0 |
| A2 subquery on `(SELECT DISTINCT * FROM t)` | 0 | **NULL** | 0 |
| A3 subquery on `(SELECT * FROM t)` | 0 | 0 | 0 |
| A4 subquery on `(SELECT DISTINCT b FROM t)` | 0 | **NULL** | 0 |
| A5 A2 with `s.b IS NOT NULL` in the subquery | 0 | 0 | 0 |
| A6 `WHERE NOT (t.a IN (...A2...))` | the row 3 | **no row** | the row 3 |
| A7 `EXISTS (...A2...)` | 0 | 0 | 0 |

The other two rows are right everywhere. The answer is wrong only for a row whose subquery is
empty (the correlated condition is unknown), only when the subquery reads a DISTINCT derived
table, and only when that table holds a NULL in the compared column (A5). A guess consistent
with this: the plan of a NULL-aware semi-join over the DISTINCT table checks "the subquery has
a NULL" on the whole table, without the correlated condition, so an empty subquery is taken
for one with a NULL. EXISTS (A7) does not need that check and is right. Not checked against the
source.

The campaign pair on its database: `data/polardbx/distinct-add-seeds.sql`, seed 3, D1-D7 (the
reduced original returns 3 and 5; its mutant returns nothing).

## Limitations

- One PolarDB-X image (`latest`, 5.4.19 snapshot), all-in-one container.
- Upstream (round 20, a web search with a generic description, not the tracker itself): no
  matching report of PolarDB-X (`polardbx-sql`) was found. Similar defects of other engines:
  MySQL bugs #111485 and #118016 (semi-join / DISTINCT subquery rewrites), #117911 and
  #117959 (`INTERSECT` over outer joins), SPARK-25708 (`HAVING` without `GROUP BY` treated as
  a plain filter).
