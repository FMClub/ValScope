# Reduced SQLite violations

`python3 bridge/reduce_sqlite.py results/sqlite-confirmed.jsonl --lib 3.26.0=LIB ... --latest LIB-3.54.1 --out reduced.jsonl --sql repro`

Each confirmed pair is reduced greedily: the query (replace a compound by an arm, an AND /
OR by an operand, drop a clause, a join or a column, replace a comparison by 1 or 0), then
the database (rows, indexes and ANALYZE removed). After every query step the verified
mutator runs again on the smaller query, and a step is kept only if a mutant of the same
rule still violates the relation on the reporting release AND the relation holds on
3.54.1 (`--latest`), so the reduced pair still shows the bug of the pair, fixed since.
The theorem of the rule applies to every reduced pair.

42 of the 43 pairs are reduced: queries from 452 to 122 characters on average (80 to 202),
databases from 33 to 6 statements (5 to 20). Pair 40 is not reduced: the collation-law
check rejects its query (it applies `||` to text columns above a de-duplication). Each
reduced pair is a self-contained script in `results/sqlite-repro/pair-N.sql`.

-- pair 1 (UNION->UNION-ALL, expected Up): 365 -> 156 characters
    original: SELECT t2b.c2 AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0) UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a UNION SELECT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t2b.c2 AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0) UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a UNION ALL SELECT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 14 / 31

-- pair 2 (UNION-ALL->UNION, expected Down): 454 -> 115 characters
    original: SELECT t3b.c1 AS k2 FROM t2 AS t2a LEFT JOIN t3 AS t3b ON (0) UNION ALL SELECT DISTINCT t1a.c1 AS k2 FROM t1 AS t1a
    mutant  : SELECT t3b.c1 AS k2 FROM t2 AS t2a LEFT JOIN t3 AS t3b ON (0) UNION SELECT DISTINCT t1a.c1 AS k2 FROM t1 AS t1a
    rows    : 19 / 8

-- pair 3 (UNION-ALL->UNION, expected Down): 579 -> 88 characters
    original: SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t2a.c2 AS k0 FROM t2 AS t2a
    mutant  : SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t2a.c2 AS k0 FROM t2 AS t2a
    rows    : 16 / 14

-- pair 4 (UNION-ALL->UNION, expected Down): 579 -> 88 characters
    original: SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t2a.c2 AS k0 FROM t2 AS t2a
    mutant  : SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t2a.c2 AS k0 FROM t2 AS t2a
    rows    : 16 / 14

-- pair 5 (UNION->UNION-ALL, expected Up): 727 -> 146 characters
    original: SELECT t1a.c1 AS k0, t1a.c4 AS k1 FROM t1 AS t1a UNION SELECT DISTINCT t1c.c1 AS k0, t2a.c3 AS k1 FROM t2 AS t2a INNER JOIN t1 AS t1c ON NOT ((0))
    mutant  : SELECT t1a.c1 AS k0, t1a.c4 AS k1 FROM t1 AS t1a UNION ALL SELECT DISTINCT t1c.c1 AS k0, t2a.c3 AS k1 FROM t2 AS t2a INNER JOIN t1 AS t1c ON NOT ((0))
    rows    : 42 / 38

-- pair 6 (UNION-ALL->UNION, expected Down): 712 -> 115 characters
    original: SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 9 / 6

-- pair 7 (UNION-ALL->UNION, expected Down): 712 -> 115 characters
    original: SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t3b.c3 AS k0 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 9 / 6

-- pair 8 (UNION->UNION-ALL, expected Up): 612 -> 118 characters
    original: SELECT t2a.c3 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t1c.c4 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1c ON NOT ((0))
    mutant  : SELECT t2a.c3 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1c.c4 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1c ON NOT ((0))
    rows    : 8 / 8

-- pair 9 (UNION->UNION-ALL, expected Up): 572 -> 191 characters
    original: SELECT t3a.c7 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON NOT ((0)) UNION SELECT t2b.c2 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (0)
    mutant  : SELECT t3a.c7 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON NOT ((0)) UNION ALL SELECT t2b.c2 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (0)
    rows    : 15 / 17

-- pair 10 (UNION->UNION-ALL, expected Up): 455 -> 112 characters
    original: SELECT t3c.c6 AS k0 FROM t3 AS t3a INNER JOIN t3 AS t3c ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t3c.c6 AS k0 FROM t3 AS t3a INNER JOIN t3 AS t3c ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 8 / 7

