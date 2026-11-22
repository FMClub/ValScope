-- Candidate TiDB bug (issues/017): a valid query fails with error 1105
-- "Can't find column t1._tidb_rowid in schema" although t1 has an INT PRIMARY KEY (clustered,
-- so there is no _tidb_rowid).  Found by bridge/campaign_mysql.py on TiDB v8.5.3 (seed 22).
-- Needed, from the variants of round 14 (data/tidb/rowid-parts.sql): t1 in both operands of
-- the compound, a DISTINCT with an OR over two columns in one of them, and a UNIQUE index on
-- those two columns.
-- expected: every query runs (a tag line, then its rows or 'ok')
DROP DATABASE IF EXISTS vs_rowid; CREATE DATABASE vs_rowid; USE vs_rowid;
CREATE TABLE t1 (c1 BIGINT, c4 DOUBLE, rid INT PRIMARY KEY);
INSERT INTO t1 VALUES (1, 2, 1), (3, 4, 2), (10, 20, 3);
CREATE UNIQUE INDEX i3 ON t1 (c1, c4);
SELECT 'R1 t1 UNION DISTINCT t1 with OR' AS q;
(SELECT a.c4 AS k FROM t1 AS a) UNION (SELECT DISTINCT b.c4 AS k FROM t1 AS b WHERE b.c1 = 10 OR b.c4 <= 10);
SELECT 'R2 the same with UNION ALL' AS q;
(SELECT a.c4 AS k FROM t1 AS a) UNION ALL (SELECT DISTINCT b.c4 AS k FROM t1 AS b WHERE b.c1 = 10 OR b.c4 <= 10);
SELECT 'R3 the DISTINCT operand alone' AS q;
SELECT DISTINCT b.c4 AS k FROM t1 AS b WHERE b.c1 = 10 OR b.c4 <= 10;
SELECT 'R4 R1 without DISTINCT' AS q;
(SELECT a.c4 AS k FROM t1 AS a) UNION (SELECT b.c4 AS k FROM t1 AS b WHERE b.c1 = 10 OR b.c4 <= 10);
SELECT 'R5 R1 with AND instead of OR' AS q;
(SELECT a.c4 AS k FROM t1 AS a) UNION (SELECT DISTINCT b.c4 AS k FROM t1 AS b WHERE b.c1 = 10 AND b.c4 <= 10);
SELECT 'R6 R1 with the other column selected' AS q;
(SELECT a.c1 AS k FROM t1 AS a) UNION (SELECT DISTINCT b.c1 AS k FROM t1 AS b WHERE b.c1 = 10 OR b.c4 <= 10);
SELECT 'R7 R1 in a derived table' AS q;
SELECT COUNT(*) FROM ((SELECT a.c4 AS k FROM t1 AS a) UNION (SELECT DISTINCT b.c4 AS k FROM t1 AS b WHERE b.c1 = 10 OR b.c4 <= 10)) AS r;
SELECT 'R8 DISTINCT with OR, self-join' AS q;
SELECT DISTINCT b.c4 FROM t1 AS a JOIN t1 AS b ON 1 WHERE b.c1 = 10 OR b.c4 <= 10;
DROP INDEX i3 ON t1;
SELECT 'R9 R1 without the unique index' AS q;
(SELECT a.c4 AS k FROM t1 AS a) UNION (SELECT DISTINCT b.c4 AS k FROM t1 AS b WHERE b.c1 = 10 OR b.c4 <= 10);
SELECT 'end' AS q;
DROP DATABASE vs_rowid;
