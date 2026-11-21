-- issues/011: GROUP BY on an expression over a DOUBLE(M,D) / FLOAT(M,D) column: the number of
-- groups depends on an unrelated aggregate.  3.87 % 2, 5.87 % 2, 91.87 % 2 and 1.87 % 2 all
-- print as 1.8700 but differ in their last bits as doubles.
-- expected: the same number of groups in every line of a block
-- (MariaDB 10.11.14, DOUBLE(12,4): 2, 1, 1, 2 groups; plain DOUBLE: 2 everywhere)
DROP DATABASE IF EXISTS vs_dbl; CREATE DATABASE vs_dbl; USE vs_dbl;
CREATE TABLE t (id INT PRIMARY KEY AUTO_INCREMENT, x DOUBLE(12,4));
INSERT INTO t (x) VALUES (3.87), (5.87), (91.87), (1.87);
SELECT 'DOUBLE(12,4): COUNT(DISTINCT x - 5)' AS q, COUNT(*) FROM (SELECT x % 2 AS k, COUNT(DISTINCT x - 5) AS c FROM t GROUP BY x % 2) AS d;
SELECT 'DOUBLE(12,4): COUNT(x - 5)' AS q, COUNT(*) FROM (SELECT x % 2 AS k, COUNT(x - 5) AS c FROM t GROUP BY x % 2) AS d;
SELECT 'DOUBLE(12,4): MAX(id)' AS q, COUNT(*) FROM (SELECT x % 2 AS k, MAX(id) AS c FROM t GROUP BY x % 2) AS d;
SELECT 'DOUBLE(12,4): GROUP_CONCAT(id)' AS q, COUNT(*) FROM (SELECT x % 2 AS k, GROUP_CONCAT(id) AS c FROM t GROUP BY x % 2) AS d;
CREATE TABLE u (id INT PRIMARY KEY AUTO_INCREMENT, x DOUBLE);
INSERT INTO u (x) VALUES (3.87), (5.87), (91.87), (1.87);
SELECT 'DOUBLE: COUNT(DISTINCT x - 5)' AS q, COUNT(*) FROM (SELECT x % 2 AS k, COUNT(DISTINCT x - 5) AS c FROM u GROUP BY x % 2) AS d;
SELECT 'DOUBLE: COUNT(x - 5)' AS q, COUNT(*) FROM (SELECT x % 2 AS k, COUNT(x - 5) AS c FROM u GROUP BY x % 2) AS d;
DROP DATABASE vs_dbl;
