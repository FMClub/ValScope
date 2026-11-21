# Candidate MariaDB bug: a window function with `SUM(DISTINCT ...)` in a grouped join loses the groups that pass `HAVING`

Status: open, candidate (MariaDB 10.11.14; found by the translation check of
`bridge/run_on_db.py --value` on `data/python-generator-queries.sql`, right after window
functions over groups were admitted as opaque items). Not reported upstream. CI runs the
reproducer on MariaDB 10.11, MySQL 8.4, `mariadb:11` and `mysql:9` (see Limitations).

## Summary

In a grouped query over a join, a select list that holds both a window function and an
aggregate with `DISTINCT` (`SUM(DISTINCT x)`, `COUNT(DISTINCT x)`) makes MariaDB apply
`HAVING` wrongly. On the small database below no group is returned, although two groups
satisfy the predicate. On the sample database of `scripts/setup_mariadb.sh` the opposite
happens: all 10 groups are returned, three of which fail the predicate (the predicate,
also put in the select list, is `0` for them). Removing any one ingredient (the window,
the `DISTINCT` of the aggregate, the join) gives the right result.

## Minimal reproducer

`data/mariadb/window-sum-distinct-having.sql`:

```sql
CREATE TABLE t (id INT PRIMARY KEY, g INT, x INT, y INT);
CREATE TABLE u (id INT PRIMARY KEY, k INT);
INSERT INTO t VALUES (1, 1, 1, 5), (2, 1, 2, 20), (3, 2, 3, 30), (4, 3, 4, 1);
INSERT INTO u VALUES (1, 1), (2, 2), (3, 3), (4, 4);

-- expected: g = 1 (MAX(y) = 20) and g = 2 (MAX(y) = 30).  Returned: no rows.
SELECT t.g, SUM(DISTINCT t.x) AS s, COUNT(*) OVER () AS r
FROM t JOIN u ON u.k = t.id GROUP BY t.g HAVING MAX(t.y) >= 10;
```

| Variant | Rows (expected 2) |
| --- | --- |
| window + `SUM(DISTINCT t.x)`, join | **0** |
| the same with `ORDER BY t.g` | **0** |
| window + `COUNT(DISTINCT t.x)`, join | **0** |
| `RANK() OVER (ORDER BY t.g)` instead of `COUNT(*) OVER ()` | **0** |
| window + `SUM(t.x)` (no `DISTINCT`), join | 2 |
| `SUM(DISTINCT t.x)` without a window, join | 2 |
| window + `SUM(DISTINCT t.x)`, no join | 2 |

## Second symptom: an expression over the window function is 0

With the same ingredients (a grouped join, an aggregate with `DISTINCT`, a window function)
and no `HAVING`, an expression over the window function evaluates to 0:

```sql
-- the tables above.  Expected r3 = 4, 5, 6.  Returned: 0, 0, 0 (r itself is 1, 2, 3).
SELECT t.g, COUNT(DISTINCT t.x) AS c, RANK() OVER (ORDER BY t.g) AS r, RANK() OVER (ORDER BY t.g) + 3 AS r3
FROM t JOIN u ON u.k = t.id GROUP BY t.g;
```

With `COUNT(t.x)`, or without the join, `r3` is 4, 5, 6. This one was found by a ValScope
rule: once the engine's mutants of a window item survived the round trip, `expr->expr+k`
turned `RANK() OVER (...)` into `RANK() OVER (...) + 3` in a Python-generator query, and the
mutated column went from 1 to 0 where the theorem promises a value >= 1 (`Le col 1`). Such
violations are recognised by the baseline signature `mariadb-window-distinct-agg`
(`scripts/check_violations.py`).

## How it was found

The query of the corpus was

```sql
SELECT DISTINCT t2.c12 AS c12, DENSE_RANK() OVER (ORDER BY 1=1) AS col_1, SUM(DISTINCT t2.c2) AS col_1_2,
       t2.c9 AS c9, t2.c13 AS c13
FROM t2 AS t2 CROSS JOIN t3 AS t3 ON (t3.c3 = t2.c1)
GROUP BY t2.c12, t2.c13, t2.c13, t2.c9, t2.c13, t2.c13, t2.c13 HAVING (BIT_AND(t2.c14) >= 10)
ORDER BY t2.c13 DESC LOCK IN SHARE MODE
```

The bridge re-prints a query from its algebra term (without the `ORDER BY`, which does not
change the bag of rows) and requires both to return the same rows before it mutates it.
They did not (7 rows as written, 10 re-printed), so the query was not used, and the
difference was analysed by hand: the 7 rows are right, the 10 rows contain the three
groups whose `BIT_AND(t2.c14)` is 3 or 5. ValScope's own relations were not involved:
this is a metamorphic relation of the translation check (`ORDER BY` without `LIMIT`
does not change the result).

## Limitations

- MariaDB 10.11.14 (locally, and CI), 11.4.13 and 11.8.9 (CI): both symptoms present.
- MariaDB 13.0.2 (`mariadb:latest`, round 12): both symptoms present.
  MySQL 8.4.13 and 9.7.4 (CI): 2 rows in every variant, correct; the problem is specific to
  MariaDB.
- Not checked against the MariaDB bug tracker.
- Possibly related upstream reports (found by a web search of the titles; the tickets were
  not read in full): MDEV-9787 "Window functions: HAVING and GROUP BY", MDEV-10859 "Wrong
  result of aggregate window function in query with HAVING and no ORDER BY" (fixed in
  10.2.4), MDEV-25736 "ROW_NUMBER() returns wrong results for query with distinct count and
  grouping". MDEV-25736 has the same ingredients (window, `COUNT(DISTINCT)`, grouping) and
  should be compared first.