-- pair 11 (UNION->UNION-ALL, expected Up): 259 -> 84 characters
    original: SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a
    mutant  : SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a
    rows    : 12 / 12

-- pair 12 (UNION->UNION-ALL, expected Up): 361 -> 113 characters
    original: SELECT t3a.c9 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (0) UNION SELECT DISTINCT t2a.c14 AS k2 FROM t2 AS t2a
    mutant  : SELECT t3a.c9 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (0) UNION ALL SELECT DISTINCT t2a.c14 AS k2 FROM t2 AS t2a
    rows    : 6 / 5

-- pair 13 (UNION-ALL->UNION, expected Down): 358 -> 89 characters
    original: SELECT t3a.c3 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t2a.c14 AS k0 FROM t2 AS t2a
    mutant  : SELECT t3a.c3 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t2a.c14 AS k0 FROM t2 AS t2a
    rows    : 9 / 9

-- pair 14 (UNION->UNION-ALL, expected Up): 514 -> 112 characters
    original: SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t2c.c1 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2c ON (1)
    mutant  : SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t2c.c1 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2c ON (1)
    rows    : 10 / 10

-- pair 15 (UNION->UNION-ALL, expected Up): 400 -> 112 characters
    original: SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t2c.c1 AS k0 FROM t2 AS t2a INNER JOIN t2 AS t2c ON (1)
    mutant  : SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t2c.c1 AS k0 FROM t2 AS t2a INNER JOIN t2 AS t2c ON (1)
    rows    : 8 / 9

-- pair 16 (UNION->UNION-ALL, expected Up): 662 -> 112 characters
    original: SELECT t2a.c1 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t2b.c2 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (1)
    mutant  : SELECT t2a.c1 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2b.c2 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (1)
    rows    : 7 / 7

-- pair 17 (UNION->UNION-ALL, expected Up): 527 -> 84 characters
    original: SELECT t1a.c4 AS k1 FROM t1 AS t1a UNION SELECT DISTINCT t3a.c2 AS k1 FROM t3 AS t3a
    mutant  : SELECT t1a.c4 AS k1 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c2 AS k1 FROM t3 AS t3a
    rows    : 17 / 19

-- pair 18 (UNION->UNION-ALL, expected Up): 384 -> 112 characters
    original: SELECT t2b.c2 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (0) UNION SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a
    mutant  : SELECT t2b.c2 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (0) UNION ALL SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a
    rows    : 9 / 8

-- pair 19 (UNION->UNION-ALL, expected Up): 613 -> 140 characters
    original: SELECT t1b.c1 AS k1 FROM t3 AS t3a INNER JOIN t1 AS t1b ON (0) UNION SELECT DISTINCT t3b.c8 AS k1 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (1)
    mutant  : SELECT t1b.c1 AS k1 FROM t3 AS t3a INNER JOIN t1 AS t1b ON (0) UNION ALL SELECT DISTINCT t3b.c8 AS k1 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (1)
    rows    : 9 / 8

-- pair 20 (UNION->UNION-ALL, expected Up): 173 -> 84 characters
    original: SELECT t2a.c2 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a
    mutant  : SELECT t2a.c2 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a
    rows    : 15 / 17

-- pair 21 (UNION->UNION-ALL, expected Up): 402 -> 139 characters
    original: SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a UNION SELECT t1a.c1 AS k0 FROM t1 AS t1a WHERE (0)
    mutant  : SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a UNION ALL SELECT t1a.c1 AS k0 FROM t1 AS t1a WHERE (0)
    rows    : 13 / 15

-- pair 22 (UNION->UNION-ALL, expected Up): 568 -> 140 characters
    original: SELECT t2b.c2 AS k1 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (0) UNION SELECT DISTINCT t3b.c2 AS k1 FROM t3 AS t3a INNER JOIN t3 AS t3b ON (1)
    mutant  : SELECT t2b.c2 AS k1 FROM t1 AS t1a INNER JOIN t2 AS t2b ON (0) UNION ALL SELECT DISTINCT t3b.c2 AS k1 FROM t3 AS t3a INNER JOIN t3 AS t3b ON (1)
    rows    : 9 / 8

-- pair 23 (EXCEPT->left, expected Up): 419 -> 130 characters
    original: SELECT t3a.c8 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a EXCEPT SELECT t2a.c2 AS k0 FROM t2 AS t2a
    mutant  : SELECT t3a.c8 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a
    rows    : 11 / 17

