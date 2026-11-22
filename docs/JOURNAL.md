# Work journal

Autonomous rounds: each round finishes a milestone, records it here, tidies the repository,
audits the code, and sets the TODO list of the next round. Newest round last. Open items
that outlive a round are kept in `issues/004-open-problems.md`.

## Round 1 (2026-11-21)

**Milestone.** A mutated value is followed through a derived table: `theories/VLineage.v`
(`wmutate_sound`), `bridge/lineage.py`, `gen_fragment.py --value-ext`. Also in this stretch:
issue 011 (GROUP BY on `DOUBLE(M,D)`), the old `CROSS JOIN` mismatches explained, the ninth
SQLite campaign (51 confirmed pairs, 5 bugs).

**Tidying.** `bridge/sql_bridge.py` (2481 lines) split by responsibility: `common.py`,
`collation_law.py`, `determinism.py`, `lineage.py`; `sql_bridge.py` (1686 lines) keeps
`Translation`, the round-trip validation and the entry points, and re-exports the moved
names, so no caller changed. README file table brought up to date.

**Audit findings / TODO for round 2.**
1. Record the tenth SQLite campaign (seeds 7001-7030, running); one set-rule pair on 3.34.0
   only (`cond->TRUE`, seed 7006) may be a bug other than bug 1: bisect it.
2. `sql_bridge.py`: `Translation` is still 1080 lines (parsing and printing in one class).
3. `OCount` is never produced by `lineage.py` (`COUNT(d.c)` becomes an opaque item).
4. `scripts/check_reduced_mysql.py` decides the cover check from the text of the query,
   not from the bridge (`cover_for`).

## Round 2 (2026-11-21)

**Milestone.** Structure and tooling: `bridge/printer.py` (the term printer as a mixin;
`sql_bridge.py` is down to 1258 lines), `make lint` (pyflakes, also in CI),
`scripts/record_sqlite_pairs.py` (confirm, bisect, reduce, bisect again and record the new
pairs of a campaign in one step; `results/` is touched only when every step succeeded).
Pair 52 recorded with it: seed 7006, `cond->TRUE` on 3.34.0 only, bug 3
(`INNER JOIN ... ON (1)` 36 rows, `CROSS JOIN` 6 rows after reduction).

**Also done.** `lineage.py` recognises `COUNT(d.c)`; `check_reduced_mysql.py` asks the bridge
whether a pair is checked by a cover; README "What is proved" lists the theorems of
VUnion (frame), VDistinct, VSet and VLineage; `demo.sh`: the negative control also runs on
value queries and fails the run when it finds nothing; the SQLite demo generates value
queries over numeric columns (`gen_fragment.py --sqlite-seed`) with `--value-ext`.

**Audit findings.**
- Unprintable mutants were suspected to be a large loss (596 per 2400 queries in a
  campaign). Measured with the schema: 48 of 6606 mutants (`DISTINCT` around a join that is
  an operand of another join); the rest of the counter is `INTERSECT ALL` / `EXCEPT ALL`,
  which SQLite does not have. No action.

**TODO for round 3.**
1. Record the tenth SQLite campaign (seeds 7001-7030) with the new script.
2. `campaign_sqlite.py` counts mutants that SQLite cannot express (`INTERSECT ALL`) under
   `mutants_not_printable` as well as `mutants_not_in_dialect`: separate the counters.
3. The lineage path runs only when the outer query is itself a supported value query.

## Round 3 (2026-11-21)

**Milestone.** The tenth SQLite campaign (seeds 7001-7030) recorded: 60 confirmed pairs,
**6 bugs**. Bug 6 is the first one found by the value side: `HAVING COUNT(x) IN (SELECT
text_column ...)` turns the `COUNT(x)` of the select list into text; introduced in 3.15.0
(2016), fixed in 3.54.0 (2026-07), present in the SQLite that Python ships.

