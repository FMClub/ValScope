-- pair 29, seed 11, rule LEFT->INNER-JOIN: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.31.1; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 REAL, c4 TEXT);
INSERT INTO t1 VALUES (NULL, 'x');
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 , c14 TEXT COLLATE NOCASE, c15 TEXT COLLATE NOCASE);
CREATE TABLE t3 (c1 INTEGER, c2 INTEGER, c3 INTEGER, c6 TEXT, c7 REAL, c8 INTEGER, c9 );
CREATE INDEX i3 ON t1 (c1);
-- original
SELECT ABS(t1a.c4) AS k1 FROM (SELECT x.c4 AS c4 FROM t1 AS x WHERE (x.c4 = 3) AND (x.c1 IS NULL)) AS t1a LEFT JOIN (SELECT x.c1 AS c1 FROM t1 AS x) AS t1b ON t1a.c4 = t1a.c4;
-- mutant
SELECT ABS(t1a.c4) AS k1 FROM (SELECT x.c4 AS c4 FROM t1 AS x WHERE (x.c4 = 3) AND (x.c1 IS NULL)) AS t1a INNER JOIN (SELECT x.c1 AS c1 FROM t1 AS x) AS t1b ON t1a.c4 = t1a.c4;