-- pair 24 (UNION->UNION-ALL, expected Up): 401 -> 112 characters
    original: SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON (1)
    mutant  : SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON (1)
    rows    : 12 / 11

-- pair 25 (UNION->UNION-ALL, expected Up): 101 -> 84 characters
    original: SELECT t3a.c3 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a
    mutant  : SELECT t3a.c3 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a
    rows    : 15 / 17

-- pair 26 (cond->TRUE, expected Up): 573 -> 148 characters
    original: SELECT t3b.c6 AS k1 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t1a.c4 = 1) AND (t1a.c4 = t1a.c4) LEFT JOIN t2 AS t2c ON NOT ((0)) WHERE t2c.c14 = t3b.c1
    mutant  : SELECT t3b.c6 AS k1 FROM t1 AS t1a LEFT JOIN t3 AS t3b ON (t1a.c4 = 1) AND (t1a.c4 = t1a.c4) LEFT JOIN t2 AS t2c ON NOT ((0)) WHERE 1 = 1
    rows    : 36 / 100

-- pair 27 (cond->TRUE, expected Up): 211 -> 136 characters
    original: SELECT t3a.c1 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (1) WHERE t2b.c3 IN (SELECT t3i27.c2 FROM t3 AS t3i27 WHERE t3i27.c9 IS NULL)
    mutant  : SELECT t3a.c1 AS k0 FROM t3 AS t3a CROSS JOIN t2 AS t2b WHERE t2b.c3 IN (SELECT t3i27.c2 FROM t3 AS t3i27 WHERE t3i27.c9 IS NULL)
    rows    : 12 / 1

-- pair 28 (DISTINCT-add, expected Down): 158 -> 104 characters
    original: SELECT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 IN (SELECT t2i75.c14 FROM t2 AS t2i75)
    mutant  : SELECT DISTINCT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 IN (SELECT t2i75.c14 FROM t2 AS t2i75)
    rows    : 5 / 6

-- pair 29 (LEFT->INNER-JOIN, expected Down): 329 -> 174 characters
    original: SELECT ABS(t1a.c4) AS k1 FROM (SELECT x.c4 AS c4 FROM t1 AS x WHERE (x.c4 = 3) AND (x.c1 IS NULL)) AS t1a LEFT JOIN (SELECT x.c1 AS c1 FROM t1 AS x) AS t1b ON t1a.c4 = t1a.c4
    mutant  : SELECT ABS(t1a.c4) AS k1 FROM (SELECT x.c4 AS c4 FROM t1 AS x WHERE (x.c4 = 3) AND (x.c1 IS NULL)) AS t1a INNER JOIN (SELECT x.c1 AS c1 FROM t1 AS x) AS t1b ON t1a.c4 = t1a.c4
    rows    : 0 / 22

-- pair 30 (EXCEPT->left, expected Up): 481 -> 131 characters
    original: SELECT t2a.c1 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2a.c14 AS k0 FROM t2 AS t2a EXCEPT SELECT t2a.c3 AS k0 FROM t2 AS t2a
    mutant  : SELECT t2a.c1 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2a.c14 AS k0 FROM t2 AS t2a
    rows    : 8 / 11

-- pair 31 (UNION-ALL->UNION, expected Down): 675 -> 145 characters
    original: SELECT t2a.c3 AS k1 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1b.c1 AS k1 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1 FROM t1 AS x) AS t1b ON (1)
    mutant  : SELECT t2a.c3 AS k1 FROM t2 AS t2a UNION SELECT DISTINCT t1b.c1 AS k1 FROM t1 AS t1a LEFT JOIN (SELECT x.c1 AS c1 FROM t1 AS x) AS t1b ON (1)
    rows    : 12 / 10

-- pair 32 (DISTINCT-add, expected Down): 103 -> 80 characters
    original: SELECT t1b.c1 AS k1 FROM t2 AS t2a CROSS JOIN t1 AS t1b WHERE (t1b.c4 IS NOT 10)
    mutant  : SELECT t1b.c1 AS k1 FROM t2 AS t2a CROSS JOIN (SELECT DISTINCT * FROM t1 AS t1b) AS t1b WHERE (t1b.c4 IS NOT 10)
    rows    : 40 / 50

