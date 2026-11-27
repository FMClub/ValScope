# 025: MySQL reads `!!x` as `!x`

Status: open, candidate (MySQL 8.4.13; other releases not tried). Found while auditing the checker of the rules exported by SQLMRLab's bridge (rules proved in `SqlFull.v`; see SQLMRLab's `rocq/bridge/README.md`). Not reported upstream.
Found by audit 23 as a TRANSLATION mismatch: the checker re-prints `!!a` as `NOT (NOT a)`, and the
two texts give different rows.

```sql
SELECT !!1, !(!1), ! !1, NOT NOT 1;
-- expected 1, 1, 1, 1.  MySQL 8.4.13: 0, 1, 1, 1.
```

`SELECT a FROM p WHERE !!a` returns the rows with `a = 0`; `EXPLAIN` shows the filter `p.a = 0`
for `!!a` and `0 <> p.a` for `NOT (NOT a)`. Two adjacent `!` are taken as one, as if the lexer
read them as a single token; with a space or parentheses between them the result is right.

The checker no longer translates a text that contains `!!` (`_check_read_as_written` in
`bridge/sql_bridge.py`), so that the defect is recorded once here and not with every query.
