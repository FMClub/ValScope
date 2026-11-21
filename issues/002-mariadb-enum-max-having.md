# Candidate MariaDB bug: `HAVING MAX(enum_col) <> n` depends on an unrelated aggregate in the select list

> This repository has no issue tracker, so this document (submitted through a PR) records the finding.
> Status: **candidate, not yet reported upstream.** It was reproduced on one version only (see "Limitations").

## Summary

On MariaDB 10.11.14 the predicate `HAVING MAX(e) <> 3`, where `e` is an `ENUM` column, selects different groups depending on which aggregate appears in the select list. The `HAVING` clause and the data are identical; only the select list differs.

| Select list | Groups returned (of 3) |
| --- | --- |
| `g, COUNT(DISTINCT d)` | 1, 2, 3 |
| `g, COUNT(d)` | 1, 2 |
| `g, SUM(id)` | 1, 2 |
| `g` | 1, 2 |

So the same predicate is evaluated with two different semantics:

- When the select list contains `COUNT(DISTINCT d)`, `MAX(e)` is compared with `3` as a **string** (`'value3'` is converted to the number 0, `0 <> 3` is true), so the group whose maximum is `'value3'` is kept. A control with `MAX(CAST(e AS CHAR)) <> 3` behaves the same way.
- Otherwise `MAX(e)` is compared with `3` as the **enum index**, so the group whose maximum is `'value3'` (index 3) is removed. This agrees with the select-list expression `MAX(e) <> 3`, which returns `0` for that group, and with `MAX(e) + 0`, which returns `3`.

This document does not claim which of the two results is the intended one. Either way, a predicate must not change meaning because of an unrelated aggregate in the select list.

## Minimal reproducer

```sql
CREATE TABLE t (
  id INT PRIMARY KEY,
  g  INT,
  d  DATE,
  e  ENUM('value1','value2','value3') NULL
);
INSERT INTO t VALUES
  (1, 1, '2024-01-01', 'value1'),
  (2, 2, '2024-01-02', 'value2'),
  (3, 3, '2024-01-03', 'value3');

-- returns groups 1, 2 and 3
SELECT g, COUNT(DISTINCT d) FROM t GROUP BY g HAVING MAX(e) <> 3;

-- returns groups 1 and 2
SELECT g, COUNT(d) FROM t GROUP BY g HAVING MAX(e) <> 3;
SELECT g, SUM(id) FROM t GROUP BY g HAVING MAX(e) <> 3;
SELECT g       FROM t GROUP BY g HAVING MAX(e) <> 3;

-- the same predicate in the select list: value3 gives 0, i.e. enum-index semantics
SELECT g, MAX(e) AS m, MAX(e) + 0 AS mi, (MAX(e) <> 3) AS ne FROM t GROUP BY g;
--   g  m       mi  ne
--   1  value1  1   1
--   2  value2  2   1
--   3  value3  3   0

-- control: explicit string comparison returns all three groups
SELECT g, COUNT(DISTINCT d) FROM t GROUP BY g HAVING MAX(CAST(e AS CHAR)) <> 3;
```

Observed on `10.11.14-MariaDB-0ubuntu0.24.04.1` with `sql_mode = STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION`.

## How it was found

The value-semantic mutator applies rule 18 (`COUNT(DISTINCT c) → COUNT(c)`) to a seed query. The rule changes the value of one output column but must not change which groups are returned, because `HAVING` does not depend on it. The seed query was:

```sql
SELECT COUNT(DISTINCT t2.c5) AS col_1, t2.c3 AS c3, t2.c13 AS c13, t2.c15 AS col_1_2, t2.c2 AS col_1_3
FROM t2 AS t2
GROUP BY t2.c3, t2.c13, t2.c15, t2.c2
HAVING (MAX(t2.c10) <> 3)
```

where `c10` is `ENUM('value1','value2','value3')`. The original query returned 13 groups and the mutated query (`COUNT(t2.c5)`) returned 11.

It was the only report left after the tool-side fixes described in `issues/001-mutation-soundness-audit.md` (97 reports before the fixes, 1 after). The other 96 reports disappeared with those fixes; every category that was sampled among them was a false positive caused by the tool, not by the database. They were not all checked one by one.

## Further observation (not analysed)

On the 13-row table of the original campaign, `MAX(c10) + 0` returned `0` for every group (string semantics), while on the three-row table above it returns the enum index. The difference may come from the access path (for example a covering index on `c10`), which would mean the semantics depend on the plan as well as on the select list. This was not investigated.

## Limitations

- Reproduced on MariaDB 10.11.14 (locally) and, in CI (`data/mariadb/enum-max-having.sql`),
  on MariaDB 11.8.9 and MySQL 9.7.4: both also return groups 1, 2, 3 with `COUNT(DISTINCT d)`
  and 1, 2 otherwise, so the behaviour is not specific to MariaDB (it may be a shared,
  documented conversion rule; see the next point). Percona, TiDB, OceanBase and PolarDB were
  not tested.
- The cause inside the server was not analysed; the `COUNT(DISTINCT)` and non-`DISTINCT` variants probably take different aggregation paths.
- The intended semantics of `MAX(enum_col)` in a comparison with a number was not checked against the documentation.

## Suggested next steps

1. Re-run the reproducer on the latest MariaDB release and on MySQL 8.x and 9.x, and record the results here.
2. If it still reproduces, report it upstream with the three-row reproducer.
