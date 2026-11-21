-- pair 47, seed 6004, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT COLLATE NOCASE);
INSERT INTO t1 VALUES (7, 'a');
INSERT INTO t1 VALUES ('10', 'A');
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 , c14 REAL, c15 INTEGER);
CREATE TABLE t3 (c1 TEXT COLLATE NOCASE, c2 INTEGER, c3 REAL, c6 TEXT COLLATE NOCASE, c7 TEXT COLLATE NOCASE, c8 INTEGER, c9 REAL);
-- original
SELECT t2a.c3 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
-- mutant
SELECT t2a.c3 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
