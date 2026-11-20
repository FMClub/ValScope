-- pair 41, seed 2022, rule EXCEPT->left: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT COLLATE NOCASE, c4 TEXT COLLATE NOCASE, rid INTEGER PRIMARY KEY) WITHOUT ROWID;
INSERT INTO t1 VALUES ('A', 'a', 2);
INSERT INTO t1 VALUES (' 1', 'A', 6);
CREATE TABLE t2 (c1 REAL, c2 INTEGER, c3 REAL, c14 TEXT, c15 REAL);
CREATE TABLE t3 (c1 TEXT, c2 TEXT COLLATE NOCASE, c3 INTEGER, c6 INTEGER, c7 TEXT, c8 TEXT, c9 TEXT);
-- original
SELECT t2a.c3 AS k1, t2a.c3 AS k2 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k1, t1a.c4 AS k2 FROM (SELECT x.c4 AS c4 FROM t1 AS x) AS t1a EXCEPT SELECT t1a.c1 AS k1, t1a.c4 AS k2 FROM t1 AS t1a;
-- mutant
SELECT t2a.c3 AS k1, t2a.c3 AS k2 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k1, t1a.c4 AS k2 FROM (SELECT x.c4 AS c4 FROM t1 AS x) AS t1a;
