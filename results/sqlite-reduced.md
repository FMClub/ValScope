# Reduced SQLite violations

`python3 bridge/reduce_sqlite.py results/sqlite-confirmed.jsonl --lib 3.26.0=LIB ... --latest LIB-3.54.1 --boundaries results/sqlite-bisect-original.jsonl --src sqlite-src --out reduced.jsonl --sql repro`

Each confirmed pair is reduced greedily, query then database. After every query step the
verified mutator runs again, so every reduced pair is a pair the engine produced and the
theorem of its rule applies. A step is kept only if the pair keeps its verdict on every
witness: violated on the reporting release, on the last bad commit and on the introducing
commit of its bug, and not violated on the fixing commit, on the last good commit and on
3.54.1 (`--boundaries`, `--latest`). So a reduced pair shows the same bug as its pair.

All 64 pairs are reduced: queries from 440 to 124 characters on average (80 to 233),
databases to 6 statements on average (5 to 14); 63 of the 64 databases no longer need
`WITHOUT ROWID`. Each reduced pair is a self-contained script in
`results/sqlite-repro/pair-N.sql`.

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
    mutant  : SELECT t1b.c1 AS k0 FROM t3 AS t3a INNER JOIN t1 AS t1b ON t3a.c6 IN (SELECT t2i75.c14 FROM t2 AS t2i75) GROUP BY t3a.c1, t3a.c2, t3a.c3, t3a.c6, t3a.c7, t3a.c8, t3a.c9, t3a.rid, t1b.c1, t1b.c4
    rows    : 5 / 40

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

-- pair 38 (UNION->UNION-ALL, expected Up): 750 -> 176 characters
    original: SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION SELECT DISTINCT t3a.c7 AS k2 FROM t3 AS t3a CROSS JOIN (SELECT x.c1 AS c1 FROM t2 AS x UNION ALL SELECT x.c1 AS c1 FROM t2 AS x) AS t2b
    mutant  : SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3a.c7 AS k2 FROM t3 AS t3a CROSS JOIN (SELECT x.c1 AS c1 FROM t2 AS x UNION ALL SELECT x.c1 AS c1 FROM t2 AS x) AS t2b
    rows    : 14 / 15

-- pair 39 (DISTINCT-add, expected Down): 850 -> 134 characters
    original: SELECT t3b.c3 || '' AS k1 FROM t1 AS t1a INNER JOIN (SELECT x.c3 AS c3, x.c7 AS c7 FROM t3 AS x) AS t3b ON (1) WHERE (t3b.c7 IS NOT 5)
    mutant  : SELECT t3b.c3 || '' AS k1 FROM t1 AS t1a INNER JOIN (SELECT x.c3 AS c3, x.c7 AS c7 FROM (SELECT DISTINCT * FROM t3 AS x) AS x) AS t3b ON (1) WHERE (t3b.c7 IS NOT 5)
    rows    : 60 / 90

-- pair 40 (EXCEPT->left, expected Up): 530 -> 202 characters
    original: SELECT t2a.c3 AS k1, t2a.c3 AS k2 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k1, t1a.c4 AS k2 FROM (SELECT x.c4 AS c4 FROM t1 AS x) AS t1a EXCEPT SELECT t1a.c1 AS k1, t1a.c4 AS k2 FROM t1 AS t1a
    mutant  : SELECT t2a.c3 AS k1, t2a.c3 AS k2 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k1, t1a.c4 AS k2 FROM (SELECT x.c4 AS c4 FROM t1 AS x) AS t1a
    rows    : 12 / 17

-- pair 41 (UNION->UNION-ALL, expected Up): 388 -> 112 characters
    original: SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION SELECT DISTINCT t3b.c1 AS k2 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (1)
    mutant  : SELECT t1a.c4 AS k2 FROM t1 AS t1a UNION ALL SELECT DISTINCT t3b.c1 AS k2 FROM t1 AS t1a INNER JOIN t3 AS t3b ON (1)
    rows    : 12 / 18

-- pair 42 (UNION-ALL->UNION, expected Down): 543 -> 89 characters
    original: SELECT t2a.c2 AS k1 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2a.c14 AS k1 FROM t2 AS t2a
    mutant  : SELECT t2a.c2 AS k1 FROM t2 AS t2a UNION SELECT DISTINCT t2a.c14 AS k1 FROM t2 AS t2a
    rows    : 16 / 14

