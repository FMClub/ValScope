-- The INTERSECT->UNION pairs of seeds 7 and 8 on TiDB v8.5.3 (round 18): the rows of the original and of the
-- mutant (Up: every row of the original must be in the mutant), with the hex of k0.
DROP DATABASE IF EXISTS vs_i7; CREATE DATABASE vs_i7; USE vs_i7;
CREATE TABLE `t1` (
  `c1` decimal(10,2) DEFAULT NULL,
  `c4` decimal(10,2) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
INSERT INTO `t1` VALUES (7.50, 0.00);
CREATE TABLE `t2` (
  `c1` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `c2` date DEFAULT NULL,
  `c3` double DEFAULT NULL,
  `c14` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `c15` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
INSERT INTO `t2` VALUES ('a ', '2024-01-01', 0.0e0, '-1', NULL);
CREATE TABLE `t3` (
  `c1` double DEFAULT NULL,
  `c2` date DEFAULT NULL,
  `c3` int DEFAULT NULL,
  `c6` varchar(20) DEFAULT NULL,
  `c7` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `c8` int DEFAULT NULL,
  `c9` bigint DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
INSERT INTO `t3` VALUES (2.5e0, '2024-01-01', 10, '0', '01', 2, 2);
SELECT 'pair 2 original' AS q, HEX(k0), k0 FROM ((SELECT t3a.c6 AS k0 FROM t3 AS t3a) UNION ((SELECT t1b.c4 AS k0 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (1)) INTERSECT (SELECT t2a.c3 AS k0 FROM t2 AS t2a))) AS r;
SELECT 'pair 2 mutant' AS q, HEX(k0), k0 FROM ((SELECT t3a.c6 AS k0 FROM t3 AS t3a) UNION ((SELECT t1b.c4 AS k0 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (1)) UNION (SELECT t2a.c3 AS k0 FROM t2 AS t2a))) AS r;
SELECT 'pair 2 original, bare' AS q;
(SELECT t3a.c6 AS k0 FROM t3 AS t3a) UNION ((SELECT t1b.c4 AS k0 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (1)) INTERSECT (SELECT t2a.c3 AS k0 FROM t2 AS t2a));
SELECT 'pair 2 mutant, bare' AS q;
(SELECT t3a.c6 AS k0 FROM t3 AS t3a) UNION ((SELECT t1b.c4 AS k0 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (1)) UNION (SELECT t2a.c3 AS k0 FROM t2 AS t2a));
DROP DATABASE vs_i7;
DROP DATABASE IF EXISTS vs_i8; CREATE DATABASE vs_i8; USE vs_i8;
CREATE TABLE `t2` (
  `c1` bigint DEFAULT NULL,
  `c2` int DEFAULT NULL,
  `c3` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL,
  `c14` bigint DEFAULT NULL,
  `c15` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
INSERT INTO `t2` VALUES (NULL, -3, '', 2, '2');
CREATE TABLE `t3` (
  `c1` int DEFAULT NULL,
  `c2` double DEFAULT NULL,
  `c3` bigint DEFAULT NULL,
  `c6` date DEFAULT NULL,
  `c7` int DEFAULT NULL,
  `c8` double DEFAULT NULL,
  `c9` int DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
INSERT INTO `t3` VALUES (NULL, 10.5e0, 2, '2024-12-28', NULL, 1.0e0, NULL);
INSERT INTO `t3` VALUES (7, -0.5e0, 4, NULL, 4, 7.5e0, 0);
SELECT 'pair 3 original' AS q, HEX(k0), k0 FROM ((SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c1 IS NULL) INTERSECT ((SELECT t3a.c6 AS k0 FROM t3 AS t3a) INTERSECT (SELECT t3a.c7 AS k0 FROM t3 AS t3a))) AS r;
SELECT 'pair 3 mutant' AS q, HEX(k0), k0 FROM ((SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c1 IS NULL) INTERSECT ((SELECT t3a.c6 AS k0 FROM t3 AS t3a) UNION (SELECT t3a.c7 AS k0 FROM t3 AS t3a))) AS r;
SELECT 'pair 3 original, bare' AS q;
(SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c1 IS NULL) INTERSECT ((SELECT t3a.c6 AS k0 FROM t3 AS t3a) INTERSECT (SELECT t3a.c7 AS k0 FROM t3 AS t3a));
SELECT 'pair 3 mutant, bare' AS q;
(SELECT t2a.c15 AS k0 FROM t2 AS t2a WHERE t2a.c1 IS NULL) INTERSECT ((SELECT t3a.c6 AS k0 FROM t3 AS t3a) UNION (SELECT t3a.c7 AS k0 FROM t3 AS t3a));
DROP DATABASE vs_i8;
SELECT 'end' AS q;
