-- pair 39, seed 2011, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 , rid INTEGER PRIMARY KEY) WITHOUT ROWID;
CREATE TABLE t2 (c1 TEXT COLLATE NOCASE, c2 TEXT, c3 INTEGER, c14 REAL, c15 INTEGER);
CREATE TABLE t3 (c1 TEXT, c2 INTEGER, c3 REAL, c6 , c7 TEXT COLLATE NOCASE, c8 REAL, c9 INTEGER);
INSERT INTO t3 VALUES (5, 7, NULL, 5, 'a', 2, -3);
INSERT INTO t3 VALUES ('', 2, 4, 1, 'A', -1, 2);
-- original
SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION SELECT DISTINCT t3a.c7 AS k2 FROM t3 AS t3a;
-- mutant
SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c7 AS k2 FROM t3 AS t3a;
