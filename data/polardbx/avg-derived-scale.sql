-- PolarDB-X: the AVG->MAX pair of seed 3 of the campaign with --tidb --no-group-window (reduced).
-- Every group has one row, so AVG and MAX of a group are equal; the outer AVG of the two
-- derived columns is 11/6, printed with as many decimals as its type has.
DROP DATABASE IF EXISTS vs_ad; CREATE DATABASE vs_ad; USE vs_ad;
CREATE TABLE t2 (c1 DECIMAL(10,2), c2 INT, c3 INT, c14 INT, c15 DECIMAL(10,2), rid INT PRIMARY KEY);
INSERT INTO t2 VALUES (2.00, 2, 10, 2, 3.00, 2), (-2.25, 2, 0, 3, 4.00, 4), (-1.00, 0, -1, NULL, 1.50, 5),
  (5.25, 0, NULL, NULL, 10.25, 8), (1.00, 2, 1, 1, -0.25, 9), (4.00, -1, 10, NULL, 1.25, 11);
SELECT 'A1 original: 10.25 -2.25 0.6667 1.83333333 (MySQL 9 scales)' AS q;
SELECT MAX(d.k0) AS c0, MIN(d.k1) AS c1, AVG(d.k2) AS c2, AVG(d.k3) AS c3 FROM (SELECT t2a.c15 AS k0, t2a.c1 AS k1, MIN(t2a.c14 % 2) AS k2, AVG(t2a.c2 - 3) + 4 AS k3 FROM t2 AS t2a GROUP BY t2a.c15, t2a.c1) AS d;
SELECT 'A2 mutant: the same, c3 with 4 decimals' AS q;
SELECT MAX(d.k0) AS c0, MIN(d.k1) AS c1, AVG(d.k2) AS c2, AVG(d.k3) AS c3 FROM (SELECT t2a.c15 AS k0, t2a.c1 AS k1, MIN((t2a.c14 % 2)) AS k2, (MAX((t2a.c2 - 3)) + 4) AS k3 FROM t2 AS t2a GROUP BY t2a.c15, t2a.c1) AS d;
SELECT 'A3 the derived table of the original: k3 of every group' AS q;
SELECT t2a.c15 AS k0, t2a.c1 AS k1, AVG(t2a.c2 - 3) + 4 AS k3 FROM t2 AS t2a GROUP BY t2a.c15, t2a.c1 ORDER BY 1;
SELECT 'A4 the derived table of the mutant' AS q;
SELECT t2a.c15 AS k0, t2a.c1 AS k1, MAX(t2a.c2 - 3) + 4 AS k3 FROM t2 AS t2a GROUP BY t2a.c15, t2a.c1 ORDER BY 1;
USE information_schema; DROP DATABASE vs_ad;
