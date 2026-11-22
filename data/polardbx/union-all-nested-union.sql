-- PolarDB-X (issues/024): UNION ALL with a parenthesized UNION as an operand.  The two
-- INTERSECT->UNION pairs of the campaign with --tidb (data/polardbx/intersect-union-pairs.sql).
-- expected (MySQL 9, MariaDB): the rows named in each tag line.
DROP DATABASE IF EXISTS vs_ua; CREATE DATABASE vs_ua; USE vs_ua;
CREATE TABLE t (a INT, rid INT PRIMARY KEY);
INSERT INTO t VALUES (1, 0), (1, 1);
SELECT 'U1 1 1: t UNION ALL (empty UNION empty)' AS q;
(SELECT t.a FROM t) UNION ALL ((SELECT t.a FROM t WHERE 1 = 0) UNION (SELECT t.a FROM t WHERE 1 = 0));
SELECT 'U2 1 1 2 3: t UNION ALL (2 UNION 3)' AS q;
(SELECT t.a FROM t) UNION ALL ((SELECT 2 AS a) UNION (SELECT 3 AS a));
SELECT 'U3 2 3 1 1: (2 UNION 3) UNION ALL t' AS q;
((SELECT 2 AS a) UNION (SELECT 3 AS a)) UNION ALL (SELECT t.a FROM t);
SELECT 'U4 1 5 5 6: (t UNION 5) UNION ALL (5 UNION 6)' AS q;
((SELECT t.a FROM t) UNION (SELECT 5 AS a)) UNION ALL ((SELECT 5 AS a) UNION (SELECT 6 AS a));
SELECT 'U5 1 1 1 1: t UNION ALL t' AS q;
(SELECT t.a FROM t) UNION ALL (SELECT t.a FROM t);
SELECT 'U6 1 1 2 3: t UNION ALL (2 UNION 3) as a derived table' AS q;
(SELECT t.a FROM t) UNION ALL (SELECT d.a FROM ((SELECT 2 AS a) UNION (SELECT 3 AS a)) AS d);
SELECT 'U7 1 2: t UNION (2 UNION ALL 2)' AS q;
(SELECT t.a FROM t) UNION ((SELECT 2 AS a) UNION ALL (SELECT 2 AS a));
SELECT 'U8 1 9: t UNION ALL t UNION 9, without parentheses (the last UNION removes the duplicates on its left)' AS q;
SELECT t.a FROM t UNION ALL SELECT t.a FROM t UNION SELECT 9 AS a;
SELECT 'U9 1 9 1 1: t UNION 9 UNION ALL t, without parentheses' AS q;
SELECT t.a FROM t UNION SELECT 9 AS a UNION ALL SELECT t.a FROM t;
SELECT 'U10 1 1 2: t UNION ALL (2 INTERSECT 2)' AS q;
(SELECT t.a FROM t) UNION ALL ((SELECT 2 AS a) INTERSECT (SELECT 2 AS a));
SELECT 'U11 1 1 2: t UNION ALL (2 EXCEPT 3)' AS q;
(SELECT t.a FROM t) UNION ALL ((SELECT 2 AS a) EXCEPT (SELECT 3 AS a));
USE information_schema; DROP DATABASE vs_ua;
