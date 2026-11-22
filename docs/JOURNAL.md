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

## Round 14 (2026-11-22)

**Milestone.** The tool made trustworthy on TiDB, and a second TiDB candidate. TiDB reports
`utf8mb4_bin` for every text column of a result, whatever its collation
(`scripts/probe_collations.py`, now run before every dispatched campaign and in a new CI job
for TiDB v8.5). `MySQLTarget` checks this at connection time and, when the metadata cannot be
trusted, compares text with the coarsest collation of the database. `issues/017`: on TiDB
v7.5.1 and v8.5.3, `SELECT DISTINCT c4 FROM t1 WHERE c1 = 10 OR c4 <= 10` fails with "Can't
find column t1._tidb_rowid" after `ANALYZE TABLE`, when `t1` has a clustered integer key and
a unique index on `(c1, c4)`.

- Issue 016 checked on MySQL 9.7.4 and MariaDB 11.8.9: both correct.
- Runs and campaigns now print internal errors of a server (an error that is the server's
  fault, not the query's) with the first query of each; issue 017 had only been a line of the
  error summary.
- Triage hints for 016.

**Audit findings (five false alarms on TiDB, all fixed; each fix was checked by rerunning the
same campaign, seeds 1-40, three times).**
- Text compared as binary (the metadata above): the `DISTINCT` pairs over `_ci` columns.
- My first fix skipped the probing of compound arms on TiDB, which also turned off the
  mixed-types rule: ten new pairs in the rerun. The arms are probed again.
- `relation_holds` with a rounding tolerance near the pivot of `AwayOne` made the relation
  stricter instead of looser (1.94 counted as "at 1, must stay"). A rounded value near the
  pivot now allows any mutant value.
- The tolerance came from TiDB reporting 0 decimals for an unrounded `STDDEV_SAMP`;
  `printed_decimals` checks the values of the result that reports the decimals. My first
  version checked both results and dropped the tolerance where it was right (five `AVG->MAX`
  pairs of a UNION of a DECIMAL and a DOUBLE arm, which TiDB types as DECIMAL(.., 4)).
- Lesson: on a new server, every tolerance and every piece of metadata is a hypothesis. The
  campaign with the same seeds, rerun after each fix, is what showed the regressions of the
  fixes themselves.

**TODO for round 15.**
1. Read the fourth rerun of the TiDB campaign; what remains must be issue 016 only.
2. TiDB types `UNION` of DECIMAL and DOUBLE as DECIMAL and rounds the DOUBLE (MySQL: DOUBLE).
   Write it down as an observation with a script; decide whether it is a defect.
3. The second TiDB campaign (seeds 131-170, `--rich`) with the fixes.

## Round 15 (2026-11-22)

**Milestone.** Every pair of the two TiDB campaigns is accounted for: after the fixes of round 14
the reruns leave only `issues/016` (ten pairs) and `issues/018` (four). `issues/018` (new): TiDB
types a UNION of a `DECIMAL` and a `DOUBLE` arm as `DECIMAL` with the scale of the `DECIMAL`
arm and rounds the `DOUBLE` to it; `SELECT ATAN(1) UNION ALL SELECT 1.5` gives 0.8 (MySQL 9.7.4
and MariaDB: 0.7853981633974483). A web search found no report of it; TiDB's documentation
says its precision math is consistent with MySQL.

- The `AVG->MAX` pairs left on TiDB are this defect seen by ValScope: the original's values are
  rounded wrongly, the mutant's (whose column became `DOUBLE`) are right. They are recorded as
  issue 018, not hidden by a tolerance; triage has a hint for them.
- `results/mariadb-campaign.md`: the TiDB campaigns before and after the fixes.

**Audit findings.**
- A tolerance that would hide these pairs (infer the rounding from the values when the server
  reports none) was considered and not added: it would also hide a real error of one unit of
  the last digit, on every server, to make a known defect of one server quiet. Where a
  difference is a defect of the server, the right place for it is an issue.

**TODO for round 16.**
1. The MySQL / MariaDB / Percona campaigns ran before the four checker fixes of rounds 12-14;
   rerun one of each with the same seeds to see that nothing known disappeared (a fix that
   loosened the checker too much would show as missing pairs).
2. `README.md` and `docs/USAGE.md`: TiDB as a target (port, password, `--tidb`, what the
   checker does differently there).

## Round 16 (2026-11-22)

**Milestone.** A regression check of the checker against its own history. The 84 recorded
MariaDB pairs of campaigns 2-6 were judged again with the present checker
(`recheck_mysql.py`); 6 had become `incomparable`. Two tolerances of round 12 turned a whole
pair incomparable when one column of the query had a property (a number arm and a text arm
in a compound; a step function of a variance), and so hid five pairs of `issues/012`. Both are
now applied per column: `rejudge` judges a violation again with only those columns made
comparable (a numeric text as its number; a step-function column dropped if it moved by at
most one step), and any other difference stays a violation.

- After the change: the five issue-012 pairs are violated again; the false alarms the rules were
  made for (round 9, seeds 78 and 80) stay `incomparable` / `collation`; the demo baseline
  (18 known, 0 new) and the negative control (1181) are unchanged.
- `last_arm_mix` is a set. A compound can mix types and collations; with a single value the
  collation rule was skipped whenever the types rule fired first.
- Reruns with the seeds of earlier campaigns: MariaDB 10.11.14 campaign 4, 8 of 8 recorded
  pairs found again and nothing else; MySQL 9.7.4 seeds 131-170, the 6 pairs of issue 015 (the
  6 false alarms of round 11 gone); MariaDB 13.0.2 seeds 231-280, 17 pairs of known issues (the
  false alarm gone).
- `docs/USAGE.md`: what differs per MySQL-protocol server (TiDB) and what the bridge does.

**Audit findings.**
- One recorded pair was misclassified: seed 196 of campaign 5, recorded as issue 013 in round
  11 by its hint, is a false alarm (only `CEIL(VAR_SAMP)` of another column moved, by one step at
  integer boundaries). The record now says `tool: step function`. A hint is not a verdict; the
  rows of a pair are.
- Two recorded issue-012 pairs (seed 42, a `UNION ALL` with an `EXCEPT` over a `_ci` and a `_bin`
  column; first written down here as seed 83, corrected in round 17) are hidden by the collation
  rule, which still applies to the whole pair: which rows an `EXCEPT` keeps
  depends on the representative, so making columns comparable does not repair it. Recorded
  here as a known cost of that rule.

**TODO for round 17.**
1. The last round of this run: tidy the repository (scripts and data that served one
   investigation only; `data/tidb/` has four scripts for issue 017), check that README, USAGE,
   issue 004 and the results agree with each other.
2. A recheck of the recorded pairs belongs in CI or in a script, so that the next change of
   the checker is checked against its history as this one was.

## Round 17 (2026-11-22)

**Milestone.** The check of round 16 made permanent: `scripts/recheck_recorded.py` judges the
207 recorded MariaDB pairs again with the present checker and fails when a pair of a server
defect is no longer violated, or a false alarm is violated again. Known, deliberate exceptions
are listed in the script with their reason (seed 42: the collation rule). It runs in the CI job
for MariaDB 10.11, not blocking, because plan-dependent pairs (issue 003) may differ between
patch releases; locally it is strict (84 pairs of campaigns 2-6: 0 changed, 2 hidden on purpose).

**Tidying.**
- Removed the `column_info` option of `sql.yml` and its script: the mysql client prints no
  column metadata in batch mode; `scripts/probe_collations.py` replaced it.
- `data/tidb/rowid-intersect.sql` renamed `rowid-distinct-or.sql` (it has no INTERSECT left).
- README, `issues/004` and `results/` brought into agreement: the record has 207 pairs, 206 of
  server defects and one false alarm; the campaigns found issues 012 to 018; issue 004 lists
  Percona Server and TiDB.

**Audit findings.**
- The journal of round 16 named the wrong seed for the pairs hidden by the collation rule (83
  instead of 42); the script showed it at its first run. Corrected in place, with a note.
- CI after the change of round 16 (`rejudge`): all eight jobs green (Coq 8.18, Rocq 9,
  MariaDB 10.11, 11.4, 11.8, MySQL 8.4, MySQL 9, TiDB v8.5).

**End of this run of rounds (13-17).** New candidates: `issues/016`, `017`, `018` (TiDB). Fixed
false alarms of the tool: five on TiDB (round 14), two whole-pair tolerances narrowed (round 16),
one misclassified record corrected. Open, for a next run:
1. The collation rule still hides any defect of an `INTERSECT` / `EXCEPT` over mixed
   collations (two recorded pairs of issue 012).
2. None of the candidates was reported upstream; the TiDB tracker was not searched.
3. OceanBase and PolarDB-X were not tried.

## Round 18 (2026-11-22)

**Milestone.** One judgement for every runner. The verdict pipeline existed twice on the
MySQL side (run_on_db.py and recheck_mysql.py, where recheck had drifted: no single-precision
tolerance, no strict types, no type-mismatch skip; the translation check compared exactly
where every other check allowed the collation) and five times on the SQLite side. Now
`capture()` / `judge_results()` in `run_on_db.py` serve run_on_db, recheck_mysql and
reduce_mysql, and `checker.judge()` serves the five SQLite tools. Before and after, on the
same inputs: MariaDB demo 11642 / 4190 / 3492 / 3714 / 2735 checks and 21 known violations,
negative control 1181 / 1008; SQLite demo 2029 / 703; 64 reduced SQLite pairs replay; the CI
SQLite campaign 5662 checks; 84 recorded MariaDB pairs unchanged.

- `results/server-campaigns.json` and `scripts/compare_campaign.py`: the pairs of the
  campaigns on MySQL 9, MariaDB 13 and TiDB, compared with a rerun by the campaign workflow.
  (The workflow's artifacts cannot be downloaded from here; campaigns are deterministic, so
  the record is rule, seeds, number of pairs and issue.)
- The recheck of the recorded MariaDB pairs is blocking in CI (10.11.19 agrees with 10.11.14).
- `issues/019` (new, TiDB v8.5.3): `A INTERSECT (B INTERSECT C)` keeps a row of a `VARCHAR`
  `A` that matches only the NULL of a `DATE` column.
- Upstream leads for issues 016 and 017 written into the issues (web search only).

**Audit findings.**
- The refactor made the translation check modulo collation, and on TiDB this hid the
  translation pair of seed 6 (issue 016 inside a compound): the collation rule applied to every
  INTERSECT / EXCEPT over text there. It now applies only when the rows that differ hold a
  string that a collation can make equal to another (a letter, an accent, a trailing space).
  That also uncovered issue 019 (seed 8). The two recorded pairs of seed 42 stay hidden; their
  differing rows do hold such strings.
- Seed 7 of the same rerun was a false alarm on TiDB and MySQL 9 alike: in a column with a text
  arm, `'0'` and `'0.00'` were kept apart in one result and merged in the other. Two results
  that are sets are now compared as sets after their numbers are read as numbers; a bag keeps
  its duplicates (or issue 016 would disappear again).
- My own comparison script double-counted groups that triage had split by shape; fixed.

**Closing checks.** The reruns with the recorded seeds match the record exactly: TiDB v8.5.3
seeds 1-40, 9 of 9 pairs (with issue 019); MariaDB 13.0.2 seeds 231-280, 17 of 17. The
translation check of `campaign_sqlite.py` is now modulo the collation too (the CI campaign:
the same 238 queries and 5662 checks). CI: all eight jobs green, with the recheck of the
recorded pairs blocking.

**TODO for round 19.**
1. The SQLite tools still each read their records and build their databases themselves (one
   loader would do).
3. OceanBase and PolarDB-X were not tried.

## Round 19 (2026-11-22)

**Milestone 1: one loader for the SQLite tools.** `bridge/sqlite_records.py` reads the records
of SQLite pairs, builds their databases (a seed of `gen_sqlite_db.py`, or the statements of a
reduced pair) and judges a pair (`verdict`); `confirm_sqlite.py`, `bisect_sqlite.py`,
`reduce_sqlite.py`, `scripts/replay_reduced_sqlite.py` and `scripts/record_sqlite_pairs.py` no
longer each read and build for themselves. Before and after, on the same inputs: the 64
reduced pairs replay; the confirmation table of the 64 pairs is identical; the bisection of
pair 1 and the reduction of pair 53 (26 statements to 6, the same 124-character query) give the
same output.

**Milestone 2: OceanBase and PolarDB-X.** Campaigns through `campaign.yml` on OceanBase CE
4.4.2.1 (seeds 1-40 `--focus`, 131-170 `--rich`, both `--value-ext --no-set-all`) and on
PolarDB-X 5.4.19 (seeds 1-10 `--focus --value-ext`); every pair reproduced with `sql.yml` on
the server, on MySQL 9 and on the local MariaDB, and recorded in `results/server-campaigns.json`.
- `issues/023` (OceanBase): `SUM(x - k)` next to `SUM(x)` and `COUNT(DISTINCT x)` is
  `SUM(x) - k * COUNT(DISTINCT x)`; also `AVG`, `VAR_SAMP` (a negative variance),
  `STDDEV_SAMP`. All 27 server pairs of the two campaigns once the false alarms were fixed.
- `issues/020` (PolarDB-X): an `INTERSECT` / `EXCEPT` arm that aggregates without `GROUP BY`
  ignores a constant false `HAVING` (3 pairs). My first reproducer missed it: its comparison
  values happened not to meet the row of the aggregates of no rows.
- `issues/021` (PolarDB-X): a correlated `IN` over `(SELECT DISTINCT * FROM t)` is NULL instead
  of 0 where the subquery is empty and the table holds a NULL.
- `issues/022` (PolarDB-X): an `INTERSECT` / `EXCEPT` arm `(SELECT DISTINCT * FROM u) LEFT JOIN u
  ... WHERE b.x IN (subquery)` loses its `WHERE`. It needs a table whose `DISTINCT` does
  something: my first small table had a primary key and the case did not reproduce.

**What the tool needed first.**
- OceanBase refuses `INTERSECT ALL` / `EXCEPT ALL` (155 of 600 queries): `--no-set-all`.
- PolarDB-X: the campaign stopped on the `INTERNAL ERROR` lines after the error summary (one
  tested `parse_run`); `CREATE DATABASE` on a connection whose database was dropped is refused
  (`USE information_schema` first); no `WEIGHT_STRING` (approximate keys for `_ci` / `_ai`);
  values the driver cannot convert (the query fails, the connection is opened again); request
  ids before error messages (removed); `DELETE` without `WHERE` forbidden (the reducer
  truncates).
- `sql.yml` / `campaign.yml` waited for `SELECT VERSION()`, which OceanBase answers before its
  tenant accepts DDL: a probe script ran against a server that refused every `CREATE`. The
  wait now requires a `CREATE DATABASE`.

**Audit finding.** Six OceanBase pairs (nested `UNION`s, seeds 8, 12, 16) were false alarms of
the checker, not of the server: OceanBase and MySQL 9 de-duplicate a `UNION` nested in another
in the outer column's (binary) collation, so the set keeps `'a'` and `'A'`; the checker folds
with the coarsest collation of the arms and then counted that row twice against a result that
kept one. In such a compound (a column whose arms have more than one collation), a set's rows
that the collation makes one now count once (verdict `collation`). The first version of the
rule applied to every fold, and CI caught it: 48 of the 64 reduced SQLite pairs (SQLite 3.26.0
UNIONs that lose `'A'` and keep `'a'`) were no longer violated. Narrowed, they replay 64 / 64. The 84 recorded MariaDB pairs, the MariaDB demo (11642 / 4190 / 3492 / 3714 / 2735
checks, 21 violations, negative control 1181 / 1008) are unchanged; the rerun of OceanBase seeds
1-40 lost exactly those six (`collation` 97 to 103). One real difference remains and is not
counted: `(empty) UNION (SELECT DISTINCT v FROM s)` keeps both `'a'` and `'A'` on OceanBase, one
on MySQL; modulo the collation the two are the same set.

**TODO for round 20.**
1. Triage hints come in a fixed order; four OceanBase pairs of issue 023 are hinted 013 / 009.
   A hint could say which server it is for.
2. About 45% of the generated queries fail on PolarDB-X (`Do not support RexSubQuery`,
   unsupported functions); a `--polardbx` generator option would test more of it.
3. The trackers of OceanBase and PolarDB-X were not searched for 020-023.
