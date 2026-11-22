# Candidate TiDB bug: `SELECT DISTINCT` with an `OR` over two indexed columns fails with "Can't find column t1._tidb_rowid"

Status: open, candidate (TiDB v7.5.1 and v8.5.3; MariaDB 10.11.14 runs every query). Found
by `bridge/campaign_mysql.py --tidb` on TiDB v8.5.3 (seed 22): two mutants failed with this
error and were counted as `mutant_failed`, the campaign's error summary listed the message.
Not reported upstream.

## Summary

`data/tidb/rowid-distinct-or.sql`:

```sql
CREATE TABLE t1 (c1 BIGINT, c4 DOUBLE, rid INT PRIMARY KEY);
INSERT INTO t1 VALUES (0, 4, 0), (5, 10, 1), (0, NULL, 2), (2, 10, 3), (1, 3, 4), (2, 4.5, 5),
  (-1, -3, 6), (10, 10, 7), (3, NULL, 8), (4, 1.25, 9), (-1, 3.25, 10), (4, 7, 11), (4, NULL, 12),
  (7, 1.25, 13), (NULL, 1, 14);
CREATE INDEX i2 ON t1 (c4);
CREATE UNIQUE INDEX i3 ON t1 (c1, c4);
ANALYZE TABLE t1;

SELECT DISTINCT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10;
-- ERROR 1105 (HY000): Can't find column vs_rowid.t1._tidb_rowid in schema
--   Column: [vs_rowid.t1.c1,vs_rowid.t1.c4,vs_rowid.t1.rid] Unique key: []
```

`rid INT PRIMARY KEY` is a clustered primary key in TiDB, so the table has no hidden
`_tidb_rowid`; the planner nevertheless asks for it. The query is valid and runs before the
`ANALYZE TABLE` (then the plan is an index merge of `i3` and `i2` with a `TableRowIDScan`).

| Query, after `ANALYZE TABLE t1` | TiDB v7.5.1, v8.5.3 |
| --- | --- |
| S1 `SELECT DISTINCT c4 ... WHERE c1 = 10 OR c4 <= 10` | **error 1105** |
| the same before `ANALYZE` | runs |
| S2 without `DISTINCT` | runs |
| S3 `GROUP BY c4` instead of `DISTINCT` | **error 1105** |
| S4 `COUNT(*)` | runs |
| S5 `AND` instead of `OR` | runs |
| S6 `SELECT DISTINCT rid` | **error 1105** |
| S7 S1 without an index on `c1` alone | **error 1105** |
| S8 S7 without the unique index `(c1, c4)` | runs |

So the ingredients are: a clustered integer primary key, a unique index on the two columns of
the `OR`, an index on one of them, statistics, and an aggregation (`DISTINCT` / `GROUP BY`)
above the scan.

## How it was found

The first query of `gen_fragment.py --focus --tidb --mysql-seed 22` is a compound whose
`INTERSECT` operand is `SELECT DISTINCT t1a.c4 ... WHERE (t1a.c1 = 10) OR (t1a.c4 <= 10)`. Its
mutants failed with error 1105 in the campaign; the variants of
`data/tidb/rowid-parts.sql` (the database of seed 22, with and without `ANALYZE`) showed that
the operand alone fails and only after `ANALYZE`, and the table above was taken from there.

## Limitations

- TiDB v7.5.1 and v8.5.3 only.
- Upstream (web search, round 18; the tracker itself was not searched): TiDB's documentation
  says `_tidb_rowid` does not exist for a table with a clustered primary key, which confirms
  that the plan refers to a column that cannot be there. The forum has reports of the same
  error family ("Can't find column Column#40 in schema", TiDB 7.1.0, on a table with a
  clustered key and a new index), not of this query.
- An error is not a wrong result, and ValScope does not judge errors: a mutant the server
  refuses is skipped. This one was noticed in the error summary of the campaign, which
  lists every message (`campaign_mysql.py`, "error xN"). Internal errors (1105) of TiDB are
  now worth reading in every campaign.
