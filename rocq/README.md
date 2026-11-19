# ValScope in Rocq

This directory is a re-implementation of the core of ValScope in Rocq (formerly Coq).
It lives on its own branch; the Python implementation at the repository root is not touched.

The idea: **a mutation rule is a theorem**. Once the theorem is proved, a generic,
verified engine turns it into a mutator that works on whole queries, and the mutator
is plugged into the framework by adding one line to a registry.

```
 rule = rewrite function + theorem          (theories/StdRules.v, ExtraRules.v)
            |
            v   registry: the list of plugged-in rules   (theories/Registry.v)
 generic engine: applies every rule at every position
 where the polarity analysis allows it; proved sound
 once, for ALL rule sets                    (theories/Engine.v)
            |
            v   extraction
 OCaml core + command-line mutator          (cli/valscope_mutate)
            |
            v   bridge (sqlglot)
 SQL text -> algebra term -> mutants -> SQL text   (bridge/sql_bridge.py)
```

## Build and test

Requires Coq/Rocq 8.18 or newer, OCaml with ocamlfind, and for the bridge Python 3 with
`sqlglot` (and `pymysql` to run against a database). Tested with Coq 8.18.0, OCaml 4.14.1,
sqlglot 30.33.0.

```bash
make        # check all proofs and extract the OCaml core
make cli    # build cli/valscope_mutate
make test   # SQL -> mutants -> SQL round trip (no database needed)
```

The proofs use no axioms: `Print Assumptions mutate_sound` prints
`Closed under the global context`.

Try it on a query:

```bash
python3 bridge/sql_bridge.py "SELECT t.a FROM t WHERE NOT EXISTS (SELECT u.x FROM u WHERE u.x < t.a)"
```

List the plugged-in rules:

```bash
./cli/valscope_mutate --rules
```

Check every mutant of a file of queries against a MySQL-compatible server:

```bash
python3 bridge/gen_fragment.py 400 7 > queries.sql
python3 bridge/run_on_db.py queries.sql --port 3306 --user root --password ... --database test
```

## How to add a rule (plug-in)

1. Write the rewrite at the root of a query or predicate. It returns the list of rewrites,
   empty when the rule does not match.
2. Prove the theorem: every rewrite is above (`Up`) or below (`Down`) its input.
3. Package both with `mk_qrule` / `mk_prule` and add the rule to `Registry.v`.

`theories/ExtraRules.v` is a complete example of a rule that is not in the original
ValScope table (`A INTERSECT B -> A`):

```coq
Definition f_intersect_operand (q : query) : list query :=
  match q with QIntersect a b => [a; b] | _ => [] end.

Theorem f_intersect_operand_sound :
  forall q q', In q' (f_intersect_operand q) -> dle q_le Up q q'.
Proof. ... Qed.

Definition r_intersect_operand : qrule :=
  mk_qrule "INTERSECT->operand" Up f_intersect_operand f_intersect_operand_sound.
```

Nothing else changes. `Engine.v` is not touched, and `mutate_sound` covers the new rule
because it is an instance of `engine_sound`, which is proved for every list of rules.
A rule cannot be registered without its proof: the record type `qrule` has the proof as a
field. The engine decides where the rule may fire (direction flips under `NOT` and in the
right operand of `EXCEPT`; the `ON` condition and right input of a `LEFT JOIN` are never
entered), so a rule author only reasons about the root.

## Files

| File | Content |
| --- | --- |
| `theories/Bag.v` | Bags as lists, SQL set operations, the inclusion relation `bag_le` |
| `theories/Logic3.v` | Values with NULL, three-valued logic ordered `F < U < T`, comparisons |
| `theories/Syntax.v` | Expressions, predicates and queries (mutually inductive) |
| `theories/Semantics.v` | Bag semantics with correlated subqueries; the relations `q_le` and `p_le` |
| `theories/Approx.v` | Monotone / antitone behaviour of every constructor |
| `theories/Rule.v` | The plug-in interface: a rule is a rewrite packaged with its theorem |
| `theories/Engine.v` | The generic mutator and `engine_sound`, for all rule sets |
| `theories/StdRules.v` | The standard rules, each a theorem plus a packaged plug-in |
| `theories/ExtraRules.v` | A rule that is not in the original table, as a plug-in example |
| `theories/Registry.v` | The plugged-in rules, `mutate` and `mutate_sound` |
| `theories/Counter.v` | Proofs that some positions must not be mutated |
| `theories/Extract.v` | Extraction to OCaml |
| `cli/main.ml` | Command-line front end of the extracted core (S-expression protocol) |
| `bridge/sql_bridge.py` | SQL text to algebra term and back |
| `bridge/test_bridge.py` | Round-trip test |
| `bridge/gen_fragment.py` | Random queries inside the supported fragment |
| `bridge/run_on_db.py` | Executes original and mutants and checks the inclusion |