**What made it visible.** Numeric columns for value queries (ninth round) and a reference
that is the newest release: `confirm_sqlite.py` and `campaign_sqlite.py` take `--latest LIB`.

**Bridge fixes found on the way.**
- `GROUP BY (x % 5)`: parenthesised grouping keys were re-printed with two levels of
  parentheses and then failed the round trip, so the recorded pair could not be reduced.
  `_strip_parens` now removes every level; atoms are stored without outer parentheses, so
  a re-printed query is a fixed point of the bridge (new test).
- `record_sqlite_pairs.py`: reduced pairs that coincide share one bisection record (the
  completeness check counted records); intermediate files of an interrupted run are reused.

**Audit findings / TODO for round 4.**
1. The reduced pairs 53 and 54 were produced before the parenthesis fix and carry
   `((((COUNT(...))))` in their text: re-reduce them.
2. CI does not exercise bug 6: its SQLite (3.45.1, Ubuntu) has the bug, so a
   `--value-ext` demo query can hit it; decide between a signature in the baseline and a
   regression test that expects it.
3. `campaign_sqlite.py` still uses Python's SQLite as the reference by default: document
   that campaigns should pass `--latest`, or build it in CI.
4. The value rules proper have found nothing on SQLite: look at what the 49596 checks
   cover (which rules, which shapes), and whether SQLite's dynamic typing of results
   (text vs integer, as in bug 6) is checked for value mutants too.

## Round 4 (2026-11-21)

**Milestone.** The value rules find bug 6 too: 64 confirmed pairs, 6 bugs. The mutated
column of a value mutant held the text `'2'` on one side and a number on the other; the
checker filed that as "incomparable". With numeric inputs (the numeric probe passed) it is
now a violation (`check_value(strict_types=True)`); pairs 61 to 64 are the first violations
of value rules on SQLite.

**Also done.**
- `scripts/replay_reduced_sqlite.py` and a CI step: every reduced pair of `results/` must
  still be violated on the release that reported it (64 of 64; with `--latest` also
  consistent on 3.54.1). A change of the checker that hides a known bug fails CI.
- Pairs 53 and 54 reduced again after the parenthesis fix.

**Audit findings / TODO for round 5.**
1. `incomparable` on MariaDB / MySQL (543 of the corpus run): the same question there. Is a
   non-number on one side only ever legitimate when the type probe says the item is numeric?
2. Campaign default reference is still Python's SQLite; CI has no newest build.
3. `results/sqlite-campaign.md` has grown by accretion (ten rounds appended): a summary
   table per round at the top would make it readable.
4. Old open point: bug 5 may be bug 1 hidden by a plan change.

## Round 5 (2026-11-21)

**Milestone.** Documentation of the SQLite results brought in order:
`results/sqlite-campaign.md` opens with a table of all campaigns (seeds, queries, checks,
new pairs, running total: 64 pairs, 6 bugs); USAGE 8.7 describes `record_sqlite_pairs.py`
and `replay_reduced_sqlite.py`; `--latest` documented.

**Audit findings.**
- `incomparable` on MariaDB (543 checks of the corpus run) was examined with the question
  of round 4. All are value rules applied to items that are not numbers there (`DATE + 3`,
  `DATE_FORMAT(...) * 2`, a BLOB key `+ 3`): the original column is text or a date and the
  mutant a number. On a statically typed server this is legitimate (`AVG->MAX` on a text
  column also changes the type), so `strict_types` stays off for MySQL-protocol servers.
  Such mutants are wasted work, not wrong verdicts.

**TODO for round 6.**
1. Skip value mutants of items that the type probe shows as non-numeric (dates, text,
   BLOB) on MySQL-protocol servers instead of running them and getting `incomparable`.
2. Old open point: is bug 5 the defect of bug 1 hidden by a plan change?
3. A newest-release SQLite build in CI, so the replay step can also check `--latest`.

## Round 6 (2026-11-21)

