-- pair 8, seed 1008, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT COLLATE NOCASE);
INSERT INTO t1 VALUES ('a', 'B');
INSERT INTO t1 VALUES (NULL, 'b');
CREATE TABLE t2 (c1 TEXT COLLATE NOCASE, c2 TEXT COLLATE NOCASE, c3 TEXT, c14 REAL, c15 TEXT COLLATE NOCASE);
CREATE TABLE t3 (c1 REAL, c2 INTEGER, c3 , c6 , c7 REAL, c8 TEXT, c9 INTEGER, rid INTEGER PRIMARY KEY);
INSERT INTO t3 VALUES (2.0, 0, '7', 0, NULL, '01', 1, 3);
-- original
SELECT t2a.c3 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t1c.c4 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1c ON NOT ((0));
-- mutant
SELECT t2a.c3 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1c.c4 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1c ON NOT ((0));
