# 032: A left join whose `ON` is an `IN` over an empty sub-query joins every row

Status: open, candidate (MySQL 8.4.13; other releases not tried). Found while auditing the checker of the rules exported by SQLMRLab's bridge (rules proved in `SqlFull.v`; see SQLMRLab's `rocq/bridge/README.md`). Not reported upstream.
Found by audit 20 (no example rule was reported on it).

```sql
CREATE TABLE n (a INT NOT NULL, b INT NOT NULL);
CREATE TABLE w (a BIGINT, b TINYINT);
CREATE TABLE m (a INT NOT NULL, b INT NOT NULL, c INT, PRIMARY KEY (a, b), KEY (c));
INSERT INTO n VALUES (1, 1), (7, 3), (6, 6), (2, 9), (2, 7), (2, 7), (0, 5);
INSERT INTO w VALUES (1, 1), (2, 7), (NULL, 2), (900000000000000000, -5), (-3, NULL), (2, 7), (5, 0);
INSERT INTO m VALUES (1, 1, 1), (1, 2, NULL), (2, 7, 2), (5, 5, 7), (3, 2, 2), (0, 0, NULL), (2, 2, 5);

SELECT g.b FROM n AS g WHERE g.a = 3;
-- no row
SELECT COUNT(*) FROM m AS s LEFT JOIN w AS y ON y.b IN (SELECT g.b FROM n AS g WHERE g.a = 3);
-- expected 7 (every row of m, padded).  MySQL 8.4.13: 21.
SELECT COUNT(*) FROM m AS s LEFT JOIN w AS y ON FALSE;
-- 7
```

Audit 20 saw the same with `ON EXISTS (SELECT ... FROM k JOIN m ON TRUE WHERE ...)` that is false
on its own (every pair is joined), and with an `IN` that is NULL taken as a match; with a
one-table sub-query or an inner join the answer was right.