## What is proved

- `engine_sound` (and its instance `mutate_sound`): for every list of rules, every query,
  direction and database, each mutant is a super-bag (`Up`) or a sub-bag (`Down`) of the
  original.
- Polarity (`Approx.v`): `NOT` and the right operand of `EXCEPT` are antitone; `AND`, `OR`,
  `EXISTS`, `DISTINCT`, `UNION [ALL]`, `INTERSECT`, `WHERE`, `INNER JOIN` and the left input
  of a `LEFT JOIN` are monotone.
- Non-monotone positions (`Counter.v`): the `ON` condition and the right input of a
  `LEFT JOIN`, and `LIMIT`, with concrete counterexamples. `left_join_only_left_entered`
  shows the engine never enters them, whatever rules are plugged in.

## Plugged-in rules

| Plug-in | Direction | Rule in mutation.md |
| --- | --- | --- |
| `cond->TRUE` | Up | 5, 12 (at WHERE / ON positions) |
| `cond->FALSE` | Down | 6, 13 read backwards |
| `AND-drop-operand` | Up | 11 |
| `OR-drop-operand` | Down | not in the table |
| `cmp-weaken` | Up | 8, 9, 10 |
| `cmp-strengthen` | Down | 8, 9, 10 backwards |
| `DISTINCT-drop` / `DISTINCT-add` | Up / Down | 1 |
| `UNION->UNION-ALL` / `UNION-ALL->UNION` | Up / Down | 2 |
| `EXCEPT->left` | Up | 3 |
| `INTERSECT->UNION` / `UNION->INTERSECT` | Up / Down | 4 |
| `INNER->LEFT-JOIN` / `LEFT->INNER-JOIN` | Up / Down | 17 |
| `INTERSECT->operand` | Up | not in the table |

## Measured

On MariaDB 10.11.14 with the sample schema, 400 queries from `gen_fragment.py` (seed 7):
11746 inclusion checks over all 16 plug-ins, 0 violations. As a negative control, flipping
the expected direction reports 300 violations on the first 60 queries.

Of 511 queries produced by the Python generator, only 6 are inside the supported fragment
(the rest use aggregates, GROUP BY, CTEs or window functions).

## Not done yet

- Aggregation, `GROUP BY`, `HAVING` (rules 15, 16), window functions, scalar subqueries, `IN`.
- Strings, `LIKE`, `REGEXP` (rules 7, 14).
- The value-semantic rules 18 to 26: they need a second relation (an order on values,
  row by row) next to bag inclusion, and a second kind of plug-in.
- Derived tables are opaque to the bridge (they are not mutated), and mutants that put
  `DISTINCT` around a FROM item cannot be printed as SQL yet and are dropped (3602 of
  15372 in the run above).

## Trusted base and caveats

- Verified: the rules, the engine and the registry, with respect to the SQL model in
  `Semantics.v`.
- Not verified: `cli/main.ml` (parsing and printing of terms), `bridge/sql_bridge.py`,
  sqlglot, and Rocq's extraction. The bridge is responsible for the algebra term meaning
  the same as the SQL text; it rejects what it does not model instead of approximating.
- The model is not MySQL: bag semantics, three-valued logic, integers and NULL only,
  `DISTINCT` set operations, no `ORDER BY`, no errors. A real DBMS can deviate from it
  (collation, type coercion, plan-dependent behaviour); the proofs do not cover that.
- After extraction the proofs are erased, so OCaml code can build an unproved rule record.
  Plug-ins should be written and registered in Rocq.
