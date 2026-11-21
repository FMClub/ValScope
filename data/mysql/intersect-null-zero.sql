-- issues/008, second form (found on MySQL 9.7.4, seed 177 of the campaign, rule cmp-weaken):
-- INTERSECT matches the NULL of the left operand with the 0 of the right operand when the
-- left operand is a UNION.  t has the rows (-1, 3) and (5, NULL); the left operand is {NULL}.
-- Bare compounds: a tag line, then the rows.  expected: no row after B1 to B4 and B6,
-- two rows 0 after B5.  Then the same compounds in a derived table: expected 0, 0, 0, 0, 2, 0.
-- (MySQL 9.7.4: a row 0 after B1, B2 and B6, one row after B5; MySQL 8.4.13: see issues/008)
DROP DATABASE IF EXISTS vs_inz; CREATE DATABASE vs_inz; USE vs_inz;
CREATE TABLE t (a INT, b INT);
INSERT INTO t VALUES (-1, 3), (5, NULL);
SELECT 'B1: (empty UNION {NULL}) INTERSECT ALL {0, 0}' AS q;
((SELECT t.a AS k FROM t WHERE 0) UNION (SELECT t.b AS k FROM t WHERE t.a = 5)) INTERSECT ALL (SELECT 0 AS k FROM t);
SELECT 'B2: B1 with INTERSECT' AS q;
((SELECT t.a AS k FROM t WHERE 0) UNION (SELECT t.b AS k FROM t WHERE t.a = 5)) INTERSECT (SELECT 0 AS k FROM t);
SELECT 'B3: {NULL} INTERSECT ALL {0, 0}, no UNION' AS q;
(SELECT t.b AS k FROM t WHERE t.a = 5) INTERSECT ALL (SELECT 0 AS k FROM t);
SELECT 'B4: B1 with 7 instead of 0' AS q;
((SELECT t.a AS k FROM t WHERE 0) UNION (SELECT t.b AS k FROM t WHERE t.a = 5)) INTERSECT ALL (SELECT 7 AS k FROM t);
SELECT 'B5: {0, 0} EXCEPT ALL (empty UNION {NULL}); expected 0, 0' AS q;
(SELECT 0 AS k FROM t) EXCEPT ALL ((SELECT t.a AS k FROM t WHERE 0) UNION (SELECT t.b AS k FROM t WHERE t.a = 5));
SELECT 'B6: ({NULL} UNION {NULL}) INTERSECT ALL {0, 0}' AS q;
((SELECT t.b AS k FROM t WHERE t.a = 5) UNION (SELECT t.b AS k FROM t WHERE t.a = 5)) INTERSECT ALL (SELECT 0 AS k FROM t);
SELECT 'end of the bare compounds' AS q;
SELECT 'W1' AS q, COUNT(*) FROM (((SELECT t.a AS k FROM t WHERE 0) UNION (SELECT t.b AS k FROM t WHERE t.a = 5)) INTERSECT ALL (SELECT 0 AS k FROM t)) AS r;
SELECT 'W2' AS q, COUNT(*) FROM (((SELECT t.a AS k FROM t WHERE 0) UNION (SELECT t.b AS k FROM t WHERE t.a = 5)) INTERSECT (SELECT 0 AS k FROM t)) AS r;
SELECT 'W3' AS q, COUNT(*) FROM ((SELECT t.b AS k FROM t WHERE t.a = 5) INTERSECT ALL (SELECT 0 AS k FROM t)) AS r;
SELECT 'W4' AS q, COUNT(*) FROM (((SELECT t.a AS k FROM t WHERE 0) UNION (SELECT t.b AS k FROM t WHERE t.a = 5)) INTERSECT ALL (SELECT 7 AS k FROM t)) AS r;
SELECT 'W5' AS q, COUNT(*) FROM ((SELECT 0 AS k FROM t) EXCEPT ALL ((SELECT t.a AS k FROM t WHERE 0) UNION (SELECT t.b AS k FROM t WHERE t.a = 5))) AS r;
SELECT 'W6' AS q, COUNT(*) FROM (((SELECT t.b AS k FROM t WHERE t.a = 5) UNION (SELECT t.b AS k FROM t WHERE t.a = 5)) INTERSECT ALL (SELECT 0 AS k FROM t)) AS r;
DROP DATABASE vs_inz;
