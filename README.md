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
| `scripts/` | `setup_mariadb.sh` (set up the sample database), `demo.sh` (end-to-end run), CI helpers |
| `data/` | Sample MariaDB database and 870 queries produced by the original Python generator |
| `docs/` | `USAGE.md`: the step-by-step guide; `JOURNAL.md`: the log of work rounds |
| `results/` | The SQLite campaigns: 64 confirmed violations from 5 bugs (4 withdrawn), reduced pairs, commits; the campaigns over random databases on MariaDB (six campaigns, 207 pairs: 206 assigned to issues 003, 009, 010, 012, 013, 014, one false alarm found later) and on MySQL, Percona Server and TiDB |
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
and sqlglot 26.33 to 30.33 (`requirements.txt` pins 30.33.0). The GitHub Actions workflow
(`.github/workflows/ci.yml`) checks the proofs with Coq 8.18 and with Rocq 9 (9.2 from opam,
where `coq_makefile` / `coqc` became `rocq makefile` / `rocq c`; the Makefile and
`demo.sh` use whichever exists), runs the tests and the end-to-end runs on SQLite and
MariaDB 10.11 on every push.

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
| `theories/VUnion.v` | `UNION ALL` of value queries: one arm is mutated (`tmut_sound`), mutants keep keys, HAVING and source (`tmut_frame`) |
| `theories/VDistinct.v` | Value queries under `DISTINCT` / `UNION`, also on parts of a `UNION ALL`: the cover relation |
| `theories/VSet.v` | HAVING mutation inside `INTERSECT` / `EXCEPT` of value queries (`shmut_sound`) |
| `theories/VLineage.v` | A mutated value followed through a derived table (`wmut_sound`) |
| `theories/Registry.v` | The plugged-in rules and the mutators with their theorems: `mutate`, `vmutate`, `hmutate`, `tmutate`, `thmutate`, `shmutate`, `wmutate` |
| `theories/Counter.v` | A concrete lawful world; proofs that some positions must not be mutated |
| `theories/Extract.v` | Extraction to OCaml |
| `cli/main.ml` | Command-line front end of the extracted core (S-expression protocol) |
| `bridge/sql_bridge.py` | SQL text to algebra term and back (`Translation`), round-trip validation, the entry points `mutate_sql` and `mutate_value` |
| `bridge/printer.py` | Term to SQL (`Printer`, a mixin of `Translation`) and the type probes |
| `bridge/common.py` | The `Unsupported` exception, the S-expression reader, shared constants and helpers |
| `bridge/collation_law.py` | Which queries and mutants are outside the model because of collations; storage classes of columns |
| `bridge/determinism.py` | Constructs whose result SQL does not determine (rejected) |
| `bridge/lineage.py` | The outer query over a derived value query (`VLineage.v`) |
| `bridge/checker.py` | Bag inclusion modulo the DBMS's collation, and the five value relations |
| `bridge/test_bridge.py` | Tests of the bridge and the checkers (no database needed) |
| `bridge/gen_fragment.py` | Random queries inside the supported fragments, for any schema |
| `bridge/run_on_db.py` | Translation validation, execution of mutants, relation checks (MySQL protocol or SQLite file) |
| `bridge/gen_sqlite_db.py` | Random SQLite databases for the campaigns |
| `bridge/sqlite_exec.py` | Runs SQL on any SQLite shared library through ctypes |
| `bridge/build_old_sqlite.sh` | Builds old SQLite releases as shared libraries |
| `bridge/campaign_sqlite.py` | Differential campaign on several SQLite releases |
| `bridge/confirm_sqlite.py` | Re-checks recorded violations from scratch and writes a report |
| `bridge/bisect_sqlite.py` | Finds the SQLite commits that introduced and fixed each recorded violation |
| `bridge/reduce_sqlite.py`, `bridge/reduce_mysql.py` | Reduce a violating pair (query, data, indexes), re-running the verified mutator at every step |
| `bridge/campaign_mysql.py`, `bridge/gen_mysql_db.py` | Campaign on a MySQL-protocol server over random databases (one per seed) |
| `bridge/recheck_mysql.py` | Judges the pairs of such a campaign again, optionally without secondary indexes |
| `bridge/test_mysql.py` | Tests that need a MySQL-protocol server |
| `scripts/check_violations.py` | Compares the violations of a run with a baseline of known ones (keys and signatures) |
| `scripts/record_sqlite_pairs.py` | Adds the new pairs of an SQLite campaign to `results/`: confirm, bisect, reduce, bisect again, regenerate the reports |
| `scripts/replay_reduced_sqlite.py` | Replays the reduced SQLite pairs of `results/` on their releases: every known bug must still be detected (CI) |
| `scripts/recheck_recorded.py` | Judges the recorded MariaDB pairs (`results/mariadb-campaign.jsonl`) again with the present checker: a pair of a server defect must still be violated, a false alarm must not |
| `scripts/probe_collations.py` | Prints the collation the bridge reads for each result column of a few queries on a server; a wrong one would make the checker report false alarms |
| `scripts/check_reduced_mysql.py` | Checks that a reduced script still shows its violation |
| `scripts/triage_mysql.py` | Triage of a server campaign: every pair again, without secondary indexes, reduced, grouped by the shape of the reduced query, with a hint of the known issue |
| `.github/workflows/campaign.yml` | A campaign over random databases on any server image, started by hand; candidates, triage and reduced scripts as an artifact |
| `.github/workflows/sql.yml` | One SQL script of `data/` on any server image, started by hand (a reproducer on a release that is installed nowhere else) |
| `docs/JOURNAL.md` | The log of the autonomous work rounds: milestone, audit findings, what was done |
| `docs/USAGE.md` | End-to-end usage guide |
| `results/` | The SQLite campaigns (summary, confirmed and reduced pairs, bisection) and the MariaDB campaigns over random databases (classified pairs) |

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
- `tmut_sound` / `thmut_sound` (instances `tmutate_sound`, `thmutate_sound`, `VUnion.v`):
  the same two statements for a `UNION ALL` of value queries whose arms have the same
  number of columns; one arm is mutated, the other arm's rows correspond to themselves.
