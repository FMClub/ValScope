-- issues/003: HAVING COUNT(x) IN (subquery) in a grouped query
-- expected: IN -> 1, NOT IN -> 2, literal list -> 1 (MariaDB 10.11.14: NULL, "1,2", 1)
DROP DATABASE IF EXISTS vs_hin; CREATE DATABASE vs_hin; USE vs_hin;
CREATE TABLE t (id INT PRIMARY KEY, g INT, x INT);
INSERT INTO t VALUES (1, 1, 10), (2, 1, 20), (3, 2, 30);
CREATE TABLE s (id INT PRIMARY KEY, v INT);
INSERT INTO s VALUES (1, 2), (2, 7);
SELECT 'IN (subquery)' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g FROM t GROUP BY g HAVING COUNT(x) IN (SELECT v FROM s)) AS r;
SELECT 'NOT IN (subquery)' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g FROM t GROUP BY g HAVING COUNT(x) NOT IN (SELECT v FROM s)) AS r;
SELECT 'IN (2, 7)' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g FROM t GROUP BY g HAVING COUNT(x) IN (2, 7)) AS r;
-- a variant of the second campaign: whether the match is found depends on an aggregate of
-- the select list.  Expected 1 in both lines (MariaDB 10.11.14: NULL with COUNT(x), 1 with
-- COUNT(DISTINCT x); on other data it is the other way round)
CREATE TABLE s2 (v INT);
INSERT INTO s2 VALUES (10);
SELECT 'MIN IN (subquery), COUNT' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g, COUNT(x) AS c FROM t GROUP BY g HAVING MIN(x) IN (SELECT v FROM s2)) AS r;
SELECT 'MIN IN (subquery), COUNT DISTINCT' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g, COUNT(DISTINCT x) AS c FROM t GROUP BY g HAVING MIN(x) IN (SELECT v FROM s2)) AS r;
DROP DATABASE vs_hin;
