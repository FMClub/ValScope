-- pair 11, seed 1023, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT);
CREATE TABLE t2 (c1 INTEGER, c2 REAL, c3 , c14 , c15 INTEGER);
CREATE TABLE t3 (c1 REAL, c2 TEXT COLLATE NOCASE, c3 INTEGER, c6 TEXT COLLATE NOCASE, c7 TEXT COLLATE NOCASE, c8 INTEGER, c9 TEXT);
INSERT INTO t3 VALUES (10.5, 'b', 2, '01', '0', -1, NULL);
INSERT INTO t3 VALUES (1, 'B', 5, -3, 'a', 1, 2);
-- original
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a;
-- mutant
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a;
