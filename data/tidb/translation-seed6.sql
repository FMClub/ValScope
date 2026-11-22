-- The TRANSLATION pair of seed 6 on TiDB v8.5.3 (round 18): the query as written (NOT IN) and as
-- re-printed by the bridge (NOT (... IN ...)).  The rows of both, with their count and the hex of k0.
DROP DATABASE IF EXISTS vs_t6; CREATE DATABASE vs_t6; USE vs_t6;
CREATE TABLE `t1` (
  `c1` decimal(10,2) DEFAULT NULL,
  `c4` varchar(20) COLLATE utf8mb4_general_ci DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE `t2` (
  `c1` double DEFAULT NULL,
  `c2` varchar(20) DEFAULT NULL,
  `c3` int DEFAULT NULL,
  `c14` varchar(20) DEFAULT NULL,
  `c15` date DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
CREATE TABLE `t3` (
  `c1` decimal(10,2) DEFAULT NULL,
  `c2` double DEFAULT NULL,
  `c3` varchar(20) DEFAULT NULL,
  `c6` decimal(10,2) DEFAULT NULL,
  `c7` int DEFAULT NULL,
  `c8` date DEFAULT NULL,
  `c9` double DEFAULT NULL,
  `rid` int NOT NULL,
  PRIMARY KEY (`rid`) /*T![clustered_index] CLUSTERED */
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
INSERT INTO `t3` VALUES (NULL, NULL, '5', NULL, 4, NULL, 0.0e0, 9);
SELECT 'written' AS q;
((SELECT t2a.c1 AS k0 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON t1b.c1 <> t1b.c4 INNER JOIN t3 AS t3c ON t1b.c1 < t1b.c1) UNION ALL (SELECT t3a.c9 AS k0 FROM t3 AS t3a WHERE t3a.c3 NOT IN (SELECT t2i26.c1 FROM t2 AS t2i26 WHERE (t2i26.c2 = -1 AND t3a.c6 > 0)))) UNION ALL ((SELECT t1a.c4 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1a.c4 = 3 WHERE t1b.c4 IN (SELECT t2i75.c2 FROM t2 AS t2i75 WHERE (t2i75.c14 = t2i75.c2 AND t1a.c1 = 2))) INTERSECT (SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON t3a.c7 >= -1 WHERE t3a.c1 >= 10));
SELECT 'written, count and hex' AS q, COUNT(*), GROUP_CONCAT(HEX(k0)) FROM (((SELECT t2a.c1 AS k0 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON t1b.c1 <> t1b.c4 INNER JOIN t3 AS t3c ON t1b.c1 < t1b.c1) UNION ALL (SELECT t3a.c9 AS k0 FROM t3 AS t3a WHERE t3a.c3 NOT IN (SELECT t2i26.c1 FROM t2 AS t2i26 WHERE (t2i26.c2 = -1 AND t3a.c6 > 0)))) UNION ALL ((SELECT t1a.c4 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1a.c4 = 3 WHERE t1b.c4 IN (SELECT t2i75.c2 FROM t2 AS t2i75 WHERE (t2i75.c14 = t2i75.c2 AND t1a.c1 = 2))) INTERSECT (SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON t3a.c7 >= -1 WHERE t3a.c1 >= 10))) AS r;
SELECT 'reprinted' AS q;
((SELECT t2a.c1 AS k0 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON t1b.c1 <> t1b.c4 INNER JOIN t3 AS t3c ON t1b.c1 < t1b.c1) UNION ALL (SELECT t3a.c9 AS k0 FROM t3 AS t3a WHERE NOT (t3a.c3 IN (SELECT t2i26.c1 FROM t2 AS t2i26 WHERE (t2i26.c2 = (-1)) AND (t3a.c6 > 0))))) UNION ALL ((SELECT t1a.c4 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1a.c4 = 3 WHERE t1b.c4 IN (SELECT t2i75.c2 FROM t2 AS t2i75 WHERE (t2i75.c14 = t2i75.c2) AND (t1a.c1 = 2))) INTERSECT (SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON t3a.c7 >= (-1) WHERE t3a.c1 >= 10));
SELECT 'reprinted, count and hex' AS q, COUNT(*), GROUP_CONCAT(HEX(k0)) FROM (((SELECT t2a.c1 AS k0 FROM t2 AS t2a LEFT JOIN t1 AS t1b ON t1b.c1 <> t1b.c4 INNER JOIN t3 AS t3c ON t1b.c1 < t1b.c1) UNION ALL (SELECT t3a.c9 AS k0 FROM t3 AS t3a WHERE NOT (t3a.c3 IN (SELECT t2i26.c1 FROM t2 AS t2i26 WHERE (t2i26.c2 = (-1)) AND (t3a.c6 > 0))))) UNION ALL ((SELECT t1a.c4 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1a.c4 = 3 WHERE t1b.c4 IN (SELECT t2i75.c2 FROM t2 AS t2i75 WHERE (t2i75.c14 = t2i75.c2) AND (t1a.c1 = 2))) INTERSECT (SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON t3a.c7 >= (-1) WHERE t3a.c1 >= 10))) AS r;
SELECT 'the middle arm, NOT IN' AS q, t3a.c9 FROM t3 AS t3a WHERE t3a.c3 NOT IN (SELECT t2i26.c1 FROM t2 AS t2i26 WHERE (t2i26.c2 = -1 AND t3a.c6 > 0));
SELECT 'the middle arm, NOT (IN)' AS q, t3a.c9 FROM t3 AS t3a WHERE NOT (t3a.c3 IN (SELECT t2i26.c1 FROM t2 AS t2i26 WHERE (t2i26.c2 = -1) AND (t3a.c6 > 0)));
SELECT 'end' AS q;
DROP DATABASE vs_t6;
