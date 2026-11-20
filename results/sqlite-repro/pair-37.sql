-- pair 37, seed 515, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 INTEGER, c4 INTEGER);
CREATE TABLE t2 (c1 , c2 , c3 INTEGER, c14 INTEGER, c15 INTEGER);
INSERT INTO t2 VALUES (NULL, '0', 1, -1, NULL);
INSERT INTO t2 VALUES (3, '10', 2, 3, 1);
INSERT INTO t2 VALUES (-3, NULL, 0, 0, 3);
CREATE TABLE t3 (c1 , c2 INTEGER, c3 INTEGER, c6 INTEGER, c7 REAL, c8 INTEGER, c9 REAL);
INSERT INTO t3 VALUES (2, 10, 4, 10, 3.5, 10, 1);
INSERT INTO t3 VALUES (NULL, 5, 3, NULL, 3.5, 1, 3);
CREATE UNIQUE INDEX i4 ON t2 ((c1 + 1), c14, c2) WHERE c15 IS NOT NULL;
ANALYZE;
-- original
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t2b.c15 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c15 IS NOT t3a.c9);
-- mutant
SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t2b.c15 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c15 IS NOT t3a.c9);
