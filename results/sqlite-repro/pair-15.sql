-- pair 15, seed 1162, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 INTEGER);
CREATE TABLE t2 (c1 TEXT COLLATE NOCASE, c2 INTEGER, c3 TEXT COLLATE NOCASE, c14 TEXT COLLATE NOCASE, c15 TEXT COLLATE NOCASE, rid INTEGER PRIMARY KEY);
INSERT INTO t2 VALUES ('a', 2, NULL, 'B', NULL, 2);
INSERT INTO t2 VALUES ('A', 5, ' 1', 2, 2, 4);
CREATE TABLE t3 (c1 INTEGER, c2 TEXT, c3 INTEGER, c6 INTEGER, c7 , c8 , c9 TEXT);
-- original
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t2c.c1 AS k0 FROM t2 AS t2a INNER JOIN t2 AS t2c ON (1);
-- mutant
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t2c.c1 AS k0 FROM t2 AS t2a INNER JOIN t2 AS t2c ON (1);
