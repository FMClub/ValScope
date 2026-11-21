-- issues/013: -3.00 % 3 is the DECIMAL -0.00.  A plain GROUP BY puts it in the group of 0.00;
-- the same GROUP BY with COUNT(DISTINCT ...) or GROUP_CONCAT(...) makes it a group of its own,
-- and -0.00 = 0.00 is false.
-- expected: 1 group in every line; "equal" 1
DROP DATABASE IF EXISTS vs_nz; CREATE DATABASE vs_nz; USE vs_nz;
CREATE TABLE d (x DECIMAL(10,2));
INSERT INTO d VALUES (-3), (0), (3);
SELECT 'COUNT(x)' AS q, COUNT(*) FROM (SELECT x % 3 AS k, COUNT(x) AS c FROM d GROUP BY x % 3) AS g;
SELECT 'MAX(x)' AS q, COUNT(*) FROM (SELECT x % 3 AS k, MAX(x) AS c FROM d GROUP BY x % 3) AS g;
SELECT 'COUNT(DISTINCT x)' AS q, COUNT(*) FROM (SELECT x % 3 AS k, COUNT(DISTINCT x) AS c FROM d GROUP BY x % 3) AS g;
SELECT 'GROUP_CONCAT(x)' AS q, COUNT(*) FROM (SELECT x % 3 AS k, GROUP_CONCAT(x) AS c FROM d GROUP BY x % 3) AS g;
SELECT 'DISTINCT' AS q, COUNT(*) FROM (SELECT DISTINCT x % 3 AS k FROM d) AS g;
SELECT 'equal' AS q, (-3.00 % 3) = (0.00 % 3), CAST(-3.00 % 3 AS CHAR);
DROP DATABASE vs_nz;
