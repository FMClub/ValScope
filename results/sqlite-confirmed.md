# SQLite violations found by the verified mutators

44 recorded, 44 confirmed (reproduced on the reporting version, relation holds on SQLite 3.53.1).

| # | Reported on | Seed | Rule | Expected | Rows (original / mutant) | Violated on | Confirmed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3.26.0 | 1004 | `UNION->UNION-ALL` | Up | 35 / 35 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 2 | 3.26.0 | 1004 | `UNION-ALL->UNION` | Down | 34 / 36 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 3 | 3.26.0 | 1005 | `UNION-ALL->UNION` | Down | 5 / 6 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 4 | 3.26.0 | 1005 | `UNION-ALL->UNION` | Down | 5 / 6 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 5 | 3.26.0 | 1005 | `UNION->UNION-ALL` | Up | 129 / 117 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 6 | 3.26.0 | 1008 | `UNION-ALL->UNION` | Down | 4 / 5 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 7 | 3.26.0 | 1008 | `UNION-ALL->UNION` | Down | 4 / 5 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 8 | 3.26.0 | 1008 | `UNION->UNION-ALL` | Up | 20 / 16 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 9 | 3.26.0 | 1014 | `UNION->UNION-ALL` | Up | 35 / 28 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 10 | 3.26.0 | 1021 | `UNION->UNION-ALL` | Up | 10 / 9 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 11 | 3.26.0 | 1023 | `UNION->UNION-ALL` | Up | 9 / 8 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 12 | 3.26.0 | 1156 | `UNION->UNION-ALL` | Up | 10 / 9 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 13 | 3.26.0 | 1156 | `UNION-ALL->UNION` | Down | 8 / 9 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 14 | 3.26.0 | 1157 | `UNION->UNION-ALL` | Up | 13 / 12 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 15 | 3.26.0 | 1162 | `UNION->UNION-ALL` | Up | 20 / 16 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 16 | 3.26.0 | 1163 | `UNION->UNION-ALL` | Up | 8 / 7 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 17 | 3.26.0 | 1166 | `UNION->UNION-ALL` | Up | 22 / 20 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 18 | 3.26.0 | 1166 | `UNION->UNION-ALL` | Up | 9 / 8 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 19 | 3.26.0 | 1166 | `UNION->UNION-ALL` | Up | 81 / 72 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 20 | 3.26.0 | 1167 | `UNION->UNION-ALL` | Up | 12 / 13 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 21 | 3.26.0 | 1173 | `UNION->UNION-ALL` | Up | 13 / 13 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 22 | 3.26.0 | 1173 | `UNION->UNION-ALL` | Up | 58 / 52 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 23 | 3.26.0 | 1178 | `EXCEPT->left` | Up | 20 / 19 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 24 | 3.26.0 | 1178 | `UNION->UNION-ALL` | Up | 39 / 34 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 25 | 3.26.0 | 240 | `UNION->UNION-ALL` | Up | 9 / 8 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 26 | 3.31.1 | 292 | `cond->TRUE` | Up | 19 / 14 | 3.31.1 | yes |
| 27 | 3.34.0 | 663 | `cond->TRUE` | Up | 6 / 1 | 3.34.0 | yes |
| 28 | 3.34.0 | 1 | `DISTINCT-add` | Down | 1 / 3 | 3.34.0 | yes |
| 29 | 3.31.1 | 11 | `LEFT->INNER-JOIN` | Down | 0 / 16 | 3.31.1 | yes |
| 30 | 3.26.0 | 22 | `EXCEPT->left` | Up | 10 / 9 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 31 | 3.26.0 | 194 | `UNION-ALL->UNION` | Down | 40 / 45 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 32 | 3.26.0 | 237 | `DISTINCT-add` | Down | 40 / 50 | 3.26.0 | yes |
| 33 | 3.26.0 | 336 | `DISTINCT-add` | Down | 78 / 6 | 3.26.0 | yes |
| 34 | 3.26.0 | 336 | `DISTINCT-add` | Down | 78 / 90 | 3.26.0 | yes |
| 35 | 3.26.0 | 340 | `UNION-ALL->UNION` | Down | 7 / 8 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 36 | 3.26.0 | 352 | `UNION-ALL->UNION` | Down | 409 / 10 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 37 | 3.26.0 | 515 | `UNION->UNION-ALL` | Up | 14 / 13 | 3.26.0 | yes |
| 38 | 3.26.0 | 2004 | `DISTINCT-add` | Down | 15 / 16 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 39 | 3.26.0 | 2011 | `UNION->UNION-ALL` | Up | 81 / 72 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 40 | 3.26.0 | 2011 | `INTERSECT->operand` | Up | 81 / 73 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 41 | 3.26.0 | 2022 | `DISTINCT-add` | Down | 0 / 1 | 3.26.0 | yes |
| 42 | 3.26.0 | 2022 | `EXCEPT->left` | Up | 11 / 43 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 43 | 3.26.0 | 2009 | `INNER->LEFT-JOIN` | Up | 2 / 2 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |
| 44 | 3.26.0 | 2009 | `cond->TRUE` | Up | 2 / 2 | 3.26.0, 3.30.1, 3.31.1, 3.34.0 | yes |

