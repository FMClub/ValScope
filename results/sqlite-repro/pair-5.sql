-- pair 5, seed 1005, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT);
INSERT INTO t1 VALUES (0, NULL);
CREATE TABLE t2 (c1 INTEGER, c2 TEXT COLLATE NOCASE, c3 TEXT COLLATE NOCASE, c14 INTEGER, c15 REAL, rid INTEGER PRIMARY KEY) WITHOUT ROWID;
INSERT INTO t2 VALUES (-3, 2, 'b', 1, 1.25, 3);
INSERT INTO t2 VALUES (-3, '', 'B', 7, 3.0, 4);
CREATE TABLE t3 (c1 , c2 REAL, c3 INTEGER, c6 REAL, c7 , c8 , c9 INTEGER, rid INTEGER PRIMARY KEY) WITHOUT ROWID;
-- original
SELECT t1a.c1 AS k0, t1a.c4 AS k1 FROM t1 AS t1a UNION SELECT DISTINCT t1c.c1 AS k0, t2a.c3 AS k1 FROM t2 AS t2a INNER JOIN t1 AS t1c ON NOT ((0));
-- mutant
SELECT t1a.c1 AS k0, t1a.c4 AS k1 FROM t1 AS t1a UNION ALL SELECT DISTINCT t1c.c1 AS k0, t2a.c3 AS k1 FROM t2 AS t2a INNER JOIN t1 AS t1c ON NOT ((0));
