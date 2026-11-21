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
