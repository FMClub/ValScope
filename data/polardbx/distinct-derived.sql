-- PolarDB-X: a table replaced by (SELECT DISTINCT * FROM it), the two DISTINCT-add pairs of
-- the second campaign (data/polardbx/distinct-add-seeds.sql has them on their databases).
-- expected (MySQL 9, MariaDB): each query returns the rows named in its tag line.
DROP DATABASE IF EXISTS vs_dd; CREATE DATABASE vs_dd; USE vs_dd;
CREATE TABLE t (a INT, b INT, rid INT PRIMARY KEY);
INSERT INTO t VALUES (3, NULL, 0), (NULL, 1, 1), (4, 2, 2);
-- A: a correlated IN whose subquery is empty for the row (3, NULL): t.b <= 10 is unknown
SELECT 'A1 (3 0) (NULL NULL) (4 NULL): IN, subquery on t' AS q;
SELECT t.a, t.a IN (SELECT s.b FROM t AS s WHERE t.b <= 10) FROM t ORDER BY t.rid;
SELECT 'A2 the same: subquery on (SELECT DISTINCT * FROM t)' AS q;
SELECT t.a, t.a IN (SELECT s.b FROM (SELECT DISTINCT * FROM t) AS s WHERE t.b <= 10) FROM t ORDER BY t.rid;
SELECT 'A3 the same: subquery on (SELECT * FROM t)' AS q;
SELECT t.a, t.a IN (SELECT s.b FROM (SELECT * FROM t) AS s WHERE t.b <= 10) FROM t ORDER BY t.rid;
SELECT 'A4 the same: subquery on (SELECT DISTINCT s.b FROM t)' AS q;
SELECT t.a, t.a IN (SELECT s.b FROM (SELECT DISTINCT s0.b FROM t AS s0) AS s WHERE t.b <= 10) FROM t ORDER BY t.rid;
SELECT 'A5 (3 0) (NULL NULL) (4 0): no NULL in the subquery, on (SELECT DISTINCT * FROM t)' AS q;
SELECT t.a, t.a IN (SELECT s.b FROM (SELECT DISTINCT * FROM t) AS s WHERE t.b <= 10 AND s.b IS NOT NULL) FROM t ORDER BY t.rid;
SELECT 'A6 3: as a WHERE NOT (... IN ...), on (SELECT DISTINCT * FROM t)' AS q;
SELECT t.a FROM t WHERE NOT (t.a IN (SELECT s.b FROM (SELECT DISTINCT * FROM t) AS s WHERE t.b <= 10)) ORDER BY t.rid;
SELECT 'A7 (3 0) (NULL 1) (4 1): EXISTS, on (SELECT DISTINCT * FROM t)' AS q;
SELECT t.a, EXISTS (SELECT s.b FROM (SELECT DISTINCT * FROM t) AS s WHERE t.b <= 10) FROM t ORDER BY t.rid;
-- B: an EXCEPT whose right arm is empty
CREATE TABLE l (k0 INT, k1 INT, rid INT PRIMARY KEY);
INSERT INTO l VALUES (3, NULL, 0), (NULL, NULL, 1), (9, NULL, 2), (4, 7, 3);
CREATE TABLE r (x INT, y INT, rid INT PRIMARY KEY);
INSERT INTO r VALUES (5, 6, 0);
SELECT 'B1 none: the right arm alone' AS q;
SELECT a.a AS k0, b.a AS k1 FROM (SELECT DISTINCT * FROM t) AS a LEFT JOIN t AS b ON (0) WHERE (b.a, b.b) IN (SELECT r.x, r.y FROM r);
SELECT 'B2 (3 NULL) (NULL NULL) (9 NULL) (4 7): EXCEPT, arm on t' AS q;
(SELECT l.k0, l.k1 FROM l) EXCEPT (SELECT a.a AS k0, b.a AS k1 FROM t AS a LEFT JOIN t AS b ON (0) WHERE (b.a, b.b) IN (SELECT r.x, r.y FROM r));
SELECT 'B3 the same: EXCEPT, arm on (SELECT DISTINCT * FROM t)' AS q;
(SELECT l.k0, l.k1 FROM l) EXCEPT (SELECT a.a AS k0, b.a AS k1 FROM (SELECT DISTINCT * FROM t) AS a LEFT JOIN t AS b ON (0) WHERE (b.a, b.b) IN (SELECT r.x, r.y FROM r));
SELECT 'B4 none: INTERSECT, arm on (SELECT DISTINCT * FROM t)' AS q;
(SELECT l.k0, l.k1 FROM l) INTERSECT (SELECT a.a AS k0, b.a AS k1 FROM (SELECT DISTINCT * FROM t) AS a LEFT JOIN t AS b ON (0) WHERE (b.a, b.b) IN (SELECT r.x, r.y FROM r));
SELECT 'B5 (4 7): UNION ALL, arm on (SELECT DISTINCT * FROM t)' AS q;
(SELECT l.k0, l.k1 FROM l WHERE l.k1 IS NOT NULL) UNION ALL (SELECT a.a AS k0, b.a AS k1 FROM (SELECT DISTINCT * FROM t) AS a LEFT JOIN t AS b ON (0) WHERE (b.a, b.b) IN (SELECT r.x, r.y FROM r));
SELECT 'B6 as B2: EXCEPT, one column IN, arm on (SELECT DISTINCT * FROM t)' AS q;
(SELECT l.k0, l.k1 FROM l) EXCEPT (SELECT a.a AS k0, b.a AS k1 FROM (SELECT DISTINCT * FROM t) AS a LEFT JOIN t AS b ON (0) WHERE b.a IN (SELECT r.x FROM r));
SELECT 'B7 as B2: EXCEPT, arm on (SELECT DISTINCT * FROM t) without the join' AS q;
(SELECT l.k0, l.k1 FROM l) EXCEPT (SELECT a.a AS k0, NULL AS k1 FROM (SELECT DISTINCT * FROM t) AS a WHERE (a.a, a.b) IN (SELECT r.x, r.y FROM r));
SELECT 'B8 as B2: EXCEPT, arm on (SELECT DISTINCT * FROM t), b.a = 5 for the IN' AS q;
(SELECT l.k0, l.k1 FROM l) EXCEPT (SELECT a.a AS k0, b.a AS k1 FROM (SELECT DISTINCT * FROM t) AS a LEFT JOIN t AS b ON (0) WHERE b.a = 5);
USE information_schema; DROP DATABASE vs_dd;
