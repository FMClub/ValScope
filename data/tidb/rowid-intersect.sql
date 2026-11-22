-- Candidate TiDB bug (issues/017): SELECT DISTINCT with an OR over two indexed columns fails
-- with error 1105 "Can't find column t1._tidb_rowid in schema", although t1 has an INT PRIMARY
-- KEY (clustered: there is no _tidb_rowid).  Only after ANALYZE TABLE.  Found by
-- bridge/campaign_mysql.py on TiDB v8.5.3 (seed 22); narrowed in data/tidb/rowid-parts.sql.
-- expected: every query runs (a tag line, then its rows)
DROP DATABASE IF EXISTS vs_rowid; CREATE DATABASE vs_rowid; USE vs_rowid;
CREATE TABLE t1 (c1 BIGINT, c4 DOUBLE, rid INT PRIMARY KEY);
INSERT INTO t1 VALUES (0, 4, 0), (5, 10, 1), (0, NULL, 2), (2, 10, 3), (1, 3, 4), (2, 4.5, 5), (-1, -3, 6), (10, 10, 7), (3, NULL, 8), (4, 1.25, 9), (-1, 3.25, 10), (4, 7, 11), (4, NULL, 12), (7, 1.25, 13), (NULL, 1, 14);
CREATE INDEX i2 ON t1 (c4);
CREATE UNIQUE INDEX i3 ON t1 (c1, c4);
CREATE INDEX i5 ON t1 (c1);
SELECT 'before ANALYZE' AS q;
SELECT DISTINCT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10;
ANALYZE TABLE t1;
SELECT 'S1 DISTINCT, OR over c1 and c4' AS q;
SELECT DISTINCT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10;
SELECT 'S2 S1 without DISTINCT' AS q;
SELECT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10;
SELECT 'S3 S1 with GROUP BY c4' AS q;
SELECT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10 GROUP BY c4;
SELECT 'S4 S1 with COUNT(*)' AS q;
SELECT COUNT(*) FROM t1 WHERE c1 = 10 OR c4 <= 10;
SELECT 'S5 S1 with AND' AS q;
SELECT DISTINCT c4 FROM t1 WHERE c1 = 10 AND c4 <= 10;
SELECT 'S6 S1 selecting rid' AS q;
SELECT DISTINCT rid FROM t1 WHERE c1 = 10 OR c4 <= 10;
EXPLAIN SELECT DISTINCT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10;
DROP INDEX i5 ON t1;
ANALYZE TABLE t1;
SELECT 'S7 S1 without the index on c1' AS q;
SELECT DISTINCT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10;
DROP INDEX i3 ON t1;
ANALYZE TABLE t1;
SELECT 'S8 S7 without the unique index' AS q;
SELECT DISTINCT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10;
SELECT 'end' AS q;
DROP DATABASE vs_rowid;
