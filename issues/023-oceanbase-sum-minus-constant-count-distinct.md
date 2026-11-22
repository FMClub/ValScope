# Candidate OceanBase bug: `SUM(x - k)` next to `SUM(x)` and `COUNT(DISTINCT x)` is computed as `SUM(x) - k * COUNT(DISTINCT x)`

Status: open, candidate (OceanBase CE `oceanbase/oceanbase-ce:latest`, 4.4.2.1, version string
`5.7.25-OceanBase_CE-v4.4.2.1`; MySQL 9 and MariaDB 10.11.14 are correct). Found by the two
OceanBase campaigns of round 19 (seeds 1-40 `--focus --value-ext --no-set-all`, seeds 131-170
`--rich --value-ext --no-set-all`): most of their value pairs. Not reported upstream.

## Summary

`data/oceanbase/count-distinct-expression.sql`:

```sql
CREATE TABLE u (a INT);
INSERT INTO u VALUES (1), (2), (2), (3), (NULL);

SELECT SUM(u.a - 2), SUM(u.a), COUNT(DISTINCT u.a) FROM u;
-- expected: 0 8 3.  OceanBase: 2 8 3   (8 - 2 * 3: the COUNT(DISTINCT) for the COUNT)
SELECT AVG(u.a - 2), AVG(u.a), COUNT(DISTINCT u.a) FROM u;
-- expected: 0.0000 2.0000 3.  OceanBase: 0.5000 2.0000 3   ((8 - 2 * 3) / 4)
```

| Query | Expected | OceanBase 4.4.2.1 | MySQL 9, MariaDB 10.11 |
| --- | --- | --- | --- |
| C2 / K7 `SUM(a - 2), COUNT(DISTINCT a)` | 0 3 | 0 3 | 0 3 |
| K12 `SUM(a - 2), SUM(a)` | 0 8 | 0 8 | 0 8 |
| K18 `SUM(a - 2), SUM(a), COUNT(a)` | 0 8 4 | 0 8 4 | 0 8 4 |
| K11 `SUM(a - 2), SUM(a), COUNT(DISTINCT a)` | 0 8 3 | **2** 8 3 | 0 8 3 |
| K16 the same with `a + (-2)` | 0 8 3 | **2** 8 3 | 0 8 3 |
| K13 `AVG(a - 2), AVG(a), COUNT(DISTINCT a)` | 0.0000 2.0000 3 | **0.5000** 2.0000 3 | 0.0000 2.0000 3 |
| K15 K13 on a table with a primary key | 0.0000 2.0000 3 | **0.5000** 2.0000 3 | 0.0000 2.0000 3 |
| K17 `SUM(a * 2), SUM(a), COUNT(DISTINCT a)` | 16 8 3 | 16 8 3 | 16 8 3 |
| K2 seed 35: `AVG(c6 - 2), AVG(c6) ... HAVING COUNT(DISTINCT c6) <> 10`, rows 4, 4 | 2.0000 4.0000 | **3.0000** 4.0000 | 2.0000 4.0000 |

Every wrong value is `SUM(x) - k * COUNT(DISTINCT x)` (and that divided by `COUNT(x)` for
`AVG`). A rewrite consistent with this: an aggregate of `x - k` is computed from the aggregates
of `x` that the query already has (`SUM(x - k) = SUM(x) - k * COUNT(x)`), and the
`COUNT(DISTINCT x)` of the query is taken for the `COUNT(x)` it needs, as if DISTINCT did not
matter. All three must be there: without `SUM(x)` / `AVG(x)` (K7) or without the DISTINCT
(K18) it is right; a product (K17) is not rewritten. The `COUNT(DISTINCT x)` may be in the
`HAVING` (K2). Not checked against the source.

The campaign pairs (`data/oceanbase/campaign-pairs.sql`, V queries) show the same with
`VAR_SAMP(x - k)` / `STDDEV_SAMP(x - k)` next to `STDDEV_SAMP(x)` or `AVG(x)` (seeds 31, 140,
143; seed 31 gives a negative variance, -0.67) and with `AVG(x - 2) * 2` next to `AVG(x)`
(seed 162). Pairs of the two campaigns of this issue (27 of their 33): seeds 31, 35 (11 pairs), 133, 140 (2),
141, 142, 143 (5), 144, 150, 162, 166, 169.

## Limitations

- One OceanBase release (CE 4.4.2.1), the `mini` deployment of its container.
- The variance and standard-deviation cases were not reduced as far as `SUM` and `AVG`; they are
  assigned here by their look (an aggregate of `x - k` beside aggregates of `x` and a
  `COUNT(DISTINCT x)`).
- The OceanBase tracker was not searched.
