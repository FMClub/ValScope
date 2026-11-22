# Candidate TiDB bug: `A INTERSECT (B INTERSECT C)` keeps a row of `A` that matches only the NULL of a DATE column

Status: open, candidate (TiDB v8.5.3; MySQL 9.7.4 and MariaDB 10.11.14 are correct). Found by
the campaign on TiDB v8.5.3 (`--focus --tidb`, seed 8, rule `INTERSECT->UNION`) in round 18,
once the collation rule no longer hid it (see Limitations). Not reported upstream.

## Summary

`data/tidb/intersect-date-int.sql`:

```sql
CREATE TABLE t2 (c1 BIGINT, c15 VARCHAR(20));
CREATE TABLE t3 (c6 DATE, c7 INT);
INSERT INTO t2 VALUES (NULL, '2');
INSERT INTO t3 VALUES ('2024-12-28', NULL), (NULL, 4);

-- {'2'} INTERSECT ({2024-12-28, NULL} INTERSECT {NULL, 4}) = {'2'} INTERSECT {NULL} = {}
(SELECT c15 AS k FROM t2) INTERSECT ((SELECT c6 AS k FROM t3) INTERSECT (SELECT c7 AS k FROM t3));
-- expected: no row.  TiDB v8.5.3: '2'
```

| Query | Expected | TiDB v8.5.3 | MySQL 9.7.4, MariaDB 10.11.14 |
| --- | --- | --- | --- |
| I1 `B INTERSECT C` | NULL | NULL | NULL |
| I2 `A INTERSECT (B INTERSECT C)` | no row | **'2'** | no row |
| I3 I2 as a derived table | no row | **'2'** | no row |
| I5 `(A INTERSECT B) INTERSECT C` | no row | no row | no row |
| I7 `A INTERSECT (SELECT NULL)` | no row | no row | no row |
| I8 I2 with `c6` a `VARCHAR` | no row | no row | no row |
| I9 I2 with 3 instead of 4 in `c7` | no row | **'2'** | no row |

The inner result is right (I1), and `A` against a literal NULL is right (I7). What remains is
the outer `INTERSECT` comparing the `VARCHAR` of `A` with the inner result, whose column comes
from a `DATE`. A guess consistent with I8: TiDB compares in `DATE`, the string `'2'` is not a
date and becomes NULL, and an `INTERSECT` treats two NULLs as equal, so `'2'` matches the
inner NULL. MySQL derives a string type for the column and compares `'2'` with NULL as
distinct. Not checked against the source.

## Limitations

- TiDB v8.5.3 only.
- The pair was found in round 18 and not before: on TiDB, whose result collations are not
  trusted, every `INTERSECT` / `EXCEPT` over text counted as a mixed-collation compound and its
  violations as `collation`. The rule now applies only when the differing rows hold strings a
  collation can make equal; `'2'` is not one.
- The TiDB tracker was not searched.