**Milestone.** An open point since the sixth campaign round is closed: the former bug 5
(pair 38) is bug 1. Its first good commit with SQLite's default settings is the UNION ALL
flattening of 3.35.0, a plan change. With the query flattener switched off
(`bisect_sqlite.py --optimizations-off 0x1`, via `sqlite3_test_control`) the pair stays
violated on that commit, on 3.40.0 and on 3.51.0, and its first good commit is `9b7005f`,
the fix of bug 1. **64 pairs, 5 bugs**; the affinity bug found by the HAVING and value
rules (called bug 6 in rounds 3 to 5 above) is now bug 5.

**Done.** `sqlite_exec.OPTIMIZATIONS_OFF`, `bisect_sqlite.py --optimizations-off MASK`; the
record of pair 38 in `results/sqlite-bisect.jsonl` carries the fixing commit found that way
and the plan change as `plan_change`; README, `results/`, issue 004 renumbered.

**Audit findings / TODO for round 7.**
1. (from round 5) Skip value mutants of non-numeric items on MySQL-protocol servers.
2. With the flattener off, pair 38 is bad on every release back to 3.5.7, i.e. before the
   introducing commit of bug 1 (`9ed1dfa`, itself an optimisation). The introducing
   commits of all bugs could be re-checked with optimisations off.
3. (from round 5) A newest-release SQLite build in CI for `replay --latest`.

## Round 7 (2026-11-21)

**Milestone.** CI checks the SQLite results against the newest release: it builds 3.54.1
from source (`bisect_sqlite.py --build`), replays the 64 reduced pairs on their releases
(violated) and on 3.54.1 (consistent), and the CI campaign uses it as the reference.

**Done.**
- A flaky CI step found and fixed: reducing the translation mismatch of issue 010 failed
  once ("the pair is not violated on this server"). The pair depends on the plan, and the
  scratch copy of the tables had no statistics until InnoDB recomputed them in the
  background. `reduce_mysql.py` and `check_reduced_mysql.py` now run `ANALYZE TABLE` on
  their copies.

**Tried and withdrawn.** Skipping value mutants of non-numeric items on MySQL-protocol
servers (TODO of round 5): it removed 523 `incomparable` verdicts but also 268 passed
checks. A value mutant of a date or text item is still checked for the row count and for
the other columns before its column is found incomparable, so running it is not wasted.
Reverted; a comment in `checker._non_numeric` says why.

**Not pursued.** Re-checking every introducing commit with optimisations off (round 6):
the grouping into bugs does not depend on it.

**TODO for round 8.**
1. MariaDB / MySQL campaigns have only run the fixed demo seeds. A seeded campaign over
   random databases, as on SQLite, does not exist for MySQL-protocol servers.
2. `scripts/demo.sh` is the only end-to-end entry point and mixes build, tests and runs.
3. Upstream reports for the MariaDB / MySQL candidates remain undone (no tracker access).

## Round 8 (2026-11-21)

**Milestone.** Campaigns on MySQL-protocol servers over random databases:
`bridge/gen_mysql_db.py`, `bridge/campaign_mysql.py`, `bridge/recheck_mysql.py`. First
campaign on MariaDB 10.11.14 (40 databases, 3200 queries, 122200 checks): 125 violating
pairs, all classified (`results/mariadb-campaign.md`).

- Two new candidate bugs: `issues/012` (`number IN (SELECT date_column ...)` is FALSE
  instead of NULL when the subquery has a NULL and the column is indexed) and `issues/013`
  (the DECIMAL `-0.00` from `-3.00 % 3` is grouped with `0.00` or apart depending on an
  unrelated aggregate, and `-0.00 = 0.00` is false).
- Issue 009 is a family: 110 pairs, with wrong values, NULLs and missing rows.
- One false alarm of the tool, fixed: a DOUBLE printed with a fixed number of decimals can
  be off by one unit of its last digit (`check_value(output_decimals=...)`).

