-- pair 36, seed 352, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 INTEGER, c4 INTEGER);
CREATE TABLE t2 (c1 , c2 INTEGER, c3 INTEGER, c14 INTEGER, c15 INTEGER, rid INTEGER PRIMARY KEY);
CREATE TABLE t3 (c1 , c2 REAL, c3 REAL, c6 INTEGER, c7 TEXT, c8 , c9 TEXT COLLATE NOCASE);
INSERT INTO t3 VALUES (3, 3.25, 7.0, 2, 'a', 2, 'a');
INSERT INTO t3 VALUES ('7', 7, NULL, 2, NULL, NULL, 'A');
-- original
SELECT t2b.c2 AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0) UNION ALL SELECT DISTINCT t3a.c9 AS k0 FROM (SELECT x.c9 AS c9 FROM t3 AS x) AS t3a;
-- mutant
SELECT t2b.c2 AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0) UNION SELECT DISTINCT t3a.c9 AS k0 FROM (SELECT x.c9 AS c9 FROM t3 AS x) AS t3a;
