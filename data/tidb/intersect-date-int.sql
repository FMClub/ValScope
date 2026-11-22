-- Candidate TiDB bug (round 18): an INTERSECT whose right operand is an INTERSECT of a DATE and an
-- INT column returns a row that is in neither.  Found by the campaign on TiDB v8.5.3 (seed 8, rule
-- INTERSECT->UNION).  t2 has one row with c15 = '2'; t3 has (2024-12-28, NULL) and (NULL, 4).
-- {'2'} INTERSECT ({2024-12-28, NULL} INTERSECT {NULL, 4}) = {'2'} INTERSECT {NULL} = {}.
-- expected: no row after every tag line except I1 (NULL), I4 (NULL) and I6 ('2')
DROP DATABASE IF EXISTS vs_idi; CREATE DATABASE vs_idi; USE vs_idi;
CREATE TABLE t2 (c1 BIGINT, c15 VARCHAR(20));
CREATE TABLE t3 (c6 DATE, c7 INT);
INSERT INTO t2 VALUES (NULL, '2');
INSERT INTO t3 VALUES ('2024-12-28', NULL), (NULL, 4);
SELECT 'I1 the inner INTERSECT (expected one row, NULL)' AS q;
(SELECT c6 AS k FROM t3) INTERSECT (SELECT c7 AS k FROM t3);
SELECT 'I2 the query of the campaign (expected no row)' AS q;
(SELECT c15 AS k FROM t2 WHERE c1 IS NULL) INTERSECT ((SELECT c6 AS k FROM t3) INTERSECT (SELECT c7 AS k FROM t3));
SELECT 'I3 the same, as a derived table' AS q;
SELECT r.k FROM ((SELECT c15 AS k FROM t2 WHERE c1 IS NULL) INTERSECT ((SELECT c6 AS k FROM t3) INTERSECT (SELECT c7 AS k FROM t3))) AS r;
SELECT 'I4 the inner INTERSECT in a derived table (expected NULL)' AS q;
SELECT r.k FROM ((SELECT c6 AS k FROM t3) INTERSECT (SELECT c7 AS k FROM t3)) AS r;
SELECT 'I5 left-deep: (A INTERSECT B) INTERSECT C (expected no row)' AS q;
((SELECT c15 AS k FROM t2 WHERE c1 IS NULL) INTERSECT (SELECT c6 AS k FROM t3)) INTERSECT (SELECT c7 AS k FROM t3);
SELECT 'I6 A alone (expected 2)' AS q;
SELECT c15 AS k FROM t2 WHERE c1 IS NULL;
SELECT 'I7 A INTERSECT {NULL} (expected no row)' AS q;
(SELECT c15 AS k FROM t2) INTERSECT (SELECT NULL AS k);
SELECT 'I8 A INTERSECT (DATE INTERSECT INT) with a VARCHAR c6 (expected no row)' AS q;
CREATE TABLE t4 (c6 VARCHAR(20), c7 INT);
INSERT INTO t4 VALUES ('2024-12-28', NULL), (NULL, 4);
(SELECT c15 AS k FROM t2 WHERE c1 IS NULL) INTERSECT ((SELECT c6 AS k FROM t4) INTERSECT (SELECT c7 AS k FROM t4));
SELECT 'I9 with 3 instead of 4 (expected no row)' AS q;
UPDATE t3 SET c7 = 3 WHERE c7 = 4;
(SELECT c15 AS k FROM t2 WHERE c1 IS NULL) INTERSECT ((SELECT c6 AS k FROM t3) INTERSECT (SELECT c7 AS k FROM t3));
SELECT 'end' AS q;
DROP DATABASE vs_idi;
