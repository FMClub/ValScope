# Candidate PolarDB-X bug: the parentheses of a UNION on the right of a UNION ALL (or of a UNION ALL on the right of a UNION) are dropped

Status: open, candidate (PolarDB-X `polardbx/polardb-x:latest`, `5.6.29-PXC-5.4.19-SNAPSHOT`;
MySQL 9 and MariaDB 10.11.14 are correct). Found by the PolarDB-X campaign with `--tidb`
(`--focus --value-ext --tidb`, seeds 1-10) in round 20: the two pairs of rule `INTERSECT->UNION`
(seeds 1 and 3), whose mutants are `L UNION ALL (A UNION B)` and `(A UNION B) UNION ALL (C UNION D)`.
Not reported upstream.

## Summary

`data/polardbx/union-all-nested-union.sql`:

```sql
CREATE TABLE t (a INT, rid INT PRIMARY KEY);
INSERT INTO t VALUES (1, 0), (1, 1);

(SELECT t.a FROM t) UNION ALL ((SELECT 2 AS a) UNION (SELECT 3 AS a));
-- expected: 1 1 2 3.  PolarDB-X: 1 2 3
(SELECT t.a FROM t) UNION ((SELECT 2 AS a) UNION ALL (SELECT 2 AS a));
-- expected: 1 2.  PolarDB-X: 1 2 2
```

| Query | Expected | PolarDB-X | MySQL 9, MariaDB 10.11 |
| --- | --- | --- | --- |
| U1 `t UNION ALL (empty UNION empty)` | 1 1 | **1** | 1 1 |
| U2 `t UNION ALL (2 UNION 3)` | 1 1 2 3 | **1 2 3** | 1 1 2 3 |
| U3 `(2 UNION 3) UNION ALL t` | 2 3 1 1 | 2 3 1 1 | 2 3 1 1 |
| U4 `(t UNION 5) UNION ALL (5 UNION 6)` | 1 5 5 6 | **1 5 6** | 1 5 5 6 |
| U5 `t UNION ALL t` | 1 1 1 1 | 1 1 1 1 | 1 1 1 1 |
| U6 U2 with the `UNION` in a derived table | 1 1 2 3 | 1 1 2 3 | 1 1 2 3 |
| U7 `t UNION (2 UNION ALL 2)` | 1 2 | **1 2 2** | 1 2 |
| U8 `t UNION ALL t UNION 9` (no parentheses) | 1 9 | 1 9 | 1 9 |
| U9 `t UNION 9 UNION ALL t` (no parentheses) | 1 9 1 1 | 1 9 1 1 | 1 9 1 1 |
| U10 / U11 `t UNION ALL (2 INTERSECT 2)` / `(2 EXCEPT 3)` | 1 1 2 | 2 1 1 (right) | 1 1 2 |

Every wrong answer is the answer to the same chain without the parentheses on its right
operand: U2 is U8's reading of `t UNION ALL 2 UNION 3` (the last `UNION` removes the
duplicates on its left, as MySQL's manual says for a chain), U7 is `(t UNION 2) UNION ALL 2`.
A parenthesized left operand (U3) is right, since a left-deep chain keeps it anyway, and so are
a derived table (U6) and an `INTERSECT` / `EXCEPT` operand (U10, U11). A guess: the parser or
the planner flattens nested `UNION`s into one n-ary union and keeps one ALL / DISTINCT flag per
link, losing the grouping of the right operand. Not checked against the source.

The two campaign pairs on their reduced databases: `data/polardbx/intersect-union-pairs.sql`
(pair 2: 1 row instead of 4; pair 3: 2 rows instead of 3).

## Limitations

- One PolarDB-X image (`latest`, 5.4.19 snapshot), all-in-one container.
- Upstream (a web search with a generic description, round 20): no matching PolarDB-X report
  was found. MySQL had defects of the same family long ago: bug #6565 (a mix of `UNION ALL` and
  `UNION DISTINCT` in a view), bug #50136.
