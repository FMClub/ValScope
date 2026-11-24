# 031: `x IN (SELECT ... GROUP BY ... HAVING ...)` is NULL instead of 0

Status: open, candidate (MySQL 8.4.13; other releases not tried). Found while auditing the checker of the rules exported by SQLMRLab's bridge (rules proved in `SqlFull.v`; see SQLMRLab's `rocq/bridge/README.md`). Not reported upstream.
Found by audit 20 (no example rule was reported on it).

```sql
CREATE TABLE p (a INT, b INT);
INSERT INTO p VALUES (1, 1), (2, 2), (5, 5), (3, 2), (NULL, 3), (4, NULL), (2, 7), (2, 7), (NULL, NULL), (0, 1);

SELECT z.b FROM p AS z GROUP BY z.b HAVING COUNT(z.a) <> z.b;
-- 1, 3, 5, 7 (the group of NULL has HAVING 1 <> NULL, unknown, and is not kept)
SELECT 2 IN (SELECT z.b FROM p AS z GROUP BY z.b HAVING COUNT(z.a) <> z.b);
-- expected 0.  MySQL 8.4.13: NULL.  (2 NOT IN ...: also NULL, expected 1.)
SELECT 2 IN (SELECT b FROM (SELECT z.b FROM p AS z GROUP BY z.b HAVING COUNT(z.a) <> z.b) AS d);
-- 0: right.
```

The sub-query has no NULL, so the `IN` is FALSE. A plausible reading (not checked in the source):
the comparison `2 = z.b` is pushed into the `HAVING` and the group of NULL makes it unknown.
