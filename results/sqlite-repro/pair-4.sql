-- pair 4, seed 1005, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT);
CREATE TABLE t2 (c1 INTEGER, c2 TEXT COLLATE NOCASE, c3 TEXT COLLATE NOCASE, c14 INTEGER, c15 REAL, rid INTEGER PRIMARY KEY);
INSERT INTO t2 VALUES (4, 'a', '', 2, 7.0, 0);
INSERT INTO t2 VALUES (-1, 'A', 3, -1, -1, 5);
CREATE TABLE t3 (c1 , c2 REAL, c3 INTEGER, c6 REAL, c7 , c8 , c9 INTEGER, rid INTEGER PRIMARY KEY);
-- original
SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t2a.c2 AS k0 FROM t2 AS t2a;
-- mutant
SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t2a.c2 AS k0 FROM t2 AS t2a;
