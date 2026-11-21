-- pair 26, seed 292, rule cond->TRUE: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.31.1; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 INTEGER, c4 INTEGER, rid INTEGER PRIMARY KEY) WITHOUT ROWID;
INSERT INTO t1 VALUES (-3, 2, 8);
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 INTEGER, c14 REAL, c15 INTEGER);
INSERT INTO t2 VALUES (5, 4, -3, 1, -3);
CREATE TABLE t3 (c1 INTEGER, c2 INTEGER, c3 REAL, c6 INTEGER, c7 INTEGER, c8 INTEGER, c9 INTEGER, rid INTEGER PRIMARY KEY);
INSERT INTO t3 VALUES (1, -3, 7, -1, 1, 10, 7, 11);
-- original
SELECT t3b.c6 AS k1 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t1a.c4 = 1) AND (t1a.c4 = t1a.c4) LEFT JOIN t2 AS t2c ON NOT ((0)) WHERE t2c.c14 = t3b.c1;
-- mutant
SELECT t3b.c6 AS k1 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t1a.c4 = 1) AND (t1a.c4 = t1a.c4) LEFT JOIN t2 AS t2c ON NOT ((0)) WHERE 1 = 1;
