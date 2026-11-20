-- pair 10, seed 1021, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT COLLATE NOCASE);
INSERT INTO t1 VALUES (' 1', 'a');
INSERT INTO t1 VALUES ('2', 'A');
CREATE TABLE t2 (c1 INTEGER, c2 INTEGER, c3 TEXT, c14 INTEGER, c15 );
CREATE TABLE t3 (c1 , c2 REAL, c3 TEXT, c6 INTEGER, c7 INTEGER, c8 TEXT COLLATE NOCASE, c9 INTEGER);
-- original
SELECT t3c.c6 AS k0 FROM t3 AS t3a INNER JOIN t3 AS t3c ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
-- mutant
SELECT t3c.c6 AS k0 FROM t3 AS t3a INNER JOIN t3 AS t3c ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
