-- issues/010: a window function and SUM(DISTINCT ...) in a grouped join: HAVING is applied wrongly
-- every query must return the groups 1 and 2 (MAX(t.y) >= 10); MariaDB 10.11.14 returns no row
-- for the first one
DROP DATABASE IF EXISTS vs_wsd; CREATE DATABASE vs_wsd; USE vs_wsd;
CREATE TABLE t (id INT PRIMARY KEY, g INT, x INT, y INT);
CREATE TABLE u (id INT PRIMARY KEY, k INT);
INSERT INTO t VALUES (1, 1, 1, 5), (2, 1, 2, 20), (3, 2, 3, 30), (4, 3, 4, 1);
INSERT INTO u VALUES (1, 1), (2, 2), (3, 3), (4, 4);
SELECT 'window + SUM(DISTINCT)' AS q, COUNT(*) FROM (SELECT t.g, SUM(DISTINCT t.x) AS s, COUNT(*) OVER () AS r FROM t JOIN u ON u.k = t.id GROUP BY t.g HAVING MAX(t.y) >= 10) AS d;
SELECT 'the same, ORDER BY t.g' AS q, COUNT(*) FROM (SELECT t.g, SUM(DISTINCT t.x) AS s, COUNT(*) OVER () AS r FROM t JOIN u ON u.k = t.id GROUP BY t.g HAVING MAX(t.y) >= 10 ORDER BY t.g) AS d;
SELECT 'window + SUM' AS q, COUNT(*) FROM (SELECT t.g, SUM(t.x) AS s, COUNT(*) OVER () AS r FROM t JOIN u ON u.k = t.id GROUP BY t.g HAVING MAX(t.y) >= 10) AS d;
SELECT 'SUM(DISTINCT), no window' AS q, COUNT(*) FROM (SELECT t.g, SUM(DISTINCT t.x) AS s FROM t JOIN u ON u.k = t.id GROUP BY t.g HAVING MAX(t.y) >= 10) AS d;
SELECT 'no join' AS q, COUNT(*) FROM (SELECT t.g, SUM(DISTINCT t.x) AS s, COUNT(*) OVER () AS r FROM t GROUP BY t.g HAVING MAX(t.y) >= 10) AS d;
SELECT 'COUNT(DISTINCT)' AS q, COUNT(*) FROM (SELECT t.g, COUNT(DISTINCT t.x) AS s, COUNT(*) OVER () AS r FROM t JOIN u ON u.k = t.id GROUP BY t.g HAVING MAX(t.y) >= 10) AS d;
SELECT 'RANK' AS q, COUNT(*) FROM (SELECT t.g, SUM(DISTINCT t.x) AS s, RANK() OVER (ORDER BY t.g) AS r FROM t JOIN u ON u.k = t.id GROUP BY t.g HAVING MAX(t.y) >= 10) AS d;
SELECT 'rows, top level' AS q, t.g, SUM(DISTINCT t.x) AS s, COUNT(*) OVER () AS r FROM t JOIN u ON u.k = t.id GROUP BY t.g HAVING MAX(t.y) >= 10;
DROP DATABASE vs_wsd;
