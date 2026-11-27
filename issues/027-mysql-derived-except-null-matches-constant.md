# 027: In a derived table, MySQL's `EXCEPT` and `INTERSECT` match a NULL of one operand with any `NOT NULL` value of the other

Status: open, candidate (MySQL 8.4.13; other releases not tried). Found while auditing the checker of the rules exported by SQLMRLab's bridge (rules proved in `SqlFull.v`; see SQLMRLab's `rocq/bridge/README.md`). Not reported upstream.
Probably the same defect as [008](008-mysql-intersect-not-null-outer-join.md), which shows it with
the value 0; here the value is not 0. Found by audit 19 as false violations of the example
rules `where-or->union-all-where` and `proj-where-or->union-all-proj-where`.

```sql
CREATE TABLE n (a INT);
CREATE TABLE p (a INT);
INSERT INTO n VALUES (1);
INSERT INTO p VALUES (1);

(SELECT 9 FROM n) EXCEPT (SELECT NULL FROM p);
-- 9: right.
SELECT * FROM ((SELECT 9 FROM n) EXCEPT (SELECT NULL FROM p)) AS d;
-- expected 9.  MySQL 8.4.13: no row.
```

The NULL is taken for the value of the other operand, whatever it is (a literal select item, a
`NOT NULL` column, `COUNT(*)` or a comparison). At the top level and directly under `EXISTS`
the answer is right; `UNION` is not affected.

The integer fragment of the checker has `INTERSECT` and `EXCEPT` only as operands of the statement
itself since then.
