-- pair 13, seed 1156, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 REAL);
CREATE TABLE t2 (c1 REAL, c2 , c3 , c14 TEXT COLLATE NOCASE, c15 TEXT COLLATE NOCASE);
INSERT INTO t2 VALUES (1.25, 5, NULL, 'B', 1);
INSERT INTO t2 VALUES (2.0, 2, -1, 'b', 10);
CREATE TABLE t3 (c1 TEXT, c2 , c3 , c6 REAL, c7 INTEGER, c8 TEXT, c9 TEXT, rid INTEGER PRIMARY KEY) WITHOUT ROWID;
-- original
SELECT t3a.c3 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t2a.c14 AS k0 FROM t2 AS t2a;
-- mutant
SELECT t3a.c3 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t2a.c14 AS k0 FROM t2 AS t2a;
