-- pair 60, seed 7025, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 INTEGER);
INSERT INTO t1 VALUES ('b', NULL);
INSERT INTO t1 VALUES ('B', 2);
CREATE TABLE t2 (c1 TEXT, c2 TEXT COLLATE NOCASE, c3 REAL, c14 INTEGER, c15 );
CREATE TABLE t3 (c1 REAL, c2 TEXT, c3 REAL, c6 REAL, c7 TEXT COLLATE NOCASE, c8 INTEGER, c9 REAL);
-- original
SELECT t3a.c2 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a;
-- mutant
SELECT t3a.c2 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a;
