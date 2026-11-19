# Candidate MariaDB bug: `MIN` / `MAX` of a `BIT` column return decimal text without `GROUP BY`

> This repository has no issue tracker, so this document (submitted through a PR) records the finding.
> Status: **candidate, not yet reported upstream, not checked against the MariaDB bug tracker.**
> It was reproduced on one version only (see "Limitations").

## Summary

On MariaDB 10.11.14, `MIN(x)` and `MAX(x)` over a `BIT(8)` column, in a query without
`GROUP BY`, return the **decimal text** of the value (`'2'`, `'242'`), while the result
metadata says the column type is `BIT` (type code 16). The same aggregate returns the
**bit value** (`0x02`, `0xF2`) when the query has a `GROUP BY`, or when it is wrapped in a
derived table or a `UNION ALL`. So two queries that must return the same value return
different bytes for the same column type.

## How it was found

By the Rocq version of ValScope (branch `main`), running the set-semantic rules
on the queries of the Python generator (`data/python-generator-queries.sql`) against the sample
schema, where `t2.c12` is `BIT(8)`. The rule `DISTINCT-add` wraps an operand of an `EXCEPT`
in `SELECT DISTINCT * FROM (...)`. The theorem says the mutant returns a subset of the
original's rows; it returned a row the original did not have, because the operand
`SELECT MIN(c12) ...` returned `b'2'` directly and `b'\x02'` under the derived table.

## Minimal reproducer

```sql
CREATE TABLE b (id INT PRIMARY KEY, g INT, x BIT(8));
INSERT INTO b VALUES (1, 1, 2), (2, 1, 242), (3, 2, 65);

SELECT x FROM b ORDER BY id;                         -- 0x02, 0xF2, 0x41
SELECT MIN(x), MAX(x) FROM b;                        -- '2', '242'     (decimal text)
SELECT * FROM (SELECT MIN(x) AS m FROM b) AS d;      -- 0x02
```

Observed with Python's `pymysql` (text protocol). The `mariadb` command-line client prints
both forms the same way, so the difference is only visible in the bytes a client receives.

## Variants

All on the table above; the values are the bytes received by the client.

| Query | Result | Column type |
| --- | --- | --- |
| `SELECT x FROM b ORDER BY id` | `0x02`, `0xF2`, `0x41` | BIT |
| `SELECT MIN(x), MAX(x) FROM b` | `'2'`, `'242'` | BIT, BIT |
| `SELECT MIN(x) FROM b WHERE g = 1` | `'2'` | BIT |
| `SELECT DISTINCT MIN(x) FROM b` | `'2'` | BIT |
| `SELECT g, MIN(x) FROM b GROUP BY g` | `0x02`, `0x41` | BIT |
| `SELECT * FROM (SELECT MIN(x) AS m FROM b) AS d` | `0x02` | BIT |
| `SELECT MIN(x) FROM b UNION ALL SELECT MIN(x) FROM b` | `0x02`, `0x02` | BIT |
| `SELECT HEX(MIN(x)), MIN(x) + 0 FROM b` | `'2'`, `2` | VARCHAR, INT |

- The value itself is right (`MIN(x) + 0 = 2`, `MIN(x) = b'00000010'` is true); only its
  encoding in the result differs.
- An index on `x` does not change the result (the plan is "Select tables optimized away"
  with and without it, and the result is the same with `WHERE g = 1`).

## Why it matters

A client that decodes a `BIT` column as raw bytes (as the protocol metadata says) reads the
wrong value from `MIN` / `MAX` of a `BIT` column in a non-grouped query: `'2'` is the byte
`0x32` (50), not 2. Results of equivalent queries cannot be compared byte by byte.

## Limitations

- Reproduced on MariaDB 10.11.14 (Ubuntu 24.04 package) only. MySQL, other MariaDB
  versions and other MySQL-compatible systems were not tested.
- Not checked against the MariaDB bug tracker or documentation; it may be known or
  documented behaviour of the text protocol for aggregates over `BIT`.
- The cause was not analysed. A guess: in a non-grouped aggregate the result is sent from
  an item that converts the integer value to a string, while the field metadata is taken
  from the `BIT` column.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