**TODO for round 9.**
1. CI results of issues 012 and 013 on MySQL and newer MariaDB: read them, update the issues.
2. A MariaDB campaign that avoids `SELECT DISTINCT` over grouped queries (issue 009 hides
   the rest), and the same campaign on MySQL (CI only: no local MySQL server).
3. `campaign_mysql.py` runs `run_on_db.py` twice per seed as a subprocess: fine, but the
   records get their seed after the fact; a shared function would be cleaner.

## Round 9 (2026-11-21)

**Milestone.** Second MariaDB campaign (seeds 41-90, `--no-value-distinct`: 50 databases,
4000 queries, 148599 checks, 37 violating pairs), all classified
(`results/mariadb-campaign.md`), and a tool that does the mechanical part of the
classification: `scripts/triage_mysql.py` (every pair again, without secondary indexes,
reduced, grouped by the shape of the reduced query).

- No new defect. Issues 003 (11 pairs), 012 (9), 013 (7) and 010 (5) again, three in new
  forms: 003 is switched on or off by an aggregate of the select list; 012 also happens
  with text, a BIGINT or a row on the left, exactly for values that are not dates.
- Five false alarms, fixed: DECIMALs of different scales (`AVG` over `AVG`); compounds
  whose arms mix numeric types with a date, or `_ci` with `_bin` under EXCEPT
  (`last_arm_mix`, `arm_mix_verdict`).
- CI results read for issues 011-013: MariaDB 11.4.13 and 11.8.9 affected, MySQL 8.4.13 and
  9.7.4 not. CI now runs a 12-database campaign on MySQL 8.4: no violation.

**Tidying.** One judging path for MySQL pairs: `reduce_mysql.py` and `triage_mysql.py` use
`recheck_mysql.judge`; `printed_decimals` and `arm_mix_verdict` live in `run_on_db.py`.
`campaign_mysql.py` removes its temporary directory and reports the server's errors.

**Audit findings.**
- `gen_mysql_db.py SEED | mysql` stopped at the first UNIQUE index that failed, so a
  database built by hand was not the one of the campaign. Documented with `--force`;
  `reduce_mysql.py --build-seed` builds it itself.
- Issue 003 is plan-dependent: two pairs of the demo are violated locally and not in CI.
  Baseline signature `mariadb-having-in-subquery`.
- The first version of the mixed-types rule hid the known pair of issue 005 (BIT against
  text arms); narrowed to two numeric types plus a non-numeric one.

**TODO for round 10.**
1. Read the errors of the MySQL campaign in CI (166 refused mutants): a printer problem for
   MySQL, or statements only MariaDB accepts?
2. `scripts/triage_mysql.py` groups by shape only; a hint of the known issue (signatures on
   the reduced pair) would make a repeated campaign cheaper to read.
3. The MariaDB campaign with other generator settings (`--rich`, set queries only) and on
   the Python-generator queries over random databases.


## Round 10 (2026-11-21)

**Milestone.** A new candidate bug, `issues/014`: MariaDB's subquery cache looks its key up
under the collation of the outer column (`utf8mb4_general_ci`) while the subquery compares
under `utf8mb4_bin`, so `'A'` and `'a'` share an entry and the result of a correlated
subquery depends on the order of the rows. Found by the first campaign of the rich
generator once it wrote MySQL spelling (seed 147, rule `OR-drop-operand`).

- `--rich` was SQLite-only: MariaDB refused 737 of 3200 queries of the third campaign. With
  `--mysql-seed` the opaque predicates are now `<=>`, `CAST AS CHAR / SIGNED`, `CONCAT`; the
  SQLite stream of random choices is unchanged (checked by hash).
- Campaigns 3 and 4 recorded (17 pairs: issue 013 twelve times, 003 and 012 twice each,
  014 once). `results/mariadb-campaign.jsonl` has 172 pairs.
