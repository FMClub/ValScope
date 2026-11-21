-- A pair of the campaign on MySQL 9.7.4 (seed 177, rule cmp-weaken), as reduced.
-- The left operand of INTERSECT ALL is {NULL} (original) or {3, NULL} (mutant); the right
-- operand is {0, 0}: COALESCE of the NULL of an outer join.  No value is in both.
-- expected: no row from the four INTERSECT queries (only the 'operand' lines are printed)
DROP DATABASE IF EXISTS vs_ia; CREATE DATABASE vs_ia; USE vs_ia;
CREATE TABLE t2 (c1 INT, c2 INT, c15 INT);
INSERT INTO t2 VALUES (-1, -1, 3), (4, 5, NULL);
SELECT 'operand: left, original' AS q, r.k0 FROM ((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE (CONCAT(t2a.c2, '')) = ('5'))) AS r;
SELECT 'operand: left, mutant' AS q, r.k0 FROM ((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE (CONCAT(t2a.c2, '')) <= ('5'))) AS r;
SELECT 'operand: right' AS q, COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN (SELECT x.c1 AS c1 FROM t2 AS x) AS t2b ON (0);
SELECT 'original' AS q, r.* FROM (((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE (CONCAT(t2a.c2, '')) = ('5'))) INTERSECT ALL (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN (SELECT x.c1 AS c1 FROM t2 AS x) AS t2b ON (0))) AS r;
SELECT 'mutant' AS q, r.* FROM (((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE (CONCAT(t2a.c2, '')) <= ('5'))) INTERSECT ALL (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN (SELECT x.c1 AS c1 FROM t2 AS x) AS t2b ON (0))) AS r;
SELECT 'simple: {NULL} INTERSECT ALL {0, 0}' AS q, r.* FROM ((SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5) INTERSECT ALL (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0))) AS r;
SELECT 'simple: {3, NULL} INTERSECT {0}' AS q, r.* FROM ((SELECT t2a.c15 AS k0 FROM t2 AS t2a) INTERSECT (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0))) AS r;
SELECT 'simple: no outer join' AS q, r.* FROM ((SELECT t2a.c15 AS k0 FROM t2 AS t2a) INTERSECT ALL (SELECT 0 AS k0 FROM t2 AS t2a)) AS r;
-- variants; every one of them must return no row (the tag line is printed, then the rows)
SELECT 'V1: UNION left, constant right' AS q;
((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5)) INTERSECT ALL (SELECT 0 AS k0 FROM t2 AS t2a);
SELECT 'V2: UNION left, COALESCE over an outer join right' AS q;
((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5)) INTERSECT ALL (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0));
SELECT 'V3: V2 with INTERSECT' AS q;
((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5)) INTERSECT (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0));
SELECT 'V4: V2 with UNION ALL on the left' AS q;
((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION ALL (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5)) INTERSECT ALL (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0));
SELECT 'V5: no UNION on the left' AS q;
(SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5) INTERSECT ALL (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0));
SELECT 'V6: V2 with COALESCE(c1, 0) of the table, no outer join' AS q;
((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5)) INTERSECT ALL (SELECT COALESCE(t2a.c1, 0) - COALESCE(t2a.c1, 0) AS k0 FROM t2 AS t2a);
SELECT 'V7: V2 with EXCEPT ALL, operands swapped (expected 0, 0)' AS q;
(SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0)) EXCEPT ALL ((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5));
SELECT 'V8: V2, right operand 7 instead of 0' AS q;
((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c2 = 5)) INTERSECT ALL (SELECT COALESCE(t2b.c1, 7) AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0));
SELECT 'end of the variants' AS q;
-- as the campaign ran them, without a derived table around the compound
((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE (CONCAT(t2a.c2, '')) = ('5'))) INTERSECT ALL (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN (SELECT x.c1 AS c1 FROM t2 AS x) AS t2b ON (0));
SELECT 'end of the bare original (rows above this line are wrong)' AS q;
((SELECT t2a.c2 AS k0 FROM t2 AS t2a WHERE (0)) UNION (SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE (CONCAT(t2a.c2, '')) <= ('5'))) INTERSECT ALL (SELECT COALESCE(t2b.c1, 0) AS k0 FROM t2 AS t2a LEFT JOIN (SELECT x.c1 AS c1 FROM t2 AS x) AS t2b ON (0));
SELECT 'end of the bare mutant (rows above this line are wrong)' AS q;
DROP DATABASE vs_ia;
