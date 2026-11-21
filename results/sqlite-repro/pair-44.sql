-- pair 44, seed 4028, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 , c4 REAL);
CREATE TABLE t2 (c1 INTEGER, c2 REAL, c3 , c14 , c15 TEXT COLLATE NOCASE);
INSERT INTO t2 VALUES (2, 1.5, '4', 10, 'a');
INSERT INTO t2 VALUES (7, 10.5, 0, '0', 'A');
CREATE TABLE t3 (c1 INTEGER, c2 TEXT COLLATE NOCASE, c3 INTEGER, c6 REAL, c7 INTEGER, c8 INTEGER, c9 INTEGER);
-- original
SELECT t1c.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1c ON (0) UNION ALL SELECT DISTINCT t2b.c15 AS k2 FROM t2 AS t2a INNER JOIN t2 AS t2b ON (1);
-- mutant
SELECT t1c.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1c ON (0) UNION SELECT DISTINCT t2b.c15 AS k2 FROM t2 AS t2a INNER JOIN t2 AS t2b ON (1);