- `tmut_frame` (`tmutate_frame`): a value mutant keeps the grouping keys, the HAVING
  predicate and the source of every arm, so whatever is computed from the groups alone (a
  window function over them) is the same in the original and the mutant.
- `tmut_distinct_sound`, `tmut_mask_sound`, `tmut_mask_plain_sound`, `thmut_distinct_sound`
  (`VDistinct.v`): under `DISTINCT` on the whole query or on some parts of a `UNION ALL`,
  the rows of the two results cover each other (every row of each is related to a row of
  the other); a mutation outside the DISTINCT parts keeps the one-to-one correspondence;
  HAVING mutants give set inclusion.
- `shmut_sound` (`shmutate_sound`, `VSet.v`): HAVING mutation inside the operands of
  `INTERSECT` / `EXCEPT` of value queries gives set inclusion, with the direction flipped
  in the right operand of `EXCEPT`.
- `wmut_sound` (`wmutate_sound`, `wmutate_distinct_sound`, `VLineage.v`): an outer query
  over a derived value query (opaque `WHERE` and `HAVING`, `GROUP BY` on columns, items
  that are a column, `SUM` / `MIN` / `MAX` / `AVG` / `COUNT` of a column, or opaque) passes
  the relation of a mutated inner column on to the one item that reads it.
- `INTERSECT ALL` / `EXCEPT ALL` (`Bag.v`): an element occurs `min(a, b)` times in
  `INTERSECT ALL` and `a - b` times in `EXCEPT ALL`, modulo the collation; `EXCEPT ALL` is
  antitone on the right; `INTERSECT <= INTERSECT ALL` and `EXCEPT <= EXCEPT ALL`.
