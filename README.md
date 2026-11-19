# ValScope in Rocq

ValScope finds logic bugs in database systems by metamorphic testing. This repository is
its re-implementation in Rocq (formerly Coq): the mutation rules and the engine that
applies them are proved; a thin Python layer (`bridge/`) connects the extracted engine to
real databases. The original Python implementation is kept on branch
[`vanilla-python`](https://github.com/FMClub/ValScope/tree/vanilla-python).

## Quick start

On Ubuntu 24.04 (details and other systems: [`docs/USAGE.md`](docs/USAGE.md)):

```bash
sudo apt-get install -y coq ocaml ocaml-findlib make gcc python3-pip mariadb-server
```

```bash
python3 -m pip install -r requirements.txt
```

```bash
scripts/demo.sh sqlite
```

checks every proof, builds the mutator, runs the tests, builds a random SQLite database
and tests it with all rules (no server needed). To test MariaDB / MySQL with the sample
database instead:

```bash
scripts/setup_mariadb.sh && scripts/demo.sh mariadb
```

`setup_mariadb.sh` starts a local MariaDB if none answers (port 3306, root password
`123456`; override with `HOST`, `PORT`, `DB_USER`, `PASSWORD`) and loads the sample
database `test` from `data/mariadb/`. Logs and violations are written to `out/`.

## Repository layout

| Directory | Content |
| --- | --- |
| `theories/` | The Rocq development: SQL model, rules, engine, proofs, extraction |
| `cli/` | Command-line front end of the extracted engine (`cli/valscope_mutate`) |
| `bridge/` | Python glue (not verified): SQL <-> terms, execution, result checks, query generators |
| `scripts/` | `setup_mariadb.sh` (set up the sample database), `demo.sh` (end-to-end run) |
| `data/` | Sample MariaDB database and 870 queries produced by the original Python generator |
| `docs/` | `USAGE.md`: the step-by-step guide |
| `results/` | The SQLite campaign: 42 confirmed violations |
| `issues/` | Problem reports and candidate DBMS bugs |

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

**Step-by-step instructions** (environment, build, generating queries, testing a MySQL-
compatible server, an SQLite file, old SQLite releases or another DBMS, reading the
results): [`docs/USAGE.md`](docs/USAGE.md).

## Build and test

Requires Coq/Rocq 8.18 or newer, OCaml with ocamlfind, and for the bridge Python 3 with
`sqlglot` (and `pymysql` to run against a database). Tested with Coq 8.18.0, OCaml 4.14.1,
sqlglot 30.33.0.

```bash
make        # check all proofs and extract the OCaml core
make cli    # build cli/valscope_mutate
make test   # SQL -> mutants -> SQL round trip (no database needed)
```

The set-semantic proofs use no axioms: `Print Assumptions mutate_sound` prints
`Closed under the global context`. The value-semantic ones use the axioms of Coq's `Reals`
library (see "What is proved").

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

Check every mutant of a file of queries against a MySQL-compatible server (or, with
`--sqlite FILE.db`, an SQLite database file):

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

## The SQL model

`theories/Semantics.v` gives SQL a bag semantics with three-valued logic and correlated
subqueries. Values are `NULL`, integers, rationals (decimals) and strings. Everything that
differs between DBMSs is a parameter of the **world** (`db_t`), and the theorems hold for
every world that satisfies the laws:

| Part of the world | What it models |
| --- | --- |
| `tables` | the contents of the tables |
| `vcmp` | comparison of values (type coercions, collations); UNKNOWN when incomparable |
| `vadd`, `vmul` | arithmetic |
| `veq` | the **collation equivalence**: which values DISTINCT, UNION, INTERSECT, EXCEPT and IN treat as equal |
| `to_text`, `ceq` | conversion to text and character comparison for `LIKE` / `REGEXP` (case sensitivity) |
| `atoms`, `eatoms`, `qatoms` | the meaning of predicates, expressions and subqueries the mutators do not analyse |

Laws: `veq` is an equivalence; comparisons satisfy the weakening laws (`x < y` implies
`x <= y`, ...); every operation respects `veq` (equivalent inputs give the same truth value
and equivalent results); multiplying by an integer constant multiplies numbers (used by
rule 23 only). Bags are compared modulo `veq`: `q_le q q'` means that every row of `q`
occurs in `q'` at least as often, counting rows that are equivalent under the collation as
the same row. A compatibility theorem (`Approx.compat`) shows that evaluation respects
`veq`. `Counter.v` builds a concrete world that satisfies every law.

Why the laws matter: if an operation could tell apart two values that `DISTINCT` treats as
equal (`LENGTH('a ')` and `LENGTH('a')` under a PAD SPACE collation), the result of a query
would depend on which representative `DISTINCT` keeps, which SQL does not specify. Such
queries have no determined result, and no rule can promise anything about them.

The value-semantic layer (`Value.v`) reads values as real numbers: integers and decimals
are numbers, text and NULL are not; `COUNT` counts non-NULL values and `COUNT(DISTINCT)`
counts collation classes. Select items it does not analyse (`VAR_POP`, `GROUP_CONCAT`,
`SUM(DISTINCT)`, scalar subqueries) are opaque items: copied into every mutant and never
mutated.

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
| `theories/Bag.v` | Bags as lists modulo an equivalence, SQL set operations, the inclusion relation `bag_le` |
| `theories/Logic3.v` | Values (NULL, integers, rationals, strings), three-valued logic ordered `F < U < T`, comparisons |
| `theories/Pattern.v` | `LIKE` patterns and a fragment of regular expressions, with their generalisation lemmas |
| `theories/Syntax.v` | Expressions, predicates and queries (mutually inductive) |
| `theories/Semantics.v` | The world record with its laws; bag semantics with correlated subqueries; `q_le` and `p_le` |
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
| `theories/Counter.v` | A concrete lawful world; proofs that some positions must not be mutated |
| `theories/Extract.v` | Extraction to OCaml |
| `cli/main.ml` | Command-line front end of the extracted core (S-expression protocol) |
| `bridge/sql_bridge.py` | SQL text to algebra term and back |
| `bridge/checker.py` | Bag inclusion modulo the DBMS's collation, and the five value relations |
| `bridge/test_bridge.py` | Tests of the bridge and the checkers (no database needed) |
| `bridge/gen_fragment.py` | Random queries inside the supported fragments, for any schema |
| `bridge/run_on_db.py` | Translation validation, execution of mutants, relation checks (MySQL protocol or SQLite file) |
| `bridge/gen_sqlite_db.py` | Random SQLite databases for the campaigns |
| `bridge/sqlite_exec.py` | Runs SQL on any SQLite shared library through ctypes |
| `bridge/build_old_sqlite.sh` | Builds old SQLite releases as shared libraries |
| `bridge/campaign_sqlite.py` | Differential campaign on several SQLite releases |
| `bridge/confirm_sqlite.py` | Re-checks recorded violations from scratch and writes a report |
| `docs/USAGE.md` | End-to-end usage guide |
| `results/` | The SQLite campaign: summary, confirmed pairs (report and data) |

## What is proved

- `engine_sound` (and its instance `mutate_sound`): for every list of rules, every query,
  direction and lawful world (any data, any collation, any type coercion), each mutant is a
  super-bag (`Up`) or a sub-bag (`Down`) of the original, modulo the collation equivalence.
- `compat` (`Approx.v`): evaluation respects the collation equivalence: equivalent row
  contexts give equal truth values and equivalent bags.
- `LIKE` and `REGEXP` (`Pattern.v`): replacing `_` by `%` or a character by `_`, dropping an
  anchor and turning `x+` into `x*` make a pattern match more strings; turning `%` into `_`
  and adding both anchors make it match fewer, for any character comparison.
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
  any function from groups to values (integers, decimals, text), so it does not depend on
  which aggregates are used.

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
| `LIKE-generalise` | Up | 7 (`_` -> `%`, a character -> `_`) |
| `LIKE-specialise` | Down | 7 backwards (every `%` -> `_`) |
| `REGEXP-generalise` | Up | 14 (drop an anchor, `x+` -> `x*`) |
| `REGEXP-specialise` | Down | 14 backwards (add both anchors) |
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

MariaDB 10.11.14, sample database `data/mariadb/` (from the original Python generator).

| Run | Queries | Supported | Checks passed | Violations |
| --- | --- | --- | --- | --- |
| Set-semantic, Python generator queries (`data/python-generator-queries.sql`) | 870 | 327 | 4005 | 1 (candidate bug, below) |
| Value-semantic and HAVING, same queries | 870 | 69 | 671 | 0 |
| Set-semantic, `gen_fragment.py 300 7` | 300 | 300 | 10726 | 0 |
| Value-semantic and HAVING, `gen_fragment.py --value 300 11` | 300 | 277 | 3388 | 1 (known candidate, PR #5) |
| Earlier runs: set seeds 7-9 / value seeds 11-16 | 1200 / 3000 | all / 2736 | 40736 / 37572 | 0 / 1 |

- Negative controls (`--flip`) report violations by the thousand (for example 1018 on the
  300 value queries above).
- Of the queries of the original Python generator, 374 of 870 are now inside the fragment
  (6 of 511 before derived tables, CTEs, opaque set-operation arms, opaque select items,
  `LIKE` and `REGEXP` were added). The rest use `LIMIT` without `ORDER BY` in a subquery
  (nondeterministic, rejected), `SELECT DISTINCT` with aggregates, `RIGHT JOIN` and window
  functions.
- Translation validation rejected 2 queries: one with `ORDER BY ... LIMIT` over ties (its
  result is not determined), and one that exposed a bridge bug (`NOT LIKE` lost its
  negation; fixed).
- **Candidate MariaDB bug** (set-semantic, Python generator query): `MIN` / `MAX` over a
  `BIT(8)` column return the decimal text of the value (`'2'`, `'242'`) when the query has
  no `GROUP BY`, while the result metadata says `BIT` and the same aggregate under a
  derived table, `UNION ALL` or `GROUP BY` returns the bit value (`0x02`). Minimal case:
  `CREATE TABLE b (x BIT(8)); INSERT INTO b VALUES (2), (242); SELECT MIN(x), MAX(x) FROM b;`
  Written up in `issues/005-mariadb-bit-min-max-text.md` (PR #8).
- The value violation on generated queries is the known `HAVING COUNT(x) IN (subquery)`
  candidate (`issues/003-mariadb-having-count-in-subquery.md`).

Testing found defects in the unverified bridge and checker, all fixed and covered by
tests: an atom put back without parentheses (`t.c - 5000 * 2`); FLOAT results compared
exactly; rows matched on exact floats; `NOT LIKE` printed as `LIKE`; `REGEXP_LIKE` printed
for MariaDB; CTE names left inside opaque atoms after inlining; big integers compared as
floats.

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
than to guess. Its module docstring states, for each encoding, why a lawful world exists
in which the term means what the SQL text means.

- **One atom per occurrence.** Expressions, tables and unanalysed predicates are replaced
  by numbered atoms (`EAtom`, `T`, `Atom`). Two occurrences never share an atom, even with
  identical text, so alias shadowing cannot make the term mean something else.
- **Parenthesised atoms.** An atom is printed in parentheses unless it is a plain name or
  number, because a mutant may put it into a context it was not written in.
- **Analysed when in the fragment, opaque otherwise.** Derived tables and CTE references
  are translated (`Named`) when their body is in the fragment, otherwise kept as opaque
  tables; arms of set operations outside the fragment are opaque queries (`QAtom`); `LIKE`
  with a literal pattern without escapes, and `REGEXP` with a literal pattern of the
  fragment (`^`, `$`, literal characters, `.`, `?`, `*`, `+`) are analysed, other patterns
  are opaque predicates; select items that are not analysed are opaque items.
- **Rejected, not approximated:** `LIMIT` at the top or without `ORDER BY` in a subquery,
  aggregates and window functions in set-semantic select lists, `HAVING` without
  aggregation, window functions in value queries, `RIGHT` / `FULL` / `USING` / `NATURAL`
  joins, `INTERSECT ALL` / `EXCEPT ALL`, recursive CTEs, table functions with column
  arguments, non-aggregated select items that are not grouping keys, value queries whose
  clauses refer to a select alias, non-deterministic functions (`RAND`, `NOW`, SQLite
  `random()`, `date('now')`, ...) and user variables.
- **Translation validation** (`run_on_db.py`, `campaign_sqlite.py`): the query as written
  and the query re-printed from its term must return the same rows, otherwise the query is
  not used and the mismatch is reported.
- **Type guards:** a set-semantic check is skipped when the column types of the two results
  differ; a value check is `incomparable` when the mutated column is not numeric; value
  queries with FLOAT / DOUBLE grouping keys (MariaDB) or text inputs (SQLite) are skipped;
  single-precision inputs are compared with a looser tolerance (1e-4 relative instead of
  1e-9); integers and decimals are compared exactly.
- **Collation:** inclusion is checked modulo the database's own string equality, computed
  exactly (`WEIGHT_STRING` on MariaDB / MySQL; `NOCASE` / `RTRIM` on SQLite). A result
  that is included only modulo that equality is reported as `collation`, not as a violation.
- **Failing mutants** are skipped, never treated as empty results; a lost server connection
  stops the run.

## Results on SQLite

Run on four old SQLite releases (3.26.0, 3.30.1, 3.31.1, 3.34.0), the verified mutators found
**42 distinct query pairs** whose results violate the relation guaranteed by the rule's
theorem. Each one reproduces from scratch and is consistent on SQLite 3.53.1. Details,
root-cause notes and how to reproduce: [`results/sqlite-campaign.md`](results/sqlite-campaign.md).

## Not done yet

- Value mutation applies to the select items of one top-level `SELECT`. Following a
  mutated value through derived tables or `UNION ALL` (what the Python lineage analysis
  does) is not modelled; value queries with `SELECT DISTINCT` are rejected.
- Window functions and `IN` with a row constructor are opaque or rejected.
- About 5% to 10% of the set-semantic mutants cannot be printed as SQL (`DISTINCT` around a
  join below a projection) and are dropped. `DISTINCT` added around the table of a
  correlated subquery is printed as a derived table, which MySQL / MariaDB reject (the
  correlation is out of scope); those mutants fail and are dropped.
- Only the MySQL and SQLite dialects of sqlglot were tested.

## Trusted base and caveats

- Verified: the rules, the engine and the registry, with respect to the SQL model in
  `Semantics.v`, for every lawful world.
- Not verified: `cli/main.ml` (parsing and printing of terms), `bridge/sql_bridge.py`,
  sqlglot, Rocq's extraction, and the checker. The bridge is responsible for the algebra
  term meaning the same as the SQL text; it rejects what it does not model instead of
  approximating.
- The world's laws are assumptions about the DBMS. Known places where a real DBMS breaks
  them: functions that tell apart strings the collation treats as equal (`LENGTH`, `HEX`,
  `LIKE` against trailing spaces under PAD SPACE, `BINARY` casts); approximate (FLOAT /
  DOUBLE) arithmetic, which is not exact and not associative; errors and overflow (the
  model has none); plan-dependent behaviour such as grouping by DOUBLE values.
- `LIKE` and `REGEXP` are modelled as character-by-character matching with the world's
  character comparison. Collations with contractions or expansions (`'ss' = 'ß'` in some
  Unicode collations) do not compare character by character.
- The list of monotone functions (`EXP`, `FLOOR`, `CEIL`, `ROUND`, `ATAN`, `SIGN`; `ROUND`
  only on SQLite) is an assumption of the bridge. In the model a monotone function is any
  non-decreasing function on the reals.
- The checker matches rows of a value check by sorting the mutated column within groups of
  rows that agree outside it. This is justified because the rule functions are
  non-decreasing and keep the side of the pivot (0 or 1); it is not proved.
- When a database uses several collations, the checker applies the coarsest one to every
  result column; a real difference only in case on a binary column is then missed.
- After extraction the proofs are erased, so OCaml code can build an unproved rule record.
  Plug-ins should be written and registered in Rocq.
