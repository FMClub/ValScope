-- Candidate TiDB bug: a valid query fails with error 1105 "Can't find column t1._tidb_rowid in schema"
-- although t1 has an INT PRIMARY KEY (clustered, so there is no _tidb_rowid).  The database of
-- seed 22 of bridge/gen_mysql_db.py and the first query of gen_fragment.py --focus --tidb for it.
-- expected: every query runs (the tag line, then its rows or an error)
DROP DATABASE IF EXISTS vs_rowid; CREATE DATABASE vs_rowid; USE vs_rowid;
CREATE TABLE t1 (c1 BIGINT, c4 DOUBLE, rid INT PRIMARY KEY) ENGINE=InnoDB;
INSERT INTO t1 VALUES (0, 4, 0), (5, 10, 1), (0, NULL, 2), (2, 10, 3), (1, 3, 4), (2, 4.5, 5), (-1, -3, 6), (10, 10, 7), (3, NULL, 8), (4, 1.25, 9), (-1, 3.25, 10), (4, 7, 11), (4, NULL, 12), (7, 1.25, 13), (NULL, 1, 14);
CREATE TABLE t2 (c1 VARCHAR(20) COLLATE utf8mb4_general_ci, c2 DATE, c3 DECIMAL(10,2), c14 VARCHAR(20) COLLATE utf8mb4_bin, c15 INT, rid INT PRIMARY KEY) ENGINE=InnoDB;
INSERT INTO t2 VALUES ('4', '2024-12-01', 1, NULL, NULL, 0), ('4', '2024-02-01', -0.5, 'A', -1, 1), ('10', '2024-02-15', 4, '2', 4, 2), ('7', '2024-01-28', NULL, 'x', 4, 3), ('a ', '2024-02-15', NULL, '5', 5, 4), ('1', '2024-01-01', 1.75, '-3', 1, 5), (NULL, '2024-01-01', 2, '7', NULL, 6), ('a ', '2024-01-28', 1.5, NULL, 2, 7), (' 1', NULL, 10, '', -1, 8), ('1', '2024-01-01', 3, 'a ', -3, 9), ('a', '2024-01-15', 3.75, 'a ', 0, 10), ('2', '2024-01-15', 10, 'A', 2, 11), ('01', '2024-12-28', 7, 'x', NULL, 12), (NULL, '2024-01-15', 1, NULL, 2, 13);
CREATE TABLE t3 (c1 INT, c2 VARCHAR(20) COLLATE utf8mb4_bin, c3 DECIMAL(10,2), c6 VARCHAR(20) COLLATE utf8mb4_bin, c7 DOUBLE, c8 DECIMAL(10,2), c9 INT, rid INT PRIMARY KEY) ENGINE=InnoDB;
INSERT INTO t3 VALUES (10, '01', 1, '', -3, 3, NULL, 0), (NULL, '0', 2, '1', 1, 1, 3, 1), (0, NULL, -3, 'b', 5, 2, 2, 2), (-1, 'a', -1, 'A', 0, NULL, 1, 3), (0, '01', 10.25, ' 1', -3, NULL, 0, 4), (1, '3', 5.5, NULL, 5, 4, 3, 5), (0, '01', 7, ' 1', -1, NULL, NULL, 6), (1, 'a ', NULL, '0', 7.25, 10, 4, 7), (2, 'a', 2, 'a ', 1.1, 2, NULL, 8), (4, '-1', 0, 'a ', 10.25, 4, -1, 9), (NULL, 'A', 1.75, '', 5, 1, 4, 10), (NULL, 'a ', NULL, '2', 5.5, -3, -1, 11);
CREATE INDEX i0 ON t3 (c8);
CREATE INDEX i1 ON t3 (c6);
CREATE INDEX i2 ON t1 (c4);
CREATE UNIQUE INDEX i3 ON t1 (c1, c4);
CREATE INDEX i4 ON t3 (c7, c6, c9);
CREATE INDEX i5 ON t1 (c1);
CREATE INDEX i6 ON t2 (c1, c14);
ANALYZE TABLE t1;
ANALYZE TABLE t2;
ANALYZE TABLE t3;
SELECT 'Q1: the query of the campaign' AS q;
(SELECT t1a.c1 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1a.c4 IS NULL WHERE t1a.c4 <> 3) EXCEPT ((SELECT t3a.c3 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 < t3a.c6 INNER JOIN t3 AS t3c ON t3c.c2 > t1b.c4 WHERE (NOT (t3a.c6 <= 7) AND t3a.c7 <= t3a.c1)) INTERSECT (SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a WHERE (t1a.c1 IS NULL AND (t1a.c1 = 10 OR t1a.c4 <= 10))));
SELECT 'Q2: the INTERSECT alone' AS q;
(SELECT t3a.c3 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 < t3a.c6 INNER JOIN t3 AS t3c ON t3c.c2 > t1b.c4 WHERE (NOT (t3a.c6 <= 7)) AND (t3a.c7 <= t3a.c1)) INTERSECT (SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a WHERE (t1a.c1 = 10) OR (t1a.c4 <= 10));
SELECT 'Q3: Q1 without the DISTINCT' AS q;
(SELECT t1a.c1 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1a.c4 IS NULL WHERE t1a.c4 <> 3) EXCEPT ((SELECT t3a.c3 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 < t3a.c6 INNER JOIN t3 AS t3c ON t3c.c2 > t1b.c4 WHERE (NOT (t3a.c6 <= 7)) AND (t3a.c7 <= t3a.c1)) INTERSECT (SELECT t1a.c4 AS k0 FROM t1 AS t1a WHERE (t1a.c1 = 10) OR (t1a.c4 <= 10)));
SELECT 'Q4: Q1 with the left arm only on t1' AS q;
(SELECT t1a.c1 AS k0 FROM t1 AS t1a WHERE t1a.c4 IS NULL) EXCEPT ((SELECT t3a.c3 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 < t3a.c6) INTERSECT (SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a WHERE t1a.c4 <= 10));
SELECT 'Q5: t1 self-join, IS NULL in ON, then EXCEPT with a DISTINCT arm' AS q;
(SELECT t1a.c1 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1a.c4 IS NULL) EXCEPT (SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a);
SELECT 'end' AS q;
DROP DATABASE vs_rowid;