- `(e1, ..., en) IN (subquery)` (`Semantics.int3`) is row comparison in three-valued logic
  and is monotone in the subquery.

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
| `INTERSECT->INTERSECT-ALL` / `INTERSECT-ALL->INTERSECT` | Up / Down | not in the table (analogue of 2) |
| `EXCEPT->EXCEPT-ALL` / `EXCEPT-ALL->EXCEPT` | Up / Down | not in the table (analogue of 2) |

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

MariaDB 10.11.14, sample database `data/mariadb/` (from the original Python generator), with
all checks of the current version (round trip, collation law, per-column collations).

| Run | Queries | Supported | Checks passed | Violations |
| --- | --- | --- | --- | --- |
| Set-semantic, Python generator queries (`data/python-generator-queries.sql`) | 870 | 304 | 3863 | 2 (`BIT` candidates, `issues/005`, `issues/006`) |
| Value-semantic and HAVING, Python generator queries | 870 | 195 | 1903 | 0 |
| Set-semantic, `gen_fragment.py 200 1` (`scripts/demo.sh mariadb`) | 200 | 200 | 7718 | 0 |
| Value-semantic and HAVING, `gen_fragment.py --value 200 2` (with DISTINCT / UNION value queries) | 200 | 181 | 2697 | 4 (2 pairs, the `AVG` candidate, `issues/009`) |
| Set-semantic with `INTERSECT ALL`, `EXCEPT ALL`, row `IN`, `gen_fragment.py 300 21` | 300 | 300 | 10082 | 0 |

(Measured in the sixth round; the set checks went down a little because more mutants are
recognised as outside the model, the value checks up because of DISTINCT value queries
and window functions.)

How the audit fixes changed the numbers on the same inputs:

| | Before | After |
| --- | --- | --- |
| Set mutants skipped because the result types differed (Python queries) | 247 | 2 |
| Set mutants that MariaDB rejected (out-of-scope correlation, 200 generated queries) | 108 | 0 |
| Set mutants that could not be printed (200 generated queries) | 480 | 91 |
| Python generator queries usable by the value rules | 69 | 280 (sixth round; 138 in the fifth) |
| Translation mismatches (MariaDB / SQLite campaign) | 1 / 4 | 0 / 0 |

- Negative controls (`--flip`) report violations by the hundred on every run (for example
  759 on the 200 generated set queries).
- Of the queries of the original Python generator, 307 of 870 are translated for the set
  rules and 280 for the value rules. The rest use `LIMIT` whose kept rows are not
  determined (113), `SELECT DISTINCT` with aggregates, window functions and similar.
