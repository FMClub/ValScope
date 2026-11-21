# Campaign on MariaDB over random databases

`bridge/campaign_mysql.py` builds one random database per seed (`bridge/gen_mysql_db.py`:
random column types, NULLs, duplicates, a primary key, random indexes), generates queries
for it and checks every mutant against the relation of its rule's theorem. Unlike SQLite
there is one server and no reference release: a violation is a candidate, classified by
hand with the help of `bridge/recheck_mysql.py` (the pair again, also without secondary
indexes) and `bridge/reduce_mysql.py`.

## First campaign (round 8 of the journal)

```bash
python3 bridge/campaign_mysql.py --seeds 1-40 --queries 40 --focus --value-ext --host 127.0.0.1 --port 3306 --user root --password 123456 --out violations.jsonl
python3 bridge/recheck_mysql.py violations.jsonl --port 3306 --password 123456 --out still.jsonl
python3 bridge/recheck_mysql.py violations.jsonl --port 3306 --password 123456 --no-indexes
```

MariaDB 10.11.14, 40 databases, 3200 queries, 122200 checks passed, 125 violating pairs.

| Class | Pairs | What |
| --- | --- | --- |
| False alarm of the tool | 2 | `AVG->MAX` over a derived `VAR_SAMP`: MariaDB prints such a DOUBLE with 4 decimals in one result and 8 in the other. Fixed: the relation allows one unit of the last printed digit (`check_value(output_decimals=...)`). |
| `issues/009` | 110 | `SELECT DISTINCT` over a grouped query: aggregates computed at the end (`AVG`, `STDDEV_SAMP`, `VAR_SAMP`) take the value of another group, or NULL. 13 of them looked index-dependent or different (rows missing); `reduce_mysql.py` brought three of those to two rows without indexes and the shape of issue 009. |
| `issues/012` (new) | 5 | `number IN (SELECT date_column ...)` is FALSE instead of NULL when the subquery has a NULL and the column is indexed; `NOT IN` returns rows. Holds without the index. |
| `issues/010` | 4 | A window function with a `DISTINCT` aggregate in a grouped (semi-)join: HAVING applied wrongly, or `RANK() OVER (...) + 3` is 0. |
| `issues/003` | 3 | `HAVING <aggregate> IN (subquery)` finds no match. |
| `issues/013` (new) | 1 | The DECIMAL `-0.00` (from `-3.00 % 3`) is grouped with `0.00` or apart depending on an unrelated aggregate. |

## Second campaign (round 9 of the journal)

The same campaign on the seeds 41-90 with `--no-value-distinct`: no `SELECT DISTINCT` and no
`UNION` in the value queries, so that issue 009 does not hide the rest.

```bash
python3 bridge/campaign_mysql.py --seeds 41-90 --queries 40 --focus --value-ext --no-value-distinct --port 3306 --password 123456 --out violations.jsonl
python3 scripts/triage_mysql.py violations.jsonl --port 3306 --password 123456 --out-dir triage
```

MariaDB 10.11.14, 50 databases, 4000 queries, 148599 checks passed, 37 violating pairs.
`scripts/triage_mysql.py` (new) judged each pair again, with and without the secondary
indexes, reduced it and grouped the pairs by the shape of the reduced query.

| Class | Pairs | What |
| --- | --- | --- |
| False alarms of the tool | 5 | (1) `AVG->MAX` in a derived query: `AVG` of a `DECIMAL(10,2)` has scale 6, an `AVG` over it scale 10, and `3.3333333333 > 3.333333`. Fixed: one unit of the coarser scale is allowed for DECIMALs of different scales. (2) Three pairs: `EXCEPT ALL` of a `DISTINCT` arm over a `_ci` column and an arm over a `_bin` column; which rows match depends on whether the `DISTINCT` kept `'a'` or `'A'`. (3) One pair: a column that is `DOUBLE`, `DECIMAL` and `DATE` in three arms; the numbers become text, `'5'` or `'5.00'` depending on which arms are combined first. Fixed: such compounds give the verdicts `collation` and `incomparable` (`MySQLTarget.last_arm_mix`). |
| `issues/003` | 11 | `HAVING <aggregate> IN (subquery)`. New here: the rule `COUNT->COUNT-DISTINCT` finds it too, because an aggregate of the select list decides whether the defect shows. |
| `issues/012` | 9 | All nine hold without the secondary indexes. New here: the left value can be a `VARCHAR`, a `BIGINT` or a row `(a, b)`; the result is FALSE exactly for values that cannot be read as a date. |
| `issues/013` | 7 | Every reduced pair has two rows, `-3.00` and `0.00` or `3.00`, grouped by `x % 3` with `COUNT(DISTINCT ...)` on one side. |
| `issues/010` | 5 | A window function with a `DISTINCT` aggregate over a semi-join. |

No new defect; no pair is left unexplained. The four known defects are found again on
fifty other databases, three of them in forms that the issues did not have yet.

## Third to sixth campaign (rounds 10 to 12): the rich generator

