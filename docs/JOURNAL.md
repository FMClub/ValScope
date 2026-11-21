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
