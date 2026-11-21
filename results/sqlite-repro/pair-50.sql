-- pair 50, seed 6026, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 REAL, c4 INTEGER);
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 INTEGER, c14 REAL, c15 REAL);
CREATE TABLE t3 (c1 REAL, c2 INTEGER, c3 REAL, c6 REAL, c7 REAL, c8 TEXT COLLATE NOCASE, c9 );
INSERT INTO t3 VALUES (0, 3, 7.0, -1, 7, 'A', NULL);
INSERT INTO t3 VALUES (2.0, NULL, 7, 4.25, -1, 'a', '10');
-- original
SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a;
-- mutant
SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a;
