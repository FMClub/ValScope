-- pair 41, seed 3006, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 , c4 );
INSERT INTO t1 VALUES (4, 2);
CREATE TABLE t2 (c1 TEXT, c2 TEXT, c3 , c14 INTEGER, c15 INTEGER);
CREATE TABLE t3 (c1 TEXT COLLATE NOCASE, c2 , c3 INTEGER, c6 INTEGER, c7 INTEGER, c8 INTEGER, c9 TEXT COLLATE NOCASE, rid INTEGER PRIMARY KEY);
INSERT INTO t3 VALUES ('A', -3, NULL, 10, 3, 3, NULL, 3);
INSERT INTO t3 VALUES ('a', 1, 2, NULL, 2, 0, '2', 4);
-- original
SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION SELECT DISTINCT t3b.c1 AS k2 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (1);
-- mutant
SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3b.c1 AS k2 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (1);
