-- OceanBase CE 4.4: the three reduced UNION pairs of the campaign on seeds 1-40 (pairs 1, 2, 6 of
-- its triage; seeds 8, 12, 16), as printed by reduce_mysql.py, with the table options removed.
-- Each: the original, the mutant, the arms alone.
DROP DATABASE IF EXISTS vs_obu1; CREATE DATABASE vs_obu1; USE vs_obu1;
-- pair: UNION->UNION-ALL (Up): reduced on 5.7.25
CREATE TABLE `t1` (
  `c1` int(11) DEFAULT NULL,
  `c4` int(11) DEFAULT NULL
);
CREATE TABLE `t2` (
  `c1` bigint(20) DEFAULT NULL,
  `c2` int(11) DEFAULT NULL,
  `c3` varchar(20) DEFAULT NULL,
  `c14` bigint(20) DEFAULT NULL,
  `c15` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL
);
INSERT INTO `t2` VALUES (2, 2, 'a', NULL, '1');
INSERT INTO `t2` VALUES (2, 10, 'A', 0, 'B');
SELECT 'pair 1 original' AS q;
(SELECT t2a.c3 AS k0, t2a.c15 AS k1, t2a.c3 AS k2 FROM t2 AS t2a) UNION ((SELECT t2a.c3 AS k0, t2a.c3 AS k1, t2a.c1 AS k2 FROM t2 AS t2a) UNION (SELECT t1b.c4 AS k0, t1c.c4 AS k1, t1c.c1 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON NOT ((0)) INNER JOIN t1 AS t1c ON NOT ((0))));
SELECT 'pair 1 mutant' AS q;
(SELECT t2a.c3 AS k0, t2a.c15 AS k1, t2a.c3 AS k2 FROM t2 AS t2a) UNION ALL ((SELECT t2a.c3 AS k0, t2a.c3 AS k1, t2a.c1 AS k2 FROM t2 AS t2a) UNION (SELECT t1b.c4 AS k0, t1c.c4 AS k1, t1c.c1 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON NOT ((0)) INNER JOIN t1 AS t1c ON NOT ((0))));
USE information_schema; DROP DATABASE vs_obu1;
DROP DATABASE IF EXISTS vs_obu2; CREATE DATABASE vs_obu2; USE vs_obu2;
-- pair: UNION-ALL->UNION (Down): reduced on 5.7.25
CREATE TABLE `t2` (
  `c1` decimal(10,2) DEFAULT NULL,
  `c2` bigint(20) DEFAULT NULL,
  `c3` varchar(20) DEFAULT NULL,
  `c14` varchar(20) DEFAULT NULL,
  `c15` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `rid` int(11) NOT NULL,
  PRIMARY KEY (`rid`)
);
INSERT INTO `t2` VALUES (10.75, -3, 'A', NULL, '', 3);
INSERT INTO `t2` VALUES (NULL, 5, '', 'a ', 'a ', 9);
CREATE TABLE `t3` (
  `c1` int(11) DEFAULT NULL,
  `c2` decimal(10,2) DEFAULT NULL,
  `c3` int(11) DEFAULT NULL,
  `c6` int(11) DEFAULT NULL,
  `c7` varchar(20) DEFAULT NULL,
  `c8` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `c9` varchar(20) DEFAULT NULL
);
SELECT 'pair 2 original' AS q;
(SELECT t3a.c8 AS k0 FROM t3 AS t3a WHERE (0)) UNION ALL ((SELECT t2a.c14 AS k0 FROM t2 AS t2a) UNION (SELECT t2a.c3 AS k0 FROM t2 AS t2a));
SELECT 'pair 2 mutant' AS q;
(SELECT t3a.c8 AS k0 FROM t3 AS t3a WHERE (0)) UNION ((SELECT t2a.c14 AS k0 FROM t2 AS t2a) UNION (SELECT t2a.c3 AS k0 FROM t2 AS t2a));
USE information_schema; DROP DATABASE vs_obu2;
DROP DATABASE IF EXISTS vs_obu6; CREATE DATABASE vs_obu6; USE vs_obu6;
-- pair: UNION->UNION-ALL (Up): reduced on 5.7.25
CREATE TABLE `t1` (
  `c1` varchar(20) DEFAULT NULL,
  `c4` decimal(10,2) DEFAULT NULL
);
INSERT INTO `t1` VALUES ('B', 1.00);
INSERT INTO `t1` VALUES ('b', 2.00);
CREATE TABLE `t2` (
  `c1` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `c2` decimal(10,2) DEFAULT NULL,
  `c3` decimal(10,2) DEFAULT NULL,
  `c14` varchar(20) DEFAULT NULL,
  `c15` decimal(10,2) DEFAULT NULL
);
CREATE TABLE `t3` (
  `c1` decimal(10,2) DEFAULT NULL,
  `c2` date DEFAULT NULL,
  `c3` bigint(20) DEFAULT NULL,
  `c6` varchar(20) DEFAULT NULL,
  `c7` bigint(20) DEFAULT NULL,
  `c8` int(11) DEFAULT NULL,
  `c9` decimal(10,2) DEFAULT NULL
);
SELECT 'pair 6 original' AS q;
(SELECT t2a.c1 AS k0, t2a.c2 AS k1 FROM t2 AS t2a) UNION ((SELECT t1a.c1 AS k0, t1a.c1 AS k1 FROM t1 AS t1a) UNION (SELECT t3a.c6 AS k0, t3a.c2 AS k1 FROM t3 AS t3a));
SELECT 'pair 6 mutant' AS q;
(SELECT t2a.c1 AS k0, t2a.c2 AS k1 FROM t2 AS t2a) UNION ALL ((SELECT t1a.c1 AS k0, t1a.c1 AS k1 FROM t1 AS t1a) UNION (SELECT t3a.c6 AS k0, t3a.c2 AS k1 FROM t3 AS t3a));
USE information_schema; DROP DATABASE vs_obu6;
