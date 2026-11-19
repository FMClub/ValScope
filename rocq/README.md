# ValScope in Rocq

This directory is a re-implementation of the core of ValScope in Rocq (formerly Coq).
It lives on its own branch; the Python implementation at the repository root is not touched.

The idea: **a mutation rule is a theorem**. Once the theorem is proved, a generic,
verified engine turns it into a mutator that works on whole queries, and the mutator
is plugged into the framework by adding one line to a registry.

There are two kinds of rules, as in ValScope:

- **set-semantic** rules change which rows a query returns; the theorem is a bag
  inclusion between the original and the mutant;
- **value-semantic** rules change one select item; the rows stay in one-to-one
  correspondence and the theorem relates the values of the mutated column.

A grouped query can also have its `HAVING` predicate mutated. That needs no rules of its
own: the predicate rules and the engine used for `WHERE` and `ON` apply at the `HAVING`
position, and the theorem says that the mutant outputs the same rows plus possibly more
(`Up`) or a subset (`Down`).

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

```bash
python3 bridge/sql_bridge.py --value "SELECT t.g AS g, AVG(t.x) + 1 AS a, STDDEV_SAMP(t.x) AS sd FROM t GROUP BY t.g"
```

List the plugged-in rules:

```bash
./cli/valscope_mutate --rules
```

Check every mutant of a file of queries against a MySQL-compatible server:

```bash
python3 bridge/gen_fragment.py 400 7 > queries.sql
```

```bash
python3 bridge/run_on_db.py queries.sql --port 3306 --user root --password ... --database test
```

And the value-semantic rules:

```bash
python3 bridge/gen_fragment.py --value 500 11 > vqueries.sql
```

```bash
python3 bridge/run_on_db.py vqueries.sql --value --port 3306 --user root --password ... --database test
```

`--flip` is a negative control: it expects the opposite relation and must report violations.

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

A value rule is added the same way (`theories/VRules.v`): a rewrite of a select item,
a theorem relating the value of the rewritten item to the original on every group of
rows, `mk_vrule`, and one line in `value_rules`.

## Value relations

Several rules of the original table hold only under a condition on the data (sign of
the value, below or above 1). A rule here states an unconditional relation that mentions
the original value, so nothing has to be assumed and the checker needs to know only
five relations:

| Relation | Meaning | Used by |
| --- | --- | --- |
| `Le` | the value does not decrease | 18, 19, 20, 24, 26 |
| `Ge` | the value does not increase | 18 and 20 backwards |
| `AwayZero` | a value >= 0 does not decrease, a value <= 0 does not increase | 23, 25 |
| `TowardOne` | a value <= 1 does not decrease, a value >= 1 does not increase | 21 |
| `AwayOne` | a value >= 1 does not decrease, a value <= 1 does not increase | 22 |

NULL corresponds to NULL only. `Le` and `Ge` are carried through monotone contexts
(addition, multiplication by a non-negative constant, monotone functions); the other
three are used at the root of a select item only, because the sign or size of an inner
value cannot be read off the result.

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
| `theories/Value.v` | Aggregates, select items, value relations, value queries |
| `theories/VEngine.v` | Plug-in interface and generic engine for value rules, `vmut_sound` |
| `theories/VRules.v` | Rules 18 to 26, each a theorem plus a packaged plug-in |
| `theories/VHaving.v` | Mutation of the HAVING predicate (rules 15, 16), `hmut_sound` |
| `theories/Registry.v` | The plugged-in rules and the three mutators with their theorems: `mutate`, `vmutate`, `hmutate` |
| `theories/Counter.v` | Proofs that some positions must not be mutated |
| `theories/Extract.v` | Extraction to OCaml |
| `cli/main.ml` | Command-line front end of the extracted core (S-expression protocol) |
| `bridge/sql_bridge.py` | SQL text to algebra term and back |
| `bridge/checker.py` | Bag inclusion and the five value relations on query results |
| `bridge/test_bridge.py` | Tests of the bridge and the checkers (no database needed) |
| `bridge/gen_fragment.py` | Random queries inside the supported fragments |
| `bridge/run_on_db.py` | Translation validation, execution of mutants, relation checks |

## What is proved

- `engine_sound` (and its instance `mutate_sound`): for every list of rules, every query,
  direction and database, each mutant is a super-bag (`Up`) or a sub-bag (`Down`) of the
  original.
