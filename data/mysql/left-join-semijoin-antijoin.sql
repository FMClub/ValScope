-- issues/015 (MySQL): a LEFT JOIN whose inner side has an EXISTS, under a NOT EXISTS that
-- compares with the constant 1.  Both subqueries are materialized as "SELECT 1"; the lookup
-- of the EXISTS takes its key from the NOT EXISTS table (1 = <subquery4>.1 in EXPLAIN),
-- which has no row when NOT EXISTS is true, so the inner side of the LEFT JOIN is empty.
-- a has 5 rows, b has 11; a.x + 100 is never 1, so NOT EXISTS is true for every row of a and
-- the join gives 5 * 11 rows.
-- expected: 55 in every line, and 1 for 'small'
-- (MySQL 8.0.46, 8.4.13, 9.7.4: 5 for 'left' and 'left, EXISTS in ON'; the five rows have NULL
-- for the columns of the inner side)
DROP DATABASE IF EXISTS vs_aj; CREATE DATABASE vs_aj; USE vs_aj;
CREATE TABLE a (x INT);
CREATE TABLE b (y INT);
INSERT INTO a VALUES (1), (2), (3), (4), (5);
INSERT INTO b VALUES (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11);
SELECT 'left' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, the rows (expected 55, none with y NULL):' AS q, COUNT(*), SUM(d.y IS NULL) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, constant 2' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 2);
SELECT 'inner' AS q, COUNT(*) FROM a INNER JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, derived without EXISTS' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, no NOT EXISTS' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE a.x <> 100;
SELECT 'left, EXISTS in ON' AS q, COUNT(*) FROM a LEFT JOIN b ON EXISTS (SELECT 1 FROM b AS s) WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, NOT IN' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE a.x NOT IN (SELECT u.x + 100 FROM a AS u);
SET optimizer_switch = 'materialization=off';
SELECT 'left, materialization off' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SET optimizer_switch = 'default';
SET optimizer_switch = 'semijoin=off';
SELECT 'left, semijoin off' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SET optimizer_switch = 'default';
SET optimizer_switch = 'derived_merge=off';
SELECT 'left, derived_merge off' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SET optimizer_switch = 'default';
CREATE TABLE a1 (x INT);
CREATE TABLE b1 (y INT);
INSERT INTO a1 VALUES (1);
INSERT INTO b1 VALUES (7);
SELECT 'small' AS q, COUNT(*) FROM a1 LEFT JOIN (SELECT b1.y FROM b1 WHERE EXISTS (SELECT 1 FROM b1 AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a1 AS u WHERE a1.x + 100 = 1);
EXPLAIN FORMAT=TREE SELECT d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
EXPLAIN FORMAT=TREE SELECT d.y, a1.x FROM a1 LEFT JOIN (SELECT b1.y FROM b1 WHERE EXISTS (SELECT 1 FROM b1 AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a1 AS u WHERE a1.x + 100 = 1);
DROP DATABASE vs_aj;
