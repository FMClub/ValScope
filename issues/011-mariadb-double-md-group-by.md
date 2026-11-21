# Candidate MariaDB bug: `GROUP BY` on a `DOUBLE(M,D)` expression forms different groups depending on an unrelated aggregate

Status: open, candidate (MariaDB 10.11.14). Seen first as "the number of groups of a
`GROUP BY` on a DOUBLE expression depends on the select list" (README, issue 004 C.2) and
left unanalysed until the ninth round. Not reported upstream. CI runs the reproducer on
every server.

## Summary

For a column declared with display decimals (`DOUBLE(12,4)`, `FLOAT(8,2)`: non-standard,
deprecated types) an expression such as `x % 2` has 4 declared decimals. A plain `GROUP BY`
on it groups by the value **rounded to the declared decimals**; the same `GROUP BY` in a
query with `COUNT(DISTINCT ...)` or `GROUP_CONCAT(...)` groups by the **unrounded double**.
So the number of groups depends on an aggregate that has nothing to do with the key.

With a plain `DOUBLE` column the grouping is by the unrounded value in every variant
(consistent), and with `DECIMAL(12,4)` by the exact value (consistent).

## Minimal reproducer

`data/mariadb/double-md-group.sql`:

```sql
CREATE TABLE t (id INT PRIMARY KEY AUTO_INCREMENT, x DOUBLE(12,4));
INSERT INTO t (x) VALUES (3.87), (5.87), (91.87), (1.87);   -- x % 2 prints 1.8700 for all four

SELECT x % 2 AS k, COUNT(DISTINCT x - 5) FROM t GROUP BY x % 2;   -- 2 groups
SELECT x % 2 AS k, COUNT(x - 5)          FROM t GROUP BY x % 2;   -- 1 group
SELECT x % 2 AS k, MAX(id)               FROM t GROUP BY x % 2;   -- 1 group
SELECT x % 2 AS k, GROUP_CONCAT(id)      FROM t GROUP BY x % 2;   -- 2 groups
SELECT COUNT(DISTINCT x % 2), MIN(x % 2) = MAX(x % 2) FROM t;     -- 1, 1: the values compare equal
```

| Column type | `COUNT(DISTINCT)` | `COUNT` | `MAX` | `GROUP_CONCAT` |
| --- | --- | --- | --- | --- |
| `DOUBLE(12,4)` | **2** | 1 | 1 | **2** |
| `FLOAT(8,2)` | **3** | 1 | 1 | **3** |
| `DOUBLE` | 2 | 2 | 2 | 2 |
| `DECIMAL(12,4)` | 1 | 1 | 1 | 1 |

## Consequence for ValScope

The model groups by exact values. A value mutation that turns `COUNT(x)` into
`COUNT(DISTINCT x)` (rule `COUNT->COUNT-DISTINCT`) would change the groups on such keys, so
`run_on_db.py` skips value queries whose grouping keys are FLOAT or DOUBLE
(`approximate_group_key`). That rule is conservative: plain `DOUBLE` keys are consistent
and could be admitted; the sample schema has only `FLOAT(8,2)` and `DOUBLE(12,4)` columns,
so this would not add coverage there.

## Limitations

- MariaDB 10.11.14 only (locally); the CI log shows MySQL and the newer MariaDB releases.
- Whether upstream considers grouping by the rounded value of a `DOUBLE(M,D)` expression
  intended was not checked; the inconsistency between two queries with the same `GROUP BY`
  is the finding.
