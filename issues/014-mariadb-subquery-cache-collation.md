# Candidate MariaDB bug: the subquery cache matches its key under the collation of the outer column, not the one the subquery compares with

Status: open, candidate (MariaDB 10.11.14, 11.4.13, 11.8.9, 13.0.2; found by `bridge/campaign_mysql.py --rich`, seed
147, rule `OR-drop-operand`: `WHERE (0) OR p` and `WHERE p` returned different rows). Not
reported upstream. CI runs the reproducer on every server.

## Summary

A correlated subquery is evaluated once per distinct value of the outer columns it uses;
MariaDB keeps the results in the subquery cache. When the outer column has a
case-insensitive collation (`utf8mb4_general_ci`) and the subquery compares it with a
column of a finer collation (`utf8mb4_bin`), the comparison inside the subquery is made
under `utf8mb4_bin`, but the cache looks its key up under the collation of the outer
column. `'A'` and `'a'` then share one cache entry, and the second of them gets the answer
of the first. The result depends on the order in which the rows are read, and differs from
the semi-join and from the plain join over the same predicate.

## Minimal reproducer

`data/mariadb/subquery-cache-collation.sql`:

```sql
CREATE TABLE a (id INT PRIMARY KEY, s VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci);
CREATE TABLE b (v VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin);
INSERT INTO a VALUES (1, 'A'), (2, 'a');
INSERT INTO b VALUES ('a');

-- expected: 0 for 'A', 1 for 'a' (the comparison is made under utf8mb4_bin)
SELECT id, s, s IN (SELECT v FROM b) FROM a ORDER BY id;        -- returned: 0, 0
SELECT id, s, s IN (SELECT v FROM b) FROM a ORDER BY id DESC;   -- returned: 1, 1

SELECT id FROM a WHERE 0 OR s IN (SELECT v FROM b);             -- expected 2; returned: no rows
SELECT id FROM a WHERE s IN (SELECT v FROM b);                  -- 2 (semi-join)
SELECT a.id FROM a JOIN b ON a.s = b.v;                         -- 2

SET optimizer_switch = 'subquery_cache=off';
SELECT id, s, s IN (SELECT v FROM b) FROM a ORDER BY id;        -- 0, 1
SELECT id FROM a WHERE 0 OR s IN (SELECT v FROM b);             -- 2
```

| Query | Expected | MariaDB 10.11.14 | with `subquery_cache=off` |
| --- | --- | --- | --- |
| `s IN (SELECT v FROM b)`, rows in `id` order | 0, 1 | **0, 0** | 0, 1 |
| the same, rows in reverse order | 1, 0 | **1, 1** | 1, 0 |
| `(SELECT COUNT(*) FROM b WHERE b.v = a.s)` | 0, 1 | **0, 0** | 0, 1 |
| `EXISTS (SELECT 1 FROM b WHERE b.v = a.s)` | 0, 1 | **0, 0** | 0, 1 |
| `WHERE 0 OR s IN (SELECT v FROM b)` | row 2 | **no rows** | row 2 |
| `WHERE s IN (SELECT v FROM b)` (semi-join) | row 2 | row 2 | row 2 |
| `a JOIN b ON a.s = b.v` | row 2 | row 2 | row 2 |

Any correlated subquery is affected, not only `IN`: the scalar subquery and `EXISTS` of the
table give the same wrong values.

## How it was found

Seed 147 of the random databases, generated with `--rich`: `t2.c3` is a
`VARCHAR(20) COLLATE utf8mb4_general_ci` with the values `'A'` and `'a '` (among others),
`t3.c6` a `VARCHAR(20) COLLATE utf8mb4_bin` with the value `'a'`. The original was

```sql
SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE ((0)) OR (t2a.c3 IN (SELECT t3i86.c6 FROM t3 AS t3i86));
```

and returned no row. The rule `OR-drop-operand` removes the operand `(0)`; the mutant must
return a subset (`Down`) and returned one row (`'a '` equals `'a'` under a PAD SPACE
collation). Without the `OR`, MariaDB turns the `IN` into a semi-join, which does not use
the cache.

`bridge/reduce_mysql.py` first left all twelve rows of `t2`: it deleted a row and, when the
pair was no longer violated, inserted it again, at the end of the table. The row with `'A'`
then came after the row with `'a '`, the cache answered 1 for both, and nothing could be
deleted any more. The reducer now rewrites the table in its order at every step, and
reaches two rows of `t2` and one of `t3`. That the cache is the cause was seen by hand:
`SET optimizer_switch = 'subquery_cache=off'` makes the pair agree.

## Limitations

- Servers (local run, CI and `sql.yml`): MariaDB 10.11.14, 11.4.13, 11.8.9 and 13.0.2 show it, in every line
  of the table. MySQL 8.4.13 and 9.7.4 give the expected results (MySQL has no subquery
  cache; the `SET optimizer_switch` line fails there and the script goes on).
- Upstream: a web search for the subquery cache with collations found no matching report
  (MDEV-12429 and MDEV-3113 are about the cache, MDEV-24319 and MDEV-21265 about
  materialization with two collations; none describes this). The tracker itself was not
  searched (no access from this environment).
- The model of the tool has one equivalence per database (`issues/004`, B2.2b); a
  comparison between two collations is outside it. This pair does not depend on that: the
  two queries differ by `0 OR`, which no collation can tell apart.
