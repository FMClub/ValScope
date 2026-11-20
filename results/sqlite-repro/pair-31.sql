-- pair 31, seed 194, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 INTEGER);
INSERT INTO t1 VALUES ('A', 1);
INSERT INTO t1 VALUES ('a', 1);
CREATE TABLE t2 (c1 TEXT, c2 INTEGER, c3 INTEGER, c14 INTEGER, c15 REAL);
CREATE TABLE t3 (c1 TEXT COLLATE NOCASE, c2 TEXT, c3 INTEGER, c6 , c7 REAL, c8 INTEGER, c9 REAL);
-- original
SELECT t2a.c3 AS k1 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1b.c1 AS k1 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1 FROM t1 AS x) AS t1b ON (1);
-- mutant
SELECT t2a.c3 AS k1 FROM t2 AS t2a UNION SELECT DISTINCT t1b.c1 AS k1 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1 FROM t1 AS x) AS t1b ON (1);