## 1. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1004)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2b.c2 AS k0, t2b.c3 AS k1 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON NOT (t2b.c15 <= 0) UNION ALL SELECT DISTINCT t1a.c1 AS k0, t1a.c1 AS k1 FROM t1 AS t1a INNER JOIN t3 AS t3b ON t3b.c6 >= 1 WHERE NOT (t1a.c4 = 10) UNION SELECT DISTINCT t1a.c4 AS k0, t3b.c2 AS k1 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (t3b.c1 > 1) OR (t3b.c7 >= (-1)) WHERE t3b.c9 > 1;
-- mutant
SELECT DISTINCT t2b.c2 AS k0, t2b.c3 AS k1 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON NOT (t2b.c15 <= 0) UNION ALL SELECT DISTINCT t1a.c1 AS k0, t1a.c1 AS k1 FROM t1 AS t1a INNER JOIN t3 AS t3b ON t3b.c6 >= 1 WHERE NOT (t1a.c4 = 10) UNION ALL SELECT DISTINCT t1a.c4 AS k0, t3b.c2 AS k1 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (t3b.c1 > 1) OR (t3b.c7 >= (-1)) WHERE t3b.c9 > 1;
```

Original rows: `["(' 1', ' 1')", "('', '')", "('-3', '-3')", "('01', '01')", "('1', 2)", "('1', 3)", "('1', 7)", "('2', 2)", "('2', 3)", "('2', 7)", "('7', 2)", "('7', 3)"]`

Mutant rows: `["(' 1', ' 1')", "('', '')", "('-3', '-3')", "('01', '01')", "('1', 2)", "('1', 3)", "('1', 7)", "('2', 2)", "('2', 3)", "('2', 7)", "('7', 2)", "('7', 3)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 2. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 1004)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT DISTINCT t3b.c7 AS k0, t2a.c15 AS k1, t3b.c1 AS k2 FROM t2 AS t2a LEFT JOIN t3 AS t3b ON t3b.c1 < t3b.c6 WHERE t2a.c3 < 7 UNION SELECT DISTINCT t1a.c1 AS k0, t1a.c1 AS k1, t1a.c1 AS k2 FROM t1 AS t1a WHERE t1a.c1 IN (SELECT t3i8.c2 FROM t3 AS t3i8 WHERE t3i8.c1 <= t1a.c4) UNION ALL SELECT DISTINCT t1b.c1 AS k0, t1b.c1 AS k1, t1a.c1 AS k2 FROM t1 AS t1a INNER JOIN t1 AS t1b ON NOT (t1a.c1 IN (SELECT t3i30.c7 FROM t3 AS t3i30 WHERE t1b.c4 <> 0));
-- mutant
SELECT DISTINCT t3b.c7 AS k0, t2a.c15 AS k1, t3b.c1 AS k2 FROM t2 AS t2a LEFT JOIN t3 AS t3b ON t3b.c1 < t3b.c6 WHERE t2a.c3 < 7 UNION SELECT DISTINCT t1a.c1 AS k0, t1a.c1 AS k1, t1a.c1 AS k2 FROM t1 AS t1a WHERE t1a.c1 IN (SELECT t3i8.c2 FROM t3 AS t3i8 WHERE t3i8.c1 <= t1a.c4) UNION SELECT DISTINCT t1b.c1 AS k0, t1b.c1 AS k1, t1a.c1 AS k2 FROM t1 AS t1a INNER JOIN t1 AS t1b ON NOT (t1a.c1 IN (SELECT t3i30.c7 FROM t3 AS t3i30 WHERE t1b.c4 <> 0));
```

Original rows: `["('', '', ' 1')", "('', '', '')", "('', '', '-3')", "('', '', '01')", "('', '', 'B')", "('', '', 'a')", "('', '', None)", "(0, '1', '1')", "(0, '3', '1')", "(0, -1, '1')", "(0, 3, '1')", "(0, None, '1')"]`

Mutant rows: `["('', '', ' 1')", "('', '', '')", "('', '', '-3')", "('', '', '01')", "('', '', 'A')", "('', '', 'B')", "('', '', 'a')", "('', '', None)", "(0, '1', '1')", "(0, '3', '1')", "(0, -1, '1')", "(0, 3, '1')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 3. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 1005)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT DISTINCT t3a.c9 AS k0, t1b.c1 AS k1, t1b.c1 AS k2 FROM t3 AS t3a INNER JOIN t1 AS t1b ON NOT (t3a.c8 IS NULL) WHERE ((t1b.c4 = t1b.c1) AND (t1b.c1 <= (-1))) AND (t1b.c1 < 1) UNION ALL SELECT DISTINCT t2a.c2 AS k0, t1b.c1 AS k1, t1b.c1 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (t1b.c4 = 7) OR (t2a.c2 = 7) WHERE NOT (EXISTS (SELECT t2s1.c1 FROM t2 AS t2s1 WHERE t2s1.c3 = 5)) UNION ALL SELECT t1b.c4 AS k0, t1a.c1 AS k1, t1a.c1 AS k2 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (t1a.c1 < 3) AND (t1a.c1 < t1a.c1) WHERE ((t1a.c4 IS NULL) OR (t1b.c4 = 3)) AND (t1a.c4 IS NULL);
-- mutant
SELECT DISTINCT t3a.c9 AS k0, t1b.c1 AS k1, t1b.c1 AS k2 FROM t3 AS t3a INNER JOIN t1 AS t1b ON NOT (t3a.c8 IS NULL) WHERE ((t1b.c4 = t1b.c1) AND (t1b.c1 <= (-1))) AND (t1b.c1 < 1) UNION ALL SELECT DISTINCT t2a.c2 AS k0, t1b.c1 AS k1, t1b.c1 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (t1b.c4 = 7) OR (t2a.c2 = 7) WHERE NOT (EXISTS (SELECT t2s1.c1 FROM t2 AS t2s1 WHERE t2s1.c3 = 5)) UNION SELECT t1b.c4 AS k0, t1a.c1 AS k1, t1a.c1 AS k2 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (t1a.c1 < 3) AND (t1a.c1 < t1a.c1) WHERE ((t1a.c4 IS NULL) OR (t1b.c4 = 3)) AND (t1a.c4 IS NULL);
```

Original rows: `["(' 1', '3', '3')", "('', '3', '3')", "('-1', '3', '3')", "('2', '3', '3')", "('a', '3', '3')"]`

Mutant rows: `["(' 1', '3', '3')", "('', '3', '3')", "('-1', '3', '3')", "('2', '3', '3')", "('A', '3', '3')", "('a', '3', '3')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 4. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 1005)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT DISTINCT t3a.c9 AS k0, t1b.c1 AS k1, t1b.c1 AS k2 FROM t3 AS t3a INNER JOIN t1 AS t1b ON NOT (t3a.c8 IS NULL) WHERE ((t1b.c4 = t1b.c1) AND (t1b.c1 <= (-1))) AND (t1b.c1 < 1) UNION ALL SELECT DISTINCT t2a.c2 AS k0, t1b.c1 AS k1, t1b.c1 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (t1b.c4 = 7) OR (t2a.c2 = 7) WHERE NOT (EXISTS (SELECT t2s1.c1 FROM t2 AS t2s1 WHERE t2s1.c3 = 5)) UNION ALL SELECT t1b.c4 AS k0, t1a.c1 AS k1, t1a.c1 AS k2 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (t1a.c1 < 3) AND (t1a.c1 < t1a.c1) WHERE ((t1a.c4 IS NULL) OR (t1b.c4 = 3)) AND (t1a.c4 IS NULL);
-- mutant
SELECT DISTINCT t3a.c9 AS k0, t1b.c1 AS k1, t1b.c1 AS k2 FROM t3 AS t3a INNER JOIN t1 AS t1b ON NOT (t3a.c8 IS NULL) WHERE ((t1b.c4 = t1b.c1) AND (t1b.c1 <= (-1))) AND (t1b.c1 < 1) UNION SELECT DISTINCT t2a.c2 AS k0, t1b.c1 AS k1, t1b.c1 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (t1b.c4 = 7) OR (t2a.c2 = 7) WHERE NOT (EXISTS (SELECT t2s1.c1 FROM t2 AS t2s1 WHERE t2s1.c3 = 5)) UNION ALL SELECT t1b.c4 AS k0, t1a.c1 AS k1, t1a.c1 AS k2 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (t1a.c1 < 3) AND (t1a.c1 < t1a.c1) WHERE ((t1a.c4 IS NULL) OR (t1b.c4 = 3)) AND (t1a.c4 IS NULL);
```

Original rows: `["(' 1', '3', '3')", "('', '3', '3')", "('-1', '3', '3')", "('2', '3', '3')", "('a', '3', '3')"]`

Mutant rows: `["(' 1', '3', '3')", "('', '3', '3')", "('-1', '3', '3')", "('2', '3', '3')", "('A', '3', '3')", "('a', '3', '3')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 5. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1005)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2b.c1 AS k0, t3c.c7 AS k1, t2b.c14 AS k2 FROM t1 AS t1a LEFT JOIN t2 AS t2b ON NOT (EXISTS (SELECT t3s9.c1 FROM t3 AS t3s9 WHERE t1a.c4 = t3s9.c7)) INNER JOIN t3 AS t3c ON (t2b.c14 IS NULL) OR (t2b.c1 >= t2b.c15) WHERE (NOT (t1a.c1 = 5)) AND (t2b.c2 IN (SELECT t1i94.c4 FROM t1 AS t1i94 WHERE t3c.c3 <> t3c.c7)) UNION ALL SELECT DISTINCT t1a.c1 AS k0, t1a.c4 AS k1, t1a.c1 AS k2 FROM t1 AS t1a WHERE ((t1a.c1 <= (-1)) AND (t1a.c4 <= 7)) OR ((t1a.c1 = 10) AND (t1a.c4 <= 1)) UNION SELECT DISTINCT t1c.c1 AS k0, t2a.c3 AS k1, t1b.c4 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON t1b.c1 >= 2 INNER JOIN t1 AS t1c ON NOT (EXISTS (SELECT t1s27.c1 FROM t1 AS t1s27 WHERE t1b.c4 = t2a.c1)) WHERE NOT (t1b.c1 = t2a.c15);
-- mutant
SELECT DISTINCT t2b.c1 AS k0, t3c.c7 AS k1, t2b.c14 AS k2 FROM t1 AS t1a LEFT JOIN t2 AS t2b ON NOT (EXISTS (SELECT t3s9.c1 FROM t3 AS t3s9 WHERE t1a.c4 = t3s9.c7)) INNER JOIN t3 AS t3c ON (t2b.c14 IS NULL) OR (t2b.c1 >= t2b.c15) WHERE (NOT (t1a.c1 = 5)) AND (t2b.c2 IN (SELECT t1i94.c4 FROM t1 AS t1i94 WHERE t3c.c3 <> t3c.c7)) UNION ALL SELECT DISTINCT t1a.c1 AS k0, t1a.c4 AS k1, t1a.c1 AS k2 FROM t1 AS t1a WHERE ((t1a.c1 <= (-1)) AND (t1a.c4 <= 7)) OR ((t1a.c1 = 10) AND (t1a.c4 <= 1)) UNION ALL SELECT DISTINCT t1c.c1 AS k0, t2a.c3 AS k1, t1b.c4 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON t1b.c1 >= 2 INNER JOIN t1 AS t1c ON NOT (EXISTS (SELECT t1s27.c1 FROM t1 AS t1s27 WHERE t1b.c4 = t2a.c1)) WHERE NOT (t1b.c1 = t2a.c15);
```

Original rows: `["('', '', '2')", "('', '', '7')", "('', '', 'B')", "('', '', 'x')", "('', '-1', '2')", "('', '-1', 'B')", "('', '10', '2')", "('', '10', '7')", "('', '10', 'B')", "('', '10', 'x')", "('', '3', '')", "('', '3', '2')"]`

Mutant rows: `["('', '', '2')", "('', '', '7')", "('', '', 'B')", "('', '', 'x')", "('', '-1', '2')", "('', '-1', 'B')", "('', '10', '2')", "('', '10', '7')", "('', '10', 'B')", "('', '10', 'x')", "('', '3', '')", "('', '3', '2')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 6. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 1008)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t3b.c2 = 1) AND (t3b.c1 > t1a.c4) INNER JOIN t3 AS t3c ON (t3c.c7 IS NULL) OR (t3c.c2 <> t1a.c1) WHERE (NOT (t3b.c3 IN (SELECT t1i68.c1 FROM t1 AS t1i68 WHERE t3c.c1 <> 0))) AND (t1a.c4 IN (SELECT t1i38.c4 FROM t1 AS t1i38 WHERE t3c.c3 < 0)) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON t1a.c4 <= 0 LEFT JOIN t2 AS t2c ON NOT (t2c.c2 >= t1a.c4) WHERE EXISTS (SELECT t2s97.c1 FROM t2 AS t2s97 WHERE t2s97.c15 < 7) UNION ALL SELECT t1b.c1 AS k0 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON NOT (EXISTS (SELECT t3s71.c1 FROM t3 AS t3s71 WHERE t3s71.c8 = t1b.c1)) WHERE (t1b.c1 < t1a.c4) AND ((t1b.c4 IS NULL) AND (t1b.c4 > t1b.c4));
-- mutant
SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t3b.c2 = 1) AND (t3b.c1 > t1a.c4) INNER JOIN t3 AS t3c ON (t3c.c7 IS NULL) OR (t3c.c2 <> t1a.c1) WHERE (NOT (t3b.c3 IN (SELECT t1i68.c1 FROM t1 AS t1i68 WHERE t3c.c1 <> 0))) AND (t1a.c4 IN (SELECT t1i38.c4 FROM t1 AS t1i38 WHERE t3c.c3 < 0)) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON t1a.c4 <= 0 LEFT JOIN t2 AS t2c ON NOT (t2c.c2 >= t1a.c4) WHERE EXISTS (SELECT t2s97.c1 FROM t2 AS t2s97 WHERE t2s97.c15 < 7) UNION SELECT t1b.c1 AS k0 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON NOT (EXISTS (SELECT t3s71.c1 FROM t3 AS t3s71 WHERE t3s71.c8 = t1b.c1)) WHERE (t1b.c1 < t1a.c4) AND ((t1b.c4 IS NULL) AND (t1b.c4 > t1b.c4));
```

Original rows: `["('0',)", "('1',)", "('2',)", "('B',)"]`

Mutant rows: `["('0',)", "('1',)", "('2',)", "('B',)", "('b',)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 7. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 1008)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t3b.c2 = 1) AND (t3b.c1 > t1a.c4) INNER JOIN t3 AS t3c ON (t3c.c7 IS NULL) OR (t3c.c2 <> t1a.c1) WHERE (NOT (t3b.c3 IN (SELECT t1i68.c1 FROM t1 AS t1i68 WHERE t3c.c1 <> 0))) AND (t1a.c4 IN (SELECT t1i38.c4 FROM t1 AS t1i38 WHERE t3c.c3 < 0)) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON t1a.c4 <= 0 LEFT JOIN t2 AS t2c ON NOT (t2c.c2 >= t1a.c4) WHERE EXISTS (SELECT t2s97.c1 FROM t2 AS t2s97 WHERE t2s97.c15 < 7) UNION ALL SELECT t1b.c1 AS k0 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON NOT (EXISTS (SELECT t3s71.c1 FROM t3 AS t3s71 WHERE t3s71.c8 = t1b.c1)) WHERE (t1b.c1 < t1a.c4) AND ((t1b.c4 IS NULL) AND (t1b.c4 > t1b.c4));
-- mutant
SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t3b.c2 = 1) AND (t3b.c1 > t1a.c4) INNER JOIN t3 AS t3c ON (t3c.c7 IS NULL) OR (t3c.c2 <> t1a.c1) WHERE (NOT (t3b.c3 IN (SELECT t1i68.c1 FROM t1 AS t1i68 WHERE t3c.c1 <> 0))) AND (t1a.c4 IN (SELECT t1i38.c4 FROM t1 AS t1i38 WHERE t3c.c3 < 0)) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON t1a.c4 <= 0 LEFT JOIN t2 AS t2c ON NOT (t2c.c2 >= t1a.c4) WHERE EXISTS (SELECT t2s97.c1 FROM t2 AS t2s97 WHERE t2s97.c15 < 7) UNION ALL SELECT t1b.c1 AS k0 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON NOT (EXISTS (SELECT t3s71.c1 FROM t3 AS t3s71 WHERE t3s71.c8 = t1b.c1)) WHERE (t1b.c1 < t1a.c4) AND ((t1b.c4 IS NULL) AND (t1b.c4 > t1b.c4));
```

Original rows: `["('0',)", "('1',)", "('2',)", "('B',)"]`

Mutant rows: `["('0',)", "('1',)", "('2',)", "('B',)", "('b',)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 8. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1008)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2a.c3 AS k0, t2a.c2 AS k1, t2a.c15 AS k2 FROM t2 AS t2a WHERE t2a.c15 IN (SELECT t2i13.c1 FROM t2 AS t2i13 WHERE t2i13.c15 <> 7) UNION SELECT DISTINCT t1c.c4 AS k0, t1c.c4 AS k1, t2b.c3 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON t3a.c1 <> 0 INNER JOIN t1 AS t1c ON NOT (EXISTS (SELECT t2s18.c1 FROM t2 AS t2s18 WHERE t3a.c7 < t2b.c2)) UNION ALL SELECT DISTINCT t1a.c4 AS k0, t1a.c1 AS k1, t2b.c3 AS k2 FROM t1 AS t1a LEFT JOIN t2 AS t2b ON (t1a.c1 IS NULL) AND (t1a.c1 <> t1a.c4) INNER JOIN t3 AS t3c ON (t3c.c8 >= 10) OR (t1a.c1 <> 1) WHERE ((t2b.c15 > 0) AND (t3c.c8 <> 7)) OR (t2b.c14 <> 7);
-- mutant
SELECT DISTINCT t2a.c3 AS k0, t2a.c2 AS k1, t2a.c15 AS k2 FROM t2 AS t2a WHERE t2a.c15 IN (SELECT t2i13.c1 FROM t2 AS t2i13 WHERE t2i13.c15 <> 7) UNION ALL SELECT DISTINCT t1c.c4 AS k0, t1c.c4 AS k1, t2b.c3 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON t3a.c1 <> 0 INNER JOIN t1 AS t1c ON NOT (EXISTS (SELECT t2s18.c1 FROM t2 AS t2s18 WHERE t3a.c7 < t2b.c2)) UNION ALL SELECT DISTINCT t1a.c4 AS k0, t1a.c1 AS k1, t2b.c3 AS k2 FROM t1 AS t1a LEFT JOIN t2 AS t2b ON (t1a.c1 IS NULL) AND (t1a.c1 <> t1a.c4) INNER JOIN t3 AS t3c ON (t3c.c8 >= 10) OR (t1a.c1 <> 1) WHERE ((t2b.c15 > 0) AND (t3c.c8 <> 7)) OR (t2b.c14 <> 7);
```

Original rows: `["('0', '0', '')", "('0', '0', '1')", "('0', '0', '4')", "('0', '0', None)", "('1', '1', '')", "('1', '1', '1')", "('1', '1', '4')", "('1', '1', None)", "('2', '2', '')", "('2', '2', '1')", "('2', '2', '4')", "('2', '2', None)"]`

Mutant rows: `["('0', '0', '')", "('0', '0', '1')", "('0', '0', '4')", "('0', '0', None)", "('1', '1', '')", "('1', '1', '1')", "('1', '1', '4')", "('1', '1', None)", "('2', '2', '')", "('2', '2', '1')", "('2', '2', '4')", "('2', '2', None)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 9. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1014)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t3a.c7 AS k0, t2b.c15 AS k1, t3a.c9 AS k2 FROM t3 AS t3a LEFT JOIN t2 AS t2b ON (t3a.c2 < t2b.c15) OR (t2b.c14 < t3a.c8) WHERE NOT (EXISTS (SELECT t2s41.c1 FROM t2 AS t2s41 WHERE t2s41.c2 <= 5)) UNION ALL SELECT DISTINCT t1b.c1 AS k0, t3a.c9 AS k1, t1b.c1 AS k2 FROM t3 AS t3a INNER JOIN t1 AS t1b ON NOT (EXISTS (SELECT t1s33.c1 FROM t1 AS t1s33 WHERE t1b.c4 >= t1b.c1)) WHERE t1b.c1 > 0 UNION SELECT DISTINCT t2b.c2 AS k0, t3a.c1 AS k1, t2b.c2 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON NOT (t2b.c14 IN (SELECT t1i22.c1 FROM t1 AS t1i22 WHERE t1i22.c1 IS NULL));
-- mutant
SELECT t3a.c7 AS k0, t2b.c15 AS k1, t3a.c9 AS k2 FROM t3 AS t3a LEFT JOIN t2 AS t2b ON (t3a.c2 < t2b.c15) OR (t2b.c14 < t3a.c8) WHERE NOT (EXISTS (SELECT t2s41.c1 FROM t2 AS t2s41 WHERE t2s41.c2 <= 5)) UNION ALL SELECT DISTINCT t1b.c1 AS k0, t3a.c9 AS k1, t1b.c1 AS k2 FROM t3 AS t3a INNER JOIN t1 AS t1b ON NOT (EXISTS (SELECT t1s33.c1 FROM t1 AS t1s33 WHERE t1b.c4 >= t1b.c1)) WHERE t1b.c1 > 0 UNION ALL SELECT DISTINCT t2b.c2 AS k0, t3a.c1 AS k1, t2b.c2 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON NOT (t2b.c14 IN (SELECT t1i22.c1 FROM t1 AS t1i22 WHERE t1i22.c1 IS NULL));
```

Original rows: `["('01', -1, '01')", "('01', -3, '01')", "('01', 0, '01')", "('01', 10, '01')", "('01', 2, '01')", "('01', 4, '01')", "('01', None, '01')", "('10', -1, '10')", "('10', -3, '10')", "('10', 0, '10')", "('10', 10, '10')", "('10', 2, '10')"]`

Mutant rows: `["('01', -1, '01')", "('01', -3, '01')", "('01', 0, '01')", "('01', 10, '01')", "('01', 2, '01')", "('01', 4, '01')", "('01', None, '01')", "('10', -1, '10')", "('10', -3, '10')", "('10', 0, '10')", "('10', 10, '10')", "('10', 2, '10')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 10. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1021)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t3b.c2 AS k0 FROM t3 AS t3a INNER JOIN t3 AS t3b ON NOT (t3a.c8 >= 10) WHERE EXISTS (SELECT t2s81.c1 FROM t2 AS t2s81 WHERE EXISTS (SELECT t2s56.c1 FROM t2 AS t2s56 WHERE t2s56.c14 >= 2)) UNION SELECT DISTINCT t3c.c6 AS k0 FROM t3 AS t3a LEFT JOIN t3 AS t3b ON (t3a.c9 <= 0) OR (t3a.c3 >= t3b.c1) INNER JOIN t3 AS t3c ON (t3c.c6 IS NULL) AND (t3c.c2 <= 10) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a WHERE NOT ((t1a.c4 > 0) AND (t1a.c4 = 5));
-- mutant
SELECT t3b.c2 AS k0 FROM t3 AS t3a INNER JOIN t3 AS t3b ON NOT (t3a.c8 >= 10) WHERE EXISTS (SELECT t2s81.c1 FROM t2 AS t2s81 WHERE EXISTS (SELECT t2s56.c1 FROM t2 AS t2s56 WHERE t2s56.c14 >= 2)) UNION SELECT DISTINCT t3c.c6 AS k0 FROM t3 AS t3a LEFT JOIN t3 AS t3b ON (t3a.c9 <= 0) OR (t3a.c3 >= t3b.c1) INNER JOIN t3 AS t3c ON (t3c.c6 IS NULL) AND (t3c.c2 <= 10) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a WHERE NOT ((t1a.c4 > 0) AND (t1a.c4 = 5));
```

Original rows: `["('',)", "('01',)", "('1',)", "('A',)", "('B',)", "('a',)", "('x',)", '(10.0,)', '(5.0,)', '(None,)']`

Mutant rows: `["('',)", "('01',)", "('1',)", "('B',)", "('a',)", "('x',)", '(10.0,)', '(5.0,)', '(None,)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 11. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1023)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t1b.c1 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (t1b.c4 = 10) AND (t1a.c4 <> 0) INTERSECT SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a LEFT JOIN t3 AS t3b ON t3a.c8 <> 3 WHERE t3b.c8 <= (-1);
-- mutant
SELECT DISTINCT t1b.c1 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (t1b.c4 = 10) AND (t1a.c4 <> 0) INTERSECT SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a LEFT JOIN t3 AS t3b ON t3a.c8 <> 3 WHERE t3b.c8 <= (-1);
```

Original rows: `["(' 1',)", "('',)", "('-1',)", "('1',)", "('10',)", "('2',)", "('4',)", "('B',)", "('b',)"]`

Mutant rows: `["(' 1',)", "('',)", "('-1',)", "('1',)", "('10',)", "('2',)", "('4',)", "('b',)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 12. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1156)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t3a.c9 AS k0, t3a.c9 AS k1, t3a.c9 AS k2 FROM t3 AS t3a WHERE t3a.c1 IN (SELECT t2i75.c2 FROM t2 AS t2i75 WHERE t2i75.c15 IS NULL) EXCEPT SELECT DISTINCT t3a.c2 AS k0, t2b.c2 AS k1, t3a.c9 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c14 <= 10) OR (t2b.c3 <> 3) UNION SELECT DISTINCT t2a.c3 AS k0, t2a.c3 AS k1, t2a.c14 AS k2 FROM t2 AS t2a;
-- mutant
SELECT DISTINCT t3a.c9 AS k0, t3a.c9 AS k1, t3a.c9 AS k2 FROM t3 AS t3a WHERE t3a.c1 IN (SELECT t2i75.c2 FROM t2 AS t2i75 WHERE t2i75.c15 IS NULL) EXCEPT SELECT DISTINCT t3a.c2 AS k0, t2b.c2 AS k1, t3a.c9 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c14 <= 10) OR (t2b.c3 <> 3) UNION ALL SELECT DISTINCT t2a.c3 AS k0, t2a.c3 AS k1, t2a.c14 AS k2 FROM t2 AS t2a;
```

Original rows: `["('2', '2', 'B')", "('5', '5', '2')", "(-1, -1, 'b')", "(1, 1, 'A')", "(10, 10, '7')", "(2, 2, 'A')", "(5, 5, '2')", "(None, None, 'B')", "(None, None, 'b')", '(None, None, None)']`

Mutant rows: `["('2', '2', 'B')", "('5', '5', '2')", "(-1, -1, 'b')", "(1, 1, 'A')", "(10, 10, '7')", "(2, 2, 'A')", "(5, 5, '2')", "(None, None, 'b')", '(None, None, None)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 13. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 1156)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT DISTINCT t3b.c7 AS k0, t3b.c2 AS k1 FROM t2 AS t2a LEFT JOIN t3 AS t3b ON t2a.c1 > t3b.c6 INTERSECT SELECT DISTINCT t3a.c3 AS k0, t3a.c6 AS k1 FROM t3 AS t3a UNION ALL SELECT DISTINCT t2a.c14 AS k0, t2a.c3 AS k1 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON t2b.c1 = t2a.c1 WHERE NOT (t2a.c2 IN (SELECT t3i43.c9 FROM t3 AS t3i43 WHERE NOT (t3i43.c1 IS NULL)));
-- mutant
SELECT DISTINCT t3b.c7 AS k0, t3b.c2 AS k1 FROM t2 AS t2a LEFT JOIN t3 AS t3b ON t2a.c1 > t3b.c6 INTERSECT SELECT DISTINCT t3a.c3 AS k0, t3a.c6 AS k1 FROM t3 AS t3a UNION SELECT DISTINCT t2a.c14 AS k0, t2a.c3 AS k1 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON t2b.c1 = t2a.c1 WHERE NOT (t2a.c2 IN (SELECT t3i43.c9 FROM t3 AS t3i43 WHERE NOT (t3i43.c1 IS NULL)));
```

Original rows: `["('2', '5')", "('2', 5)", "('7', 10)", "('A', 1)", "('A', 2)", "('b', -1)", "('b', None)", '(None, None)']`

Mutant rows: `["('2', '5')", "('2', 5)", "('7', 10)", "('A', 1)", "('A', 2)", "('B', None)", "('b', -1)", "('b', None)", '(None, None)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 14. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1157)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON NOT (EXISTS (SELECT t2s80.c1 FROM t2 AS t2s80 WHERE t1b.c4 < t1a.c1)) UNION ALL SELECT DISTINCT t1b.c1 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1b.c1 > t1b.c4 WHERE NOT (EXISTS (SELECT t1s7.c1 FROM t1 AS t1s7 WHERE NOT (t1s7.c1 <> 5))) UNION SELECT DISTINCT t2c.c1 AS k0 FROM t1 AS t1a LEFT JOIN t2 AS t2b ON NOT (t2b.c1 = t1a.c4) INNER JOIN t2 AS t2c ON t2c.c14 <> 0 WHERE t1a.c4 IN (SELECT t3i89.c6 FROM t3 AS t3i89 WHERE t2c.c2 <> t2c.c1);
-- mutant
SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON NOT (EXISTS (SELECT t2s80.c1 FROM t2 AS t2s80 WHERE t1b.c4 < t1a.c1)) UNION ALL SELECT DISTINCT t1b.c1 AS k0 FROM t1 AS t1a INNER JOIN t1 AS t1b ON t1b.c1 > t1b.c4 WHERE NOT (EXISTS (SELECT t1s7.c1 FROM t1 AS t1s7 WHERE NOT (t1s7.c1 <> 5))) UNION ALL SELECT DISTINCT t2c.c1 AS k0 FROM t1 AS t1a LEFT JOIN t2 AS t2b ON NOT (t2b.c1 = t1a.c4) INNER JOIN t2 AS t2c ON t2c.c14 <> 0 WHERE t1a.c4 IN (SELECT t3i89.c6 FROM t3 AS t3i89 WHERE t2c.c2 <> t2c.c1);
```

Original rows: `["(' 1',)", "('-1',)", "('-3',)", "('1',)", "('4',)", "('7',)", "('A',)", "('a',)", "('b',)", '(-3,)', '(1,)', '(2,)']`

Mutant rows: `["(' 1',)", "('-1',)", "('-3',)", "('1',)", "('4',)", "('7',)", "('a',)", "('b',)", '(-3,)', '(1,)', '(2,)', '(None,)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 15. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1162)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t3a.c3 AS k0, t3a.c3 AS k1 FROM t3 AS t3a WHERE (EXISTS (SELECT t1s31.c1 FROM t1 AS t1s31 WHERE t1s31.c4 IS NULL)) AND ((t3a.c6 >= 7) OR (t3a.c7 IS NULL)) INTERSECT SELECT DISTINCT t1a.c4 AS k0, t1a.c4 AS k1 FROM t1 AS t1a UNION SELECT DISTINCT t2c.c1 AS k0, t2a.c14 AS k1 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON t2a.c15 <= 10 INNER JOIN t2 AS t2c ON t2b.c2 IS NULL WHERE t2b.c2 IS NULL;
-- mutant
SELECT DISTINCT t3a.c3 AS k0, t3a.c3 AS k1 FROM t3 AS t3a WHERE (EXISTS (SELECT t1s31.c1 FROM t1 AS t1s31 WHERE t1s31.c4 IS NULL)) AND ((t3a.c6 >= 7) OR (t3a.c7 IS NULL)) INTERSECT SELECT DISTINCT t1a.c4 AS k0, t1a.c4 AS k1 FROM t1 AS t1a UNION ALL SELECT DISTINCT t2c.c1 AS k0, t2a.c14 AS k1 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON t2a.c15 <= 10 INNER JOIN t2 AS t2c ON t2b.c2 IS NULL WHERE t2b.c2 IS NULL;
```

Original rows: `["('3', '2')", "('3', 'B')", "('3', 'x')", "('3', None)", "('A', '2')", "('A', 'B')", "('A', 'x')", "('A', None)", "('B', '2')", "('B', 'B')", "('B', 'x')", "('B', None)"]`

Mutant rows: `["('3', '2')", "('3', 'B')", "('3', 'x')", "('3', None)", "('B', '2')", "('B', 'B')", "('B', 'x')", "('B', None)", "('a', '2')", "('a', 'B')", "('a', 'x')", "('a', None)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 16. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1163)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2a.c1 AS k0, t2a.c15 AS k1 FROM t2 AS t2a WHERE t2a.c2 IN (SELECT t2i6.c2 FROM t2 AS t2i6 WHERE (t2i6.c15 < 2) OR (t2i6.c1 > 10)) UNION SELECT DISTINCT t2a.c3 AS k0, t2a.c1 AS k1 FROM t2 AS t2a INNER JOIN t2 AS t2b ON t2b.c3 IS NULL WHERE ((t2b.c14 < 5) OR (t2a.c2 IS NULL)) OR (EXISTS (SELECT t3s7.c1 FROM t3 AS t3s7 WHERE t2b.c14 <> t3s7.c7)) UNION SELECT DISTINCT t2b.c2 AS k0, t2b.c14 AS k1 FROM t1 AS t1a INNER JOIN t2 AS t2b ON EXISTS (SELECT t1s26.c1 FROM t1 AS t1s26 WHERE t1s26.c1 < 7) WHERE (NOT (t2b.c14 IN (SELECT t2i22.c1 FROM t2 AS t2i22 WHERE t2b.c14 > 1))) OR (t2b.c1 IN (SELECT t3i63.c7 FROM t3 AS t3i63 WHERE t3i63.c2 IS NULL));
-- mutant
SELECT DISTINCT t2a.c1 AS k0, t2a.c15 AS k1 FROM t2 AS t2a WHERE t2a.c2 IN (SELECT t2i6.c2 FROM t2 AS t2i6 WHERE (t2i6.c15 < 2) OR (t2i6.c1 > 10)) UNION SELECT DISTINCT t2a.c3 AS k0, t2a.c1 AS k1 FROM t2 AS t2a INNER JOIN t2 AS t2b ON t2b.c3 IS NULL WHERE ((t2b.c14 < 5) OR (t2a.c2 IS NULL)) OR (EXISTS (SELECT t3s7.c1 FROM t3 AS t3s7 WHERE t2b.c14 <> t3s7.c7)) UNION ALL SELECT DISTINCT t2b.c2 AS k0, t2b.c14 AS k1 FROM t1 AS t1a INNER JOIN t2 AS t2b ON EXISTS (SELECT t1s26.c1 FROM t1 AS t1s26 WHERE t1s26.c1 < 7) WHERE (NOT (t2b.c14 IN (SELECT t2i22.c1 FROM t2 AS t2i22 WHERE t2b.c14 > 1))) OR (t2b.c1 IN (SELECT t3i63.c7 FROM t3 AS t3i63 WHERE t3i63.c2 IS NULL));
```

Original rows: `["('2', None)", "('5', 1)", "('B', 1)", "('b', 1)", '(1.0, 1.5)', '(1.0, 10.0)', '(4.5, -1.0)', '(None, 1.0)']`

Mutant rows: `["('2', None)", "('5', 1)", "('b', 1)", '(1.0, 1.5)', '(1.0, 10.0)', '(4.5, -1.0)', '(None, 1.0)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 17. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1166)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t1a.c4 AS k0, t1a.c4 AS k1, t1a.c1 AS k2 FROM t1 AS t1a WHERE ((t1a.c4 <> 1) OR (t1a.c4 > 2)) OR (NOT (t1a.c1 <= 7)) UNION SELECT DISTINCT t2b.c3 AS k0, t3a.c2 AS k1, t2b.c14 AS k2 FROM t3 AS t3a LEFT JOIN t2 AS t2b ON (t3a.c2 <= 2) AND (t3a.c7 <= 0) UNION ALL SELECT t1a.c1 AS k0, t1a.c1 AS k1, t2c.c1 AS k2 FROM t1 AS t1a INNER JOIN t2 AS t2b ON t1a.c1 IS NULL INNER JOIN t2 AS t2c ON (t2c.c3 < t1a.c4) OR (t2b.c2 <= t2b.c15) WHERE EXISTS (SELECT t1s62.c1 FROM t1 AS t1s62 WHERE (t2c.c14 = t2b.c2) AND (t1s62.c1 <> 1));
-- mutant
SELECT t1a.c4 AS k0, t1a.c4 AS k1, t1a.c1 AS k2 FROM t1 AS t1a WHERE ((t1a.c4 <> 1) OR (t1a.c4 > 2)) OR (NOT (t1a.c1 <= 7)) UNION ALL SELECT DISTINCT t2b.c3 AS k0, t3a.c2 AS k1, t2b.c14 AS k2 FROM t3 AS t3a LEFT JOIN t2 AS t2b ON (t3a.c2 <= 2) AND (t3a.c7 <= 0) UNION ALL SELECT t1a.c1 AS k0, t1a.c1 AS k1, t2c.c1 AS k2 FROM t1 AS t1a INNER JOIN t2 AS t2b ON t1a.c1 IS NULL INNER JOIN t2 AS t2c ON (t2c.c3 < t1a.c4) OR (t2b.c2 <= t2b.c15) WHERE EXISTS (SELECT t1s62.c1 FROM t1 AS t1s62 WHERE (t2c.c14 = t2b.c2) AND (t1s62.c1 <> 1));
```

Original rows: `['(-3, -3, 2)', "(1, 1, '0')", "(10, 10, '4')", "(2, 2, '5')", '(2, 2, None)', '(4, 4, None)', '(5, 5, 5)', '(5, 5, None)', '(7, 7, 7)', "(None, ' 1', None)", "(None, '-3', None)", "(None, '3', None)"]`

Mutant rows: `['(-3, -3, 2)', "(1, 1, '0')", "(10, 10, '4')", "(2, 2, '5')", '(2, 2, None)', '(4, 4, None)', '(5, 5, 5)', '(5, 5, None)', '(7, 7, 7)', "(None, ' 1', None)", "(None, '-3', None)", "(None, '3', None)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 18. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1166)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t2b.c2 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (t2b.c14 IS NULL) OR (t2b.c3 <= 1) WHERE t1a.c1 >= t1a.c1 INTERSECT SELECT t1a.c4 AS k0 FROM t1 AS t1a WHERE (NOT (EXISTS (SELECT t1s51.c1 FROM t1 AS t1s51 WHERE t1s51.c1 >= 10))) OR ((t1a.c4 <> 10) AND (t1a.c1 < 3)) UNION SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t1b.c1 <= 7 WHERE NOT (t1b.c4 = 1);
-- mutant
SELECT t2b.c2 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (t2b.c14 IS NULL) OR (t2b.c3 <= 1) WHERE t1a.c1 >= t1a.c1 INTERSECT SELECT t1a.c4 AS k0 FROM t1 AS t1a WHERE (NOT (EXISTS (SELECT t1s51.c1 FROM t1 AS t1s51 WHERE t1s51.c1 >= 10))) OR ((t1a.c4 <> 10) AND (t1a.c1 < 3)) UNION ALL SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t1b.c1 <= 7 WHERE NOT (t1b.c4 = 1);
```

Original rows: `["(' 1',)", "('1',)", "('10',)", "('2',)", "('3',)", "('B',)", "('b',)", "('x',)", '(None,)']`

Mutant rows: `["(' 1',)", "('1',)", "('10',)", "('2',)", "('3',)", "('b',)", "('x',)", '(None,)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 19. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1166)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t1b.c4 AS k0, t1b.c1 AS k1 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t1b.c1 <= 5 WHERE (NOT (t3a.c2 >= 1)) AND (NOT (t1b.c4 <> 2)) UNION ALL SELECT t3a.c7 AS k0, t3a.c7 AS k1 FROM t3 AS t3a INNER JOIN t2 AS t2b ON EXISTS (SELECT t3s74.c1 FROM t3 AS t3s74 WHERE t3s74.c8 > 3) INNER JOIN t3 AS t3c ON t3c.c1 > (-1) WHERE ((t3a.c9 IS NULL) AND (t3a.c7 <> t3a.c6)) AND ((t2b.c3 <> 10) AND (t3a.c1 >= 10)) UNION SELECT DISTINCT t1c.c1 AS k0, t3b.c8 AS k1 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (t1a.c1 <= 10) OR (t3b.c2 <= 3) INNER JOIN t1 AS t1c ON NOT (EXISTS (SELECT t1s81.c1 FROM t1 AS t1s81 WHERE t3b.c7 < 1));
-- mutant
SELECT t1b.c4 AS k0, t1b.c1 AS k1 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t1b.c1 <= 5 WHERE (NOT (t3a.c2 >= 1)) AND (NOT (t1b.c4 <> 2)) UNION ALL SELECT t3a.c7 AS k0, t3a.c7 AS k1 FROM t3 AS t3a INNER JOIN t2 AS t2b ON EXISTS (SELECT t3s74.c1 FROM t3 AS t3s74 WHERE t3s74.c8 > 3) INNER JOIN t3 AS t3c ON t3c.c1 > (-1) WHERE ((t3a.c9 IS NULL) AND (t3a.c7 <> t3a.c6)) AND ((t2b.c3 <> 10) AND (t3a.c1 >= 10)) UNION ALL SELECT DISTINCT t1c.c1 AS k0, t3b.c8 AS k1 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (t1a.c1 <= 10) OR (t3b.c2 <= 3) INNER JOIN t1 AS t1c ON NOT (EXISTS (SELECT t1s81.c1 FROM t1 AS t1s81 WHERE t3b.c7 < 1));
```

Original rows: `["('0', ' 1')", "('0', '1')", "('0', '10')", "('0', '2')", "('0', '3')", "('0', 'B')", "('0', 'b')", "('0', 'x')", "('0', None)", "('4', ' 1')", "('4', '1')", "('4', '10')"]`

Mutant rows: `["('0', ' 1')", "('0', '1')", "('0', '10')", "('0', '2')", "('0', '3')", "('0', 'b')", "('0', 'x')", "('0', None)", "('4', ' 1')", "('4', '1')", "('4', '10')", "('4', '2')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 20. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1167)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2a.c2 AS k0 FROM t2 AS t2a WHERE NOT (t2a.c3 IN (SELECT t3i59.c7 FROM t3 AS t3i59 WHERE t2a.c1 > t2a.c15)) UNION SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a;
-- mutant
SELECT DISTINCT t2a.c2 AS k0 FROM t2 AS t2a WHERE NOT (t2a.c3 IN (SELECT t3i59.c7 FROM t3 AS t3i59 WHERE t2a.c1 > t2a.c15)) UNION ALL SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a;
```

Original rows: `["(' 1',)", "('-3',)", "('10',)", "('3',)", "('4',)", "('5',)", "('A',)", "('B',)", "('b',)", '(-1,)', '(1,)', '(None,)']`

Mutant rows: `["(' 1',)", "('-3',)", "('10',)", "('3',)", "('4',)", "('5',)", "('5',)", "('A',)", "('B',)", '(-1,)', '(1,)', '(None,)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 21. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1173)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a WHERE t1a.c1 <> 5 UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a LEFT JOIN t3 AS t3b ON (t3b.c3 < 2) AND (t3a.c7 < t3b.c9) INNER JOIN t2 AS t2c ON NOT (EXISTS (SELECT t3s62.c1 FROM t3 AS t3s62 WHERE t3s62.c7 <= t3b.c1)) UNION SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a WHERE ((t1a.c4 = 5) AND (t1a.c4 >= 2)) AND ((t1a.c1 IS NULL) OR (t1a.c4 IS NULL));
-- mutant
SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a WHERE t1a.c1 <> 5 UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a LEFT JOIN t3 AS t3b ON (t3b.c3 < 2) AND (t3a.c7 < t3b.c9) INNER JOIN t2 AS t2c ON NOT (EXISTS (SELECT t3s62.c1 FROM t3 AS t3s62 WHERE t3s62.c7 <= t3b.c1)) UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a WHERE ((t1a.c4 = 5) AND (t1a.c4 >= 2)) AND ((t1a.c1 IS NULL) OR (t1a.c4 IS NULL));
```

Original rows: `["('',)", "('-1',)", "('01',)", "('1',)", "('2',)", "('4',)", "('5',)", "('A',)", "('a',)", '(1,)', '(2,)', '(3,)']`

Mutant rows: `["('',)", "('-1',)", "('01',)", "('1',)", "('2',)", "('2',)", "('4',)", "('5',)", "('A',)", '(1,)', '(2,)', '(3,)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 22. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1173)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2b.c3 AS k0, t2b.c2 AS k1, t2b.c3 AS k2 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (t1a.c1 <= 10) AND (t2b.c1 <> 2) LEFT JOIN t1 AS t1c ON NOT (t1a.c1 > t2b.c1) WHERE t1a.c4 >= 5 UNION SELECT DISTINCT t3b.c6 AS k0, t3b.c2 AS k1, t3a.c3 AS k2 FROM t3 AS t3a INNER JOIN t3 AS t3b ON t3b.c3 <> 10 LEFT JOIN t3 AS t3c ON (t3c.c2 < 1) OR (t3b.c9 <= 2) WHERE (t3b.c9 < (-1)) OR ((t3c.c2 <= 2) AND (t3a.c3 <= t3b.c6)) UNION ALL SELECT DISTINCT t3b.c2 AS k0, t1a.c1 AS k1, t1a.c4 AS k2 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (t1a.c4 <= t3b.c7) OR (t3b.c6 IS NULL);
-- mutant
SELECT DISTINCT t2b.c3 AS k0, t2b.c2 AS k1, t2b.c3 AS k2 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (t1a.c1 <= 10) AND (t2b.c1 <> 2) LEFT JOIN t1 AS t1c ON NOT (t1a.c1 > t2b.c1) WHERE t1a.c4 >= 5 UNION ALL SELECT DISTINCT t3b.c6 AS k0, t3b.c2 AS k1, t3a.c3 AS k2 FROM t3 AS t3a INNER JOIN t3 AS t3b ON t3b.c3 <> 10 LEFT JOIN t3 AS t3c ON (t3c.c2 < 1) OR (t3b.c9 <= 2) WHERE (t3b.c9 < (-1)) OR ((t3c.c2 <= 2) AND (t3a.c3 <= t3b.c6)) UNION ALL SELECT DISTINCT t3b.c2 AS k0, t1a.c1 AS k1, t1a.c4 AS k2 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (t1a.c4 <= t3b.c7) OR (t3b.c6 IS NULL);
```

Original rows: `["('', '', 2)", "('', 'x', '2')", "('', 'x', 1)", "('1', '', 2)", "('1', '0', None)", "('1', 'A', 3)", "('1', 'a', None)", "('1', 'x', '2')", "('1', 'x', 1)", "('2', '', 2)", "('2', 'x', '2')", "('2', 'x', 1)"]`

Mutant rows: `["('', '', 2)", "('', 'x', '2')", "('', 'x', 1)", "('1', '', 2)", "('1', '0', None)", "('1', 'A', 3)", "('1', 'a', None)", "('1', 'x', '2')", "('1', 'x', 1)", "('2', '', 2)", "('2', 'x', '2')", "('2', 'x', 1)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 23. `EXCEPT->left` on SQLite 3.26.0 (seed 1178)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t3a.c8 AS k0, t2b.c2 AS k1 FROM t3 AS t3a LEFT JOIN t2 AS t2b ON t2b.c15 <= 0 UNION ALL SELECT DISTINCT t1a.c1 AS k0, t1a.c1 AS k1 FROM t1 AS t1a WHERE EXISTS (SELECT t1s61.c1 FROM t1 AS t1s61 WHERE NOT (t1s61.c4 = t1a.c4)) EXCEPT SELECT t2a.c2 AS k0, t2a.c3 AS k1 FROM t2 AS t2a WHERE t2a.c14 IN (SELECT t3i32.c6 FROM t3 AS t3i32 WHERE NOT (EXISTS (SELECT t1s66.c1 FROM t1 AS t1s66 WHERE t2a.c1 <> 3)));
-- mutant
SELECT DISTINCT t3a.c8 AS k0, t2b.c2 AS k1 FROM t3 AS t3a LEFT JOIN t2 AS t2b ON t2b.c15 <= 0 UNION ALL SELECT DISTINCT t1a.c1 AS k0, t1a.c1 AS k1 FROM t1 AS t1a WHERE EXISTS (SELECT t1s61.c1 FROM t1 AS t1s61 WHERE NOT (t1s61.c4 = t1a.c4));
```

Original rows: `["('-1', '-1')", "('-3', '-3')", "('01', '01')", "('B', 'B')", "('a', 'a')", "('b', 'b')", '(-3, 1.25)', '(-3, 4.0)', '(1, 1.25)', '(1, 4.0)', '(10, 1.25)', '(10, 4.0)']`

Mutant rows: `["('-1', '-1')", "('-3', '-3')", "('01', '01')", "('a', 'a')", "('b', 'b')", '(-3, 1.25)', '(-3, 4.0)', '(1, 1.25)', '(1, 4.0)', '(10, 1.25)', '(10, 4.0)', '(2, 1.25)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 24. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 1178)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t1a.c4 AS k0, t1b.c4 AS k1 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (t1b.c1 > 5) AND (t1b.c4 >= t1a.c4) WHERE NOT (EXISTS (SELECT t2s70.c1 FROM t2 AS t2s70 WHERE (t2s70.c1 = 7) OR (t1a.c1 < t1a.c4))) UNION SELECT DISTINCT t1b.c1 AS k0, t3a.c7 AS k1 FROM t3 AS t3a INNER JOIN t1 AS t1b ON EXISTS (SELECT t3s52.c1 FROM t3 AS t3s52 WHERE t3a.c2 <> t1b.c1) WHERE (t3a.c2 = 3) OR (t3a.c7 < 7);
-- mutant
SELECT DISTINCT t1a.c4 AS k0, t1b.c4 AS k1 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (t1b.c1 > 5) AND (t1b.c4 >= t1a.c4) WHERE NOT (EXISTS (SELECT t2s70.c1 FROM t2 AS t2s70 WHERE (t2s70.c1 = 7) OR (t1a.c1 < t1a.c4))) UNION ALL SELECT DISTINCT t1b.c1 AS k0, t3a.c7 AS k1 FROM t3 AS t3a INNER JOIN t1 AS t1b ON EXISTS (SELECT t3s52.c1 FROM t3 AS t3s52 WHERE t3a.c2 <> t1b.c1) WHERE (t3a.c2 = 3) OR (t3a.c7 < 7);
```

Original rows: `["('-1', ' 1')", "('-1', '')", "('-1', '1')", "('-1', '10')", "('-1', '2')", "('-3', ' 1')", "('-3', '')", "('-3', '1')", "('-3', '10')", "('-3', '2')", "('01', ' 1')", "('01', '')"]`

Mutant rows: `["('-1', ' 1')", "('-1', '')", "('-1', '1')", "('-1', '10')", "('-1', '2')", "('-3', ' 1')", "('-3', '')", "('-3', '1')", "('-3', '10')", "('-3', '2')", "('01', ' 1')", "('01', '')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 25. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 240)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t3a.c3 AS k0 FROM t3 AS t3a WHERE t3a.c3 < 0 UNION SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a;
-- mutant
SELECT t3a.c3 AS k0 FROM t3 AS t3a WHERE t3a.c3 < 0 UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a;
```

Original rows: `["('',)", "('-1',)", "('-3',)", "('0',)", "('10',)", "('3',)", "('7',)", "('A',)", "('a',)"]`

Mutant rows: `["('',)", "('-1',)", "('-3',)", "('0',)", "('10',)", "('3',)", "('7',)", "('a',)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 26. `cond->TRUE` on SQLite 3.31.1 (seed 292)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t3a.c2 AS k0, t3a.c3 AS k1 FROM t3 AS t3a WHERE t3a.c1 IN (SELECT t1i3.c4 FROM t1 AS t1i3 WHERE (t1i3.c1 >= t3a.c2) AND (t1i3.c1 < t3a.c7)) UNION ALL SELECT DISTINCT t3b.c8 AS k0, t3b.c8 AS k1 FROM t3 AS t3a LEFT JOIN t3 AS t3b ON t3b.c9 <= 0 WHERE NOT (t3a.c1 IN (SELECT t1i7.c1 FROM t1 AS t1i7 WHERE (t3a.c6 = 7) OR (t3a.c6 > 3))) UNION SELECT t1a.c4 AS k0, t3b.c6 AS k1 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t1a.c4 = 1) AND (t1a.c4 = t1a.c4) LEFT JOIN t2 AS t2c ON NOT (t2c.c14 IN (SELECT t1i58.c4 FROM t1 AS t1i58 WHERE t3b.c2 >= t1a.c1)) WHERE t2c.c14 = t3b.c1;
-- mutant
SELECT t3a.c2 AS k0, t3a.c3 AS k1 FROM t3 AS t3a WHERE t3a.c1 IN (SELECT t1i3.c4 FROM t1 AS t1i3 WHERE (t1i3.c1 >= t3a.c2) AND (t1i3.c1 < t3a.c7)) UNION ALL SELECT DISTINCT t3b.c8 AS k0, t3b.c8 AS k1 FROM t3 AS t3a LEFT JOIN t3 AS t3b ON t3b.c9 <= 0 WHERE NOT (t3a.c1 IN (SELECT t1i7.c1 FROM t1 AS t1i7 WHERE (t3a.c6 = 7) OR (t3a.c6 > 3))) UNION SELECT t1a.c4 AS k0, t3b.c6 AS k1 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t1a.c4 = 1) AND (t1a.c4 = t1a.c4) LEFT JOIN t2 AS t2c ON NOT (t2c.c14 IN (SELECT t1i58.c4 FROM t1 AS t1i58 WHERE t3b.c2 >= t1a.c1)) WHERE 1 = 1;
```

Original rows: `['(-3, -1)', '(-3, 2)', '(-3, 5)', '(1, -1)', '(1, 2)', '(1, 5)', '(3, -1)', '(3, 2)', '(3, 5)', '(4, -1)', '(4, 2)', '(4, 5)']`

Mutant rows: `['(-3, None)', '(1, -1)', '(1, -3)', '(1, 10)', '(1, 2)', '(1, 3)', '(1, 4)', '(1, 5)', '(1, None)', '(2, None)', '(3, None)', '(4, None)']`

Per version: 3.26.0: ok, 3.30.1: ok, 3.31.1: violation, 3.34.0: ok, 3.53.1: ok

## 27. `cond->TRUE` on SQLite 3.34.0 (seed 663)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t3a.c1 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t3a.c3 < t2b.c15) OR (t3a.c2 >= t3a.c7) WHERE (t2b.c3 IN (SELECT t3i27.c2 FROM t3 AS t3i27 WHERE t3i27.c9 IS NULL)) AND ((t2b.c3 <> 7) OR (t3a.c3 > 2));
-- mutant
SELECT t3a.c1 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (1 = 1) OR (t3a.c2 >= t3a.c7) WHERE (t2b.c3 IN (SELECT t3i27.c2 FROM t3 AS t3i27 WHERE t3i27.c9 IS NULL)) AND ((t2b.c3 <> 7) OR (t3a.c3 > 2));
```

Original rows: `['(1.25,)', '(2.0,)', '(2.0,)', '(4.0,)', '(None,)', '(None,)']`

Mutant rows: `['(-3.0,)']`

Per version: 3.26.0: ok, 3.30.1: ok, 3.31.1: ok, 3.34.0: violation, 3.53.1: ok

## 28. `DISTINCT-add` on SQLite 3.34.0 (seed 1)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT DISTINCT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 IN (SELECT t2i75.c14 FROM t2 AS t2i75 WHERE t1b.c1 >= 3) WHERE (LIKELY(t3a.c3 > 1));
-- mutant
SELECT DISTINCT t1b.c1 AS k0 FROM (SELECT DISTINCT * FROM t3 AS t3a) AS t3a INNER JOIN t1 AS t1b ON t3a.c6 IN (SELECT t2i75.c14 FROM t2 AS t2i75 WHERE t1b.c1 >= 3) WHERE (LIKELY(t3a.c3 > 1));
```

Original rows: `['(4,)']`

Mutant rows: `['(10,)', '(4,)', '(7,)']`

Per version: 3.26.0: ok, 3.30.1: ok, 3.31.1: ok, 3.34.0: violation, 3.53.1: ok

## 29. `LEFT->INNER-JOIN` on SQLite 3.31.1 (seed 11)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT DISTINCT t1b.c1 || '' AS k0, ABS(t1a.c4) AS k1 FROM (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE (x.c4 = 3 AND x.c1 IS NULL)) AS t1a LEFT JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE (x.c4 IS NULL OR x.c4 = 0) UNION ALL SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1b ON t1a.c4 = t1a.c4 WHERE t1a.c4 <= 3;
-- mutant
SELECT DISTINCT t1b.c1 || '' AS k0, ABS(t1a.c4) AS k1 FROM (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE (x.c4 = 3 AND x.c1 IS NULL)) AS t1a INNER JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE (x.c4 IS NULL OR x.c4 = 0) UNION ALL SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1b ON t1a.c4 = t1a.c4 WHERE t1a.c4 <= 3;
```

Original rows: `[]`

Mutant rows: `["('-0.5', 0.0)", "('-0.5', None)", "('-1.0', 0.0)", "('-1.0', None)", "('0.5', 0.0)", "('0.5', None)", "('1.0', 0.0)", "('1.0', None)", "('10.0', 0.0)", "('10.0', None)", "('10.25', 0.0)", "('10.25', None)"]`

Per version: 3.26.0: ok, 3.30.1: ok, 3.31.1: violation, 3.34.0: ok, 3.53.1: ok

## 30. `EXCEPT->left` on SQLite 3.26.0 (seed 22)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2a.c1 AS k0, t2a.c2 AS k1 FROM t2 AS t2a WHERE (t2a.c15 IS NOT t2a.c1) UNION ALL SELECT DISTINCT t2a.c14 AS k0, t2a.c14 AS k1 FROM t2 AS t2a INNER JOIN (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2b ON t2a.c15 < t2b.c2 LEFT JOIN t2 AS t2c ON t2c.c14 > t2a.c14 WHERE ((LIKELY(t2c.c2 > 0))) OR ((t2b.c3 = ('1')) OR (t2a.c14 > t2b.c1)) EXCEPT SELECT t2a.c3 AS k0, t2a.c15 AS k1 FROM t2 AS t2a WHERE t2a.c3 IS NULL;
-- mutant
SELECT DISTINCT t2a.c1 AS k0, t2a.c2 AS k1 FROM t2 AS t2a WHERE (t2a.c15 IS NOT t2a.c1) UNION ALL SELECT DISTINCT t2a.c14 AS k0, t2a.c14 AS k1 FROM t2 AS t2a INNER JOIN (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2b ON t2a.c15 < t2b.c2 LEFT JOIN t2 AS t2c ON t2c.c14 > t2a.c14 WHERE ((LIKELY(t2c.c2 > 0))) OR ((t2b.c3 = ('1')) OR (t2a.c14 > t2b.c1));
```

Original rows: `["(' 1', ' 1')", "(' 1', 1.5)", "('', None)", "('10', '10')", "('3', 7.0)", "('A', 'A')", "('a', 'a')", "('x', 'x')", '(None, 2.0)', '(None, None)']`

Mutant rows: `["(' 1', ' 1')", "(' 1', 1.5)", "('', None)", "('10', '10')", "('3', 7.0)", "('A', 'A')", "('x', 'x')", '(None, 2.0)', '(None, None)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 31. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 194)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT t2a.c3 AS k0, t2a.c3 AS k1, t2b.c1 AS k2 FROM t2 AS t2a LEFT JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x WHERE (x.c15 > -1 AND x.c1 <= -1)) AS t2b ON (t2a.c2 <> 7) OR (t2a.c2 IS NULL) UNION ALL SELECT DISTINCT t2c.c15 AS k0, t1b.c1 AS k1, t2c.c2 AS k2 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE x.c1 IS NULL UNION ALL SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1b ON t1b.c4 < 7 LEFT JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2c ON (COALESCE(t1b.c1, 5)) > (-1) WHERE EXISTS (SELECT t1s55.c1 FROM t1 AS t1s55 WHERE ((t1s55.c1 > 1)) = 1);
-- mutant
SELECT t2a.c3 AS k0, t2a.c3 AS k1, t2b.c1 AS k2 FROM t2 AS t2a LEFT JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x WHERE (x.c15 > -1 AND x.c1 <= -1)) AS t2b ON (t2a.c2 <> 7) OR (t2a.c2 IS NULL) UNION SELECT DISTINCT t2c.c15 AS k0, t1b.c1 AS k1, t2c.c2 AS k2 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE x.c1 IS NULL UNION ALL SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1b ON t1b.c4 < 7 LEFT JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2c ON (COALESCE(t1b.c1, 5)) > (-1) WHERE EXISTS (SELECT t1s55.c1 FROM t1 AS t1s55 WHERE ((t1s55.c1 > 1)) = 1);
```

Original rows: `['(-1, -1, None)', "(0.25, '-1', 4)", "(0.25, '1', 4)", "(0.25, '4', 4)", "(0.25, 'A', 4)", "(0.5, '-1', 2)", "(0.5, '1', 2)", "(0.5, '4', 2)", "(0.5, 'A', 2)", "(1.0, '-1', 0)", "(1.0, '1', 0)", "(1.0, '4', 0)"]`

Mutant rows: `['(-1, -1, None)', "(0.25, '-1', 4)", "(0.25, '1', 4)", "(0.25, '4', 4)", "(0.25, 'A', 4)", "(0.25, 'a', 4)", "(0.5, '-1', 2)", "(0.5, '1', 2)", "(0.5, '4', 2)", "(0.5, 'A', 2)", "(0.5, 'a', 2)", "(1.0, '-1', 0)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 32. `DISTINCT-add` on SQLite 3.26.0 (seed 237)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT t2a.c3 AS k0, t1b.c1 AS k1 FROM t2 AS t2a INNER JOIN t1 AS t1b ON 1 = 1 WHERE (t1b.c4 IS NOT 10);
-- mutant
SELECT t2a.c3 AS k0, t1b.c1 AS k1 FROM t2 AS t2a INNER JOIN (SELECT DISTINCT * FROM t1 AS t1b) AS t1b ON 1 = 1 WHERE (t1b.c4 IS NOT 10);
```

Original rows: `["(10, '-3')", "(10, '2')", "(10, '3')", "(10, '4')", "(10, '5')", "(10, 'A')", '(10, None)', '(10, None)', "(5, '-3')", "(5, '2')", "(5, '3')", "(5, '4')"]`

Mutant rows: `["(10, '-1')", "(10, '-3')", "(10, '0')", "(10, '2')", "(10, '3')", "(10, '4')", "(10, '5')", "(10, 'A')", '(10, None)', '(10, None)', "(5, '-1')", "(5, '-3')"]`

Per version: 3.26.0: violation, 3.30.1: ok, 3.31.1: ok, 3.34.0: ok, 3.53.1: ok

## 33. `DISTINCT-add` on SQLite 3.26.0 (seed 336)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x UNION ALL SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT (EXISTS (SELECT t1s99.c1 FROM t1 AS t1s99 WHERE (CAST(t1a.c1 AS TEXT)) = ('-1'))) WHERE (t1b.c4 IS NOT t1a.c1);
-- mutant
SELECT DISTINCT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x UNION ALL SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT (EXISTS (SELECT t1s99.c1 FROM t1 AS t1s99 WHERE (CAST(t1a.c1 AS TEXT)) = ('-1'))) WHERE (t1b.c4 IS NOT t1a.c1);
```

Original rows: `['(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)']`

Mutant rows: `['(-1,)', '(-3,)', '(1,)', '(10,)', '(5,)', '(None,)']`

Per version: 3.26.0: violation, 3.30.1: ok, 3.31.1: ok, 3.34.0: ok, 3.53.1: ok

## 34. `DISTINCT-add` on SQLite 3.26.0 (seed 336)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x UNION ALL SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT (EXISTS (SELECT t1s99.c1 FROM t1 AS t1s99 WHERE (CAST(t1a.c1 AS TEXT)) = ('-1'))) WHERE (t1b.c4 IS NOT t1a.c1);
-- mutant
SELECT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x UNION ALL SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1a INNER JOIN (SELECT DISTINCT * FROM t1 AS t1b) AS t1b ON NOT (EXISTS (SELECT t1s99.c1 FROM t1 AS t1s99 WHERE (CAST(t1a.c1 AS TEXT)) = ('-1'))) WHERE (t1b.c4 IS NOT t1a.c1);
```

Original rows: `['(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)']`

Mutant rows: `['(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)', '(-1,)']`

Per version: 3.26.0: violation, 3.30.1: ok, 3.31.1: ok, 3.34.0: ok, 3.53.1: ok

## 35. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 340)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT t2c.c2 AS k0 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE (x.c1 COLLATE NOCASE = 'a' AND x.c1 = '7')) AS t1b ON t1b.c1 = ('7') LEFT JOIN t2 AS t2c ON t1b.c1 IN (SELECT t3i78.c3 FROM t3 AS t3i78 WHERE NOT (t1a.c1 IS NULL)) WHERE (NOT (t1b.c4 = 5)) AND ((t1a.c4 <= t1a.c4) OR ((t1a.c4 LIKE '%'))) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE x.c4 IS NULL) AS t1b ON (t1b.c1 = t1b.c4) AND (t1a.c1 IS NULL) WHERE NOT (t1a.c1 >= 7);
-- mutant
SELECT t2c.c2 AS k0 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE (x.c1 COLLATE NOCASE = 'a' AND x.c1 = '7')) AS t1b ON t1b.c1 = ('7') LEFT JOIN t2 AS t2c ON t1b.c1 IN (SELECT t3i78.c3 FROM t3 AS t3i78 WHERE NOT (t1a.c1 IS NULL)) WHERE (NOT (t1b.c4 = 5)) AND ((t1a.c4 <= t1a.c4) OR ((t1a.c4 LIKE '%'))) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x WHERE x.c4 IS NULL) AS t1b ON (t1b.c1 = t1b.c4) AND (t1a.c1 IS NULL) WHERE NOT (t1a.c1 >= 7);
```

Original rows: `["(' 1',)", "('0',)", "('1',)", "('2',)", "('3',)", "('a',)", '(None,)']`

Mutant rows: `["(' 1',)", "('0',)", "('1',)", "('2',)", "('3',)", "('A',)", "('a',)", '(None,)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 36. `UNION-ALL->UNION` on SQLite 3.26.0 (seed 352)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT t2b.c2 AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (t2b.c2 > t2b.c1) OR (t2b.c15 <= 5) INNER JOIN t1 AS t1c ON 1 = 1 WHERE NOT ((t1c.c4 < t2a.c3) AND (t2b.c14 > 2)) UNION ALL SELECT DISTINCT t3a.c9 AS k0 FROM (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a WHERE (ABS(t3a.c6)) > 1;
-- mutant
SELECT t2b.c2 AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (t2b.c2 > t2b.c1) OR (t2b.c15 <= 5) INNER JOIN t1 AS t1c ON 1 = 1 WHERE NOT ((t1c.c4 < t2a.c3) AND (t2b.c14 > 2)) UNION SELECT DISTINCT t3a.c9 AS k0 FROM (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a WHERE (ABS(t3a.c6)) > 1;
```

Original rows: `["('3',)", "('5',)", "('a',)", '(-3,)', '(-3,)', '(-3,)', '(-3,)', '(-3,)', '(-3,)', '(-3,)', '(-3,)', '(-3,)']`

Mutant rows: `["('3',)", "('5',)", "('A',)", "('a',)", '(-3,)', '(0,)', '(1,)', '(2,)', '(3,)', '(None,)']`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 37. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 515)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t1a.c4 AS k0, t2b.c2 AS k1 FROM t1 AS t1a INNER JOIN (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2b ON (t2b.c3 GLOB '0*') WHERE NOT (t1a.c1 IN (SELECT t1i58.c4 FROM t1 AS t1i58 WHERE (t1i58.c1 LIKE '1%'))) UNION SELECT DISTINCT t2b.c15 AS k0, t3a.c1 AS k1 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c15 IS NOT t3a.c9) WHERE t3a.c2 <= 1;
-- mutant
SELECT DISTINCT t1a.c4 AS k0, t2b.c2 AS k1 FROM t1 AS t1a INNER JOIN (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2b ON (t2b.c3 GLOB '0*') WHERE NOT (t1a.c1 IN (SELECT t1i58.c4 FROM t1 AS t1i58 WHERE (t1i58.c1 LIKE '1%'))) UNION ALL SELECT DISTINCT t2b.c15 AS k0, t3a.c1 AS k1 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c15 IS NOT t3a.c9) WHERE t3a.c2 <= 1;
```

Original rows: `['(-1, None)', '(0, None)', '(1, 3)', '(1, 4)', '(1, None)', '(2, 3)', '(2, 4)', '(2, None)', '(3, 3)', '(3, 4)', '(3, None)', '(None, 3)']`

Mutant rows: `['(-1, None)', '(0, None)', '(1, 3)', '(1, 4)', '(1, None)', '(2, 3)', '(2, 4)', '(2, None)', '(2, None)', '(3, 3)', '(3, 4)', '(3, None)']`

Per version: 3.26.0: violation, 3.30.1: ok, 3.31.1: ok, 3.34.0: ok, 3.53.1: ok

## 38. `DISTINCT-add` on SQLite 3.26.0 (seed 2004)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT DISTINCT COALESCE(t1a.c1, 0) AS k0, t1a.c1 || '' AS k1 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON EXISTS (SELECT t2s93.c1 FROM t2 AS t2s93 WHERE t2s93.c14 <> t1a.c4) WHERE t3b.c1 <> (-1) UNION ALL SELECT DISTINCT t1a.c1 AS k0, ABS(t1a.c1) AS k1 FROM t1 AS t1a WHERE NOT (EXISTS (SELECT t2s0.c1 FROM t2 AS t2s0 WHERE (t1a.c4 = 1) AND (t2s0.c3 < 7))) EXCEPT SELECT DISTINCT t2a.c15 AS k0, t2a.c15 AS k1 FROM t2 AS t2a INNER JOIN t3 AS t3b ON NOT (EXISTS (SELECT t1s38.c1 FROM t1 AS t1s38 WHERE t2a.c14 >= t3b.c8));
-- mutant
SELECT DISTINCT * FROM (SELECT DISTINCT COALESCE(t1a.c1, 0) AS k0, t1a.c1 || '' AS k1 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON EXISTS (SELECT t2s93.c1 FROM t2 AS t2s93 WHERE t2s93.c14 <> t1a.c4) WHERE t3b.c1 <> (-1)) AS vs_d4 UNION ALL SELECT DISTINCT t1a.c1 AS k0, ABS(t1a.c1) AS k1 FROM t1 AS t1a WHERE NOT (EXISTS (SELECT t2s0.c1 FROM t2 AS t2s0 WHERE (t1a.c4 = 1) AND (t2s0.c3 < 7))) EXCEPT SELECT DISTINCT t2a.c15 AS k0, t2a.c15 AS k1 FROM t2 AS t2a INNER JOIN t3 AS t3b ON NOT (EXISTS (SELECT t1s38.c1 FROM t1 AS t1s38 WHERE t2a.c14 >= t3b.c8));
```

Original rows: `["('-1', '-1')", "('-1', 1.0)", "('01', '01')", "('01', 1.0)", "('1', '1')", "('1', 1.0)", "('3', '3')", "('3', 3.0)", "('A', 'A')", "('A', 0.0)", "('a', 'a')", "('x', 'x')"]`

Mutant rows: `["('-1', '-1')", "('-1', 1.0)", "('01', '01')", "('01', 1.0)", "('1', '1')", "('1', 1.0)", "('3', '3')", "('3', 3.0)", "('A', 'A')", "('A', 0.0)", "('a', 'a')", "('a', 0.0)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: collation

## 39. `UNION->UNION-ALL` on SQLite 3.26.0 (seed 2011)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t1a.c1 AS k0, t3b.c2 AS k1, t1a.c4 AS k2 FROM t1 AS t1a INNER JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3b ON 1 = 1 WHERE t3b.c9 = t1a.c4 INTERSECT SELECT DISTINCT t3a.c2 AS k0, t3a.c7 AS k1, t3a.c1 AS k2 FROM t3 AS t3a WHERE (t3a.c9 BETWEEN 7 AND 7) UNION SELECT DISTINCT t3a.c9 || '' AS k0, t2b.c1 AS k1, t3a.c7 AS k2 FROM t3 AS t3a INNER JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2b ON 1 = 1 WHERE t2b.c1 <> 10;
-- mutant
SELECT t1a.c1 AS k0, t3b.c2 AS k1, t1a.c4 AS k2 FROM t1 AS t1a INNER JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3b ON 1 = 1 WHERE t3b.c9 = t1a.c4 INTERSECT SELECT DISTINCT t3a.c2 AS k0, t3a.c7 AS k1, t3a.c1 AS k2 FROM t3 AS t3a WHERE (t3a.c9 BETWEEN 7 AND 7) UNION ALL SELECT DISTINCT t3a.c9 || '' AS k0, t2b.c1 AS k1, t3a.c7 AS k2 FROM t3 AS t3a INNER JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2b ON 1 = 1 WHERE t2b.c1 <> 10;
```

Original rows: `["('-1', '', 'x')", "('-1', '-3', 'x')", "('-1', '0', 'x')", "('-1', '01', 'x')", "('-1', '2', 'x')", "('-1', '4', 'x')", "('-1', 'B', 'x')", "('-1', 'a', 'x')", "('-1', 'b', 'x')", "('-3', '', 'a')", "('-3', '', 'x')", "('-3', '-3', 'a')"]`

Mutant rows: `["('-1', '', 'x')", "('-1', '-3', 'x')", "('-1', '0', 'x')", "('-1', '01', 'x')", "('-1', '2', 'x')", "('-1', '4', 'x')", "('-1', 'a', 'x')", "('-1', 'b', 'x')", "('-3', '', 'a')", "('-3', '', 'x')", "('-3', '-3', 'a')", "('-3', '-3', 'x')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 40. `INTERSECT->operand` on SQLite 3.26.0 (seed 2011)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t1a.c1 AS k0, t3b.c2 AS k1, t1a.c4 AS k2 FROM t1 AS t1a INNER JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3b ON 1 = 1 WHERE t3b.c9 = t1a.c4 INTERSECT SELECT DISTINCT t3a.c2 AS k0, t3a.c7 AS k1, t3a.c1 AS k2 FROM t3 AS t3a WHERE (t3a.c9 BETWEEN 7 AND 7) UNION SELECT DISTINCT t3a.c9 || '' AS k0, t2b.c1 AS k1, t3a.c7 AS k2 FROM t3 AS t3a INNER JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2b ON 1 = 1 WHERE t2b.c1 <> 10;
-- mutant
SELECT DISTINCT t3a.c2 AS k0, t3a.c7 AS k1, t3a.c1 AS k2 FROM t3 AS t3a WHERE (t3a.c9 BETWEEN 7 AND 7) UNION SELECT DISTINCT t3a.c9 || '' AS k0, t2b.c1 AS k1, t3a.c7 AS k2 FROM t3 AS t3a INNER JOIN (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c14 AS c14, x.c15 AS c15 FROM t2 AS x) AS t2b ON 1 = 1 WHERE t2b.c1 <> 10;
```

Original rows: `["('-1', '', 'x')", "('-1', '-3', 'x')", "('-1', '0', 'x')", "('-1', '01', 'x')", "('-1', '2', 'x')", "('-1', '4', 'x')", "('-1', 'B', 'x')", "('-1', 'a', 'x')", "('-1', 'b', 'x')", "('-3', '', 'a')", "('-3', '', 'x')", "('-3', '-3', 'a')"]`

Mutant rows: `["('-1', '', 'x')", "('-1', '-3', 'x')", "('-1', '0', 'x')", "('-1', '01', 'x')", "('-1', '2', 'x')", "('-1', '4', 'x')", "('-1', 'a', 'x')", "('-1', 'b', 'x')", "('-3', '', 'a')", "('-3', '', 'x')", "('-3', '-3', 'a')", "('-3', '-3', 'x')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 41. `DISTINCT-add` on SQLite 3.26.0 (seed 2022)

Expected relation: Down. Verdict: violation.

```sql
-- original
SELECT DISTINCT t1b.c1 AS k0, t1a.c4 AS k1, t1a.c1 AS k2 FROM t1 AS t1a INNER JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1b ON 1 = 1 WHERE (EXISTS (SELECT t2s79.c1 FROM t2 AS t2s79 WHERE (CAST(t2s79.c14 AS INTEGER)) = 1)) AND (NOT (t1a.c4 IS NULL)) INTERSECT SELECT DISTINCT t3a.c6 AS k0, t3a.c3 AS k1, t3a.c7 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t3a.c2 || '') = ('7') WHERE (COALESCE(t2b.c15, 1)) > 10 UNION ALL SELECT DISTINCT t3b.c1 AS k0, t3b.c3 || '' AS k1, t1a.c4 AS k2 FROM t1 AS t1a INNER JOIN (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x WHERE x.c1 = 10 UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3b ON t3b.c1 < 7 WHERE ((t3b.c7 IS NOT 5)) AND ((t3b.c8 < 2) AND ((t1a.c1 IS 2)));
-- mutant
SELECT DISTINCT t1b.c1 AS k0, t1a.c4 AS k1, t1a.c1 AS k2 FROM t1 AS t1a INNER JOIN (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1b ON 1 = 1 WHERE (EXISTS (SELECT t2s79.c1 FROM t2 AS t2s79 WHERE (CAST(t2s79.c14 AS INTEGER)) = 1)) AND (NOT (t1a.c4 IS NULL)) INTERSECT SELECT DISTINCT t3a.c6 AS k0, t3a.c3 AS k1, t3a.c7 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t3a.c2 || '') = ('7') WHERE (COALESCE(t2b.c15, 1)) > 10 UNION ALL SELECT DISTINCT t3b.c1 AS k0, t3b.c3 || '' AS k1, t1a.c4 AS k2 FROM t1 AS t1a INNER JOIN (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x WHERE x.c1 = 10 UNION ALL SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3b ON t3b.c1 < 7 WHERE ((t3b.c7 IS NOT 5)) AND ((t3b.c8 < 2) AND ((t1a.c1 IS 2)));
```

Original rows: `[]`

Mutant rows: `["('2', '1', None)"]`

Per version: 3.26.0: violation, 3.30.1: ok, 3.31.1: ok, 3.34.0: ok, 3.53.1: ok

## 42. `EXCEPT->left` on SQLite 3.26.0 (seed 2022)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT t1c.c4 AS k0, t2a.c3 AS k1, t2a.c3 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (CAST(t2a.c3 AS INTEGER)) = 1 LEFT JOIN t1 AS t1c ON t1b.c1 IN (SELECT t2i1.c1 FROM t2 AS t2i1 WHERE t1b.c4 >= 2) UNION ALL SELECT DISTINCT t1a.c4 AS k0, t1a.c4 AS k1, t1a.c4 AS k2 FROM (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1a EXCEPT SELECT CAST(t3c.c7 AS INTEGER) AS k0, t1a.c1 AS k1, t1a.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1b ON t1b.c1 <= 7 INNER JOIN t3 AS t3c ON (t1b.c1 < t1b.c1) OR (t1a.c4 >= 0) WHERE ((t3c.c7 > 1)) = 1;
-- mutant
SELECT t1c.c4 AS k0, t2a.c3 AS k1, t2a.c3 AS k2 FROM t2 AS t2a INNER JOIN t1 AS t1b ON (CAST(t2a.c3 AS INTEGER)) = 1 LEFT JOIN t1 AS t1c ON t1b.c1 IN (SELECT t2i1.c1 FROM t2 AS t2i1 WHERE t1b.c4 >= 2) UNION ALL SELECT DISTINCT t1a.c4 AS k0, t1a.c4 AS k1, t1a.c4 AS k2 FROM (SELECT x.c1 AS c1, x.c4 AS c4 FROM t1 AS x) AS t1a;
```

Original rows: `["('0', '0', '0')", "('0', 1.0, 1.0)", "('1', '1', '1')", "('1', 1.0, 1.0)", "('2', '2', '2')", "('2', 1.0, 1.0)", "('A', 'A', 'A')", "('A', 1.0, 1.0)", "('a', 'a', 'a')", '(None, 1.0, 1.0)', '(None, None, None)']`

Mutant rows: `["('0', '0', '0')", "('0', 1.0, 1.0)", "('0', 1.0, 1.0)", "('1', '1', '1')", "('1', 1.0, 1.0)", "('1', 1.0, 1.0)", "('1', 1.0, 1.0)", "('1', 1.0, 1.0)", "('2', '2', '2')", "('2', 1.0, 1.0)", "('2', 1.0, 1.0)", "('A', 1.0, 1.0)"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: ok

## 43. `INNER->LEFT-JOIN` on SQLite 3.26.0 (seed 2009)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2b.c14 + 0 AS k0, t2b.c15 AS k1 FROM (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a INNER JOIN t2 AS t2b ON (LIKELY(t3a.c8 > 1)) WHERE EXISTS (SELECT t2s99.c1 FROM t2 AS t2s99 WHERE (CAST(t3a.c9 AS TEXT)) = ('0')) UNION ALL SELECT t1a.c4 AS k0, t1a.c4 AS k1 FROM t1 AS t1a WHERE t1a.c1 = ('1') UNION ALL SELECT DISTINCT t3a.c1 AS k0, t3a.c8 AS k1 FROM (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x WHERE x.c8 >= 1 UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a INNER JOIN t1 AS t1b ON NOT (t3a.c3 <= 3) WHERE (t3a.c2 COLLATE NOCASE) = ('a');
-- mutant
SELECT DISTINCT t2b.c14 + 0 AS k0, t2b.c15 AS k1 FROM (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a INNER JOIN t2 AS t2b ON (LIKELY(t3a.c8 > 1)) WHERE EXISTS (SELECT t2s99.c1 FROM t2 AS t2s99 WHERE (CAST(t3a.c9 AS TEXT)) = ('0')) UNION ALL SELECT t1a.c4 AS k0, t1a.c4 AS k1 FROM t1 AS t1a WHERE t1a.c1 = ('1') UNION ALL SELECT DISTINCT t3a.c1 AS k0, t3a.c8 AS k1 FROM (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x WHERE x.c8 >= 1 UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a LEFT JOIN t1 AS t1b ON NOT (t3a.c3 <= 3) WHERE (t3a.c2 COLLATE NOCASE) = ('a');
```

Original rows: `["('2', '2')", "('B', 'A')"]`

Mutant rows: `["('2', '2')", "('b', 'a')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: collation

## 44. `cond->TRUE` on SQLite 3.26.0 (seed 2009)

Expected relation: Up. Verdict: violation.

```sql
-- original
SELECT DISTINCT t2b.c14 + 0 AS k0, t2b.c15 AS k1 FROM (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a INNER JOIN t2 AS t2b ON (LIKELY(t3a.c8 > 1)) WHERE EXISTS (SELECT t2s99.c1 FROM t2 AS t2s99 WHERE (CAST(t3a.c9 AS TEXT)) = ('0')) UNION ALL SELECT t1a.c4 AS k0, t1a.c4 AS k1 FROM t1 AS t1a WHERE t1a.c1 = ('1') UNION ALL SELECT DISTINCT t3a.c1 AS k0, t3a.c8 AS k1 FROM (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x WHERE x.c8 >= 1 UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a INNER JOIN t1 AS t1b ON NOT (t3a.c3 <= 3) WHERE (t3a.c2 COLLATE NOCASE) = ('a');
-- mutant
SELECT DISTINCT t2b.c14 + 0 AS k0, t2b.c15 AS k1 FROM (SELECT DISTINCT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a INNER JOIN t2 AS t2b ON (LIKELY(t3a.c8 > 1)) WHERE EXISTS (SELECT t2s99.c1 FROM t2 AS t2s99 WHERE (CAST(t3a.c9 AS TEXT)) = ('0')) UNION ALL SELECT t1a.c4 AS k0, t1a.c4 AS k1 FROM t1 AS t1a WHERE t1a.c1 = ('1') UNION ALL SELECT DISTINCT t3a.c1 AS k0, t3a.c8 AS k1 FROM (SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x WHERE x.c8 >= 1 UNION ALL SELECT x.c1 AS c1, x.c2 AS c2, x.c3 AS c3, x.c6 AS c6, x.c7 AS c7, x.c8 AS c8, x.c9 AS c9 FROM t3 AS x) AS t3a CROSS JOIN t1 AS t1b WHERE (t3a.c2 COLLATE NOCASE) = ('a');
```

Original rows: `["('2', '2')", "('B', 'A')"]`

Mutant rows: `["('2', '2')", "('b', 'a')"]`

Per version: 3.26.0: violation, 3.30.1: violation, 3.31.1: violation, 3.34.0: violation, 3.53.1: collation