`--rich` adds opaque predicates, derived tables and expressions in the select list. It was
written for SQLite; the third campaign (seeds 91-130) showed that MariaDB refused 737 of
its 3200 queries (`GLOB`, `IS <value>`, `COLLATE NOCASE`, `||`, `likely`). The generator now
writes the MySQL spelling for a MySQL database, and the fourth campaign used it:

```bash
python3 bridge/campaign_mysql.py --seeds 131-170 --queries 40 --rich --value-ext --no-value-distinct --port 3306 --password 123456 --out violations.jsonl
```

| Campaign | Queries (supported) | Checks passed | Pairs | Classes |
| --- | --- | --- | --- | --- |
| 3 (seeds 91-130, SQLite spelling) | 3200 (2221) | 44102 | 9 | `issues/013`: 5, `issues/003`: 2, `issues/012`: 2 |
| 4 (seeds 131-170) | 3200 (2947) | 70643 | 8 | `issues/013`: 7, **`issues/014` (new): 1** |
| 5 (seeds 171-230, `--rich --focus`) | 4800 (4372) | 160621 | 20 | `issues/003`: 8, `issues/013`: 8, `issues/012`: 2; 2 false alarms (mixed types under a compound in a derived table, fixed) |
| 6 (seeds 281-360, `--rich`) | 6400 (5911) | 144990 | 19 | `issues/003`: 11, `issues/013`: 4, `issues/010`: 1, `issues/012`: 1 (by their hints); 2 false alarms: a number arm and a text arm, and `AVG(x) * 2` printed as 5.3333 or 5.3334 in a column the mutation does not touch (fixed: such a DECIMAL may differ in its last digit) |

`issues/014`: the subquery cache looks its key up under the collation of the outer column
(`utf8mb4_general_ci`) while the subquery compares under `utf8mb4_bin`; `'A'` and `'a'` share
one entry, so `WHERE 0 OR s IN (SELECT v FROM b)` and `WHERE s IN (SELECT v FROM b)` return
different rows. Found by `OR-drop-operand` on seed 147. The hints of `scripts/triage_mysql.py`
named the issue of the other sixteen pairs; each was confirmed on its reduced script. The
eighteen pairs of the fifth campaign carry the issue of their hint (the reduced scripts of
four of them were read).

## Other servers (round 10 and 11)

CI runs a small campaign (seeds 1-12, `--focus`) on MySQL 8.4 and 9 and on MariaDB 11.4 and
11.8, and `.github/workflows/campaign.yml` runs any campaign on any server image by hand.

| Server | Campaign | Checks passed | Pairs | Classes |
| --- | --- | --- | --- | --- |
| MySQL 8.4.13 | seeds 1-12, `--focus` | 36003 | 0 | |
| MySQL 9.7.4 | seeds 1-12, `--focus` | 35882 | 0 | |
| MariaDB 11.4.13, 11.8.9 | seeds 1-12, `--focus` | 36142 | 3 | `issues/010`: 2, `issues/003`: 1 (the form that 11.x did not fix) |
| MariaDB 11.8.9 | seeds 131-170, `--rich` | 70641 | 11 | `issues/013`: 7, `issues/010`: 2, `issues/003`: 1, `issues/014`: 1 |
| MySQL 9.7.4 | seeds 131-170, `--rich` | 68746 | 12 | 6 false alarms (mixed types, fixed); 6 pairs of seed 144: `issues/015` |
| MariaDB 13.0.2 (`mariadb:latest`) | seeds 231-280, `--rich` | 91064 | 18 | `issues/013`: 8, `issues/010`: 4, `issues/012`: 4, `issues/003`: 2 (by their hints); 1 false alarm (a number arm and a text arm, fixed) |
| MySQL 8.4.13 | seeds 231-280, `--rich` | 89483 | 2 | `issues/008`: 1; the same false alarm: 1 |
| MySQL 9.7.4 | seeds 171-230, `--rich --focus` | 155729 | 3 | `issues/008` in a new, simpler form (NULL matches 0): 1; 2 false alarms (a number arm and a text arm; `CEIL(VAR_SAMP(...))` in another column, both fixed) |


The reproducers of `data/mariadb/` on MariaDB 13.0.2 (`sql.yml` with the directory): issues
009, 010, 011, 012, 013 and 014 give the same wrong results as on 10.11.14; of issue 003
the minimal case is right and the nested one (`having-in-nested.sql`) wrong, as on 11.x.

## The records

`results/mariadb-campaign.jsonl` has the 207 pairs that are still violated (campaign, seed,
rule, expected relation, verdict, original, mutant, the issue they were assigned to; for the
campaigns after the first also the reduced pair and the verdict without secondary indexes). A pair is
reproduced with `python3 bridge/gen_mysql_db.py SEED | mysql --force DATABASE` and its two queries.

In the first campaign nearly nine pairs out of ten come from one defect family (issue 009),
which hides whatever else a `SELECT DISTINCT` over a grouped query might show; hence the
second campaign.
