-- pair 25, seed 240, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 INTEGER, rid INTEGER PRIMARY KEY);
INSERT INTO t1 VALUES ('a', 3, 0);
INSERT INTO t1 VALUES ('A', 3, 8);
CREATE TABLE t2 (c1 INTEGER, c2 INTEGER, c3 TEXT, c14 REAL, c15 INTEGER);
CREATE TABLE t3 (c1 INTEGER, c2 , c3 INTEGER, c6 INTEGER, c7 REAL, c8 INTEGER, c9 REAL);
-- original
SELECT t3a.c3 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a;
-- mutant
SELECT t3a.c3 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a;
