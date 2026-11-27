# 030: A constant select item of a derived table on the NULL side of a left join is read as the constant in `WHERE`

Status: open, candidate (MySQL 8.4.13; other releases not tried). Found while auditing the checker of the rules exported by SQLMRLab's bridge (rules proved in `SqlFull.v`; see SQLMRLab's `rocq/bridge/README.md`). Not reported upstream.
Found by audit 20; reported in a real check as a violation of
`distinct-proj-where->proj-where-distinct` (and twice of `cmp-weaken`, which found the defect).

```sql
CREATE TABLE p (a INT, b INT);
CREATE TABLE q (a INT, b INT);
INSERT INTO p VALUES (1, 1), (2, 2), (5, 5), (NULL, 3);
INSERT INTO q VALUES (5, 1), (3, 3);

SELECT h.a, v.c2 FROM p AS h LEFT JOIN (SELECT 2 AS c2 FROM q AS d) AS v ON h.a = 7;
-- (1, NULL), (2, NULL), (5, NULL), (NULL, NULL): right, no row matches.
SELECT h.a, v.c2 FROM p AS h LEFT JOIN (SELECT 2 AS c2 FROM q AS d) AS v ON h.a = 7 WHERE v.c2 = h.a;
-- expected no row.  MySQL 8.4.13: (2, NULL).
```

`EXPLAIN` shows the filter `h.a = 2`: the constant is propagated into the `WHERE` although the
row is padded with NULL. Audit 20 saw the same with other conditions (`g.c0 <> 1`, `c IN (-1)`,
`(b < h.c1) IS FALSE`), with comparisons as items (`9 = 7 AS c2`), in the `ON` of a later join,
with CTEs and with an empty derived table.
