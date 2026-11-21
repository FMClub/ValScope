-- pair 21, seed 1173, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 );
CREATE TABLE t2 (c1 TEXT, c2 , c3 , c14 INTEGER, c15 INTEGER, rid INTEGER PRIMARY KEY);
CREATE TABLE t3 (c1 INTEGER, c2 TEXT COLLATE NOCASE, c3 , c6 INTEGER, c7 INTEGER, c8 INTEGER, c9 REAL);
INSERT INTO t3 VALUES (NULL, 'A', -3, 10, 2, -1, -0.5);
INSERT INTO t3 VALUES (1, 'a', 2, 4, -1, 2, 2);
-- original
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a UNION SELECT t1a.c1 AS k0 FROM t1 AS t1a WHERE (0);
-- mutant
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a UNION ALL SELECT t1a.c1 AS k0 FROM t1 AS t1a WHERE (0);
