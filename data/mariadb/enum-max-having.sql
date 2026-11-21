-- issues/002: HAVING MAX(enum_col) <> 3 depends on an unrelated aggregate in the select list
-- (the groups must be the same in every query; MariaDB 10.11.14 returns 1,2,3 for the first)
DROP DATABASE IF EXISTS vs_enum; CREATE DATABASE vs_enum; USE vs_enum;
CREATE TABLE t (id INT PRIMARY KEY, g INT, d DATE, e ENUM('value1','value2','value3') NULL);
INSERT INTO t VALUES (1, 1, '2024-01-01', 'value1'), (2, 2, '2024-01-02', 'value2'), (3, 3, '2024-01-03', 'value3');
SELECT 'COUNT(DISTINCT d)' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g, COUNT(DISTINCT d) FROM t GROUP BY g HAVING MAX(e) <> 3) AS r;
SELECT 'COUNT(d)' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g, COUNT(d) FROM t GROUP BY g HAVING MAX(e) <> 3) AS r;
SELECT 'SUM(id)' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g, SUM(id) FROM t GROUP BY g HAVING MAX(e) <> 3) AS r;
SELECT 'g only' AS q, GROUP_CONCAT(g ORDER BY g) FROM (SELECT g FROM t GROUP BY g HAVING MAX(e) <> 3) AS r;
DROP DATABASE vs_enum;
