-- What a server reports as the collation of a result column, and what DISTINCT keeps, for a
-- utf8mb4_general_ci column holding 'a', 'A' and 'a '.  Run with column_info = yes.
-- bridge/run_on_db.py sets character_set_results = NULL and reads the collation of every
-- column from its metadata; a server that reports binary or utf8mb4_bin for a _ci column
-- makes the checker compare 'a' and 'A' as different strings.
-- expected: one row from each DISTINCT (MySQL, MariaDB and TiDB with the new collations)
DROP DATABASE IF EXISTS vs_rc; CREATE DATABASE vs_rc; USE vs_rc;
CREATE TABLE t (c VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci, b VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin);
INSERT INTO t VALUES ('a', 'a'), ('A', 'A'), ('a ', 'a ');
SELECT @@character_set_results, @@collation_connection;
SELECT 'distinct ci' AS q, COUNT(*) FROM (SELECT DISTINCT c FROM t) AS d;
SELECT 'distinct bin' AS q, COUNT(*) FROM (SELECT DISTINCT b FROM t) AS d;
SELECT COLLATION(c), COLLATION(b) FROM t LIMIT 1;
SET character_set_results = NULL;
SELECT c, b FROM t LIMIT 1;
SELECT DISTINCT c FROM t;