-- pair 43 (UNION-ALL->UNION, expected Down): 339 -> 89 characters
    original: SELECT t2a.c15 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a
    mutant  : SELECT t2a.c15 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t3a.c2 AS k0 FROM t3 AS t3a
    rows    : 15 / 10

-- pair 44 (UNION-ALL->UNION, expected Down): 612 -> 144 characters
    original: SELECT t1c.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1c ON (0) UNION ALL SELECT DISTINCT t2b.c15 AS k2 FROM t2 AS t2a INNER JOIN t2 AS t2b ON (1)
    mutant  : SELECT t1c.c4 AS k2 FROM t1 AS t1a LEFT JOIN t1 AS t1c ON (0) UNION SELECT DISTINCT t2b.c15 AS k2 FROM t2 AS t2a INNER JOIN t2 AS t2b ON (1)
    rows    : 17 / 8

-- pair 45 (UNION-ALL->UNION, expected Down): 693 -> 117 characters
    original: SELECT t1b.c1 AS k2 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (0) UNION ALL SELECT DISTINCT t2a.c15 AS k2 FROM t2 AS t2a
    mutant  : SELECT t1b.c1 AS k2 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (0) UNION SELECT DISTINCT t2a.c15 AS k2 FROM t2 AS t2a
    rows    : 7 / 8

-- pair 46 (UNION->UNION-ALL, expected Up): 679 -> 113 characters
    original: SELECT t2c.c15 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2c ON (0) UNION SELECT DISTINCT t2a.c3 AS k2 FROM t2 AS t2a
    mutant  : SELECT t2c.c15 AS k2 FROM t3 AS t3a INNER JOIN t2 AS t2c ON (0) UNION ALL SELECT DISTINCT t2a.c3 AS k2 FROM t2 AS t2a
    rows    : 7 / 6

-- pair 47 (UNION-ALL->UNION, expected Down): 365 -> 88 characters
    original: SELECT t2a.c3 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t2a.c3 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 14 / 13

-- pair 48 (EXCEPT->left, expected Up): 480 -> 158 characters
    original: SELECT t3c.c3 AS k1 FROM t2 AS t2a INNER JOIN t3 AS t3c ON (0) UNION ALL SELECT DISTINCT t3a.c1 AS k1 FROM t3 AS t3a EXCEPT SELECT t3a.c8 AS k1 FROM t3 AS t3a
    mutant  : SELECT t3c.c3 AS k1 FROM t2 AS t2a INNER JOIN t3 AS t3c ON (0) UNION ALL SELECT DISTINCT t3a.c1 AS k1 FROM t3 AS t3a
    rows    : 5 / 4

-- pair 49 (UNION->UNION-ALL, expected Up): 412 -> 119 characters
    original: SELECT t2a.c15 AS k1 FROM t2 AS t2a UNION SELECT DISTINCT t2b.c1 AS k1 FROM t1 AS t1a INNER JOIN t2 AS t2b ON NOT ((0))
    mutant  : SELECT t2a.c15 AS k1 FROM t2 AS t2a UNION ALL SELECT DISTINCT t2b.c1 AS k1 FROM t1 AS t1a INNER JOIN t2 AS t2b ON NOT ((0))
    rows    : 14 / 16

-- pair 50 (UNION->UNION-ALL, expected Up): 418 -> 84 characters
    original: SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a
    mutant  : SELECT t3a.c9 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t3a.c8 AS k0 FROM t3 AS t3a
    rows    : 13 / 16

-- pair 51 (UNION-ALL->UNION, expected Down): 378 -> 89 characters
    original: SELECT t2a.c14 AS k0 FROM t2 AS t2a UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t2a.c14 AS k0 FROM t2 AS t2a UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 15 / 13

-- pair 52 (cond->TRUE, expected Up): 593 -> 131 characters
    original: SELECT t1a.c4 AS k1 FROM t1 AS t1a INNER JOIN t1 AS t1b ON (1) INNER JOIN t1 AS t1c ON t1b.c4 IN (SELECT t3i93.c7 FROM t3 AS t3i93)
    mutant  : SELECT t1a.c4 AS k1 FROM t1 AS t1a CROSS JOIN t1 AS t1b INNER JOIN t1 AS t1c ON t1b.c4 IN (SELECT t3i93.c7 FROM t3 AS t3i93)
    rows    : 36 / 6

-- pair 53 (HAVING cond->TRUE, expected Up): 316 -> 124 characters
    original: SELECT COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    mutant  : SELECT COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5)
    rows    : 2 / 4

-- pair 54 (HAVING cond->TRUE, expected Up): 316 -> 124 characters
    original: SELECT COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    mutant  : SELECT COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5)
    rows    : 2 / 4

