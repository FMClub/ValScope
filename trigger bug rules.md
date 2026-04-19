# ValScope: Mutation Rule Statistics and Bug Triggering Analysis
This document provides a detailed analysis of the mutation rules used in ValScope and their effectiveness in triggering confirmed logical bugs across different DBMSs.

Specifically, it includes:
(1) the full list of 26 mutation rules categorized by semantic type;
(2) the mapping between each confirmed bug and its corresponding triggering rule;
(3) aggregated statistics on how frequently each rule contributes to bug discovery.

This analysis complements the evaluation in the paper by offering a fine-grained view of the effectiveness and coverage of different mutation rules.

## Mutation Rule Index (rule1 ~ rule26)

Total number of operators: 26
Transforming C1 into C2 achieves the over-approximation; the inverse achieves the under-approximation.

| Rule ID | Category | C1 | C2 |
| ------ | -------- | -- | -- |
| rule1 | Set-Semantic / Relation | SELECT DISTINCT a FROM r | SELECT a FROM r |
| rule2 | Set-Semantic / Relation | r1 UNION r2 | r1 UNION ALL r2 |
| rule3 | Set-Semantic / Relation | A EXCEPT B | A |
| rule4 | Set-Semantic / Relation | A INTERSECT B | A UNION B |
| rule5 | Set-Semantic / Predicate | WHERE cond | WHERE TRUE |
| rule6 | Set-Semantic / Predicate | WHERE FALSE | WHERE cond |
| rule7 | Set-Semantic / Predicate | col LIKE '_abc%' | col LIKE '%abc%' |
| rule8 | Set-Semantic / Predicate | a < b | a <= b |
| rule9 | Set-Semantic / Predicate | a = b | a >= b |
| rule10 | Set-Semantic / Predicate | a > b | a >= b |
| rule11 | Set-Semantic / Predicate | a AND b AND c | a AND b |
| rule12 | Set-Semantic / Predicate | ON cond | ON TRUE |
| rule13 | Set-Semantic / Predicate | ON 1=0 | ON cond |
| rule14 | Set-Semantic / Predicate | REGEXP '^abc+$' | REGEXP 'abc*' |
| rule15 | Set-Semantic / Predicate | HAVING cond | HAVING 1=1 |
| rule16 | Set-Semantic / Predicate | HAVING 1=0 | HAVING cond |
| rule17 | Set-Semantic / Predicate | INNER JOIN | LEFT JOIN |
| rule18 | Value-Semantic / Aggregation | COUNT(DISTINCT c) | COUNT(c) |
| rule19 | Value-Semantic / Aggregation | AVG(c) | MAX(c) |
| rule20 | Value-Semantic / Aggregation | MIN(c) | MAX(c) |
| rule21 | Value-Semantic / Aggregation | VAR_SAMP(c) | STDDEV_SAMP(c) (c<1) |
| rule22 | Value-Semantic / Aggregation | STDDEV_SAMP(c) | VAR_SAMP(c) (c>1) |
| rule23 | Value-Semantic / Aggregation | SUM(c) | SUM(c*k) (k has the same sign as c) |
| rule24 | Value-Semantic / Expression | expr | expr + k (k>0) |
| rule25 | Value-Semantic / Expression | expr | expr * k (k has same sign as expr) |
| rule26 | Value-Semantic / Expression | FUNC(c) (FUNC is monotonic) | FUNC(c*k) (k > 0) |



## Bug Triggering Rules

### MySQL


