-- pair 43, seed 4004, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT);
CREATE TABLE t2 (c1 INTEGER, c2 TEXT COLLATE NOCASE, c3 INTEGER, c14 INTEGER, c15 INTEGER);
CREATE TABLE t3 (c1 TEXT, c2 TEXT COLLATE NOCASE, c3 REAL, c6 INTEGER, c7 REAL, c8 TEXT, c9 TEXT COLLATE NOCASE);
INSERT INTO t3 VALUES ('01', 'b', 2.5, NULL, 0, -1, '01');
INSERT INTO t3 VALUES ('A', 'B', -1, 1, -1, NULL, '-3');
-- original
SELECT t2a.c15 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a;
-- mutant
SELECT t2a.c15 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a;