-- pair 55 (UNION-ALL->UNION, expected Down): 338 -> 116 characters
    original: SELECT t2c.c3 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2c ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t2c.c3 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2c ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 7 / 8

-- pair 56 (UNION-ALL->UNION, expected Down): 338 -> 116 characters
    original: SELECT t2c.c3 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2c ON (0) UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t2c.c3 AS k0 FROM t1 AS t1a INNER JOIN t2 AS t2c ON (0) UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 7 / 8

-- pair 57 (UNION->UNION-ALL, expected Up): 296 -> 84 characters
    original: SELECT t3a.c1 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    mutant  : SELECT t3a.c1 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c4 AS k0 FROM t1 AS t1a
    rows    : 12 / 11

-- pair 58 (UNION-ALL->UNION, expected Down): 419 -> 117 characters
    original: SELECT t3b.c2 AS k1 FROM t3 AS t3a INNER JOIN t3 AS t3b ON (0) UNION ALL SELECT DISTINCT t2a.c15 AS k1 FROM t2 AS t2a
    mutant  : SELECT t3b.c2 AS k1 FROM t3 AS t3a INNER JOIN t3 AS t3b ON (0) UNION SELECT DISTINCT t2a.c15 AS k1 FROM t2 AS t2a
    rows    : 7 / 8

-- pair 59 (UNION-ALL->UNION, expected Down): 419 -> 117 characters
    original: SELECT t3b.c2 AS k1 FROM t3 AS t3a INNER JOIN t3 AS t3b ON (0) UNION ALL SELECT DISTINCT t2a.c15 AS k1 FROM t2 AS t2a
    mutant  : SELECT t3b.c2 AS k1 FROM t3 AS t3a INNER JOIN t3 AS t3b ON (0) UNION SELECT DISTINCT t2a.c15 AS k1 FROM t2 AS t2a
    rows    : 7 / 8

-- pair 60 (UNION->UNION-ALL, expected Up): 161 -> 84 characters
    original: SELECT t3a.c2 AS k0 FROM t3 AS t3a UNION SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a
    mutant  : SELECT t3a.c2 AS k0 FROM t3 AS t3a UNION ALL SELECT DISTINCT t1a.c1 AS k0 FROM t1 AS t1a
    rows    : 14 / 18

-- pair 61 (COUNT->COUNT-DISTINCT, expected Ge col 2): 316 -> 169 characters
    original: SELECT (t2a.c1 % 5) AS k0, (SUM(t2a.c1) + 6) AS k1, COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    mutant  : SELECT (t2a.c1 % 5) AS k0, (SUM(t2a.c1) + 6) AS k1, COUNT(DISTINCT t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    rows    : 2 / 2

-- pair 62 (expr->expr+k, expected Le col 2): 316 -> 169 characters
    original: SELECT (t2a.c1 % 5) AS k0, (SUM(t2a.c1) + 6) AS k1, COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    mutant  : SELECT (t2a.c1 % 5) AS k0, (SUM(t2a.c1) + 6) AS k1, (COUNT(t2a.c1) + 3) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    rows    : 2 / 2

-- pair 63 (expr->expr*k, expected AwayZero col 2): 316 -> 169 characters
    original: SELECT (t2a.c1 % 5) AS k0, (SUM(t2a.c1) + 6) AS k1, COUNT(t2a.c1) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    mutant  : SELECT (t2a.c1 % 5) AS k0, (SUM(t2a.c1) + 6) AS k1, (COUNT(t2a.c1) * 2) AS k2 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    rows    : 2 / 2

-- pair 64 (COUNT-DISTINCT->COUNT, expected Le col 4): 316 -> 233 characters
    original: SELECT (t2a.c1 % 5) AS k0, (SUM(t2a.c1) + 6) AS k1, COUNT(t2a.c1) AS k2, (ROUND(COUNT(t2a.c1 - 3))) AS k3, COUNT(DISTINCT t2a.c1) AS k4 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    mutant  : SELECT (t2a.c1 % 5) AS k0, (SUM(t2a.c1) + 6) AS k1, COUNT(t2a.c1) AS k2, (ROUND(COUNT(t2a.c1 - 3))) AS k3, COUNT(t2a.c1) AS k4 FROM t2 AS t2a GROUP BY (t2a.c1 % 5) HAVING (COUNT(t2a.c1)) IN (SELECT t1h40.c4 FROM t1 AS t1h40)
    rows    : 2 / 2
