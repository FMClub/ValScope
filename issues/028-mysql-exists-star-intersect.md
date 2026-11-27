# 028: Under `EXISTS`, MySQL compares a `SELECT *` operand of `INTERSECT` or `EXCEPT` as one constant column

Status: open, candidate (MySQL 8.4.13; other releases not tried). Found while auditing the checker of the rules exported by SQLMRLab's bridge (rules proved in `SqlFull.v`; see SQLMRLab's `rocq/bridge/README.md`). Not reported upstream.
Found by audit 19 as a false violation of `proj-where-or->union-all-proj-where`: the printer
writes a `DISTINCT` over a set operation as `SELECT DISTINCT * FROM (...) AS vs_dN`, and the
mutant was the wrong one.

```sql
CREATE TABLE p (a INT, b INT);
INSERT INTO p VALUES (3, 1), (5, 2);

SELECT EXISTS ((SELECT * FROM p WHERE a = 3) INTERSECT (SELECT * FROM p WHERE a = 5));
-- expected 0.  MySQL 8.4.13: 1.
SELECT EXISTS ((SELECT a, b FROM p WHERE a = 3) INTERSECT (SELECT a, b FROM p WHERE a = 5));
-- 0: right.
```

Audit 19 also found `EXISTS ((SELECT * FROM (SELECT a FROM p WHERE a = 3) AS d) EXCEPT (SELECT a
FROM p WHERE a = 3))` to be 1 (0 with `d.a` in place of `*`), and `EXISTS ((SELECT * FROM p ...)
EXCEPT (SELECT a, b FROM p))` to fail with error 1222 (different number of columns). `UNION` is
not affected, nor a compound in a derived table that `EXISTS` reads.
