-- pair 39, seed 2022, rule DISTINCT-add: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 TEXT COLLATE NOCASE, rid INTEGER PRIMARY KEY);
INSERT INTO t1 VALUES (-3, 1, 9);
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 REAL, c14 TEXT, c15 REAL);
CREATE TABLE t3 (c1 TEXT, c2 TEXT COLLATE NOCASE, c3 INTEGER, c6 INTEGER, c7 TEXT, c8 TEXT, c9 TEXT);
INSERT INTO t3 VALUES ('x', 1, 2, 5, NULL, '-1', '');
CREATE INDEX i0 ON t3 (c7, c9) WHERE c7 IS NOT NULL;
CREATE INDEX i1 ON t3 (c9, c1);
-- original
SELECT t3b.c3 || '' AS k1 FROM t1 AS t1a INNER JOIN (SELECT x.c3 AS c3, x.c7 AS c7 FROM t3 AS x) AS t3b ON (1) WHERE (t3b.c7 IS NOT 5);
-- mutant
SELECT t3b.c3 || '' AS k1 FROM t1 AS t1a INNER JOIN (SELECT x.c3 AS c3, x.c7 AS c7 FROM (SELECT DISTINCT * FROM t3 AS x) AS x) AS t3b ON (1) WHERE (t3b.c7 IS NOT 5);
