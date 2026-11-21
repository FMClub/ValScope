-- issues/012: number IN (SELECT date_column ...) with a NULL in the subquery: the result must
-- be NULL when no value matches (never FALSE), so NOT IN returns no row.  With an index on the
-- date column MariaDB 10.11.14 returns FALSE and NOT IN returns rows.
-- expected in both blocks: NULL in the last column of every row, and "NOT IN rows: 0"
-- (MariaDB 10.11.14 with the index: 0 for x = -3 and x = 1, and 2 rows)
DROP DATABASE IF EXISTS vs_ind; CREATE DATABASE vs_ind; USE vs_ind;
CREATE TABLE t (x DOUBLE);
CREATE TABLE s (v DATE);
INSERT INTO t VALUES (0), (1), (-3), (NULL);
INSERT INTO s VALUES ('2024-01-01'), (NULL);
SELECT 'no index' AS q, x, x IN (SELECT v FROM s) FROM t ORDER BY x;
SELECT 'no index, NOT IN rows:' AS q, COUNT(*) FROM t WHERE x NOT IN (SELECT v FROM s);
CREATE INDEX si ON s (v);
SELECT 'index' AS q, x, x IN (SELECT v FROM s) FROM t ORDER BY x;
SELECT 'index, NOT IN rows:' AS q, COUNT(*) FROM t WHERE x NOT IN (SELECT v FROM s);
-- the same with text: a value that is not a date ('a ', 'zz', '') gives 0 with the index,
-- '2024-05-05' gives NULL and '2024-01-01' matches (1); expected NULL for all but the match
CREATE TABLE w (x VARCHAR(20));
INSERT INTO w VALUES ('a '), ('zz'), (''), ('2024-01-01'), ('2024-05-05');
SELECT 'index, text' AS q, x, x IN (SELECT v FROM s) FROM w ORDER BY x;
DROP DATABASE vs_ind;