- **Candidate MariaDB bug** (set-semantic, Python generator queries): a `BIT(8)` value
  produced by `MIN` / `MAX` without `GROUP BY`, or by a scalar subquery, is sent as decimal
  text (`'2'`, `'14'`) while the result metadata says `BIT`; under a derived table or
  `UNION ALL` the bit value (`0x02`) is sent. Minimal case:
  `CREATE TABLE b (x BIT(8)); INSERT INTO b VALUES (2), (242); SELECT MIN(x), MAX(x) FROM b;`
  Written up in `issues/005-mariadb-bit-min-max-text.md` (PR #8).
- **Candidate MariaDB bug** (`DISTINCT-add`, generated queries): a `BIT(8)` scalar subquery
  evaluated per group of a `GROUP BY` that uses a loose index scan ("Using index for
  group-by") returns `255` instead of its value when the result goes through a derived table
  and a `UNION ALL` with a string. Minimal case and plan in
  `issues/006-mariadb-bit-subquery-loose-scan.md`.
- **Candidate MariaDB bug** (`issues/009-mariadb-distinct-avg-last-group.md`, found by the
  DISTINCT value queries of the sixth round): `SELECT DISTINCT g + 0, MAX(x) * 2, AVG(g)
  FROM t GROUP BY g` returns the `AVG` of the last group on every row.
- **Candidate MySQL bug** (`issues/008-mysql-intersect-not-null-outer-join.md`, MySQL 8.4.13, CI):
  `INTERSECT` matches a row whose first column is a `NOT NULL` integer with a row that has
  `NULL` there (from an outer join): two one-row tables reproduce it on MySQL 8.4.13; on
  9.7.4 only the larger case on the sample database does (MariaDB: correct).
- **SQLite compound collation** (`issues/007-sqlite-compound-collation.md`, 3.53.1 and
  3.54.1): the same `UNION ALL` de-duplicates `'a'` and `'A'` as equal in a compound
  (collation from the first arm that has one) and as different through a derived table
  (collation of the leftmost arm, `BINARY` for an expression). Perhaps intended; the
  bridge now treats a mutant that changes this as outside the model.
- Earlier value runs found the `HAVING COUNT(x) IN (subquery)` candidate
  (`issues/003-mariadb-having-count-in-subquery.md`).

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
consequence of grouping by approximate values. (Analysed since: `issues/011`. It needs a
column with display decimals, `DOUBLE(M,D)` or `FLOAT(M,D)`; four rows reproduce it.) The model groups by exact values, so the bridge rejects
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
  aggregation, window functions in set queries, window functions that can tell identical
  rows apart (`ROW_NUMBER`, `LAG`, `NTILE`, `ROWS` frames, ...) anywhere in the query
  (also inside derived tables and subqueries), `FULL` / `USING` / `NATURAL` joins, a
  `RIGHT JOIN` after another join or with `SELECT *` (a first `RIGHT JOIN` is translated as
  the swapped `LEFT JOIN`), recursive CTEs, table functions with column
  arguments, non-aggregated select items that are not grouping keys (at every level, also
  in subqueries, derived tables and `HAVING`), order-dependent aggregates (`GROUP_CONCAT` / `STRING_AGG` without an
  `ORDER BY` over their own values, `JSON_ARRAYAGG`, `JSON_OBJECTAGG`, `ANY_VALUE`, ...),
  value queries whose clauses refer to a select alias, non-deterministic functions
  (`RAND`, `NOW`, SQLite `random()`, `date('now')`, ...) and user variables.
- **Translation validation** (`run_on_db.py`, `campaign_sqlite.py`): the query as written
  and the query re-printed from its term must return the same rows, otherwise the query is
  not used and the mismatch is reported.
- **Round-trip validation of every printed query** (`sql_bridge.py`): the original and every
  mutant are printed, parsed back into a term and compared with the term the verified
  engine produced (atoms are compared as syntax trees, parentheses ignored). A mutant that
  does not survive is dropped and counted (`mutants_roundtrip_rejected`). Tests inject
  printer bugs (lost parentheses, lost `NOT`) and check that they are caught.
- **The collation law** (`outside_collation_law`): the theorems need every operation to
  respect the collation equivalence. An operation that tells equivalent strings apart
  (`LENGTH`, `HEX`, `CONCAT`, `LIKE`, `BINARY` casts, ...; division in SQLite, where `1`
  and `1.0` are equal) applied to the output of a de-duplication (`DISTINCT`, `UNION`,
  `INTERSECT`, `EXCEPT`; `GROUP BY`, `MIN`, `MAX` inside opaque parts) makes the result
  depend on which representative was kept. Such queries are rejected and such mutants
  dropped (`mutants_outside_model`). A function counts as respecting the equivalence only
  if it is on an explicit list; in SQLite, functions that turn a number into text
  (`UPPER`, `CAST AS TEXT`, ...) do not (`1` and `1.0` are equal, their texts are not).
  Not rejected: an operation inside a subquery that reads only that subquery's rows, and
  an operation that reads only columns holding one storage class in the database under
  test (integers, or reals without `-0.0`; the runners compute them), whose equivalent
  values are identical.
- **Collations of compounds** (`changes_compound_collation`, `sqlite_collation_sources`):
  SQLite takes a compound column's collation from the first arm whose item has one (a
  column or `COLLATE`; an expression passes it on), and MySQL / MariaDB derive it from all
  arms. A mutant that changes where it comes from is dropped. The checker compares a
  compound column with the coarsest collation of its arms (SQLite: each arm's metadata;
  MySQL / MariaDB: each arm run with `LIMIT 0`), and a compound nested in a derived table
  with the coarsest collation of the database.
- **Determined `LIMIT` only:** a `LIMIT` in a subquery is accepted when every output column
  is an `ORDER BY` key (tied rows are then identical) or the input is a single row.
- **Type guards:** a set-semantic check is skipped when the column types of the two results
  differ; a value check is `incomparable` when the mutated column is not numeric; value
  queries with FLOAT / DOUBLE grouping keys (MariaDB) or text inputs (SQLite) are skipped;
  single-precision inputs are compared with a looser tolerance (1e-4 relative instead of
  1e-9); integers and decimals are compared exactly.
- **Collation:** inclusion is checked modulo the database's own string equality, per
  result column: MariaDB / MySQL report each column's collation (`WEIGHT_STRING` gives the
  key), SQLite reports the source column and its declared collation. A result that is
  included only modulo that equality is reported as `collation`, not as a violation.
