-- issues/009: AVG under SELECT DISTINCT with an expression over the grouping key and over another aggregate
DROP DATABASE IF EXISTS vs_avg; CREATE DATABASE vs_avg; USE vs_avg;
CREATE TABLE t (g INT, x INT);
INSERT INTO t VALUES (1, 10), (2, 20), (3, 30);
-- reference, without DISTINCT: a = 1, 2, 3
SELECT 'no DISTINCT' AS q, g + 0 AS k, MAX(x) * 2 AS m, AVG(g) AS a FROM t GROUP BY g;
-- the same with DISTINCT (the groups are distinct anyway): a must still be 1, 2, 3
SELECT DISTINCT g + 0 AS k, MAX(x) * 2 AS m, AVG(g) AS a FROM t GROUP BY g;
-- variants
SELECT DISTINCT g AS k, MAX(x) * 2 AS m, AVG(g) AS a FROM t GROUP BY g;
SELECT DISTINCT g + 0 AS k, MAX(x) AS m, AVG(g) AS a FROM t GROUP BY g;
SELECT DISTINCT g + 0 AS k, MAX(x) * 2 AS m, SUM(g) AS a FROM t GROUP BY g;
SELECT DISTINCT g + 0 AS k, MIN(x) + 1 AS m, AVG(x) AS a FROM t GROUP BY g;
DROP DATABASE vs_avg;
