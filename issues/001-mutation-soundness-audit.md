# Mutation rule soundness audit: design problems to discuss

> This repository has no issue tracker, so this document (submitted through a PR) stands in for issues. It records the design-level problems that need discussion.
> Implementation-level problems were fixed directly on the same branch; see "Implementation problems fixed directly" at the end.

## Audit method

- Read `mutator/set_mutator.py`, `mutator/value_mutator.py`, `changeAST.py`, `get_seedQuery.py` and `main.py` in full.
- Ran the whole pipeline (generate SQL → select seeds → mutate → check) against a local, unpatched **MariaDB 10.11.14**.
- Inspected the "bugs" the tool reported, by category, to decide whether the database was wrong or the mutation rule or the checking logic was.

**Limitations:**

- The OSDI 2026 paper could not be read (usenix.org is unreachable from the audit environment). Every conclusion below is based on the code and on measurements, not on a rule-by-rule comparison with the paper's definitions.
- Only MariaDB 10.11 was tested. MySQL, TiDB, OceanBase, Percona and PolarDB were not.
- Reports were sampled per category (1–3 per category), not checked one by one. Every sampled report was a false positive.

## Measured results

| Mode | Scale | Reports before fixes | Reports after fixes |
| --- | --- | --- | --- |
| Value-semantic mutator (`use_value_mutator = True`, the default) | 6 random seeds × 800 generated queries | 97 | 52 |
| Set-semantic mutator (`use_value_mutator = False`) | 4 random seeds × 500 generated queries | 2 | 2 |

The 54 reports that remain after the fixes all fall under Problem 1 and Problem 2. They are design-level and cannot be solved by changing a few lines.

Breakdown of the 97 reports before the fixes:

| Category | Count | Status |
| --- | --- | --- |
| `SIN/COS/TAN/LOG(x) * k`: multiplying a negative value by a positive constant makes it smaller | 56 | Fixed |
| The mutated value reaches several outer output columns, only one of which is recognised | about 28 | Problem 1 |
| The mutated inner column is used by the outer query as a join key or in WHERE, so the row count changes | about 11 | Problem 1 |
| No mutation was applied, yet the results of two executions were still compared | 2 | Fixed |

---

## Problem 1: the value-semantic "approximation propagation analysis" has no sound basis

**Symptom.** The value-semantic mutator rewrites any column, scalar function or aggregate directly under an `Alias` (including those in subqueries and CTEs). It then assumes that the rows of the original and the mutated result correspond one to one and that only one column changes monotonically. In many contexts this assumption does not hold.