- **Failing mutants** are skipped, never treated as empty results; a lost server connection
  stops the run.

## What the checker tolerates

The theorems speak of exact values; a server prints rounded ones and types a column from
the plan. Each rule below was added after a false alarm of a campaign, and each can hide a
real defect of the kind in its last column. They are all in `bridge/checker.py` and
`bridge/run_on_db.py`. The first three are part of what a passed check means; the others
give a verdict of their own (`incomparable`, `collation`, `type_mismatch_skipped`,
`approximate_group_key`), counted apart from the passed checks.

| Difference accepted | Why it is not a violation | What it can hide |
| --- | --- | --- |
| The mutated value off by 1e-9 relative (1e-4 when an input is single precision) | binary floats are summed in the order of the plan | a float wrong by less than that |
| The mutated value off by one unit of the last printed decimal, for a float printed with a fixed number of decimals and for DECIMALs of different scales (`printed_decimals`; only when the values have no more decimals than reported, and near the pivot of `AwayOne` / `AwayZero` / `TowardOne` the value may move either way) | MariaDB prints `VAR_SAMP` with 4 decimals and an `AVG` over it with 8; `AVG` of a `DECIMAL(10,2)` has scale 6, an `AVG` over it scale 10 | a value wrong in its last digit |
| Other columns equal after rounding floats to 12, then 9 significant digits; DECIMALs with a fraction one decimal shorter (`_norm`) | `AVG(x) * 2` is 5.3333 or 5.3334 depending on whether the `AVG` went through a temporary table | a value of an unmutated column wrong in its last digits |
| A column that is `FLOOR` / `CEIL` / `ROUND` / `SIGN` of a variance or standard deviation, not the mutated one, differs by at most one step per value (`rejudge`, `step_columns`) | the last bit of a float decides between 1 and 2 | a defect that moves such a value by exactly one step |
| Strings equal under the collation of their result column (`fold`; verdict `collation`) | `DISTINCT` and `GROUP BY` keep one of `'a'` and `'A'`, unspecified which | a wrong string that is collation-equal to the right one |
| In a compound column that is a number in one arm and text or a date in another (`BIT` excepted), a text that is a number is compared as that number (`rejudge`, `last_mixed_columns`) | the text of a number (`'0'`, `'0.00'`) depends on which arms meet first and on materialization | a defect that only changes how a number is written in such a column |
| `INTERSECT` / `EXCEPT` over arms with a `_ci` and another collation (`last_arm_mix`; `collation`) | which rows match depends on the representative a `DISTINCT` kept | any wrong row of such a compound |
| The two results type a column differently (number in one, text in the other): the check is skipped | the values cannot be compared as SQL values | a wrong value that comes with a type change (on SQLite with numeric inputs, text on one side only **is** reported: `strict_types`) |
| Value queries grouped by a FLOAT / DOUBLE key are not run | equal keys can differ in the last bit between plans | defects of grouping by approximate values (`issues/011` was found by hand) |

## Results on SQLite

