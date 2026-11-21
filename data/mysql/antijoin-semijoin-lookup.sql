-- Candidate MySQL bug (issues/015): a LEFT JOIN with a derived table that has an EXISTS,
-- under a NOT EXISTS of the outer query.  Every line is tagged; the number of rows per tag
-- is what matters.  a has 5 rows, b has 11; a.x + 100 is never 1, so NOT EXISTS is true for
-- every row of a, the derived table has the 11 rows of b, and the join condition is true.
-- expected: 55 rows for every tag but 'small' (1 row, y = 7)
DROP DATABASE IF EXISTS vs_aj; CREATE DATABASE vs_aj; USE vs_aj;
CREATE TABLE a (x INT);
CREATE TABLE b (y INT);
INSERT INTO a VALUES (1), (2), (3), (4), (5);
INSERT INTO b VALUES (1), (2), (3), (4), (5), (6), (7), (8), (9), (10), (11);
SELECT 'left' AS q, d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, constant 2' AS q, d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 2);
SELECT 'left, COUNT(*) = ' AS q, COUNT(*) FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'inner' AS q, d.y, a.x FROM a INNER JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, derived without EXISTS' AS q, d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, no NOT EXISTS' AS q, d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE a.x <> 100;
SELECT 'left, EXISTS in ON' AS q, b.y, a.x FROM a LEFT JOIN b ON EXISTS (SELECT 1 FROM b AS s) WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SELECT 'left, NOT IN' AS q, d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE a.x NOT IN (SELECT u.x + 100 FROM a AS u);
SET optimizer_switch = 'materialization=off';
SELECT 'left, materialization off' AS q, d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SET optimizer_switch = 'default';
SET optimizer_switch = 'semijoin=off';
SELECT 'left, semijoin off' AS q, d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SET optimizer_switch = 'default';
SET optimizer_switch = 'derived_merge=off';
SELECT 'left, derived_merge off' AS q, d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
SET optimizer_switch = 'default';
CREATE TABLE a1 (x INT);
CREATE TABLE b1 (y INT);
INSERT INTO a1 VALUES (1);
INSERT INTO b1 VALUES (7);
SELECT 'small' AS q, d.y, a1.x FROM a1 LEFT JOIN (SELECT b1.y FROM b1 WHERE EXISTS (SELECT 1 FROM b1 AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a1 AS u WHERE a1.x + 100 = 1);
EXPLAIN FORMAT=TREE SELECT d.y, a.x FROM a LEFT JOIN (SELECT b.y FROM b WHERE EXISTS (SELECT 1 FROM b AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a AS u WHERE a.x + 100 = 1);
EXPLAIN FORMAT=TREE SELECT d.y, a1.x FROM a1 LEFT JOIN (SELECT b1.y FROM b1 WHERE EXISTS (SELECT 1 FROM b1 AS s)) AS d ON 1 WHERE NOT EXISTS (SELECT 1 FROM a1 AS u WHERE a1.x + 100 = 1);
DROP DATABASE vs_aj;
