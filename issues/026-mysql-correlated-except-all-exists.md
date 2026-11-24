# 026: MySQL keeps rows of an earlier outer row in a correlated `EXCEPT ALL` under `EXISTS`

Status: open, candidate (MySQL 8.4.13; other releases not tried). Found while auditing the checker of the rules exported by SQLMRLab's bridge (rules proved in `SqlFull.v`; see SQLMRLab's `rocq/bridge/README.md`). Not reported upstream.
Found by audit 18 as a violation of `cmp-weaken` once correlated operands of set operations
were judged; the original query is the wrong one.

```sql
CREATE TABLE q (a INT, b INT);
CREATE TABLE p (a INT, b INT);
CREATE TABLE o (a INT, b INT);
INSERT INTO q VALUES (5, 1), (3, 3), (2, 7), (1, 2), (NULL, 4), (3, NULL), (2, 7);
INSERT INTO p VALUES (1, 1), (2, 2), (5, 5), (7, 7), (3, 2), (NULL, 3), (4, NULL), (8, 6), (2, 7);
INSERT INTO o VALUES (1, 7), (2, 2), (5, 0), (9, 3), (NULL, NULL), (3, 3), (7, 2);

SELECT o.a, o.b FROM o WHERE EXISTS (
  (SELECT d.a FROM (SELECT a, b FROM q WHERE q.a = o.a) AS d WHERE d.b = 7)
  EXCEPT ALL
  (SELECT d.a FROM (SELECT a, b FROM p WHERE p.b = o.b) AS d WHERE d.b = 100));
-- expected (2, 2).  MySQL 8.4.13: (2, 2), (5, 0).
```

The right operand is empty for every outer row (no row of `p` has `b = 100`), so the `EXISTS`
is that of the left operand alone, and `SELECT o.a, o.b FROM o WHERE EXISTS (SELECT d.a FROM
(SELECT a, b FROM q WHERE q.a = o.a) AS d WHERE d.b = 7)` gives `(2, 2)` on the same server. For
the outer row `(5, 0)` the left operand is empty too (the row of `q` with `a = 5` has `b = 1`);
evaluated with the constants of that row in place of `o.a`, `o.b` the compound is empty. With
`EXCEPT` instead of `EXCEPT ALL` the answer is right. Audit 19 saw the same with `INTERSECT ALL`
(not reduced here).

The integer fragment of the checker has no `INTERSECT` or `EXCEPT` in a sub-query since then.