Run on four old SQLite releases (3.26.0, 3.30.1, 3.31.1, 3.34.0), the verified mutators found
**64 distinct query pairs** whose results violate the relation guaranteed by the rule's
theorem. Each one reproduces from scratch and is consistent on SQLite 3.54.1. Bisection on
SQLite's source history maps them to **5 distinct bugs** (pairs with the same introducing
and fixing commits are one bug; three of the fixing commits name an SQLite ticket). Four
were found by the set-semantic rules; the fifth by the HAVING and value rules: `HAVING COUNT(x) IN
(SELECT text_column ...)` turned the `COUNT(x)` of the select list into text, from 3.15.0
(2016) until 3.54.0 (2026), so the SQLite that Python 3.13 ships (3.53.1) still has it. Every
pair is reduced, query and database, keeping its verdicts on the commits that introduced
and fixed its bug (self-contained scripts in `results/sqlite-repro/`). Details and how to reproduce:
[`results/sqlite-campaign.md`](results/sqlite-campaign.md),
[`results/sqlite-bisect.md`](results/sqlite-bisect.md),
[`results/sqlite-reduced.md`](results/sqlite-reduced.md).

## Results on MariaDB and MySQL

There is no reference release for these servers, so each finding is a candidate, reduced by
hand or by `bridge/reduce_mysql.py` to a short script in `data/mariadb/` that CI runs on
MariaDB 10.11, 11.4 and 11.8 and on MySQL 8.4 and 9 (`.github/workflows/sql.yml` runs one
script on any other image). None was reported upstream (no access
to the trackers from the environment this was written in). The columns say where the
script gives a wrong result; Percona Server 8.4.11 behaves as MySQL 8.4 for 008 and 015, and
TiDB is in the last column of 016.

| Issue | What | MariaDB 10.11.14 | MariaDB 11.4.13 / 11.8.9 / 13.0.2 | MySQL 8.4.13 / 9.7.4 |
| --- | --- | --- | --- | --- |
| [003](issues/003-mariadb-having-count-in-subquery.md) | `HAVING <aggregate> IN (subquery)` finds no match | wrong | fixed for the minimal case; wrong when the subquery has an `IN` subquery | correct |
| [005](issues/005-mariadb-bit-min-max-text.md) | `MIN` / `MAX` of a `BIT` column return decimal text | wrong | wrong | correct in the minimal case |
| [006](issues/006-mariadb-bit-subquery-loose-scan.md) | a `BIT(8)` scalar subquery under a loose index scan returns 255 | wrong | wrong | correct |
| [008](issues/008-mysql-intersect-not-null-outer-join.md) | `INTERSECT` and `EXCEPT` match a NULL with a `NOT NULL` value of the other operand: the `NULL` of an outer join with a column, or a NULL with the constant 0 | correct | correct | wrong (8.0.46, 8.4.13, 9.7.4; which plans show it differs) |
| [009](issues/009-mariadb-distinct-avg-last-group.md) | `SELECT DISTINCT` over a grouped query: `AVG`, `STDDEV`, `VAR` of another group, NULLs, missing rows | wrong | wrong | correct |
| [010](issues/010-mariadb-window-distinct-aggregate-having.md) | a window function with a `DISTINCT` aggregate in a grouped join: `HAVING` applied wrongly, `RANK() + 3` is 0 | wrong | wrong | correct |
| [011](issues/011-mariadb-double-md-group-by.md) | `GROUP BY` on a `DOUBLE(M,D)` expression groups by the rounded or the exact value depending on the aggregates | wrong | wrong | correct |
| [012](issues/012-mariadb-in-date-index-null.md) | `x IN (SELECT date_column ...)` is FALSE instead of NULL when the column is indexed and `x` is not a date | wrong | wrong | correct |
| [013](issues/013-mariadb-decimal-negative-zero-group.md) | the DECIMAL `-0.00` (from `-3.00 % 3`) is grouped with `0.00` or apart depending on an unrelated aggregate | wrong | wrong | correct |
| [014](issues/014-mariadb-subquery-cache-collation.md) | the subquery cache matches `'A'` and `'a'` of a `_ci` outer column although the subquery compares under `_bin`: the result depends on the order of the rows | wrong | wrong | correct |
| [015](issues/015-mysql-left-join-semijoin-antijoin.md) | a LEFT JOIN loses its inner side (NULL-extended rows) when an `EXISTS` inside it and a `NOT EXISTS` outside it are both materialized on the constant 1 | correct | correct | wrong (8.0.46, 8.4.13, 9.7.4; 5.7.44 correct) |
| [016](issues/016-tidb-null-aware-antijoin-left-cond.md) | TiDB: `x NOT IN (correlated subquery)` with a condition on the outer row alone (`t.b <=> NULL`) returns every row twice | correct | correct (11.8.9) | correct (9.7.4); **TiDB v7.5.1, v8.5.3: wrong** |
| [017](issues/017-tidb-tidb-rowid-distinct-or.md) | TiDB: `SELECT DISTINCT` with an `OR` over two columns of a unique index fails with "Can't find column t1._tidb_rowid" after `ANALYZE` (an error, not a wrong result) | runs | not run | not run; **TiDB v7.5.1, v8.5.3: error** |
| [018](issues/018-tidb-union-decimal-double-rounding.md) | TiDB: a `UNION` of a `DECIMAL` and a `DOUBLE` arm rounds the `DOUBLE` to the `DECIMAL`'s scale (`ATAN(1) UNION ALL 1.5` gives 0.8) | correct | not run | correct (9.7.4); **TiDB v8.5.3: wrong** |