- `scripts/triage_mysql.py` gives a hint of the known issue per reduced pair; a test checks
  the hints against all recorded pairs.
- CI runs the campaign on MySQL 8.4, MySQL 9, MariaDB 11.4 and 11.8. First results: no
  violation on MySQL 8.4.13 and 9.7.4; three pairs on MariaDB 11.4.13 and 11.8.9, two of
  issue 010 and one with the look of issue 003, which was recorded as fixed in 11.4.13.
  `data/mariadb/having-in-nested.sql` is that pair, run on every server.

**Audit findings.**
- `reduce_mysql.py` put a row it could not delete back at the end of the table. A table
  without a primary key is read in insertion order, and issue 014 depends on that order:
  twelve rows were left where two suffice. The table is now rewritten in order.
- The MySQL jobs refuse 122 to 166 mutants with error 1055 (ONLY_FULL_GROUP_BY). The
  campaign now prints examples (`run_on_db.py --show-failed`).
- The baseline signature of issue 003 from round 9 is needed in CI too (plan-dependent).

**TODO for round 11.**
1. Read the CI results: issue 014 on the other servers, the pair of issue 003 on 11.x,
   the mutants MySQL refuses.
2. Update issue 003 with what 11.x shows; decide whether it is one defect or two.
3. Fifth campaign (`--rich --focus`, seeds 171-230): triage and record.

## Round 11 (2026-11-21)

**Milestone.** Campaigns on servers that are not installed here, and the first candidate
bug found that way: `issues/015`, a wrong result of MySQL 8.0.46, 8.4.13 and 9.7.4 (a
regression: 5.7.44 is right). `a LEFT JOIN b ON EXISTS (...) WHERE NOT EXISTS (... = 1)`
returns the rows of `a` extended with NULLs although `b` has rows: the lookup of the
materialized `EXISTS` takes its key from the table of the `NOT EXISTS` antijoin.

- `.github/workflows/campaign.yml` (a campaign on any server image, with triage and an
  artifact) and `.github/workflows/sql.yml` (one script of `data/` on any image), both
  started by hand or through the API.
- MySQL 9.7.4, seeds 131-170 `--rich`: 12 pairs. Six were the mixed-types false alarm under
  a compound in a derived table (the arms at the top are now probed in that case); six are
  issue 015, reduced by hand to two tables after reading `EXPLAIN FORMAT=TREE` from the log.
- MariaDB 11.8.9, the same seeds: 11 pairs, issues 013, 010, 003 and 014. Issue 014 is in
  10.11.14, 11.4.13 and 11.8.9; the fix of issue 003 in 11.x is partial
  (`data/mariadb/having-in-nested.sql`).
- Fifth local campaign (MariaDB 10.11.14, seeds 171-230, `--rich --focus`): 160621 checks,
  20 pairs, 18 known by their hint, 2 false alarms that the fix above removes.
- README: a table of the candidates by server version.

**Audit findings.**
- A script that wraps a query in `SELECT COUNT(*) FROM (...)` hid issue 015 (another
  plan); the reproducer counts in the query itself.
- My first hand-written reduction did not reproduce (the constant was 100); the plan, not
  the shape of the query, said what mattered.
- MySQL refuses value mutants of a grouping expression (error 1055): recorded in
  `issues/004`, B3.6.

**TODO for round 12.**
1. More campaigns through the workflow: MySQL 9 and 8.4 with other seeds and `--focus`,
   MariaDB 12 if the image exists.
2. `scripts/triage_mysql.py` cannot name issue 014 or 015 (no hint): a hint needs the plan
   or the schema; think about what is cheap.
3. The SQLite side has not been touched for three rounds: run the rich campaign against
   the newest release again after the generator changes (the stream is unchanged, so this
   is a regression check).

## Round 12 (2026-11-21)

