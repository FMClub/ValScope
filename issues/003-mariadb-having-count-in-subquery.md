# Candidate MariaDB bug: `HAVING <aggregate> IN (subquery)` finds no match in a grouped query

> This repository has no issue tracker, so this document (submitted through a PR) records the finding.
> Status: **candidate, not yet reported upstream.** It was reproduced on one version only (see "Limitations").

## Summary

On MariaDB 10.11.14, in a query with `GROUP BY`, the predicate `HAVING COUNT(x) IN (SELECT ...)` behaves as if the subquery never contained the value. Groups that should be returned are missing, and with `NOT IN` groups that should be removed are returned.

The same condition gives the expected result when it is written with a literal list, with `EXISTS`, over a derived table, with `COUNT(x) + 0`, or when subquery materialization is switched off.

## Minimal reproducer

```sql
CREATE TABLE t (id INT PRIMARY KEY, g INT, x INT);
INSERT INTO t VALUES (1, 1, 10), (2, 1, 20), (3, 2, 30);
CREATE TABLE s (id INT PRIMARY KEY, v INT);
INSERT INTO s VALUES (1, 2), (2, 7);

-- the groups: g = 1 has COUNT(x) = 2, g = 2 has COUNT(x) = 1
SELECT g, COUNT(x) FROM t GROUP BY g;

-- expected: g = 1 (2 is in {2, 7}).  Returned: no rows.
SELECT g FROM t GROUP BY g HAVING COUNT(x) IN (SELECT v FROM s);

-- expected: g = 2 only.  Returned: g = 1 and g = 2.
SELECT g FROM t GROUP BY g HAVING COUNT(x) NOT IN (SELECT v FROM s);
```

## Variants

All on the tables above. "Expected" is what the definition of `IN` gives.

| Query (`SELECT g FROM t GROUP BY g HAVING ...`) | Expected | Returned |
| --- | --- | --- |
| `COUNT(x) IN (SELECT v FROM s)` | 1 | no rows |
| `COUNT(*) IN (SELECT v FROM s)` | 1 | no rows |
| `COUNT(x) = ANY (SELECT v FROM s)` | 1 | no rows |
| `COUNT(x) IN (SELECT CAST(v AS SIGNED) FROM s)` | 1 | no rows |
| `MIN(x) IN (SELECT v * 5 FROM s)` | 1 | no rows |
| `COUNT(x) NOT IN (SELECT v FROM s)` | 2 | 1, 2 |
| `COUNT(x) IN (2, 7)` | 1 | 1 |
| `COUNT(x) + 0 IN (SELECT v FROM s)` | 1 | 1 |
| `CAST(COUNT(x) AS SIGNED) IN (SELECT v FROM s)` | 1 | 1 |
| `EXISTS (SELECT 1 FROM s WHERE s.v = COUNT(t.x))` | 1 | 1 |
| `SUM(x) IN (SELECT v * 15 FROM s)` | 1, 2 | 1, 2 |

Other observations:

- With `COUNT(DISTINCT x)` added to the select list, the first query returns `g = 1`.
- The equivalent query over a derived table is correct:
  `SELECT g FROM (SELECT g, COUNT(x) c FROM t GROUP BY g) d WHERE c IN (SELECT v FROM s)` returns 1.
- Without `GROUP BY` the result is correct:
  `SELECT COUNT(x) FROM t HAVING COUNT(x) IN (SELECT v + 1 FROM s)` returns 3.
- `SET optimizer_switch = 'materialization=off'` makes the first query return `g = 1`.
  `semijoin=off` alone does not.
- `EXPLAIN` of the first query shows the subquery as `MATERIALIZED`.

So the wrong result appears when a bare `COUNT` or `MIN` in `HAVING` of a grouped query is looked up in a materialized subquery. `SUM` (which returns a DECIMAL) and any expression around the aggregate are not affected in these tests.

Observed on `10.11.14-MariaDB-0ubuntu0.24.04.1` with the default `optimizer_switch`.

## How it was found

By the Rocq version of ValScope (branch `claude/rocq-core`, `rocq/`), in a run of value-semantic mutations on generated queries with `HAVING`. The rule `COUNT(c) → COUNT(DISTINCT c)` changes one select item and must not change which groups are returned. For this query it did (0 rows before, 1 row after):

```sql
SELECT (t2a.c2 % 5) AS k0, ..., COUNT((t2a.c1 - 50)) AS k4
FROM t2 AS t2a
WHERE (t2a.c1 > 20) OR (t2a.c2 > 1000)
GROUP BY (t2a.c2 % 5)
HAVING (COUNT(t2a.c14 - 50)) IN (SELECT t3h55.c6 FROM t3 AS t3h55 WHERE t3h55.c8 < 50)
```

The mutant (with `COUNT(DISTINCT ...)` in the select list) returned the group whose count is 3, which is in the subquery result `{2, 4, 40, 3}`. The original returned nothing. The original is the wrong one.

It was the only violation in 37572 value-semantic checks over 3000 generated queries. The mutants of the `HAVING` predicate itself did not expose it, because the original and those mutants were wrong in the same way.

## Limitations

- Reproduced on MariaDB 10.11.14 only. No other MariaDB version was tried, and MySQL, Percona, TiDB, OceanBase and PolarDB were not tested.
- The cause inside the server was not analysed. The variants suggest a type or item-reference problem in the lookup key of the materialized subquery, but that is a guess.
- It was not checked whether this is already known upstream.

## Suggested next steps

1. Re-run the reproducer on the latest MariaDB release and on MySQL 8.x and 9.x, and record the results here.
2. Search the MariaDB bug tracker for `HAVING`, `IN` subquery and materialization.
3. If it still reproduces and is not known, report it upstream with the three-row reproducer.
