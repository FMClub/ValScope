-- issues/003 on MariaDB 11.4 / 11.8: the campaign of CI (seed 4, rule COUNT-DISTINCT->COUNT)
-- found a pair of this shape still violated there, although the minimal case of the issue
-- (having-count-in.sql) is fixed.  The pair as the reducer left it on 11.8.9.
-- The subquery returns {1}; both groups have COUNT(c1) = 1; expected: 2 groups in every line.
-- (MariaDB 10.11.14: 2 with COUNT(DISTINCT c3), 0 with COUNT(c3), nested or not)
DROP DATABASE IF EXISTS vs_hnest; CREATE DATABASE vs_hnest; USE vs_hnest;
CREATE TABLE h3 (c1 INT, c2 INT, c3 INT, c7 INT);
CREATE TABLE h1 (c1 BIGINT);
INSERT INTO h3 VALUES (1, 2, 4, 2), (2, 5, 5, 0);
INSERT INTO h1 VALUES (2), (NULL), (-1), (-3), (7), (3), (10), (4), (1), (4), (-3);
SELECT 'nested IN, COUNT(DISTINCT c3)' AS q, COUNT(*) FROM (SELECT a.c3, a.c7, COUNT(DISTINCT a.c3) AS k FROM h3 AS a GROUP BY a.c3, a.c7 HAVING COUNT(a.c1) IN (SELECT s.c1 FROM h3 AS s WHERE s.c2 IN (SELECT u.c1 FROM h1 AS u))) AS r;
SELECT 'nested IN, COUNT(c3)' AS q, COUNT(*) FROM (SELECT a.c3, a.c7, COUNT(a.c3) AS k FROM h3 AS a GROUP BY a.c3, a.c7 HAVING COUNT(a.c1) IN (SELECT s.c1 FROM h3 AS s WHERE s.c2 IN (SELECT u.c1 FROM h1 AS u))) AS r;
SELECT 'plain subquery, COUNT(DISTINCT c3)' AS q, COUNT(*) FROM (SELECT a.c3, a.c7, COUNT(DISTINCT a.c3) AS k FROM h3 AS a GROUP BY a.c3, a.c7 HAVING COUNT(a.c1) IN (SELECT s.c1 FROM h3 AS s WHERE s.c2 = 2)) AS r;
SELECT 'plain subquery, COUNT(c3)' AS q, COUNT(*) FROM (SELECT a.c3, a.c7, COUNT(a.c3) AS k FROM h3 AS a GROUP BY a.c3, a.c7 HAVING COUNT(a.c1) IN (SELECT s.c1 FROM h3 AS s WHERE s.c2 = 2)) AS r;
DROP DATABASE vs_hnest;
