# 029: A correlated scalar `MIN` over a left join and a further join keeps the value of an earlier outer row

Status: open, candidate (MySQL 8.4.13; other releases not tried). Found while auditing the checker of the rules exported by SQLMRLab's bridge (rules proved in `SqlFull.v`; see SQLMRLab's `rocq/bridge/README.md`). Not reported upstream.
Found by audit 20 (a differential of about 165,000 queries of the integer fragment against an
evaluator of its own) and seen in a real check as violations of `where-or->union-all-where`
and `proj-where-or->union-all-proj-where`.

```sql
CREATE TABLE p (a INT, b INT);
INSERT INTO p VALUES (1, 1), (2, 2), (NULL, 3);

SELECT u.a, u.b,
       (SELECT MIN(h.b) FROM p AS h LEFT JOIN p AS d ON d.b <> u.a CROSS JOIN p AS k)
FROM p AS u;
-- expected (1, 1, 1), (2, 2, 1), (NULL, 3, 1).  MySQL 8.4.13: (1, 1, 1), (2, 2, 2), (NULL, 3, 2).
```

The left join keeps every row of `h` whatever its condition is, so the minimum is that of `p.b`,
1, for every outer row. `MAX`, `SUM` and `COUNT` are right in this query; the same sub-query with
an inner join in place of the left join is right; with `INNER JOIN p AS k ON TRUE` in place of
the cross join it is wrong too. Whether it shows depends on the data and the indexes.

Audits 21 and 23 saw the same family with `COUNT(*)` (a left join and a further join with a
correlated `WHERE`) and with `SUM` (a join with a nested left join, the correlation in `ON`);
those cases are recorded in SQLMRLab's `rocq/bridge/README.md`.
