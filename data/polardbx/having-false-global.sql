-- PolarDB-X: an aggregate without GROUP BY and a HAVING that is false (the pairs of seeds 4,
-- 5 and 7 of the first campaign, rule HAVING cond->FALSE).  expected (MySQL, MariaDB): every
-- query tagged "empty" returns no row, every query tagged "one" returns one row, Q8 three.
DROP DATABASE IF EXISTS vs_hf; CREATE DATABASE vs_hf; USE vs_hf;
CREATE TABLE t3 (c9 INT, c3 DECIMAL(10,2), rid INT PRIMARY KEY);
INSERT INTO t3 VALUES (3, 1, 0), (NULL, 2, 1), (1, -3, 2), (4, 5.5, 3);
SELECT 'Q1 empty: global COUNT, HAVING 1 = 0' AS q;
SELECT COUNT(t3.c9) FROM t3 HAVING 1 = 0;
SELECT 'Q2 empty: global COUNT, HAVING FALSE' AS q;
SELECT COUNT(t3.c9) FROM t3 HAVING FALSE;
SELECT 'Q3 empty: global COUNT, HAVING on an aggregate that is false' AS q;
SELECT COUNT(t3.c9) FROM t3 HAVING COUNT(t3.c9) < 0;
SELECT 'Q4 one: global COUNT, HAVING 1 = 1' AS q;
SELECT COUNT(t3.c9) FROM t3 HAVING 1 = 1;
SELECT 'Q5 empty: SIGN(COUNT), HAVING 1 = 0' AS q;
SELECT SIGN(COUNT(t3.c9)) AS k0 FROM t3 HAVING 1 = 0;
SELECT 'Q6 empty: global COUNT over an empty WHERE, HAVING 1 = 0' AS q;
SELECT COUNT(*) FROM t3 WHERE t3.c9 > 100 HAVING 1 = 0;
SELECT 'Q7 empty: GROUP BY, HAVING 1 = 0' AS q;
SELECT t3.c9, COUNT(*) FROM t3 GROUP BY t3.c9 HAVING 1 = 0;
SELECT 'Q8 three rows (1, 3, 4): EXCEPT an arm with HAVING 1 = 0 (seed 7)' AS q;
(SELECT t3.c9 AS k0 FROM t3 WHERE t3.c9 IS NOT NULL) EXCEPT (SELECT SIGN(COUNT(t3.c9)) AS k0 FROM t3 HAVING 1 = 0);
SELECT 'Q9 empty: INTERSECT with an arm with HAVING 1 = 0 (seed 5)' AS q;
(SELECT COUNT(t3.c9) AS k0 FROM t3 HAVING 1 = 0) INTERSECT (SELECT 3 AS k0);
SELECT 'Q10 empty: derived table of a global COUNT with HAVING 1 = 0' AS q;
SELECT d.n FROM (SELECT COUNT(t3.c9) AS n FROM t3 HAVING 1 = 0) AS d;
DROP DATABASE vs_hf;