| ID   | Issue ID | Status    | Rule (from mutation.md) |
| ---- | -------- | --------- | --------------------------- |
| 1 | [118846](https://bugs.mysql.com/bug.php?id=118846) | comfirmed | rule5 |
| 2 | [119022](https://bugs.mysql.com/bug.php?id=119022) | comfirmed | rule2 |
| 3 | [119348](https://bugs.mysql.com/bug.php?id=119348) | comfirmed | rule15 |
| 4 | [119321](https://bugs.mysql.com/bug.php?id=119321) | comfirmed | rule23 |
| 5 | [119322](https://bugs.mysql.com/bug.php?id=119322) | comfirmed | rule23 |
| 6 | [119323](https://bugs.mysql.com/bug.php?id=119323) | comfirmed | rule18 |
| 7 | [119329](https://bugs.mysql.com/bug.php?id=119329) | comfirmed | rule18 |
| 8 | [119342](https://bugs.mysql.com/bug.php?id=119342) | comfirmed | rule2 |
| 9 | [119344](https://bugs.mysql.com/bug.php?id=119344) | comfirmed | rule2 |
| 10 | [119350](https://bugs.mysql.com/bug.php?id=119350) | comfirmed | rule15 |
| 11 | [119446](https://bugs.mysql.com/bug.php?id=119446) | comfirmed | rule18 |
| 12 | [119352](https://bugs.mysql.com/bug.php?id=119352) | comfirmed | rule5 |
| 13 | [119353](https://bugs.mysql.com/bug.php?id=119353) | comfirmed | rule1 |
| 14 | [119398](https://bugs.mysql.com/bug.php?id=119398) | comfirmed | rule3 |
| 15 | [119399](https://bugs.mysql.com/bug.php?id=119399) | comfirmed | rule1 |
| 16 | [119400](https://bugs.mysql.com/bug.php?id=119400) | comfirmed | rule17 |
| 17 | [119402](https://bugs.mysql.com/bug.php?id=119402) | comfirmed | rule3 |
| 18 | [119403](https://bugs.mysql.com/bug.php?id=119403) | comfirmed | rule4 |
| 19 | [119693](https://bugs.mysql.com/bug.php?id=119693) | comfirmed | rule17 |
| 20 | [119694](https://bugs.mysql.com/bug.php?id=119694) | comfirmed | rule17 |
| 21 | [119695](https://bugs.mysql.com/bug.php?id=119695) | comfirmed | rule12 |
| 22 | [119696](https://bugs.mysql.com/bug.php?id=119696) | comfirmed | rule1 |
| 23 | [119698](https://bugs.mysql.com/bug.php?id=119698) | comfirmed | rule12 |

### MariaDB

| ID   | Issue ID | Status    | Rule (from mutation.md) |
| ---- | -------- | --------- | --------------------------- |
| 1 | [33026](https://jira.mariadb.org/browse/MDEV-33026) | comfirmed | rule1 |
| 2 | [33027](https://jira.mariadb.org/browse/MDEV-33027) | comfirmed | rule1 |
| 3 | [37888](https://jira.mariadb.org/browse/MDEV-37888) | comfirmed | rule19 |
| 4 | [37891](https://jira.mariadb.org/browse/MDEV-37891) | comfirmed | rule18 |
| 5 | [38032](https://jira.mariadb.org/browse/MDEV-38032) | comfirmed | rule18 |
| 6 | [38052](https://jira.mariadb.org/browse/MDEV-38052) | comfirmed | rule18 |
| 7 | [38063](https://jira.mariadb.org/browse/MDEV-38063) | comfirmed | rule1 |
| 8 | [38064](https://jira.mariadb.org/browse/MDEV-38064) | comfirmed | rule1 |
| 9 | [38102](https://jira.mariadb.org/browse/MDEV-38102) | comfirmed | rule12 |
| 10 | [38247](https://jira.mariadb.org/browse/MDEV-38247) | comfirmed | rule18 |

### OceanBase

| ID   | Issue ID | Status    | Rule (from mutation.md) |
| ---- | -------- | --------- | --------------------------- |
| 1 | [1752](https://github.com/oceanbase/oceanbase/issues/1752) | comfirmed | rule5 |
| 2 | [1753](https://github.com/oceanbase/oceanbase/issues/1753) | comfirmed | rule1 |
| 3 | [1755](https://github.com/oceanbase/oceanbase/issues/1755) | comfirmed | rule1 |
| 4 | [2326](https://github.com/oceanbase/oceanbase/issues/2326) | comfirmed | rule21 |
| 5 | [2339](https://github.com/oceanbase/oceanbase/issues/2339) | comfirmed | rule3 |
| 6 | [2341](https://github.com/oceanbase/oceanbase/issues/2341) | comfirmed | rule3 |

### PERCONA

| ID   | Issue ID | Status    | Rule (from mutation.md) |
| ---- | -------- | --------- | --------------------------- |
| 1 | [10277](https://perconadev.atlassian.net/browse/PS-10277) | comfirmed | rule18 |
| 2 | [10297](https://perconadev.atlassian.net/browse/PS-10297) | comfirmed | rule1 |
| 3 | [10298](https://perconadev.atlassian.net/browse/PS-10298) | comfirmed | rule1 |
| 4 | [10299](https://perconadev.atlassian.net/browse/PS-10299) | comfirmed | rule12 |
| 5 | [10301](https://perconadev.atlassian.net/browse/PS-10301) | comfirmed | rule1 |
| 6 | [10302](https://perconadev.atlassian.net/browse/PS-10302) | comfirmed | rule1 |
| 7 | [10303](https://perconadev.atlassian.net/browse/PS-10303) | comfirmed | rule12 |
| 8 | [10304](https://perconadev.atlassian.net/browse/PS-10304) | comfirmed | rule17 |
| 9 | [10305](https://perconadev.atlassian.net/browse/PS-10305) | comfirmed | rule17 |
| 10 | [10252](https://perconadev.atlassian.net/browse/PS-10252) | comfirmed | rule20 |

### PolarDB

| ID   | Issue ID | Status    | Rule (from mutation.md) |
| ---- | -------- | --------- | --------------------------- |
| 1 | [243](https://github.com/polardb/polardbx-sql/issues/243) | comfirmed | rule19 |
| 2 | [246](https://github.com/polardb/polardbx-sql/issues/246) | comfirmed | rule5 |
| 3 | [247](https://github.com/polardb/polardbx-sql/issues/247) | comfirmed | rule1 |
| 4 | [248](https://github.com/polardb/polardbx-sql/issues/248) | comfirmed | rule1 |
| 5 | [254](https://github.com/polardb/polardbx-sql/issues/254) | comfirmed | rule24 |
| 6 | [255](https://github.com/polardb/polardbx-sql/issues/255) | comfirmed | rule24 |
| 7 | [256](https://github.com/polardb/polardbx-sql/issues/256) | comfirmed | rule4 |

### TIDB

| ID   | Issue ID | Status    | Rule (from mutation.md) |
| ---- | -------- | --------- | --------------------------- |
| 1 | [63643](https://github.com/pingcap/tidb/issues/63643) | confirmed | rule19 |



## Frequency of Confirmed Logical Bugs Triggered by Each Mutation Rule

![](https://i.ibb.co/wFMC2QSp/6f1a7ba5d81b11d76a9d8bfe93fec7cc.png)

