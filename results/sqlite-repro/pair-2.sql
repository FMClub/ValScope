-- pair 2, seed 1004, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 );
INSERT INTO t1 VALUES ('a', -3);
INSERT INTO t1 VALUES ('A', 5);
CREATE TABLE t2 (c1 INTEGER, c2 REAL, c3 INTEGER, c14 INTEGER, c15 , rid INTEGER PRIMARY KEY) WITHOUT ROWID;
CREATE TABLE t3 (c1 TEXT, c2 INTEGER, c3 TEXT COLLATE NOCASE, c6 TEXT, c7 INTEGER, c8 TEXT, c9 INTEGER);
-- original
SELECT t3b.c1 AS k2 FROM t2 AS t2a LEFT JOIN t3 AS t3b ON (0) UNION ALL SELECT DISTINCT t1a.c1 AS k2 FROM t1 AS t1a;
-- mutant
SELECT t3b.c1 AS k2 FROM t2 AS t2a LEFT JOIN t3 AS t3b ON (0) UNION SELECT DISTINCT t1a.c1 AS k2 FROM t1 AS t1a;