MariaDB 13.0.2 (the `latest` image, through `.github/workflows/sql.yml`) was checked for
003 and 009 to 014, and a campaign on it found 003, 010, 012 and 013 again; 005 and 006 were
not run there.

Not counted: [002](issues/002-mariadb-enum-max-having.md) (probably intended behaviour) and
[007](issues/007-sqlite-compound-collation.md) (SQLite, perhaps intended). The campaigns over
random databases that found 012 to 018 and re-found the others are in
[`results/mariadb-campaign.md`](results/mariadb-campaign.md) (the 207 MariaDB pairs, with their
issues, in `results/mariadb-campaign.jsonl`; `scripts/recheck_recorded.py` judges them again).

## Not done yet

- Value mutation applies to the select items of a `SELECT` or of the arms of a `UNION ALL`.
  Since the tenth round a mutated value is also followed through one derived table
  (`VLineage.v`, `wmutate_sound`): for `SELECT ... FROM (value query) AS d [WHERE] [GROUP BY]
  [HAVING]` the inner query is mutated, and the relation holds in the outer item that reads
  the mutated column, when that item is the column itself or `SUM` / `MIN` / `MAX` / `AVG`
  of it (order relations only) and nothing else reads the column (no other item, `WHERE`,
  grouping key or `HAVING`). The outer query is not re-printed: the mutant is the query as
  written with the body of the derived table replaced, and its reading is checked again on
  every mutant. Not followed: joins in the outer query, several levels, expressions over
  the column (what the Python lineage analysis approximates). Value queries with `SELECT DISTINCT` (and a `UNION` of value queries)
  are supported since the sixth round with a weaker check: after DISTINCT the rows no
  longer correspond one to one, and the theorem (`VDistinct.v`) states a cover in both
  directions (every row of each result is related to a row of the other).
- `SELECT DISTINCT` and `UNION` can also be any part of a `UNION ALL` of value queries
  (a `SELECT DISTINCT` arm next to plain arms): the theorem (`VDistinct.v`,
  `tmutate_mask_sound`) is the same cover, with the DISTINCT parts given by a mask over the
  `UNION ALL`. A mutation outside the DISTINCT parts keeps the one-to-one correspondence
  (`tmutate_mask_plain_sound`), and the bridge then uses the exact check. Such queries get
  no HAVING mutants (no theorem for them).
