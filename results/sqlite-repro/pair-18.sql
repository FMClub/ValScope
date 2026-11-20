-- pair 18, seed 1166, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 , c4 INTEGER);
CREATE TABLE t2 (c1 REAL, c2 , c3 REAL, c14 REAL, c15 INTEGER);
CREATE TABLE t3 (c1 REAL, c2 TEXT COLLATE NOCASE, c3 REAL, c6 INTEGER, c7 REAL, c8 TEXT COLLATE NOCASE, c9 INTEGER);
INSERT INTO t3 VALUES (NULL, 'B', 0, 1, 1, 'B', 2);
INSERT INTO t3 VALUES (7, 'a', NULL, 4, 5.25, 'b', 1);
-- original
SELECT t2b.c2 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (0) UNION SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a;
-- mutant
SELECT t2b.c2 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (0) UNION ALL SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a;
