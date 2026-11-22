-- PolarDB-X (issues/020): an aggregate without GROUP BY and a false HAVING, alone and as an
-- arm of a set operation.  The pairs of seeds 4, 5 and 7 of the first campaign (rule HAVING
-- cond->FALSE; data/polardbx/having-false-seeds.sql has them on their databases).
-- expected (MySQL 9, MariaDB): each query returns the rows named in its tag line.
DROP DATABASE IF EXISTS vs_hf; CREATE DATABASE vs_hf; USE vs_hf;
CREATE TABLE t (a INT, rid INT PRIMARY KEY);
INSERT INTO t VALUES (3, 0), (NULL, 1), (1, 2), (4, 3);
SELECT 'Q1 none: alone, HAVING 1 = 0' AS q;
SELECT COUNT(t.a) FROM t HAVING 1 = 0;
SELECT 'Q2 none: alone, HAVING FALSE' AS q;
SELECT COUNT(t.a) FROM t HAVING FALSE;
SELECT 'Q3 none: in a derived table' AS q;
SELECT d.n FROM (SELECT COUNT(t.a) AS n FROM t HAVING 1 = 0) AS d;
SELECT 'Q4 none: 0 INTERSECT (COUNT HAVING 1 = 0)' AS q;
(SELECT 0 AS k) INTERSECT (SELECT COUNT(t.a) AS k FROM t HAVING 1 = 0);
SELECT 'Q5 0: 0 EXCEPT (COUNT HAVING 1 = 0)' AS q;
(SELECT 0 AS k) EXCEPT (SELECT COUNT(t.a) AS k FROM t HAVING 1 = 0);
SELECT 'Q6 7: 7 UNION ALL (COUNT HAVING 1 = 0)' AS q;
(SELECT 7 AS k) UNION ALL (SELECT COUNT(t.a) AS k FROM t HAVING 1 = 0);
SELECT 'Q7 7: 7 UNION (COUNT HAVING 1 = 0)' AS q;
(SELECT 7 AS k) UNION (SELECT COUNT(t.a) AS k FROM t HAVING 1 = 0);
SELECT 'Q8 none: NULL INTERSECT (MIN HAVING 1 = 0)' AS q;
(SELECT NULL AS k) INTERSECT (SELECT MIN(t.a) AS k FROM t HAVING 1 = 0);
SELECT 'Q9 0: 0 EXCEPT (COUNT HAVING FALSE)' AS q;
(SELECT 0 AS k) EXCEPT (SELECT COUNT(t.a) AS k FROM t HAVING FALSE);
SELECT 'Q10 0: 0 EXCEPT (COUNT HAVING COUNT(t.a) < 0), a false condition on an aggregate' AS q;
(SELECT 0 AS k) EXCEPT (SELECT COUNT(t.a) AS k FROM t HAVING COUNT(t.a) < 0);
SELECT 'Q11 0: 0 EXCEPT (COUNT WHERE 1 = 0 HAVING 1 = 0)' AS q;
(SELECT 0 AS k) EXCEPT (SELECT COUNT(t.a) AS k FROM t WHERE 1 = 0 HAVING 1 = 0);
SELECT 'Q12 0: 0 EXCEPT (COUNT GROUP BY a HAVING 1 = 0), with GROUP BY' AS q;
(SELECT 0 AS k) EXCEPT (SELECT COUNT(t.a) AS k FROM t GROUP BY t.a HAVING 1 = 0);
SELECT 'Q13 3: (COUNT HAVING 1 = 0) as the first arm of a UNION ALL' AS q;
(SELECT COUNT(t.a) AS k FROM t HAVING 1 = 0) UNION ALL (SELECT 3 AS k);
DROP DATABASE vs_hf;
