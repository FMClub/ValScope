-- Variants of the MySQL 8.4 BIT(8) inconsistency of issues/005 (section MySQL): the same
-- MIN of a BIT column, as decimal text or as the bit value, depending on the query.
DROP DATABASE IF EXISTS vs_bit3; CREATE DATABASE vs_bit3; USE vs_bit3;
CREATE TABLE b (x BIT(8), k INT);
INSERT INTO b VALUES (14, 1), (19, 2);
CREATE TABLE s (v VARCHAR(10));
INSERT INTO s VALUES ('a');
SELECT 'A: MIN in EXCEPT', HEX(m) FROM (SELECT MIN(x) AS m FROM b EXCEPT SELECT v FROM s) u;
SELECT 'B: MIN through DISTINCT derived, EXCEPT', HEX(m) FROM (SELECT DISTINCT * FROM (SELECT MIN(x) AS m FROM b) d EXCEPT SELECT v FROM s) u;
SELECT 'C: MIN in UNION ALL', HEX(m) FROM (SELECT MIN(x) AS m FROM b UNION ALL SELECT v FROM s) u;
SELECT 'D: MIN through derived, UNION ALL', HEX(m) FROM (SELECT * FROM (SELECT MIN(x) AS m FROM b) d UNION ALL SELECT v FROM s) u;
SELECT 'E: column in UNION ALL', HEX(m) FROM (SELECT x AS m FROM b WHERE k = 1 UNION ALL SELECT v FROM s) u;
SELECT 'F: MIN with GROUP BY in UNION ALL', HEX(m) FROM (SELECT MIN(x) AS m FROM b GROUP BY k HAVING k = 1 UNION ALL SELECT v FROM s) u;
DROP DATABASE vs_bit3;
