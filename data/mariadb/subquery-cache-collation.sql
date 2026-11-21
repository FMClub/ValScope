-- issues/014: the subquery cache and two collations.  The outer column is case-insensitive
-- (utf8mb4_general_ci), the column of the subquery is utf8mb4_bin, so the comparison is made
-- under utf8mb4_bin: 'A' does not match 'a'.  The cache of the subquery looks its key up under
-- the collation of the outer column, so 'A' and 'a' share one entry and the second row gets
-- the answer of the first.
-- expected in every block: 0 for 'A' and 1 for 'a' (MariaDB 10.11.14: 0, 0 in id order;
-- 1, 1 in reverse order; 0, 1 with the cache switched off), and the row 2 in every "rows:" line
DROP DATABASE IF EXISTS vs_sc; CREATE DATABASE vs_sc; USE vs_sc;
SET NAMES utf8mb4;
CREATE TABLE a (id INT PRIMARY KEY, s VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci);
CREATE TABLE b (v VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin);
INSERT INTO a VALUES (1, 'A'), (2, 'a');
INSERT INTO b VALUES ('a');
SELECT 'id order' AS q, id, s, s IN (SELECT v FROM b) AS in_sub, (SELECT COUNT(*) FROM b WHERE b.v = a.s) AS n, EXISTS (SELECT 1 FROM b WHERE b.v = a.s) AS ex FROM a ORDER BY id;
SELECT 'reverse order' AS q, id, s, s IN (SELECT v FROM b) AS in_sub, (SELECT COUNT(*) FROM b WHERE b.v = a.s) AS n, EXISTS (SELECT 1 FROM b WHERE b.v = a.s) AS ex FROM a ORDER BY id DESC;
SELECT 'WHERE 0 OR s IN (subquery), rows:' AS q, GROUP_CONCAT(id ORDER BY id) FROM a WHERE 0 OR s IN (SELECT v FROM b);
SELECT 'WHERE s IN (subquery), rows:' AS q, GROUP_CONCAT(id ORDER BY id) FROM a WHERE s IN (SELECT v FROM b);
SELECT 'join, rows:' AS q, GROUP_CONCAT(a.id ORDER BY a.id) FROM a JOIN b ON a.s = b.v;
-- MariaDB only (MySQL has no such switch; the statement fails there and the client goes on with --force)
SET optimizer_switch = 'subquery_cache=off';
SELECT 'cache off' AS q, id, s, s IN (SELECT v FROM b) AS in_sub, (SELECT COUNT(*) FROM b WHERE b.v = a.s) AS n, EXISTS (SELECT 1 FROM b WHERE b.v = a.s) AS ex FROM a ORDER BY id;
SELECT 'cache off, WHERE 0 OR s IN (subquery), rows:' AS q, GROUP_CONCAT(id ORDER BY id) FROM a WHERE 0 OR s IN (SELECT v FROM b);
DROP DATABASE vs_sc;