Two classes of counterexamples were observed (MariaDB's results are correct; the tool reports a bug):

```sql
-- the original query returns 8 rows, the mutated query returns 0
SELECT subq.c2 AS c2, subq.c6 AS c6
FROM (SELECT s.c2 AS c2, s.c1 /* mutated to s.c1 * 2 */ AS c1, s.c6 AS c6 FROM t1 AS s) AS subq
CROSS JOIN t3 ON (t3.c2 = subq.c1)
```

The inner `c1` is used as a join key by the outer query, so changing its value changes the join result.

```sql
-- inner SUM(c4) is mutated to SUM(c4 * 2); two outer columns reference it
SELECT subq.sum_c4 AS sum_c4, subq.c6 AS c6, subq.sum_c4 AS col_1_2
FROM (SELECT SUM(s.c4) AS sum_c4, s.c6 AS c6 FROM t1 AS s GROUP BY s.c6) AS subq
```

`get_branch_type` finds only one reference. The other column is treated as "must not change" and takes part in the row-signature comparison, so the check fails.

**Root cause.** `get_branch_type` and `_compare_by_branch` are heuristics over the names of the nodes on the AST path. There is no real column lineage or monotonicity analysis:

- When the mutated value is used in an outer `JOIN ON`, `WHERE`, `HAVING`, `GROUP BY`, `DISTINCT` or set operation, it affects the set of rows, not the value of one column.
- When the mutated value passes through a non-monotone expression (`a - x`, `-x`, `MOD`, `COS(x)`, `BIT_XOR`) before it is output, the direction is undetermined.
- When several output columns reference the same value, all affected columns have to be found.
- The `where_affected` branch only looks at the type of the first comparison operator on the path. It does not distinguish whether the mutated value is on the left or the right of the operator. `x > (subquery)` and `(subquery) > x` have opposite expected directions.
- Rows are paired by sorting on the non-mutated columns first and the mutated column second. When the non-mutated columns contain duplicates, the pairing can be wrong.

**To discuss.**

- Should every expression get a four-valued propagation result (unchanged, increasing, decreasing, unknown), propagated operator by operator, with the mutation skipped on "unknown"?
- How should row correspondence be defined: require queries to carry a unique key, or match on multisets?
- How does this code relate to the approximation propagation analysis in the paper? Does it implement only part of it?

---

## Problem 2: rules 3 and 4 lack the precondition "column types are identical"

**Symptom.** `A EXCEPT B → A` and `A INTERSECT B → A UNION B` assume that the column types of the result do not change. A set operation unifies the column types of its two operands, so removing or replacing one operand changes the result type.

Measured (both reports left in set mode after the fixes are of this kind):

```sql
SELECT a.c4 AS col_1, a.c4 AS col_2 FROM t1 AS a          -- c4 is INT
EXCEPT
SELECT c.col_1, c.col_2 FROM cte AS c                      -- col_1 is TINYBLOB
```

- The first column of the original query returns `b'3'`, `b'16'` (unified to a binary string).
- The mutated query (right operand of `EXCEPT` removed) returns `3`, `16`.
- The value-by-value comparison in Python finds them unequal and reports "the original result is not a subset of the mutated result".

The same happens when a `BIT(8)` column meets an integer column in a set operation: one side is `b'\xe3'`, the other `b'227'`.

Values are now normalised (numbers, dates, times) before the check. That removes differences such as `DATE` versus string and `FLOAT` versus `DECIMAL`, but binary and `BIT` types cannot be handled by normalisation.

**To discuss.** Two directions:

- Add a precondition to the rules and apply them only when the corresponding columns of both operands have the same type. This requires type inference.
- Change the shape of the rule: keep the set operation and make one operand empty, for example `A EXCEPT (SELECT * FROM (B) AS x WHERE 1 = 0)`. Type unification then behaves the same, but the optimizer path under test is not exactly the one the original rule exercises.

---

## Problem 3: results are compared with Python semantics, not DBMS semantics

The checker fetches the results into Python and compares them there. Wherever this differs from the database's own comparison rules, false positives or false negatives are possible:

- **Collation.** `MIN(c) → MAX(c)` is also applied to string columns, and the order is then decided by code-point order after `str.lower()`. Measured under MariaDB's default `utf8mb4_general_ci`: `MIN('ax', '_x') = 'ax'` and `MAX = '_x'`, while Python considers `'_x' < 'ax'` and would conclude that "MAX is smaller than MIN".
- **Rounding to two decimals.** The value-semantic comparison applies `round(float(x), 2)` everywhere. Differences below 0.005 are invisible, and large integers and high-precision `DECIMAL` values lose precision when converted to `float`.
- **Type conversion.** A string that parses as a number is compared as a number; `bytes` goes through `str()` and is then tried as a number.
- **Failing queries.** In value-semantic mode, when both the original and the mutated query fail, the outcome is recorded as "as expected".

**To discuss.** Should the comparison be pushed down into the database (for example with `EXCEPT ALL` or a self-join, so that the DBMS decides inclusion and ordering itself), or at least be chosen per column type?

---

## Problem 4: preprocessing rewrites the query under test, so real coverage is smaller than the rule table suggests

Before mutating, both modes heavily rewrite the seed query:

- `detailsolve` in set mode:
  - removes every `GROUP BY` and `LIMIT`;
  - replaces aggregate functions with their argument, and window functions and scalar subqueries with the constant `1`;
  - forces every `LEFT/RIGHT/CROSS JOIN` to `INNER JOIN`.
- `_preprocess_ast` in value-semantic mode:
  - removes every `DISTINCT` and most `LIMIT`s;
  - replaces every aliased expression other than the target with its first argument (`ABS(c)` becomes `c`, `a + b` becomes `a`).

Consequences:

- The "original query" that is actually executed is no longer the query the generator produced. In set mode, optimizer paths for outer joins, aggregation and `LIMIT` are essentially never exercised.
- The rewritten query is often invalid. In set mode, 67 of 1801 executions failed, typically because `HAVING` references a column that is not in the select list once `GROUP BY` is removed.
- The sqlglot round trip silently changes functions: `VAR_SAMP(c)` is parsed into a `Variance` node and printed as `VARIANCE(c)`, which is the population variance in the MySQL family, not the sample variance. Both the original and the mutated query are changed, so there is no false positive, but `VAR_SAMP` is in fact never tested.

**To discuss.** Preprocessing exists to make the rules hold, at the price of changing what is tested. Should it be replaced by "do not rewrite the query; skip the rule when it does not apply"?

---

## Problem 5: the polarity rules of the set-semantic mutator need a complete definition

**Before.** The original implementation flipped the direction only under `NOT` and on the right side of `EXCEPT`, and treated every other context as positive. In the following positions the direction of a mutation is in fact undetermined:

- Scalar subqueries (`x > (SELECT ...)`, subqueries in the select list).
- Predicates or subqueries inside `CASE WHEN` or function arguments.
- Queries with `LIMIT`, and `SELECT`s with aggregates or window functions.
- The `ON` condition of an outer join (after `ON cond → ON TRUE`, the rows that used to be NULL-padded disappear).
- CTE bodies (the original implementation always treated them as positive, but a CTE can be referenced on the right side of `EXCEPT` or inside `NOT IN`).

**Now.** On this branch polarity is three-valued: positive, negative, unknown. Nothing below an unknown context is mutated. A CTE body takes the polarity of all its references and is skipped when the references disagree or when it is not referenced.

**To discuss.** This is conservative and costs coverage. Possible refinements:

- `x > ALL (subquery)` is negative in the subquery and `x > ANY (subquery)` is positive; both are currently skipped as unknown.
- `LEFT JOIN` is positive in its left table; only the `ON` condition and the right table are undetermined. The whole join is currently skipped.
- Aggregates such as `SELECT COUNT(*) FROM (subquery)` could be handed to the value-semantic side (a larger result set gives a larger `COUNT`). This is exactly what a "unified model" should cover.

---

## Problem 6: how to express rules with data-dependent preconditions

Several rules in `mutation.md` have preconditions that depend on run-time data:

| Rule | Precondition |
| --- | --- |
| 21: `VAR_SAMP(c) → STDDEV_SAMP(c)` | Documented as `c < 1`; it actually depends on whether the variance is below 1, not on `c` |
| 22: `STDDEV_SAMP(c) → VAR_SAMP(c)` | Documented as `c > 1`; it actually depends on whether the standard deviation is above 1 |
| 23: `SUM(c) → SUM(c * k)` | `k` has the same sign as `c` |
| 25: `expr → expr * k` | `k` has the same sign as `expr` |
| 26: `FUNC(c) → FUNC(c * k)` | `FUNC` is monotone and `k > 0`; `c ≥ 0` is also required |

The original code did not check these preconditions (`k` is always positive and the sign of `expr` is ignored). They are now checked per row at run time: a negative original value is expected to decrease, and rule 22 picks the expected direction from whether the original value is below 1.

**To discuss.**

- The preconditions of rules 21 and 22 in the documentation need to be corrected.
- A per-row run-time check turns "rule + precondition" into "two rules with opposite directions". Does that match the paper's definition of a mutator?
- Rule 26 is implemented only for `SUM` and `AVG`; the set of "monotone functions" is not defined.

---

## Problem 7: inconsistencies between the code, the documentation and the bug table

These are not soundness problems, but they affect reproducibility:

- **The default configuration only runs the value-semantic mutator.** With `use_value_mutator = True` in `main.py`, `changeAST.py` calls `ValueMutator` only, and the set-semantic rules 1–17 never run. The README does not say that two runs are needed.
- **Rule 2 is disabled in the code.** The branch that handles `UNION → UNION ALL` in `set_mutator.py` is commented out, yet `trigger bug rules.md` attributes three MySQL bugs to rule 2.
- **Rules 7–11 and 14 never took effect before the fixes.** The node class names and argument names were wrong (see below), so the code was dead. No bug in the bug table is attributed to these rules, which is consistent with that.
- **Source code is incomplete.** `sql_generation/` contains only `__init__.py` and `.pyc` files; `mutator/__pycache__` holds `.pyc` files for modules such as `aggregate_mutation` and `optimized_aggregate_mutation` that have no `.py` counterpart.
- **Dependency versions are not pinned.** `requirements.txt` only requires `sqlglot>=18.0.0`, but the code depends on specific node class names and argument names (for example `with` versus `with_`), which differ between versions. This audit used sqlglot 30.33.0.

**To discuss.** Is this the code that found the 67 bugs? If not, the version used at the time should be added.

---

## Problem 8 (plan): formalise and prove the rules in Rocq

Problems 1, 2, 5 and 6 all come down to rule preconditions that were neither written down precisely nor proved. Proposed direction:

1. Define in Rocq the syntax of a SQL fragment and its semantics over multisets with three-valued logic.
2. Define the approximation relations: multiset inclusion for set semantics, an order on scalars for value semantics, and the truth order `FALSE < NULL < TRUE` for predicates.
3. Prove the polarity theorem: positive contexts preserve the approximation relation, negative contexts reverse it.
4. Write a soundness lemma for each of the 26 rules and pin down the missing preconditions (sign, identical types, join kind) in the proofs.
5. Extract the verified mutator and checker to OCaml; the existing Python code only generates SQL and talks to the database.

**To discuss.** Scope: proofs only, proofs plus an extracted core, or a full rewrite including the generator.

---

## Implementation problems fixed directly

These are implementation details. They are committed on this branch and need no discussion.

Set-semantic mutator (`mutator/set_mutator.py`, `changeAST.py`):

- Rules 8–10 (weakening comparison operators): the code matched the class names `Gt/Lt/Eq`, while sqlglot uses `GT/LT/EQ`, so nothing ever matched. Now `a < b → a <= b`, `a > b → a >= b`, `a = b → a >= b`.
- Rules 7 and 14 (`LIKE`, `REGEXP`): the code looked for a `pattern` argument, while sqlglot stores it in `expression`; the class name for `REGEXP` is `RegexpLike`. Corrected.
- Rule 11 (dropping one `AND` operand): the code modified a non-existent `expressions` argument, so the SQL was identical before and after. The left operand is now kept.
- `NOT LIKE` is `Like(negate=True)` in sqlglot, not `Not(Like)`, so the direction has to be flipped.
- `REGEXP` patterns are rewritten textually only when they contain no character classes, groups, escapes, alternation or lazy quantifiers (the `^` in `[^abc]` is a negation and must not be removed).
- `node.replace()` has no effect on the root node, so `A EXCEPT B → A` at the top level left the SQL unchanged. The root is now replaced explicitly and the `WITH` clause is kept.
- A failed query used to be treated as an empty result set. An empty original made every check pass, and an "empty" mutated query could cause a false positive. Such cases are now skipped.
- Turning an `INNER JOIN` without a join condition into a `LEFT JOIN` is a syntax error. Skipped.
- `detailsolve` added `ORDER BY ... LIMIT 1` to every single-column `SELECT`, including the top-level query. It is now added only to subqueries in scalar position.
- Numbers, dates and times are normalised before the check.
- Polarity analysis is three-valued; see Problem 5.

Value-semantic mutator (`mutator/value_mutator.py`):

- `expr * k`, `SUM(c * k)`, `AVG(c * k)`: the expected direction is reversed when the original value is negative.
- `STDDEV_SAMP → VAR_SAMP`: the original code special-cased "below 1" only for the function name `Stddev`; `StddevSamp` was not covered.
- `AVG(c) → MAX(c)` is applied to numeric columns only. For a `TIME` column, `AVG` returns a number such as `41852.0000` while `MAX` returns `10:11:12`, which is 36672 in seconds and would be judged as "MAX is smaller than AVG".
- `_mutate_monotonic_multiplication` referenced an unassigned variable for `AVG`; the exception was swallowed further up and all remaining mutations of that query were skipped.
- Results are no longer compared when no mutation was applied (for example for non-numeric columns).
