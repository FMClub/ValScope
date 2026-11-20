-- pair 14, seed 1157, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 );
INSERT INTO t1 VALUES (7, '-1');
CREATE TABLE t2 (c1 TEXT COLLATE NOCASE, c2 INTEGER, c3 TEXT COLLATE NOCASE, c14 INTEGER, c15 INTEGER);
INSERT INTO t2 VALUES ('a', 7, 'x', 7, 7);
INSERT INTO t2 VALUES ('A', 10, '-3', 1, NULL);
CREATE TABLE t3 (c1 INTEGER, c2 TEXT, c3 INTEGER, c6 , c7 INTEGER, c8 , c9 TEXT COLLATE NOCASE);
-- original
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t2c.c1 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2c ON (1);
-- mutant
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t2c.c1 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2c ON (1);
