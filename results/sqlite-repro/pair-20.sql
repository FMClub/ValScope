-- pair 20, seed 1167, rule UNION->UNION-ALL: the mutant must return a super-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 , c4 INTEGER);
CREATE TABLE t2 (c1 INTEGER, c2 , c3 TEXT COLLATE NOCASE, c14 , c15 TEXT COLLATE NOCASE);
CREATE TABLE t3 (c1 INTEGER, c2 TEXT, c3 , c6 INTEGER, c7 INTEGER, c8 TEXT COLLATE NOCASE, c9 TEXT COLLATE NOCASE);
INSERT INTO t3 VALUES (4, '2', '0', 4, 3, 'B', '01');
INSERT INTO t3 VALUES (2, '0', '5', 2, -1, 'b', '01');
-- original
SELECT t2a.c2 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a;
-- mutant
SELECT t2a.c2 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a;
