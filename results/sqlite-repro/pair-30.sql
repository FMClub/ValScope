-- pair 30, seed 22, rule EXCEPT->left: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 INTEGER, c4 INTEGER, rid INTEGER PRIMARY KEY);
CREATE TABLE t2 (c1 TEXT, c2 REAL, c3 INTEGER, c14 TEXT COLLATE NOCASE, c15 REAL);
INSERT INTO t2 VALUES (' 1', NULL, -3, 'A', 1);
INSERT INTO t2 VALUES (' 1', 1.5, 10, 'a', 3);
CREATE TABLE t3 (c1 TEXT, c2 INTEGER, c3 INTEGER, c6 REAL, c7 TEXT COLLATE NOCASE, c8 INTEGER, c9 REAL);
-- original
SELECT t2a.c1 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2a.c14 AS k0 FROM t2 AS t2a EXCEPT SELECT t2a.c3 AS k0 FROM t2 AS t2a;
-- mutant
SELECT t2a.c1 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2a.c14 AS k0 FROM t2 AS t2a;