- Value rules do not apply to a top-level `INTERSECT` or `EXCEPT` of value queries: changing
  a value of one arm changes which rows the operator keeps. HAVING rules do (`VSet.v`,
  `shmutate_sound`): the result, as a set, grows with both operands of `INTERSECT` and with
  the left operand of `EXCEPT`, and shrinks with its right operand, where the direction is
  flipped. Operands with an aggregate that adds floats (`VAR_*`, `STDDEV_*`, and `SUM` /
  `AVG` unless their argument is integer arithmetic over columns that hold only integers
  on the database under test) are rejected: the server compares rows exactly, and two
  plans can round differently.
  `INTERSECT ALL` / `EXCEPT ALL` of value queries are rejected.
- Window functions are accepted as opaque items of value queries, and only those whose
  value is the same for identical rows (`RANK`, aggregates over the default frame, ...),
  with qualified columns in `PARTITION BY` / `ORDER BY` (MariaDB and MySQL resolve an
  unqualified name there to a select alias, which a mutation can change). In a grouped
  query the window ranges over the groups: a value mutant keeps the keys, HAVING and source
  of every arm (`Registry.v`, `tmutate_frame`), so it sees the same groups; a column the
  window reads must be a grouping key or inside an aggregate, and the query gets no HAVING
  mutants (they change the groups);
  `IN` with a value list stays an opaque predicate.
- Some set-semantic mutants cannot be printed as SQL and are dropped (84 of about 7800 on
  200 generated queries): `DISTINCT` around a join that is itself an operand of another
  join (a derived table would need renamed columns), and `DISTINCT` around a join of
  derived tables. `DISTINCT` around a join of base tables needs the schema (the runners
  read it from the database).
- SQLite has no `INTERSECT ALL` / `EXCEPT ALL`; those mutants are not printed for SQLite.
- SQLite before 3.39 rejects `HAVING` without `GROUP BY`; for SQLite such a value query (or
  mutant) is printed as a `WHERE` over a derived table that computes the predicate as a
  column. The round trip checks the standard form; `test_bridge.py` runs both forms.
- `ORDER BY` of the whole query without `LIMIT` is dropped (the bag of rows is the same).
- Only the MySQL and SQLite dialects of sqlglot were tested.

## Trusted base and caveats

- Verified: the rules, the engine and the registry, with respect to the SQL model in
  `Semantics.v`, for every lawful world.
- Not verified: `cli/main.ml` (parsing and printing of terms), `bridge/sql_bridge.py`,
  sqlglot, Rocq's extraction, and the checker. The bridge is responsible for the algebra
  term meaning the same as the SQL text; it rejects what it does not model instead of
  approximating.
- The world's laws are assumptions about the DBMS. Functions that tell apart strings the
  collation treats as equal are handled by the collation-law check above; its list of
  such functions is maintained by hand and may be incomplete. Other known gaps:
  approximate (FLOAT / DOUBLE) arithmetic, which is not exact and not associative; errors
  and overflow (the model has none); plan-dependent behaviour such as grouping by DOUBLE
  values.
- `LIKE` and `REGEXP` are modelled as character-by-character matching with the world's
  character comparison. Collations with contractions or expansions (`'ss' = 'ß'` in some
  Unicode collations) do not compare character by character.
- The list of monotone functions (`EXP`, `FLOOR`, `CEIL`, `ROUND`, `ATAN`, `SIGN`; `ROUND`
  only on SQLite) is an assumption of the bridge. In the model a monotone function is any
  non-decreasing function on the reals.
- The value checker decides whether a one-to-one correspondence between the result rows
  exists that satisfies the relation (bipartite matching); this is exactly the statement of
  `vmutate_sound` for results returned in any order. Floats are compared with a relative
  tolerance chosen by hand.
- SQLite does not report the collation of an expression column; for those the checker uses
  the coarsest collation of the database and can miss a case difference.
- After extraction the proofs are erased. To keep OCaml code from building an unproved
  rule, `make cli` makes the rule types abstract in the interface the front end is
  compiled against; `make check-abstract` (part of `make test`) checks that a rule forged
  in OCaml does not compile. The extracted code itself and Rocq's extraction stay trusted.
