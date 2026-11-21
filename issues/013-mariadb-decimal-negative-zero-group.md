# Candidate MariaDB bug: the DECIMAL `-0.00` (from `-3.00 % 3`) is grouped with `0.00` or apart, depending on an unrelated aggregate

Status: open, candidate (MariaDB 10.11.14; found by `bridge/campaign_mysql.py`, seed 33, rule
`COUNT->COUNT-DISTINCT`: "row count 4 vs 5"). Not reported upstream. CI runs the reproducer
on every server.

## Summary

`MOD` of a negative `DECIMAL` that divides evenly gives `-0.00`: `-3.00 % 3` prints as
`-0.00`. That value and `0.00` are

- one group for a plain `GROUP BY x % 3` (with `COUNT(x)`, `MAX(x)`), and one value for
  `SELECT DISTINCT x % 3` and `COUNT(DISTINCT x % 3)`;
- two groups for the same `GROUP BY` when the select list has `COUNT(DISTINCT ...)` or
  `GROUP_CONCAT(...)`;
- different for `=`: `(-3.00 % 3) = (0.00 % 3)` is 0.

So the number of groups depends on an aggregate that does not involve the key, as in
`issues/011` (there for `DOUBLE(M,D)`), here for an exact type.

## Minimal reproducer

`data/mariadb/decimal-negative-zero.sql`:

```sql
CREATE TABLE d (x DECIMAL(10,2));
INSERT INTO d VALUES (-3), (0), (3);

SELECT x % 3 AS k, COUNT(x)          FROM d GROUP BY x % 3;   -- 1 group:  (0.00, 3)
SELECT x % 3 AS k, COUNT(DISTINCT x) FROM d GROUP BY x % 3;   -- 2 groups: (-0.00, 1), (0.00, 2)
SELECT x % 3 AS k, GROUP_CONCAT(x)   FROM d GROUP BY x % 3;   -- 2 groups
SELECT (-3.00 % 3) = (0.00 % 3), CAST(-3.00 % 3 AS CHAR);     -- 0, '-0.00'
```

## Consequence for ValScope

The rule `COUNT->COUNT-DISTINCT` keeps the grouping keys, so the mutant must have the same
groups; here it has one more. The model has no negative zero: `-0.00` and `0.00` are the
same number.

## Limitations

- Servers (local run and CI run 61): MariaDB 10.11.14, 11.4.13 and 11.8.9 show it.
  MySQL 8.4.13 and 9.7.4 are consistent in every query.
- Not checked against the MariaDB bug tracker.
