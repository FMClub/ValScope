-- pair 33, seed 336, rule DISTINCT-add: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 INTEGER, c4 );
INSERT INTO t1 VALUES (-3, NULL);
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 REAL, c14 REAL, c15 REAL);
CREATE TABLE t3 (c1 , c2 INTEGER, c3 INTEGER, c6 INTEGER, c7 INTEGER, c8 INTEGER, c9 INTEGER);
CREATE INDEX i3 ON t1 (c1, c4) WHERE c4 IS NOT NULL;
CREATE INDEX i4 ON t1 (c4, c1);
-- original
SELECT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT ((0)) WHERE (t1b.c4 IS NOT t1a.c1);
-- mutant
SELECT DISTINCT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT ((0)) WHERE (t1b.c4 IS NOT t1a.c1);
