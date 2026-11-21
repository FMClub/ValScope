-- pair 53, seed 7012, rule HAVING cond->TRUE: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 TEXT);
INSERT INTO t1 VALUES (-3, 2);
CREATE TABLE t2 (c1 REAL, c2 , c3 TEXT, c14 , c15 TEXT, rid INTEGER PRIMARY KEY);
INSERT INTO t2 VALUES (2.0, 3, NULL, '1', 'a', 2);
INSERT INTO t2 VALUES (2, '2', 1, '1', NULL, 3);
CREATE TABLE t3 (c1 TEXT COLLATE NOCASE, c2 INTEGER, c3 TEXT, c6 TEXT COLLATE NOCASE, c7 TEXT COLLATE NOCASE, c8 TEXT, c9 );
-- original
SELECT COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40);
-- mutant
SELECT COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5);
