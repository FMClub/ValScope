-- pair 7, seed 1008, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT COLLATE NOCASE);
INSERT INTO t1 VALUES ('a', 'B');
INSERT INTO t1 VALUES (NULL, 'b');
CREATE TABLE t2 (c1 TEXT COLLATE NOCASE, c2 TEXT COLLATE NOCASE, c3 TEXT, c14 REAL, c15 TEXT COLLATE NOCASE);
CREATE TABLE t3 (c1 REAL, c2 INTEGER, c3 , c6 , c7 REAL, c8 TEXT, c9 INTEGER, rid INTEGER PRIMARY KEY);
-- original
SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
-- mutant
SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
