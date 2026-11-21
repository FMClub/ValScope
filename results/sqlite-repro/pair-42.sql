-- pair 42, seed 3009, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 );
CREATE TABLE t2 (c1 REAL, c2 , c3 INTEGER, c14 TEXT COLLATE NOCASE, c15 TEXT, rid INTEGER PRIMARY KEY);
INSERT INTO t2 VALUES (5.5, '10', 1, 'A', NULL, 1);
INSERT INTO t2 VALUES (4.25, 2, 1, 'a', 'x', 3);
CREATE TABLE t3 (c1 INTEGER, c2 TEXT COLLATE NOCASE, c3 , c6 TEXT, c7 INTEGER, c8 , c9 TEXT COLLATE NOCASE);
-- original
SELECT t2a.c2 AS k1 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2a.c14 AS k1 FROM t2 AS t2a;
-- mutant
SELECT t2a.c2 AS k1 FROM t2 AS t2a UNION SELECT DISTINCT t2a.c14 AS k1 FROM t2 AS t2a;
