-- pair 49, seed 6009, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT COLLATE NOCASE);
INSERT INTO t1 VALUES ('x', '01');
CREATE TABLE t2 (c1 TEXT COLLATE NOCASE, c2 , c3 REAL, c14 INTEGER, c15 TEXT);
INSERT INTO t2 VALUES ('B', NULL, -3, 0, NULL);
INSERT INTO t2 VALUES ('b', NULL, 1.5, 5, -1);
CREATE TABLE t3 (c1 , c2 TEXT, c3 TEXT, c6 TEXT, c7 INTEGER, c8 TEXT COLLATE NOCASE, c9 TEXT COLLATE NOCASE);
-- original
SELECT t2a.c15 AS k1 FROM t2 AS t2a UNION SELECT DISTINCT t2b.c1 AS k1 FROM t1 AS t1a INNER JOIN t2 AS t2b ON NOT ((0));
-- mutant
SELECT t2a.c15 AS k1 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2b.c1 AS k1 FROM t1 AS t1a INNER JOIN t2 AS t2b ON NOT ((0));