**Milestone.** Campaigns on four more servers through the workflows, all classified, and
issue 008 in a much simpler form: MySQL takes the NULL of one operand of `INTERSECT` /
`EXCEPT` for the constant 0 of the other. Wrong in 8.0.46, 8.4.13 and 9.7.4
(`data/mysql/intersect-null-zero.sql`, a table of twelve variants on three releases).

- MariaDB 13.0.2 (`mariadb:latest`): 91064 checks, 18 pairs of issues 003, 010, 012, 013;
  the reproducers of 009 to 014 and the nested form of 003 are all still wrong there.
- MySQL 8.4.13 (seeds 231-280): 89483 checks, issue 008 once. MySQL 9.7.4 (seeds 171-230,
  `--rich --focus`): 155729 checks, issue 008 in the new form.
- MariaDB 10.11.14, sixth local campaign (seeds 281-360): 144990 checks, 17 pairs of known
  issues. `results/mariadb-campaign.jsonl` has 207 pairs.
- `sql.yml` runs a directory of scripts; `scripts/triage_mysql.py` has hints for 008 and 015.

**Audit findings (four false alarms of the tool, all from these campaigns, all fixed).**
- A number arm and a text arm in one compound column: `COALESCE(decimal, 0)` prints as
  `'0'` or `'0.00'` depending on whether its arm is materialized. Any such column is now
  `incomparable` (BIT excepted, or issue 005 would be hidden).
- The arms of the compound at the top were not probed when an arm held a compound in a
  derived table.
- `AVG(x) * 2` in a column that the mutation does not touch: 5.3333 or 5.3334. DECIMALs of
  other columns are matched one decimal shorter, as a last attempt.
- `CEIL(VAR_SAMP(x))` in such a column: 1 or 2 from the last bit of a float. A step
  function of a variance makes "other columns changed" `incomparable`.

**TODO for round 13.**
1. The tolerances grew by four rules in two rounds. Review them together: what does each
   hide, is each as narrow as it can be, are they documented in one place?
2. The negative control (`--flip`) after these changes: the checker must still report
   violations by the hundred.
3. CI: green after the changes? The MySQL baseline (issue 008's pair) must still appear.

## Round 13 (2026-11-22)

**Milestone.** A fourth server family: TiDB. A campaign on `pingcap/tidb:v8.5.3` (port 4000, no
password; the workflows now take both as inputs) found `issues/016`: `x NOT IN (correlated
subquery)` whose subquery has a condition on the outer row alone (`t.b <=> NULL`, `t.b IS NULL`)
returns every outer row twice, in v7.5.1 and v8.5.3. It was found by the translation check,
not by a rule: the bridge prints `NOT IN` as `NOT (... IN ...)`, and the two must agree.

- `--tidb` (generator and campaign): no subquery in a join condition, no `INTERSECT ALL` /
  `EXCEPT ALL`; TiDB 7.5.1 refused 213 of 600 queries without it. Other streams unchanged.
- Percona Server 8.4.11-12: issues 015 and 008, as on MySQL 8.4.
- README: one table of every tolerance of the checker, what it accepts, why, and what it can
  hide (the TODO of round 12).
- CI after the four new tolerances: the negative control still reports 1181 / 963 (MySQL)
  and 182 / 223 (MariaDB) violations; the MySQL baseline still finds the pair of issue 008.

**Audit findings.**
- The README row of issue 016 first said "correct" for MySQL, which was never run. Corrected
  to "not run". A cell of that table is a measurement or it is marked as missing.
- The local MariaDB stops when the session's worker restarts; `scripts/setup_mariadb.sh`
  brings it back.

**TODO for round 14.**
1. The six TiDB pairs that are not translation mismatches: triage them (reduced scripts are
   in the workflow logs).
2. `issues/016` on MySQL and MariaDB 11.x, for the table.
3. `bridge/test_mysql.py` and the CI do not cover TiDB at all; a CI job for TiDB would catch
   a regression of the bridge on its dialect.
