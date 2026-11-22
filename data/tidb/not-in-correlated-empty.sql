-- Candidate TiDB bug: x NOT IN (correlated subquery) and NOT (x IN (correlated subquery))
-- differ.  Found by the translation check of bridge/campaign_mysql.py on TiDB v8.5.3 (the
-- bridge prints NOT IN as NOT (... IN ...)); 13 pairs of two campaigns, seeds 1-40 and 131-170.
-- t has one row, s is empty: every subquery is empty, x IN (empty) is FALSE and x NOT IN
-- (empty) is TRUE, whatever x is (also NULL).
-- expected: 1 in every line, unless the tag says otherwise; one row (7.75, 1) for H1
DROP DATABASE IF EXISTS vs_ni; CREATE DATABASE vs_ni; USE vs_ni;
CREATE TABLE t (a DECIMAL(10,2), b INT);
CREATE TABLE s (c INT, d INT);
INSERT INTO t VALUES (7.75, 1);
SELECT 'A1 NOT IN, correlated <=> NULL' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE t.b <=> NULL AND s.d >= t.a);
SELECT 'A2 NOT (IN), the same' AS q, COUNT(*) FROM t WHERE NOT (t.b IN (SELECT s.c FROM s WHERE t.b <=> NULL AND s.d >= t.a));
SELECT 'B1 NOT IN, correlated' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE s.d >= t.a);
SELECT 'B2 NOT (IN), correlated' AS q, COUNT(*) FROM t WHERE NOT (t.b IN (SELECT s.c FROM s WHERE s.d >= t.a));
SELECT 'C1 NOT IN, not correlated' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE s.d >= 0);
SELECT 'C2 NOT (IN), not correlated' AS q, COUNT(*) FROM t WHERE NOT (t.b IN (SELECT s.c FROM s WHERE s.d >= 0));
SELECT 'D1 NOT IN, correlated on b only' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE s.d >= t.b);
SELECT 'D2 NOT (IN), correlated on b only' AS q, COUNT(*) FROM t WHERE NOT (t.b IN (SELECT s.c FROM s WHERE s.d >= t.b));
SELECT 'E1 NOT EXISTS' AS q, COUNT(*) FROM t WHERE NOT EXISTS (SELECT 1 FROM s WHERE s.c = t.b AND s.d >= t.a);
SELECT 'F1 the value of the predicate, NOT IN' AS q, t.b NOT IN (SELECT s.c FROM s WHERE s.d >= t.a) FROM t;
SELECT 'F2 the value of the predicate, NOT (IN)' AS q, NOT (t.b IN (SELECT s.c FROM s WHERE s.d >= t.a)) FROM t;
-- narrowing A1 (TiDB v7.5.1 and v8.5.3: COUNT(*) = 2 on a table of one row)
SELECT 'H1 the rows of A1' AS q, t.a, t.b FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE t.b <=> NULL AND s.d >= t.a);
SELECT 'H2 <=> NULL only' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE t.b <=> NULL);
SELECT 'H3 IS NULL instead of <=> NULL' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE t.b IS NULL AND s.d >= t.a);
SELECT 'H4 <=> NULL on the subquery column' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE s.c <=> NULL AND s.d >= t.a);
SELECT 'H5 <=> 1 instead of <=> NULL' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE t.b <=> 1 AND s.d >= t.a);
SELECT 'H6 <=> NULL on t.a' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE t.a <=> NULL AND s.d >= t.a);
SELECT 'H7 NOT EXISTS with <=> NULL' AS q, COUNT(*) FROM t WHERE NOT EXISTS (SELECT 1 FROM s WHERE s.c = t.b AND t.b <=> NULL AND s.d >= t.a);
SELECT 'H8 A1, s has a row that does not match' AS q, COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM (SELECT 9 AS c, -100 AS d) AS s WHERE t.b <=> NULL AND s.d >= t.a);
CREATE TABLE t3 (a DECIMAL(10,2), b INT);
INSERT INTO t3 VALUES (7.75, 1), (1.00, 2), (2.00, 3);
SELECT 'H9 A1 on a table of three rows (expected 3)' AS q, COUNT(*) FROM t3 WHERE t3.b NOT IN (SELECT s.c FROM s WHERE t3.b <=> NULL AND s.d >= t3.a);
SELECT 'H10 the rows of H9' AS q, t3.a, t3.b FROM t3 WHERE t3.b NOT IN (SELECT s.c FROM s WHERE t3.b <=> NULL AND s.d >= t3.a) ORDER BY t3.b;
EXPLAIN SELECT COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE t.b <=> NULL AND s.d >= t.a);
-- the NULL case of the left side
CREATE TABLE tn (a DECIMAL(10,2), b INT);
INSERT INTO tn VALUES (7.75, NULL);
SELECT 'G1 NULL NOT IN, correlated' AS q, COUNT(*) FROM tn WHERE tn.b NOT IN (SELECT s.c FROM s WHERE s.d >= tn.a);
SELECT 'G2 NOT (NULL IN), correlated' AS q, COUNT(*) FROM tn WHERE NOT (tn.b IN (SELECT s.c FROM s WHERE s.d >= tn.a));
EXPLAIN SELECT COUNT(*) FROM t WHERE t.b NOT IN (SELECT s.c FROM s WHERE s.d >= t.a);
EXPLAIN SELECT COUNT(*) FROM t WHERE NOT (t.b IN (SELECT s.c FROM s WHERE s.d >= t.a));
DROP DATABASE vs_ni;
