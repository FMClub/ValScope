-- pair 23, seed 1178, rule EXCEPT->left: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 REAL);
INSERT INTO t1 VALUES ('b', 1.25);
INSERT INTO t1 VALUES ('B', 1);
CREATE TABLE t2 (c1 INTEGER, c2 REAL, c3 TEXT COLLATE NOCASE, c14 INTEGER, c15 REAL);
CREATE TABLE t3 (c1 REAL, c2 REAL, c3 TEXT COLLATE NOCASE, c6 TEXT, c7 TEXT COLLATE NOCASE, c8 INTEGER, c9 REAL);
-- original
SELECT t3a.c8 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a EXCEPT SELECT t2a.c2 AS k0 FROM t2 AS t2a;
-- mutant
SELECT t3a.c8 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a;
