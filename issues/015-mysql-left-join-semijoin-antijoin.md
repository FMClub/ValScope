# Candidate MySQL bug: a LEFT JOIN loses its inner side when an EXISTS inside it and a NOT EXISTS outside it are both materialized on the constant 1

Status: open, candidate (MySQL 8.0.46, 8.4.13, 9.7.4; MySQL 5.7.44 and MariaDB are correct).
Found by the campaign of `.github/workflows/campaign.yml` on `mysql:9` (`--rich`, seed 144;
rules `LEFT->INNER-JOIN`, `cmp-weaken`, `cond->FALSE`, `cond->TRUE`: six pairs). Not reported
upstream.

## Summary

```sql
CREATE TABLE a (x INT);
CREATE TABLE b (y INT);
INSERT INTO a VALUES (1), (2), (3), (4), (5);
INSERT INTO b VALUES (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11);

-- a.x + 100 is never 1: NOT EXISTS is true for every row of a.  EXISTS is true.
-- expected: 5 * 11 = 55 rows.  Returned: 5 rows, with b.y NULL.
SELECT b.y, a.x FROM a LEFT JOIN b ON EXISTS (SELECT 1 FROM b AS s)
WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
```

The LEFT JOIN returns every row of `a` once, extended with NULLs, as if `b` were empty. The
same query with `INNER JOIN` returns the 55 rows, so a LEFT JOIN returns fewer rows than
the INNER JOIN over the same tables and condition.

## Variants

`data/mysql/left-join-semijoin-antijoin.sql`; expected 55 in every line.

| Variant | MySQL 5.7.44 | MySQL 8.0.46, 8.4.13, 9.7.4 | MariaDB 10.11.14 |
| --- | --- | --- | --- |
| `a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1)` | 55 | **5** | 55 |
| `a LEFT JOIN b ON EXISTS (SELECT 1 FROM b AS s) WHERE NOT EXISTS (...)` | 55 | **5** | 55 |
| the first with `INNER JOIN` | 55 | 55 | 55 |
| the first with `a.x + 100 = 2` in the `NOT EXISTS` | 55 | 55 | 55 |
| the first without the `EXISTS` in the derived table | 55 | 55 | 55 |
| the first with `WHERE a.x <> 100` instead of the `NOT EXISTS` | 55 | 55 | 55 |
| the first with `a.x NOT IN (SELECT u.x + 100 FROM a AS u)` | 55 | 55 | 55 |
| the first with `optimizer_switch = 'materialization=off'` | 55 | 55 | 55 |
| the first with `optimizer_switch = 'semijoin=off'` | 55 | 55 | 55 |
| one row in each table | 1 | 1 | 1 |

## What the plan shows

`EXPLAIN FORMAT=TREE` of the first variant on MySQL 9.7.4:

```
-> Nested loop left join
    -> Nested loop antijoin
        -> Table scan on a
        -> Filter: ((a.x + 100) = `<subquery4>`.`1`)
            -> Single-row index lookup on <subquery4> using <auto_distinct_key> (1 = (a.x + 100))
                -> Materialize with deduplication
                    -> Table scan on u
    -> Nested loop inner join
        -> Single-row index lookup on <subquery3> using <auto_distinct_key> (1 = `<subquery4>`.`1`)
            -> Materialize with deduplication
                -> Table scan on s
        -> Table scan on b
```

Both subqueries select the constant 1 and are materialized. `<subquery3>` is the `EXISTS`
of the inner side; its lookup key should be the constant 1, and it is
`<subquery4>.1`, the column of the table materialized for the `NOT EXISTS`. That table is
the inner side of an antijoin: a row of `a` passes exactly when it has **no** row there, so
the key is NULL, the lookup finds nothing, and the inner side of the LEFT JOIN is empty.
With `= 2` in the `NOT EXISTS` the two constants differ and the plan has
`Constant row from <subquery3>` instead: the result is right. So the optimizer seems to put
`1`, `<subquery3>.1` and `<subquery4>.1` into one equality class and to pick a member that
is not available on that side of the antijoin. This reading comes from the plans, not from
the source of the server.

## How it was found

Seed 144 of the random databases with the rich generator. The original, as
`bridge/reduce_mysql.py` reduced it on MySQL 9.7.4 (5 rows of `t3`, 11 of `t1`):

```sql
SELECT t1b.c1 AS k0 FROM t3 AS t3a
LEFT JOIN (SELECT x.c1 AS c1 FROM t1 AS x WHERE EXISTS (SELECT t1s52.c1 FROM t1 AS t1s52)) AS t1b ON (1)
WHERE NOT (EXISTS (SELECT t3s36.c1 FROM t3 AS t3s36 WHERE (CAST(t3a.c6 AS SIGNED)) = 1));
```

returned 5 rows; the mutant of `LEFT->INNER-JOIN` (must return a subset, `Down`) returned
55, and the mutant of `cmp-weaken` (`= 1` to `<= 1`, a superset) returned 55 where the
original has 5 rows that are not among them. `t3a.c6` is a `DATE`, so the cast is
20240101 or more. The tables above were written by hand from the plan: the names, the
types and the cast do not matter, the constant 1 on both sides does.

## Limitations

- Upstream: a web search found reports of the same family, not this case:
  MySQL bugs 107607 and 113718 ("left join + semijoin + materialization finds false
  matches"), 105637 and 121207. Whether one of them is the same defect was not checked
  (the tracker was not read from this environment). The defect is present in the newest
  release tested, 9.7.4.
- The row counts matter: with one row per table the optimizer does not materialize and the
  result is right. Other sizes were not tried.
- The cause is inferred from `EXPLAIN`.
