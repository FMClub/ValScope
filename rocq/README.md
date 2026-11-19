# ValScope in Rocq

This directory is a re-implementation of the core of ValScope in Rocq (formerly Coq).
It lives on its own branch; the Python implementation at the repository root is not touched.

The goal is not a line-by-line translation. The Python code decides, by heuristics, which
mutations are safe and what result relation to expect. Here the relations are **defined
and proved**, and the mutators are **extracted to OCaml** from the proved definitions.

## Build

Requires Coq/Rocq 8.18 or newer (tested with Coq 8.18.0 and OCaml 4.14.1).

```bash
make        # check all proofs and extract extracted/valscope_core.ml
make test   # compile the extracted code and run extracted/smoke_test.ml
make clean
```

The proofs use no axioms: `Print Assumptions mutate_sound` prints
`Closed under the global context`.

## Files

| File | Content |
| --- | --- |
| `theories/Bag.v` | Bags as lists, SQL set operations (`DISTINCT`, `UNION`, `INTERSECT`, `EXCEPT`), the inclusion relation `bag_le`, and its monotonicity lemmas |
| `theories/Logic3.v` | Values with NULL, three-valued logic ordered `F < U < T`, comparisons |
| `theories/Syntax.v` | Expressions, predicates and queries (mutually inductive) |
| `theories/Semantics.v` | Bag semantics with correlated subqueries; the approximation relations `q_le` and `p_le` |
| `theories/Approx.v` | Monotone / antitone behaviour of every constructor (the mathematics of the polarity analysis) |
| `theories/Mutate.v` | The mutators `mut_q` / `mut_p` and the theorem `mutate_sound` |
| `theories/Counter.v` | Proofs that some positions are neither monotone nor antitone, so they must not be mutated |
| `theories/Extract.v` | Extraction of the mutators to OCaml |

## What is proved

- `mutate_sound`: for every query `q`, direction `d` and database, every mutant in
  `mut_q d q` is a super-bag of `q` (`Up`) or a sub-bag of `q` (`Down`). The same holds for
  predicates (`mut_p`, three-valued order).
- Polarity (`Approx.v`): `NOT` and the right operand of `EXCEPT` are antitone; `AND`, `OR`,
  `EXISTS`, `DISTINCT`, `UNION [ALL]`, `INTERSECT`, `WHERE`, `INNER JOIN` and the left input of
  a `LEFT JOIN` are monotone.
- Non-monotone positions (`Counter.v`): the `ON` condition and the right input of a
  `LEFT JOIN`, and `LIMIT`, with concrete counterexamples. The mutators never enter them.

## Rules covered

| Rule | Status |
| --- | --- |
| 1 `DISTINCT` removal, 2 `UNION` to `UNION ALL`, 3 `EXCEPT` to left operand, 4 `INTERSECT` to `UNION` | done |
| 5, 6 `WHERE cond` to `TRUE`, and `FALSE` to `cond` | done (`Up`: `cond` to `TRUE`; `Down`: `cond` to `FALSE`) |
| 8, 9, 10 comparison weakening (`<` to `<=`, `>` to `>=`, `=` to `>=`) | done, plus the strengthening direction |
| 11 drop a conjunct | done |
| 12, 13 `ON cond` to `TRUE` / `FALSE` | done for `INNER JOIN`; **not entered for `LEFT JOIN`** (proved unsound) |
| 17 `INNER JOIN` to `LEFT JOIN` | done, plus the reverse |
| 7 `LIKE`, 14 `REGEXP` | not yet (needs a pattern semantics and strings) |
| 15, 16 `HAVING` | not yet (needs `GROUP BY` and aggregates) |
| 18 to 26 value-semantic rules | not yet (aggregates, arithmetic, sign and magnitude conditions) |

## Not done yet

- Aggregation, `GROUP BY`, `HAVING`, window functions, scalar subqueries, `IN`.
- Strings, `LIKE`, `REGEXP`; only integers and NULL exist so far.
- The value-semantic mutators (rules 18 to 26) and their proofs.
- A SQL parser/printer and the database driver (planned as OCaml glue around the extracted core).
- The random SQL generator and the result comparison.

## Caveats

- The semantics is a model of SQL, not MySQL's: bag semantics, three-valued logic, `DISTINCT`
  set operations, no `ORDER BY`, no errors. The theorems hold for this model. A real DBMS can
  deviate from it in ways the proofs do not cover (collation, type coercion, plan-dependent
  behaviour).
- Subqueries are correlated through the context row; `ECol i` reads column `i` of the current
  row followed by the outer rows.
- Extraction maps `nat` and `Z` to OCaml `int`. The mutators never do arithmetic on them.
