-- pair 28, seed 1, rule DISTINCT-add: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.34.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 INTEGER, c4 TEXT);
INSERT INTO t1 VALUES (0, 4);
INSERT INTO t1 VALUES (7, 5);
CREATE TABLE t2 (c1 INTEGER, c2 INTEGER, c3 , c14 INTEGER, c15 );
INSERT INTO t2 VALUES (4, 2, -1, 2, 0);
CREATE TABLE t3 (c1 TEXT, c2 , c3 , c6 REAL, c7 INTEGER, c8 , c9 INTEGER, rid INTEGER PRIMARY KEY);
INSERT INTO t3 VALUES ('a', 2, '2', 0, 10, -3, NULL, 0);
INSERT INTO t3 VALUES ('01', '10', NULL, 2, NULL, 4, NULL, 1);
INSERT INTO t3 VALUES (3, NULL, 2, 7.0, 7, '-3', NULL, 2);
INSERT INTO t3 VALUES ('', 7, '3', 10, 5, NULL, 1, 3);
CREATE INDEX i1 ON t3 (c6, c8, c3);
ANALYZE;
-- original
SELECT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 IN (SELECT t2i75.c14 FROM t2 AS t2i75);
-- mutant
SELECT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 IN (SELECT t2i75.c14 FROM t2 AS t2i75) GROUP BY t3a.c1, t3a.c2, t3a.c3, t3a.c6, t3a.c7, t3a.c8, t3a.c9, t3a.rid, t1b.c1, t1b.c4;