-- pair 33 (DISTINCT-add, expected Down): 268 -> 127 characters
    original: SELECT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT ((0)) WHERE (t1b.c4 IS NOT t1a.c1)
    mutant  : SELECT DISTINCT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT ((0)) WHERE (t1b.c4 IS NOT t1a.c1)
    rows    : 39 / 6

-- pair 34 (DISTINCT-add, expected Down): 268 -> 127 characters
    original: SELECT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT ((0)) WHERE (t1b.c4 IS NOT t1a.c1)
    mutant  : SELECT DISTINCT t1b.c4 AS k0 FROM (SELECT x.c1 AS c1 FROM t1 AS x) AS t1a INNER JOIN t1 AS t1b ON NOT ((0)) WHERE (t1b.c4 IS NOT t1a.c1)
    rows    : 39 / 6

-- pair 35 (UNION-ALL->UNION, expected Down): 532 -> 115 characters
    original: SELECT t2c.c2 AS k0 FROM t1 AS t1a LEFT JOIN t2 AS t2c ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t2c.c2 AS k0 FROM t1 AS t1a LEFT JOIN t2 AS t2c ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 20 / 9

-- pair 36 (UNION-ALL->UNION, expected Down): 351 -> 145 characters
    original: SELECT t2b.c2 AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0) UNION ALL SELECT DISTINCT t3a.c9 AS k0 FROM (SELECT x.c9 AS c9 FROM t3 AS x) AS t3a
    mutant  : SELECT t2b.c2 AS k0 FROM t2 AS t2a LEFT JOIN t2 AS t2b ON (0) UNION SELECT DISTINCT t3a.c9 AS k0 FROM (SELECT x.c9 AS c9 FROM t3 AS x) AS t3a
    rows    : 15 / 7

-- pair 37 (UNION->UNION-ALL, expected Up): 406 -> 133 characters
    original: SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION SELECT DISTINCT t2b.c15 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c15 IS NOT t3a.c9)
    mutant  : SELECT t1a.c4 AS k0 FROM t1 AS t1a UNION ALL SELECT DISTINCT t2b.c15 AS k0 FROM t3 AS t3a INNER JOIN t2 AS t2b ON (t2b.c15 IS NOT t3a.c9)
    rows    : 7 / 9

-- pair 38 (DISTINCT-add, expected Down): 513 -> 163 characters
    original: SELECT DISTINCT COALESCE(t1a.c1, 0) AS k0 FROM t1 AS t1a WHERE (0) UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a EXCEPT SELECT t2a.c15 AS k0 FROM t2 AS t2a
    mutant  : SELECT DISTINCT * FROM (SELECT DISTINCT COALESCE(t1a.c1, 0) AS k0 FROM t1 AS t1a WHERE (0)) AS vs_d3 UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a EXCEPT SELECT t2a.c15 AS k0 FROM t2 AS t2a
    rows    : 6 / 7

-- pair 39 (UNION->UNION-ALL, expected Up): 750 -> 84 characters
    original: SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION SELECT DISTINCT t3a.c7 AS k2 FROM t3 AS t3a
    mutant  : SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c7 AS k2 FROM t3 AS t3a
    rows    : 14 / 15

-- pair 41 (EXCEPT->left, expected Up): 530 -> 202 characters
    original: SELECT t2a.c3 AS k1, t2a.c3 AS k2 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k1, t1a.c4 AS k2 FROM (SELECT x.c4 AS c4 FROM t1 AS x) AS t1a EXCEPT SELECT t1a.c1 AS k1, t1a.c4 AS k2 FROM t1 AS t1a
    mutant  : SELECT t2a.c3 AS k1, t2a.c3 AS k2 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k1, t1a.c4 AS k2 FROM (SELECT x.c4 AS c4 FROM t1 AS x) AS t1a
    rows    : 12 / 17

-- pair 42 (UNION->UNION-ALL, expected Up): 388 -> 112 characters
    original: SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION SELECT DISTINCT t3b.c1 AS k2 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (1)
    mutant  : SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3b.c1 AS k2 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (1)
    rows    : 12 / 18

-- pair 43 (UNION-ALL->UNION, expected Down): 543 -> 89 characters
    original: SELECT t2a.c2 AS k1 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2a.c14 AS k1 FROM t2 AS t2a
    mutant  : SELECT t2a.c2 AS k1 FROM t2 AS t2a UNION SELECT DISTINCT t2a.c14 AS k1 FROM t2 AS t2a
    rows    : 16 / 14

