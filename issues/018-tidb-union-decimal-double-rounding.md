# Candidate TiDB bug: a UNION of a DECIMAL and a DOUBLE arm rounds the DOUBLE to the DECIMAL's scale (`ATAN(1)` becomes 0.8)

Status: open, candidate (TiDB v8.5.3; MySQL 9.7.4 and MariaDB 10.11.14 keep the DOUBLE). Found
while analysing five false alarms of the TiDB campaign (round 14): the checker had to learn
that a UNION column can be rounded, and the rounding itself looked wrong. Not reported
upstream.

## Summary

`data/tidb/union-decimal-double.sql`:

```sql
CREATE TABLE t (i INT, d DECIMAL(10,2));
INSERT INTO t VALUES (1, 1.50);

SELECT ATAN(t.i) AS k FROM t UNION ALL SELECT 1.5;
-- MySQL 9.7.4, MariaDB 10.11.14: 0.7853981633974483, 1.5
-- TiDB v8.5.3:                   1.5, 0.8
```

| Query | MySQL 9.7.4, MariaDB 10.11.14 | TiDB v8.5.3 |
| --- | --- | --- |
| U1 `ATAN(t.i) UNION ALL AVG(t.i)` | 0.7853981633974483, 1 | **0.7854**, 1.0000 |
| U2 `t.d UNION ALL ATAN(t.i)` | 1.5, 0.7853981633974483 | 1.50, **0.79** |
| U3 `ATAN(t.i) UNION ALL MAX(t.i)` (an integer arm) | 0.7853981633974483, 1 | 0.7853981633974483, 1 |
| U4 `ATAN(t.i) UNION ALL 1.5` | 0.7853981633974483, 1.5 | **0.8**, 1.5 |

MySQL derives `DOUBLE` for a column with a `DECIMAL` and a `DOUBLE` arm (`CREATE TABLE ... AS`
of U2 gives `k double`). TiDB derives a `DECIMAL` with the scale of the `DECIMAL` arm and
rounds the values of the `DOUBLE` arm to it: one decimal for the literal `1.5`, so
`ATAN(1) = 0.785...` is returned as `0.8`. TiDB's documentation says its precision math is
consistent with MySQL, and that an expression with an approximate value has an approximate
result; neither holds here.

## Effect on ValScope

A mutation that changes the type of one arm changes the type of the column: `AVG->MAX` turns
the `AVG` arm (a DECIMAL) into an integer, the column becomes `DOUBLE`, and a row of the
*other* arm changes from 0.7854 to 0.7853981633974483. The checker allows one unit of the last
printed decimal when a result reports a fixed number of decimals (`printed_decimals`), so
such pairs are not reported; the five pairs of round 14 were reported only because of a
mistake in that rule, fixed since.

## Limitations

- TiDB v8.5.3 only; v7.5.1 not run.
- A web search found no TiDB report of this case (MySQL itself had bugs in UNION type
  derivation: 13372, 43432, 81642). The TiDB tracker was not searched.
- Whether TiDB considers this a documented incompatibility was not checked beyond the page on
  precision math.
