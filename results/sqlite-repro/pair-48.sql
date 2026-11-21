-- pair 48, seed 6004, rule EXCEPT->left: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT COLLATE NOCASE);
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 , c14 REAL, c15 INTEGER);
CREATE TABLE t3 (c1 TEXT COLLATE NOCASE, c2 INTEGER, c3 REAL, c6 TEXT COLLATE NOCASE, c7 TEXT COLLATE NOCASE, c8 INTEGER, c9 REAL);
INSERT INTO t3 VALUES ('A', 3, 2.25, 'A', 0, 3, NULL);
INSERT INTO t3 VALUES ('a', NULL, 7.5, 10, 1, 1, 4);
-- original
SELECT t3c.c3 AS k1 FROM t2 AS t2a INNER JOIN t3 AS t3c ON (0) UNION ALL SELECT DISTINCT t3a.c1 AS k1 FROM t3 AS t3a EXCEPT SELECT t3a.c8 AS k1 FROM t3 AS t3a;
-- mutant
SELECT t3c.c3 AS k1 FROM t2 AS t2a INNER JOIN t3 AS t3c ON (0) UNION ALL SELECT DISTINCT t3a.c1 AS k1 FROM t3 AS t3a;
