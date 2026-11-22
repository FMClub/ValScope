-- OceanBase (issues/023): an aggregate of an expression of x (x - 2, x * 2) next to COUNT(DISTINCT x).
-- The value pairs of the campaigns of round 19 (data/oceanbase/campaign-pairs.sql, V queries).
-- expected (MySQL 9, MariaDB): the values named in each tag line.
DROP DATABASE IF EXISTS vs_cd; CREATE DATABASE vs_cd; USE vs_cd;
CREATE TABLE t (a INT, b INT, rid INT PRIMARY KEY);
INSERT INTO t VALUES (1, 10, 0), (2, 10, 1), (2, 20, 2), (3, 20, 3), (NULL, 30, 4);
SELECT 'C1 0: SUM(a - 2) alone' AS q;
SELECT SUM(t.a - 2) FROM t;
SELECT 'C2 0 3: SUM(a - 2), COUNT(DISTINCT a)' AS q;
SELECT SUM(t.a - 2), COUNT(DISTINCT t.a) FROM t;
SELECT 'C3 8 3: SUM(a), COUNT(DISTINCT a)' AS q;
SELECT SUM(t.a), COUNT(DISTINCT t.a) FROM t;
SELECT 'C4 0.0000 3: AVG(a - 2), COUNT(DISTINCT a)' AS q;
SELECT AVG(t.a - 2), COUNT(DISTINCT t.a) FROM t;
SELECT 'C5 16 3: SUM(a * 2), COUNT(DISTINCT a)' AS q;
SELECT SUM(t.a * 2), COUNT(DISTINCT t.a) FROM t;
SELECT 'C6 0.666... 3: VAR_SAMP(a - 2), COUNT(DISTINCT a)' AS q;
SELECT VAR_SAMP(t.a - 2), COUNT(DISTINCT t.a) FROM t;
SELECT 'C7 0: SUM(a - 2), HAVING COUNT(DISTINCT a) > 0' AS q;
SELECT SUM(t.a - 2) FROM t HAVING COUNT(DISTINCT t.a) > 0;
SELECT 'C8 0 3: SUM(a - 2), COUNT(DISTINCT b) (another column)' AS q;
SELECT SUM(t.a - 2), COUNT(DISTINCT t.b) FROM t;
SELECT 'C9 4 3: COUNT(a), COUNT(DISTINCT a)' AS q;
SELECT COUNT(t.a), COUNT(DISTINCT t.a) FROM t;
SELECT 'C10 10: -1 2, 20: 1 2, 30: NULL 0: GROUP BY b, SUM(a - 2), COUNT(DISTINCT a)' AS q;
SELECT t.b, SUM(t.a - 2), COUNT(DISTINCT t.a) FROM t GROUP BY t.b ORDER BY t.b;
SELECT 'C11 0 3: SUM(a - 2), COUNT(DISTINCT a) from a derived table' AS q;
SELECT SUM(d.a - 2), COUNT(DISTINCT d.a) FROM (SELECT t.a FROM t) AS d;
SELECT 'C12 0 3: SUM(a) - 2 * COUNT(a) written out, COUNT(DISTINCT a)' AS q;
SELECT SUM(t.a) - 2 * COUNT(t.a), COUNT(DISTINCT t.a) FROM t;
USE information_schema; DROP DATABASE vs_cd;
