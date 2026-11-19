"""End-to-end test of the pipeline SQL -> term -> verified mutator -> SQL (no database needed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sql_bridge import mutate_sql, Unsupported  # noqa: E402

CASES = [
    # (sql, direction, rule, fragment that must appear in some mutant of that rule)
    ("SELECT DISTINCT t.a AS a FROM t WHERE t.b > 5 AND t.c LIKE 'x%'", 'Up', 'DISTINCT-drop', 'SELECT t.a AS a FROM t'),
    ("SELECT t.a FROM t WHERE t.b > 5", 'Up', 'cmp-weaken', 't.b >= 5'),
    ("SELECT t.a FROM t WHERE t.b > 5", 'Down', 'cond->FALSE', 'WHERE 1 = 0'),
    # under NOT EXISTS the direction flips: enlarging the result needs a SMALLER subquery
    ("SELECT t.a FROM t WHERE NOT EXISTS (SELECT u.x FROM u WHERE u.x < t.a)", 'Up', 'cond->FALSE',
     'NOT (EXISTS (SELECT u.x FROM u WHERE 1 = 0))'),
    ("SELECT t.a FROM t INNER JOIN u ON t.a = u.a", 'Up', 'INNER->LEFT-JOIN', 't LEFT JOIN u ON t.a = u.a'),
    ("SELECT a FROM t EXCEPT SELECT a FROM u WHERE u.b = 1", 'Up', 'cond->FALSE', 'FROM u WHERE 1 = 0'),
    ("SELECT a FROM t INTERSECT SELECT a FROM u", 'Up', 'INTERSECT->operand', 'SELECT a FROM u'),
]

# the ON condition of a LEFT JOIN must never be mutated (Counter.v)
LEFT_JOIN = "SELECT t.a FROM t LEFT JOIN u ON t.a = u.a AND u.b > 1 WHERE t.c = 2"

failures = 0
for sql, direction, rule, fragment in CASES:
    _, mutants, _ = mutate_sql(sql)
    hit = any(d == direction and r == rule and fragment in m for d, r, m in mutants)
    print('%s  %-4s %-20s %s' % ('ok  ' if hit else 'FAIL', direction, rule, sql))
    failures += not hit

_, mutants, _ = mutate_sql(LEFT_JOIN)
touched = [m for _, _, m in mutants if 'LEFT JOIN u ON' in m and 'ON (t.a = u.a) AND (u.b > 1)' not in m]
print('%s  LEFT JOIN ON condition left untouched (%d mutants)' % ('FAIL' if touched else 'ok  ', len(mutants)))
failures += bool(touched)

try:
    mutate_sql("SELECT COUNT(*) FROM t GROUP BY a")
    print('FAIL  aggregate query should be rejected')
    failures += 1
except Unsupported:
    print('ok    aggregate query rejected as unsupported')

sys.exit(1 if failures else 0)
