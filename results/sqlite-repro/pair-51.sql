-- pair 51, seed 6027, rule UNION-ALL->UNION: the mutant must return a sub-bag of the rows of the original
-- (SQLite 3.26.0; checked modulo the collations of the columns)
CREATE TABLE t1 (c1 TEXT, c4 TEXT COLLATE NOCASE);
INSERT INTO t1 VALUES ('a', 'B');
INSERT INTO t1 VALUES (0, 'b');
CREATE TABLE t2 (c1 , c2 TEXT, c3 INTEGER, c14 , c15 );
CREATE TABLE t3 (c1 INTEGER, c2 , c3 INTEGER, c6 TEXT, c7 INTEGER, c8 TEXT COLLATE NOCASE, c9 INTEGER);
-- original
SELECT t2a.c14 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
-- mutant
SELECT t2a.c14 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a;
