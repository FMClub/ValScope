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

`results/mariadb-campaign.jsonl` has the 123 pairs that are still violated (seed, rule,
expected relation, verdict, original, mutant, the issue they were assigned to). A pair is
reproduced with `python3 bridge/gen_mysql_db.py SEED | mysql --force DATABASE` and its two queries.

No violation is left unexplained. Nearly nine out of ten come from one defect family
(issue 009), which hides whatever else a `SELECT DISTINCT` over a grouped query might show.
