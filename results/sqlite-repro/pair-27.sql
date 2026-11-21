-- pair 27, seed 663, rule cond->TRUE: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.34.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 , c4 TEXT COLLATE NOCASE, rid INTEGER PRIMARY KEY);
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 INTEGER, c14 , c15 );
INSERT INTO t2 VALUES (7.5, 5, 4, 4, NULL);
INSERT INTO t2 VALUES (NULL, 7, 5, '2', NULL);
INSERT INTO t2 VALUES (5.25, 7, -3, 7, 3);
INSERT INTO t2 VALUES (0.5, NULL, 3, 3, 4);
CREATE TABLE t3 (c1 REAL, c2 , c3 INTEGER, c6 INTEGER, c7 INTEGER, c8 TEXT COLLATE NOCASE, c9 INTEGER);
INSERT INTO t3 VALUES (2, '4', 10, 4, -1, 'a', NULL);
INSERT INTO t3 VALUES (NULL, 2, 10, 4, 0, '2', 7);
INSERT INTO t3 VALUES (5, 0, 5, 7, 4, NULL, 5);
CREATE INDEX i2 ON t2 (c3, c14, c1);
CREATE INDEX i3 ON t3 (c3, c1);
CREATE INDEX i4 ON t2 ((c2 + 1), c3);
ANALYZE;
-- original
SELECT t3a.c1 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (1) WHERE t2b.c3 IN (SELECT t3i27.c2 FROM t3 AS t3i27 WHERE t3i27.c9 IS NULL);
-- mutant
SELECT t3a.c1 AS k0 FROM t3 AS t3a CROSS JOIN t2 AS t2b WHERE t2b.c3 IN (SELECT t3i27.c2 FROM t3 AS t3i27 WHERE t3i27.c9 IS NULL);
