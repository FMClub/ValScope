-- pair 52, seed 7006, rule cond->TRUE: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.34.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 REAL, c4 INTEGER);
INSERT INTO t1 VALUES (3.25, 1);
INSERT INTO t1 VALUES (2, 5);
INSERT INTO t1 VALUES (1, 0);
INSERT INTO t1 VALUES (2, 2);
CREATE TABLE t2 (c1 TEXT COLLATE NOCASE, c2 TEXT COLLATE NOCASE, c3 REAL, c14 TEXT, c15 TEXT);
CREATE TABLE t3 (c1 , c2 REAL, c3 , c6 REAL, c7 REAL, c8 TEXT COLLATE NOCASE, c9 TEXT COLLATE NOCASE);
INSERT INTO t3 VALUES (5, 2.5, '1', -0.5, 1, ' 1', '01');
CREATE INDEX i7 ON t1 (c4);
ANALYZE;
-- original
SELECT t1a.c4 AS k1 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (1) INNER JOIN t1 AS t1c ON t1b.c4 IN (SELECT t3i93.c7 FROM t3 AS t3i93);
-- mutant
SELECT t1a.c4 AS k1 FROM t1 AS t1a CROSS JOIN t1 AS t1b INNER JOIN t1 AS t1c ON t1b.c4 IN (SELECT t3i93.c7 FROM t3 AS t3i93);
