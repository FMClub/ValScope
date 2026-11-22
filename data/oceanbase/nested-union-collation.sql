-- OceanBase (issues/024): a UNION inside a UNION over a column of another collation.  The three
-- UNION pairs of the campaign on seeds 1-40 (data/oceanbase/union-pairs.sql).
-- expected (MySQL 9, MariaDB): the rows named in each tag line.
DROP DATABASE IF EXISTS vs_nu; CREATE DATABASE vs_nu; USE vs_nu;
CREATE TABLE s (v VARCHAR(20) COLLATE utf8mb4_general_ci);
INSERT INTO s VALUES ('a'), ('A');
CREATE TABLE b (v VARCHAR(20) COLLATE utf8mb4_bin);
INSERT INTO b VALUES ('x');
SELECT 'N1 one of a, A: s UNION s' AS q;
(SELECT s.v FROM s) UNION (SELECT s.v FROM s);
SELECT 'N2 x and one of a, A: b UNION (s UNION s)' AS q;
(SELECT b.v FROM b) UNION ((SELECT s.v FROM s) UNION (SELECT s.v FROM s));
SELECT 'N3 one of a, A: (empty b) UNION (s UNION s)' AS q;
(SELECT b.v FROM b WHERE 1 = 0) UNION ((SELECT s.v FROM s) UNION (SELECT s.v FROM s));
SELECT 'N4 one of a, A: (empty b) UNION ALL (s UNION s)' AS q;
(SELECT b.v FROM b WHERE 1 = 0) UNION ALL ((SELECT s.v FROM s) UNION (SELECT s.v FROM s));
SELECT 'N5 x and one of a, A: b UNION (the inner UNION as a derived table)' AS q;
(SELECT b.v FROM b) UNION (SELECT d.v FROM ((SELECT s.v FROM s) UNION (SELECT s.v FROM s)) AS d);
SELECT 'N6 x, a, A: b UNION s UNION s, without the parentheses (one UNION, in the binary collation)' AS q;
SELECT b.v FROM b UNION SELECT s.v FROM s UNION SELECT s.v FROM s;
SELECT 'N7 one of a, A: (empty b) UNION (SELECT DISTINCT v FROM s)' AS q;
(SELECT b.v FROM b WHERE 1 = 0) UNION (SELECT DISTINCT s.v FROM s);
CREATE TABLE p (v VARCHAR(20) COLLATE utf8mb4_general_ci);
INSERT INTO p VALUES ('a '), ('A'), ('');
SELECT 'N8 two rows, the empty string and one of 'a ', A: (empty b) UNION (p UNION p), trailing space (pair 2)' AS q;
(SELECT b.v FROM b WHERE 1 = 0) UNION ((SELECT p.v FROM p) UNION (SELECT p.v FROM p));
USE information_schema; DROP DATABASE vs_nu;
