-- issues/008, reduced by bridge/reduce_mysql.py on MySQL 8.4 (1 row per table), with plain tables
DROP DATABASE IF EXISTS vs_i8; CREATE DATABASE vs_i8; USE vs_i8;
CREATE TABLE t1 (c1 INT PRIMARY KEY, c4 INT);
CREATE TABLE t2 (c1 INT PRIMARY KEY, c2 INT);
INSERT INTO t1 VALUES (8811, 13);
INSERT INTO t2 VALUES (9623, 3704);
-- left arm: (3704, 13, 9623); right arm: (NULL, 13, NULL); the intersection is empty
SELECT 'left' AS q, t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1);
SELECT 'right' AS q, t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (0);
SELECT 'top-level INTERSECT ALL', COUNT(*) FROM ((SELECT t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1)) INTERSECT ALL (SELECT t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (0))) AS x;
(SELECT t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1)) INTERSECT ALL (SELECT t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (0));
SELECT 'DISTINCT over it' AS q;
SELECT DISTINCT * FROM ((SELECT t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1)) INTERSECT ALL (SELECT t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (0))) AS vs_d1;
SELECT 'INTERSECT (no ALL) in a derived table', COUNT(*) FROM ((SELECT t2a.c2 AS k0, t1b.c4 AS k1, t2a.c1 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1)) INTERSECT (SELECT t1b.c1 AS k0, t1a.c4 AS k1, t1b.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (0))) AS x;
SELECT 'only k1 (the column the arms share)', COUNT(*) FROM ((SELECT t1b.c4 AS k1 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1)) INTERSECT ALL (SELECT t1a.c4 AS k1 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON (0))) AS x;
DROP DATABASE vs_i8;
