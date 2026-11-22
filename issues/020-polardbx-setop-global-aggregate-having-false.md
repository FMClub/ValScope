# Candidate PolarDB-X bug: an arm of INTERSECT / EXCEPT that aggregates without GROUP BY ignores a constant false HAVING

Status: open, candidate (PolarDB-X `polardbx/polardb-x:latest`, version string
`5.6.29-PXC-5.4.19-SNAPSHOT`; MySQL 9 and MariaDB 10.11.14 are correct). Found by the first
campaign on PolarDB-X (`--focus --value-ext`, seeds 1-10) in round 19: the three pairs of rule
`HAVING cond->FALSE` (seeds 4, 5, 7). Not reported upstream.

## Summary

`data/polardbx/having-false-global.sql`:

```sql
CREATE TABLE t (a INT, rid INT PRIMARY KEY);
INSERT INTO t VALUES (3, 0), (NULL, 1), (1, 2), (4, 3);

SELECT COUNT(t.a) FROM t HAVING 1 = 0;                                    -- no row (right)
(SELECT 0 AS k) INTERSECT (SELECT COUNT(t.a) AS k FROM t HAVING 1 = 0);   -- expected: no row; PolarDB-X: 0
(SELECT 0 AS k) EXCEPT    (SELECT COUNT(t.a) AS k FROM t HAVING 1 = 0);   -- expected: 0;      PolarDB-X: no row
```

| Query | Expected | PolarDB-X | MySQL 9, MariaDB 10.11 |
| --- | --- | --- | --- |
| Q1 `COUNT ... HAVING 1 = 0` alone | none | none | none |
| Q2 `... HAVING FALSE` alone | none | none | none |
| Q3 Q1 as a derived table | none | none | none |
| Q4 `0 INTERSECT (COUNT HAVING 1 = 0)` | none | **0** | none |
| Q5 `0 EXCEPT (COUNT HAVING 1 = 0)` | 0 | **none** | 0 |
| Q6 `7 UNION ALL (COUNT HAVING 1 = 0)` | 7 | 7 | 7 |
| Q7 `7 UNION (COUNT HAVING 1 = 0)` | 7 | 7 | 7 |
| Q8 `NULL INTERSECT (MIN HAVING 1 = 0)` | none | **NULL** | none |
| Q9 `0 EXCEPT (COUNT HAVING FALSE)` | 0 | **none** | 0 |
| Q10 `0 EXCEPT (COUNT HAVING COUNT(t.a) < 0)` | 0 | 0 | 0 |
| Q11 `0 EXCEPT (COUNT WHERE 1 = 0 HAVING 1 = 0)` | 0 | **none** | 0 |
| Q12 `0 EXCEPT (COUNT GROUP BY a HAVING 1 = 0)` | 0 | 0 | 0 |
| Q13 `(COUNT HAVING 1 = 0) UNION ALL 3` | 3 | 3 | 3 |

The arm returns one row, the aggregates of no rows (`COUNT` 0, `MIN` NULL), as if the
constant false HAVING had become a false WHERE. That needs all of: an arm of `INTERSECT` or
`EXCEPT` (not `UNION`, not a derived table), aggregates without `GROUP BY`, and a HAVING that
is a constant (`1 = 0`, `FALSE`; a false condition on an aggregate, Q10, is right). A guess
consistent with the table: a rule of the set-operation planning pushes or simplifies a
constant HAVING below the aggregate, where it empties the input rather than the output. Not
checked against the source.

The three campaign pairs on their own databases (`data/polardbx/having-false-seeds.sql`):
each arm alone is right, the mutant (the arm with `HAVING 1 = 0` inside the compound) returns
`(NULL, NULL)` (seed 4), `(NULL, 0)` (seed 5), or loses the row 0 of the `EXCEPT` (seed 7).

## Limitations

- One PolarDB-X image (`latest`, 5.4.19 snapshot), run in its all-in-one container; whether the
  distributed deployment plans the same way is not known.
- The campaign pairs could not be reduced automatically at first (`DELETE` without `WHERE` is
  forbidden; the reducer now truncates); the reproducer was written by hand from their arms.
- Upstream (round 20, a web search with a generic description, not the tracker itself): no
  matching report of PolarDB-X (`polardbx-sql`) was found. Similar defects of other engines:
  MySQL bugs #111485 and #118016 (semi-join / DISTINCT subquery rewrites), #117911 and
  #117959 (`INTERSECT` over outer joins), SPARK-25708 (`HAVING` without `GROUP BY` treated as
  a plain filter).