- Polarity (`Approx.v`): `NOT` and the right operand of `EXCEPT` are antitone; `AND`, `OR`,
  `EXISTS`, `IN (subquery)`, `DISTINCT`, `UNION [ALL]`, `INTERSECT`, `WHERE`, `INNER JOIN`
  and the left input of a `LEFT JOIN` are monotone. `x IN (subquery)` is modelled with
  three-valued logic (`x = v1 OR ... OR x = vn`), so `NOT IN` with NULLs is covered.
- Non-monotone positions (`Counter.v`): the `ON` condition and the right input of a
  `LEFT JOIN`, and `LIMIT`, with concrete counterexamples. `left_join_only_left_entered`
  shows the engine never enters them, whatever rules are plugged in.
- `vmut_sound` (and its instance `vmutate_sound`): for every list of value rules, the
  result rows of the original and of the mutant correspond one to one, agree outside the
  mutated column, and are related by the rule's relation inside it. This holds with a
  `HAVING` clause present, because the groups do not depend on the select items.
- `hmut_sound` (and its instance `hmutate_sound`): for every list of predicate and query
  rules, a mutant of the `HAVING` predicate outputs a super-list (`Up`) or a sub-list
  (`Down`) of the original rows. The operands of `HAVING` are opaque: the theorem holds for
  any function from groups to values, so it does not depend on which aggregates are used.

Axioms: the set-semantic part uses none. The value-semantic part uses real numbers
(AVG needs division, STDDEV a square root) and therefore depends on the three axioms of
the standard library `Reals` (`sig_not_dec`, `sig_forall_dec`, functional extensionality),
as reported by `Print Assumptions vmutate_sound`.

## Plugged-in rules

| Plug-in | Direction | Rule in mutation.md |
| --- | --- | --- |
| `cond->TRUE` | Up | 5, 12, 15 (at WHERE / ON / HAVING positions) |
| `cond->FALSE` | Down | 6, 13, 16 read backwards |
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

Value plug-ins:

| Plug-in | Relation | Rule in mutation.md |
| --- | --- | --- |
| `COUNT-DISTINCT->COUNT` / `COUNT->COUNT-DISTINCT` | Le / Ge | 18 |
| `AVG->MAX` | Le | 19 |
| `MIN->MAX` / `MAX->MIN` | Le / Ge | 20 |
| `VAR_SAMP->STDDEV_SAMP` | TowardOne | 21 |
| `STDDEV_SAMP->VAR_SAMP` | AwayOne | 22 |
| `SUM(c)->SUM(c*k)` (k = 2) | AwayZero | 23 |
| `expr->expr+k` (k = 3) | Le | 24 |
| `expr->expr*k` (k = 2) | AwayZero | 25 |
| `FUNC(a)->FUNC(a+k)` (k = 3) | Le | 26, sound variant |
| `FUNC(c)->FUNC(c*k)` (k = 2) | Le | 26, only when `c >= 0` by construction |

Rule 26 as written (`FUNC(c * k)`, `k > 0`) is not sound for negative `c`. The sign of the
argument is not visible in the result, so the second plug-in fires only when the argument
is non-negative by construction (counts, non-negative constants, their sums and products).

## Measured

MariaDB 10.11.14, sample schema of the Python generator.

| Run | Queries | Checks passed | Violations |
| --- | --- | --- | --- |
| Set-semantic with `IN` subqueries, seeds 7, 8, 9 (`gen_fragment.py 400`) | 1200 | 40736 | 0 |
| Value-semantic with `HAVING`, seeds 11 to 16 (`gen_fragment.py --value 500`) | 3000 (2736 used) | 37572 | 1 |

- Every query passed translation validation (the query as written and the query
  re-printed from its term returned the same rows).
- Negative controls (`--flip`): 1850 violations on 400 set queries, 1791 on 500 value
  queries.
- 264 value queries were not used because they group by a FLOAT / DOUBLE expression (see
  "Observation" below).
- The one violation is a candidate MariaDB bug, not a false alarm: `HAVING COUNT(x) IN
  (subquery)` returns no rows where a row is expected. It is written up in
  `issues/003-mariadb-having-count-in-subquery.md` (separate PR).
- Of 511 queries produced by the Python generator, only 6 are inside the set-semantic
  fragment (the rest use CTEs, window functions or aggregates the model does not have).

Testing found three defects in the unverified bridge and checker, all fixed and covered
by tests: an atom was put back without parentheses (`t.c - 5000 * 2`); FLOAT results were
compared exactly; and rows were matched on exact floats, although floating-point
aggregates can differ in their last bits between two plans of the same query.

### Observation (not analysed further)

On MariaDB 10.11.14 the number of groups of a GROUP BY on a DOUBLE expression depends on
the select list:

```sql
SELECT (c15 % 2) AS k0, COUNT(DISTINCT (c15 - 5)) FROM t2 GROUP BY (c15 % 2);   -- 13 groups
SELECT (c15 % 2) AS k0, COUNT((c15 - 5))          FROM t2 GROUP BY (c15 % 2);   -- 12 groups
```

`c15` is `DOUBLE(12,4)`; two rows have `c15 % 2` printed as `1.8700` but different as
doubles. One plan groups them together, the other does not. This may be a known
consequence of grouping by approximate values; it was not checked against the
documentation or other versions. The model groups by exact values, so the bridge rejects
value queries whose grouping keys are FLOAT or DOUBLE.

## How the bridge fails closed

The bridge (`bridge/sql_bridge.py`) is not verified, so it is written to refuse rather
than to guess:

- **One atom per occurrence.** Expressions, tables and unanalysed predicates are replaced
  by numbered atoms. Two occurrences never share an atom, even with identical text, so
  alias shadowing cannot make the term mean something else than the SQL.
- **Parenthesised atoms.** An atom is printed in parentheses unless it is a plain name or
  number, because a mutant may put it into a context it was not written in.
- **Rejected, not approximated:** `LIMIT`, `GROUP BY` / aggregates in set-semantic queries,
  `HAVING` without aggregation, window functions, CTEs, `USING` / `NATURAL` / `RIGHT` / `FULL` joins,
  `INTERSECT ALL` / `EXCEPT ALL`, `SUM(DISTINCT)`, aggregates that are not modelled,
  non-aggregated select items that are not grouping keys, non-deterministic functions and
  user variables.
- **Translation validation** (`run_on_db.py`): the query as written and the query
  re-printed from its term must return the same bag of rows, otherwise the query is not
  used and the mismatch is reported.
- **Type guards:** a set-semantic check is skipped when the column types of the two results
  differ; a value check is `incomparable` when the mutated column is not numeric; value
  queries with FLOAT / DOUBLE grouping keys are rejected; single-precision inputs are
  compared with a looser tolerance (1e-4 relative instead of 1e-9).
- **Opaque when in doubt:** `IN` with a row constructor, with a `*` subquery or with a value
  list, and `EXISTS` / `IN` subqueries the bridge cannot translate, are kept as one opaque
  predicate that can only be replaced as a whole.
- **Collation:** an inclusion that holds only up to case and trailing spaces is classified
  `collation`, not `violation`.
- **Failing mutants** are skipped, never treated as empty results.

## Not done yet

- Window functions, scalar subqueries, CTEs, `IN` with a row constructor.
- Strings, `LIKE`, `REGEXP` (rules 7, 14).
- Value mutation is applied to the select items of one top-level SELECT. Following a
  mutated value through derived tables or `UNION ALL` (what the Python lineage analysis
  does) is not modelled.
- The value model has integer inputs. DECIMAL and FLOAT columns are tested through the
  bridge, but the theorems do not speak about rounding.
- Derived tables are opaque to the bridge (they are not mutated). About 10% of the
  set-semantic mutants cannot be printed as SQL (`DISTINCT` around a join) and are dropped.

## Trusted base and caveats

- Verified: the rules, the engine and the registry, with respect to the SQL model in
  `Semantics.v`.
- Not verified: `cli/main.ml` (parsing and printing of terms), `bridge/sql_bridge.py`,
  sqlglot, and Rocq's extraction. The bridge is responsible for the algebra term meaning
  the same as the SQL text; it rejects what it does not model instead of approximating.
- The model is not MySQL: bag semantics, three-valued logic, integers and NULL only,
  exact arithmetic, `DISTINCT` set operations, no `ORDER BY`, no errors, no overflow.
  A real DBMS can deviate from it (collation, type coercion, floating point,
  plan-dependent behaviour); the proofs do not cover that.
- The list of monotone functions (`EXP`, `FLOOR`, `CEIL`, `ROUND`, `ATAN`, `SIGN`) is an
  assumption of the bridge. In the model a monotone function is any non-decreasing
  function on the reals.
- In the model the operands of `HAVING` take integer or NULL values, like every value of
  the set-semantic model. The `HAVING` rules use only the order and the three-valued
  logic, but real-valued aggregates (AVG, STDDEV) are not literally covered.
- The checker matches rows by sorting within groups of rows that agree outside the mutated
  column. This is justified because the intended transformations are non-decreasing; it is
  not proved.
- After extraction the proofs are erased, so OCaml code can build an unproved rule record.
  Plug-ins should be written and registered in Rocq.
