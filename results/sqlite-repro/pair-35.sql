-- pair 35, seed 340, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 REAL, c4 TEXT COLLATE NOCASE);
INSERT INTO t1 VALUES (-1, 'a');
INSERT INTO t1 VALUES (5.25, 'A');
CREATE TABLE t2 (c1 INTEGER, c2 REAL, c3 INTEGER, c14 INTEGER, c15 REAL, rid INTEGER PRIMARY KEY);
CREATE TABLE t3 (c1 INTEGER, c2 , c3 TEXT COLLATE NOCASE, c6 , c7 TEXT, c8 , c9 INTEGER);
-- original
SELECT t2c.c2 AS k0 FROM t1 AS t1a LEFT JOIN t2 AS t2c ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
-- mutant
SELECT t2c.c2 AS k0 FROM t1 AS t1a LEFT JOIN t2 AS t2c ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
