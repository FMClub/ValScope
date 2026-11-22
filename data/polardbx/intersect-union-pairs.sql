-- PolarDB-X: the two INTERSECT->UNION pairs of the campaign with --tidb (seeds 1 and 3; pairs 2
-- and 3 of its triage), as reduced, with their parts.  expected: each mutant holds the rows of
-- its original (Up); the parts as named.
DROP DATABASE IF EXISTS vs_iu2; CREATE DATABASE vs_iu2; USE vs_iu2;
-- INTERSECT->UNION (Up): reduced on 5.6.29
CREATE TABLE `t1` (
	`c1` decimal(10, 2) DEFAULT NULL,
	`c4` int DEFAULT NULL
);
CREATE TABLE `t2` (
	`c1` decimal(10, 2) DEFAULT NULL,
	`c2` decimal(10, 2) DEFAULT NULL,
	`c3` int DEFAULT NULL,
	`c14` int DEFAULT NULL,
	`c15` bigint DEFAULT NULL
);
INSERT INTO `t2` VALUES (1.00, 4.00, 5, 1, 1);
INSERT INTO `t2` VALUES (7.00, 0.00, 0, 1, 1);
CREATE TABLE `t3` (
	`c1` decimal(10, 2) DEFAULT NULL,
	`c2` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
	`c3` int DEFAULT NULL,
	`c6` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
	`c7` int DEFAULT NULL,
	`c8` int DEFAULT NULL,
	`c9` int DEFAULT NULL
);
SELECT 'pair 2 original' AS q;
(SELECT t1b.c1 AS k0, t1b.c4 AS k1, t2c.c14 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1) INNER JOIN t2 AS t2c ON (1)) UNION ALL ((SELECT t1b.c1 AS k0, t1b.c1 AS k1, t3a.c8 AS k2 FROM t3 AS t3a LEFT JOIN t1 AS t1b ON (0)) INTERSECT (SELECT t2b.c1 AS k0, t1a.c1 AS k1, t3c.c1 AS k2 FROM t1 AS t1a LEFT JOIN t2 AS t2b ON (0) INNER JOIN t3 AS t3c ON (0)));
SELECT 'pair 2 mutant' AS q;
(SELECT t1b.c1 AS k0, t1b.c4 AS k1, t2c.c14 AS k2 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON (1) INNER JOIN t2 AS t2c ON (1)) UNION ALL ((SELECT t1b.c1 AS k0, t1b.c1 AS k1, t3a.c8 AS k2 FROM t3 AS t3a LEFT JOIN t1 AS t1b ON (0)) UNION (SELECT t2b.c1 AS k0, t1a.c1 AS k1, t3c.c1 AS k2 FROM t1 AS t1a LEFT JOIN t2 AS t2b ON (0) INNER JOIN t3 AS t3c ON (0)));
USE information_schema; DROP DATABASE vs_iu2;
DROP DATABASE IF EXISTS vs_iu3; CREATE DATABASE vs_iu3; USE vs_iu3;
-- INTERSECT->UNION (Up): reduced on 5.6.29
CREATE TABLE `t1` (
	`c1` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
	`c4` decimal(10, 2) DEFAULT NULL
);
INSERT INTO `t1` VALUES ('5', NULL);
CREATE TABLE `t2` (
	`c1` decimal(10, 2) DEFAULT NULL,
	`c2` int DEFAULT NULL,
	`c3` int DEFAULT NULL,
	`c14` int DEFAULT NULL,
	`c15` decimal(10, 2) DEFAULT NULL,
	`rid` int NOT NULL,
	PRIMARY KEY (`rid`)
);
INSERT INTO `t2` VALUES (2.50, NULL, 5, 3, 10.75, 3);
CREATE TABLE `t3` (
	`c1` int DEFAULT NULL,
	`c2` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
	`c3` date DEFAULT NULL,
	`c6` decimal(10, 2) DEFAULT NULL,
	`c7` int DEFAULT NULL,
	`c8` int DEFAULT NULL,
	`c9` int DEFAULT NULL
);
INSERT INTO `t3` VALUES (NULL, 'A', '2024-12-01', NULL, -1, NULL, 5);
SELECT 'pair 3 original' AS q;
((SELECT t1a.c1 AS k0 FROM t1 AS t1a) INTERSECT (SELECT t3a.c9 AS k0 FROM t3 AS t3a)) UNION ALL ((SELECT t1a.c4 AS k0 FROM t1 AS t1a) UNION (SELECT t2a.c3 AS k0 FROM t2 AS t2a));
SELECT 'pair 3 mutant' AS q;
((SELECT t1a.c1 AS k0 FROM t1 AS t1a) UNION (SELECT t3a.c9 AS k0 FROM t3 AS t3a)) UNION ALL ((SELECT t1a.c4 AS k0 FROM t1 AS t1a) UNION (SELECT t2a.c3 AS k0 FROM t2 AS t2a));
SELECT 'pair 3 part: t1.c1 INTERSECT t3.c9 (one row 5)' AS q;
(SELECT t1a.c1 AS k0 FROM t1 AS t1a) INTERSECT (SELECT t3a.c9 AS k0 FROM t3 AS t3a);
SELECT 'pair 3 part: t1.c1 UNION t3.c9 (one row 5)' AS q;
(SELECT t1a.c1 AS k0 FROM t1 AS t1a) UNION (SELECT t3a.c9 AS k0 FROM t3 AS t3a);
SELECT 'pair 3 part: t1.c4 UNION t2.c3 (NULL, 5)' AS q;
(SELECT t1a.c4 AS k0 FROM t1 AS t1a) UNION (SELECT t2a.c3 AS k0 FROM t2 AS t2a);
USE information_schema; DROP DATABASE vs_iu3;
