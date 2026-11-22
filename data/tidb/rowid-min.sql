-- TiDB internal error 1105 "Can't find column t1._tidb_rowid": minimal variants.
-- t1 has an INT PRIMARY KEY (clustered: no _tidb_rowid) and a UNIQUE index (c1, c4).
-- expected: every query runs; a tag line, then 'ok' or an error line
DROP DATABASE IF EXISTS vs_rowid2; CREATE DATABASE vs_rowid2; USE vs_rowid2;
CREATE TABLE t1 (c1 BIGINT, c4 DOUBLE, rid INT PRIMARY KEY);
CREATE TABLE t3 (c3 DECIMAL(10,2), c6 VARCHAR(20));
INSERT INTO t1 VALUES (1, 2, 1), (3, 4, 2);
INSERT INTO t3 VALUES (1, 'a');
CREATE UNIQUE INDEX i3 ON t1 (c1, c4);
SELECT 'M1 empty join INTERSECT DISTINCT from t1, unique index' AS q;
SELECT 'ok' FROM ((SELECT t3.c3 AS k FROM t3 WHERE t3.c6 < t3.c6) INTERSECT (SELECT DISTINCT t1.c4 AS k FROM t1 WHERE t1.c1 = 10 OR t1.c4 <= 10)) AS r LIMIT 1;
(SELECT t3.c3 AS k FROM t3 WHERE t3.c6 < t3.c6) INTERSECT (SELECT DISTINCT t1.c4 AS k FROM t1 WHERE t1.c1 = 10 OR t1.c4 <= 10);
SELECT 'M2 M1 without DISTINCT' AS q;
(SELECT t3.c3 AS k FROM t3 WHERE t3.c6 < t3.c6) INTERSECT (SELECT t1.c4 AS k FROM t1 WHERE t1.c1 = 10 OR t1.c4 <= 10);
SELECT 'M3 M1 without the OR' AS q;
(SELECT t3.c3 AS k FROM t3 WHERE t3.c6 < t3.c6) INTERSECT (SELECT DISTINCT t1.c4 AS k FROM t1 WHERE t1.c4 <= 10);
SELECT 'M4 M1 with a left arm that is not empty' AS q;
(SELECT t3.c3 AS k FROM t3) INTERSECT (SELECT DISTINCT t1.c4 AS k FROM t1 WHERE t1.c1 = 10 OR t1.c4 <= 10);
SELECT 'M5 M1 with WHERE 0 on the left' AS q;
(SELECT t3.c3 AS k FROM t3 WHERE 0) INTERSECT (SELECT DISTINCT t1.c4 AS k FROM t1 WHERE t1.c1 = 10 OR t1.c4 <= 10);
SELECT 'M6 M1 with EXCEPT' AS q;
(SELECT t3.c3 AS k FROM t3 WHERE t3.c6 < t3.c6) EXCEPT (SELECT DISTINCT t1.c4 AS k FROM t1 WHERE t1.c1 = 10 OR t1.c4 <= 10);
DROP INDEX i3 ON t1;
SELECT 'M7 M1 without the unique index' AS q;
(SELECT t3.c3 AS k FROM t3 WHERE t3.c6 < t3.c6) INTERSECT (SELECT DISTINCT t1.c4 AS k FROM t1 WHERE t1.c1 = 10 OR t1.c4 <= 10);
SELECT 'end' AS q;
DROP DATABASE vs_rowid2;
