"""Tests of the pipeline SQL -> term -> verified mutator -> SQL (no database needed)."""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sql_bridge import mutate_sql, mutate_value_sql, mutate_value, Translation, Unsupported  # noqa: E402
from checker import check_inclusion, check_value, SQLiteFold  # noqa: E402

failures = 0


def report(ok, text):
    global failures
    print('%s  %s' % ('ok  ' if ok else 'FAIL', text))
    failures += not ok


# ---- set-semantic mutants: (sql, direction, rule, fragment of an expected mutant)
SET_CASES = [
    ("SELECT DISTINCT t.a AS a FROM t WHERE t.b > 5 AND t.c LIKE 'x%'", 'Up', 'DISTINCT-drop', 'SELECT t.a AS a FROM t'),
    ("SELECT t.a FROM t WHERE t.b > 5", 'Up', 'cmp-weaken', 't.b >= 5'),
    ("SELECT t.a FROM t WHERE t.b > 5", 'Down', 'cond->FALSE', 'WHERE 1 = 0'),
    # under NOT EXISTS the direction flips: enlarging the result needs a SMALLER subquery
    ("SELECT t.a FROM t WHERE NOT EXISTS (SELECT u.x FROM u WHERE u.x < t.a)", 'Up', 'cond->FALSE',
     'NOT (EXISTS (SELECT u.x FROM u WHERE 1 = 0))'),
    ("SELECT t.a FROM t INNER JOIN u ON t.a = u.a", 'Up', 'INNER->LEFT-JOIN', 't LEFT JOIN u ON t.a = u.a'),
    ("SELECT a FROM t EXCEPT SELECT a FROM u WHERE u.b = 1", 'Up', 'cond->FALSE', 'FROM u WHERE 1 = 0'),
    ("SELECT a FROM t INTERSECT SELECT a FROM u", 'Up', 'INTERSECT->operand', 'SELECT a FROM u'),
    # DISTINCT around one table is printed as a derived table that keeps the alias
    ("SELECT x.a FROM t AS x INNER JOIN u AS y ON x.a = y.a", 'Down', 'DISTINCT-add',
     '(SELECT DISTINCT * FROM u AS y) AS y'),
    # an operand that is not a plain name is parenthesised when it is put back
    ("SELECT t.a FROM t WHERE t.b + 1 > t.c - 2", 'Up', 'cmp-weaken', '(t.b + 1) >= (t.c - 2)'),
    # IN is monotone in its subquery, NOT IN antitone
    ("SELECT t.a FROM t WHERE t.a IN (SELECT u.a FROM u WHERE u.b > 1)", 'Up', 'cond->TRUE',
     't.a IN (SELECT u.a FROM u WHERE 1 = 1)'),
    ("SELECT t.a FROM t WHERE t.a NOT IN (SELECT u.a FROM u WHERE u.b > 1)", 'Up', 'cond->FALSE',
     'NOT (t.a IN (SELECT u.a FROM u WHERE 1 = 0))'),
    ("SELECT t.a FROM t WHERE t.a NOT IN (SELECT u.a FROM u WHERE u.b > 1)", 'Down', 'cmp-weaken',
     'NOT (t.a IN (SELECT u.a FROM u WHERE u.b >= 1))'),
    # rule 7: LIKE patterns
    ("SELECT t.a FROM t WHERE t.c LIKE 'a_c%'", 'Up', 'LIKE-generalise', "t.c LIKE 'a%c%'"),
    ("SELECT t.a FROM t WHERE t.c LIKE 'a_c%'", 'Down', 'LIKE-specialise', "t.c LIKE 'a_c_'"),
    ("SELECT t.a FROM t WHERE t.c LIKE 'it''s%'", 'Up', 'LIKE-generalise', "t.c LIKE 'it_s%'"),
    # NOT LIKE flips the direction (regression: the negation was lost)
    ("SELECT t.a FROM t WHERE t.c NOT LIKE 'a_c%'", 'Up', 'LIKE-specialise', "NOT (t.c LIKE 'a_c_')"),
    # rule 14: regular expressions of the fragment
    ("SELECT t.a FROM t WHERE t.c REGEXP '^ab+c$'", 'Up', 'REGEXP-generalise', "t.c REGEXP 'ab+c'"),
    ("SELECT t.a FROM t WHERE t.c REGEXP '^ab+c$'", 'Up', 'REGEXP-generalise', "t.c REGEXP '^ab*c$'"),
    ("SELECT t.a FROM t WHERE t.c REGEXP 'ab'", 'Down', 'REGEXP-specialise', "t.c REGEXP '^ab$'"),
    # derived tables and CTEs are mutated inside
    ("SELECT d.a FROM (SELECT t.a FROM t WHERE t.b > 1) AS d", 'Up', 'cmp-weaken',
     'FROM (SELECT t.a FROM t WHERE t.b >= 1) AS d'),
    ("WITH d AS (SELECT t.a FROM t WHERE t.b > 1) SELECT d.a FROM d", 'Up', 'cond->TRUE',
     'FROM (SELECT t.a FROM t WHERE 1 = 1) AS d'),
    # an aggregated arm of a set operation is an opaque query; the set operation is still mutated
    ("SELECT t.a FROM t UNION SELECT MAX(u.a) FROM u", 'Up', 'UNION->UNION-ALL',
     '(SELECT t.a FROM t) UNION ALL (SELECT MAX(u.a) FROM u)'),
    # a scalar subquery in the select list is an expression of the row
    ("SELECT (SELECT MAX(u.a) FROM u WHERE u.b = t.b) AS m FROM t WHERE t.c > 1", 'Up', 'cmp-weaken',
     't.c >= 1'),
]
for sql, direction, rule, fragment in SET_CASES:
    _, mutants, _ = mutate_sql(sql)
    report(any(d == direction and r == rule and fragment in m for d, r, m in mutants),
           '%-4s %-20s %s' % (direction, rule, sql))

# the analysed fragment of LIKE / REGEXP: patterns outside it stay opaque predicates
for sql in ["SELECT t.a FROM t WHERE t.c LIKE 'a\\_b'", "SELECT t.a FROM t WHERE t.c REGEXP '[ab]+'",
            "SELECT t.a FROM t WHERE t.c LIKE t.d"]:
    tr = Translation(sql)
    report('(Atom 0)' in tr.term and 'Like' not in tr.term and 'Regex' not in tr.term, 'opaque pattern: %s' % sql)

# LEFT JOIN pads with the width of its right input
tr = Translation("SELECT x.a FROM t AS x LEFT JOIN (SELECT u.a, u.b FROM u) AS y ON x.a = y.a")
report(tr.term.count('(Left 2 ') == 1, 'LEFT JOIN padding = width of the derived table')

# the ON condition of a LEFT JOIN must never be mutated (Counter.v)
_, mutants, _ = mutate_sql("SELECT t.a FROM t LEFT JOIN u ON t.a = u.a AND u.b > 1 WHERE t.c = 2")
touched = [m for _, _, m in mutants if 'LEFT JOIN u ON' in m and 'ON (t.a = u.a) AND (u.b > 1)' not in m]
report(not touched, 'LEFT JOIN ON condition left untouched (%d mutants)' % len(mutants))

# ---- value-semantic mutants: (sql, relation, rule, column, fragment)
VALUE_CASES = [
    ("SELECT t.g AS g, COUNT(DISTINCT t.x) AS n FROM t GROUP BY t.g", 'Le', 'COUNT-DISTINCT->COUNT', 1, 'COUNT(t.x) AS n'),
    ("SELECT AVG(t.x) AS a FROM t", 'Le', 'AVG->MAX', 0, 'MAX(t.x) AS a'),
    ("SELECT MIN(t.x) AS a FROM t", 'Le', 'MIN->MAX', 0, 'MAX(t.x) AS a'),
    ("SELECT VAR_SAMP(t.x) AS v FROM t", 'TowardOne', 'VAR_SAMP->STDDEV_SAMP', 0, 'STDDEV_SAMP(t.x) AS v'),
    ("SELECT STDDEV_SAMP(t.x) AS v FROM t", 'AwayOne', 'STDDEV_SAMP->VAR_SAMP', 0, 'VAR_SAMP(t.x) AS v'),
    # regression: the argument must be parenthesised before it is multiplied
    ("SELECT SUM(t.x - 50) AS s FROM t", 'AwayZero', 'SUM(c)->SUM(c*k)', 0, 'SUM(((t.x - 50) * 2))'),
    ("SELECT t.x - 50 AS s FROM t", 'AwayZero', 'expr->expr*k', 0, '((t.x - 50) * 2) AS s'),
    ("SELECT t.x AS s FROM t", 'Le', 'expr->expr+k', 0, '(t.x + 3) AS s'),
    ("SELECT FLOOR(AVG(t.x)) AS f FROM t", 'Le', 'FUNC(a)->FUNC(a+k)', 0, 'FLOOR((AVG(t.x) + 3))'),
    ("SELECT FLOOR(COUNT(t.x)) AS f FROM t", 'Le', 'FUNC(c)->FUNC(c*k)', 0, 'FLOOR((COUNT(t.x) * 2))'),
    # a monotone relation is carried through a monotone context
    ("SELECT AVG(t.x) + 1 AS a FROM t", 'Le', 'AVG->MAX', 0, '(MAX(t.x) + 1) AS a'),
]
for sql, relation, rule, column, fragment in VALUE_CASES:
    _, mutants, _ = mutate_value_sql(sql)
    report(any(rel == relation and r == rule and c == column and fragment in m for rel, r, c, m in mutants),
           '%-9s %-24s %s' % (relation, rule, sql))

# an item that is not analysed is copied unchanged into every mutant
_, mutants, _ = mutate_value_sql("SELECT VAR_SAMP(t.b) AS s, GROUP_CONCAT(t.c) AS g, SUM(DISTINCT t.d) AS d FROM t")
report(any(r == 'VAR_SAMP->STDDEV_SAMP' for _, r, _, _ in mutants) and
       all("(GROUP_CONCAT(t.c SEPARATOR ',')) AS g" in m for _, _, c, m in mutants if c == 0) and
       all("(SUM(DISTINCT t.d)) AS d" in m for _, _, c, m in mutants if c != 2), 'opaque items copied unchanged')
# in MySQL / MariaDB, VARIANCE is the population variance: it is not rule 21's VAR_SAMP
_, mutants, _ = mutate_value_sql("SELECT VARIANCE(t.b) AS s FROM t")
report(not any(r.startswith('VAR_SAMP') for _, r, _, _ in mutants), 'VARIANCE (population) is not VAR_SAMP')

# FUNC(c * k) needs c >= 0: it must not fire when the argument can be negative
_, mutants, _ = mutate_value_sql("SELECT FLOOR(AVG(t.x)) AS f FROM t")
report(not any(r == 'FUNC(c)->FUNC(c*k)' for _, r, _, _ in mutants), 'FUNC(c*k) not applied to a possibly negative argument')
# a sign-dependent relation is not carried through a context
_, mutants, _ = mutate_value_sql("SELECT SUM(t.x) + 1 AS a FROM t")
report(not any(r == 'SUM(c)->SUM(c*k)' for _, r, _, _ in mutants), 'SUM(c*k) not applied below an addition')

# ---- HAVING: mutated by the predicate rules at the HAVING position (rules 15, 16)
HAVING_CASES = [
    ("SELECT t.g AS g, SUM(t.x) AS s FROM t GROUP BY t.g HAVING SUM(t.x) > 10", 'Up', 'cond->TRUE', 'GROUP BY t.g', True),
    ("SELECT t.g AS g, SUM(t.x) AS s FROM t GROUP BY t.g HAVING SUM(t.x) > 10", 'Down', 'cond->FALSE', 'HAVING 1 = 0', False),
    ("SELECT t.g AS g, SUM(t.x) AS s FROM t GROUP BY t.g HAVING SUM(t.x) > 10", 'Up', 'cmp-weaken', 'HAVING (SUM(t.x)) >= 10', False),
    ("SELECT COUNT(*) AS n FROM t HAVING COUNT(*) > 1 AND MAX(t.x) < 9", 'Up', 'AND-drop-operand', 'HAVING (COUNT(*)) > 1', True),
    ("SELECT t.g AS g, COUNT(*) AS n FROM t GROUP BY t.g HAVING COUNT(*) NOT IN (SELECT u.a FROM u WHERE u.b > 1)",
     'Up', 'cond->FALSE', 'NOT ((COUNT(*)) IN (SELECT u.a FROM u WHERE 1 = 0))', False),
]
for sql, direction, rule, fragment, at_end in HAVING_CASES:
    _, _, _, _, having_mutants = mutate_value(sql)
    hit = any(d == direction and r == rule and (m.endswith(fragment) if at_end else fragment in m)
              for d, r, m in having_mutants)
    report(hit, 'HAVING %-4s %-17s %s' % (direction, rule, sql))

# a value mutation leaves the HAVING clause alone
_, mutants, _ = mutate_value_sql("SELECT t.g AS g, SUM(t.x) AS s FROM t GROUP BY t.g HAVING SUM(t.x) > 10")
report(mutants and all(m.endswith('HAVING (SUM(t.x)) > 10') for _, _, _, m in mutants),
       'item mutation keeps HAVING unchanged (%d mutants)' % len(mutants))

# ---- the bridge fails closed
REJECTED = [
    ("SELECT COUNT(*) FROM t GROUP BY a", 'set', 'aggregate in a set-semantic query'),
    ("SELECT a FROM t LIMIT 3", 'set', 'LIMIT'),
    ("SELECT a FROM t WHERE b > RAND()", 'set', 'non-deterministic function'),
    ("SELECT a FROM t WHERE b > @x", 'set', 'user variable'),
    ("SELECT a FROM t NATURAL JOIN u", 'set', 'NATURAL JOIN'),
    ("SELECT t.a, SUM(t.b) AS s FROM t GROUP BY t.c", 'value', 'non-key column in a grouped select'),
    ("SELECT DISTINCT t.a AS a FROM t", 'value', 'DISTINCT in a value query'),
    ("SELECT t.a AS a FROM t HAVING t.a > 1", 'value', 'HAVING without aggregation'),
    ("SELECT t.g AS g, SUM(t.x) AS s FROM t GROUP BY t.g HAVING s > 1", 'value', 'HAVING on a select alias'),
    ("SELECT a FROM t WHERE b > random()", 'set', 'SQLite random()'),
    ("SELECT a FROM t WHERE b < date('now')", 'set', "date('now')"),
    ("SELECT a FROM t WHERE b IN (SELECT c FROM u LIMIT 2)", 'set', 'LIMIT without ORDER BY in a subquery'),
    ("WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM r WHERE n < 3) SELECT n FROM r",
     'set', 'recursive CTE'),
    ("SELECT a, ROW_NUMBER() OVER () FROM t", 'set', 'window function'),
]
for sql, kind, what in REJECTED:
    try:
        Translation(sql, kind=kind)
        report(False, 'should be rejected: %s' % what)
    except Unsupported:
        report(True, 'rejected: %s' % what)

# every occurrence gets its own atom, even with identical text
tr = Translation("SELECT t.a FROM t WHERE t.a > 1 AND EXISTS (SELECT t.a FROM u AS t WHERE t.a > 1)")
report(len(tr.exprs) == len(tr.term.split('(EAtom ')) - 1 and tr.term.count('(EAtom 0)') == 1,
       'one atom per occurrence (%d atoms)' % len(tr.exprs))

# IN forms that are not modelled stay opaque (one atom, never entered)
for sql in ["SELECT t.a FROM t WHERE (t.a, t.b) IN (SELECT u.a, u.b FROM u WHERE u.c > 1)",
            "SELECT t.a FROM t WHERE t.a IN (SELECT * FROM u WHERE u.c > 1)",
            "SELECT t.a FROM t WHERE t.a IN (1, 2, 3)"]:
    tr = Translation(sql)
    report('(In ' not in tr.term and '(Atom ' in tr.term, 'kept opaque: %s' % sql)

# the probes see every select item, including the first one
tr = Translation("SELECT AVG(t.a) + 2 AS k0, MAX(t.b) AS k1 FROM t", dialect='sqlite', kind='value')
probe = tr.numeric_probe() or ''
report('typeof(t.a)' in probe and 'typeof(t.b)' in probe, 'numeric probe covers all select items')
tr = Translation("SELECT AVG(t.a) AS k0, MAX(t.b) AS k1 FROM t GROUP BY t.g", kind='value')
probe = tr.type_probe()[0] or ''
report('t.a' in probe and 't.b' in probe, 'type probe covers all select items')

# ---- the checkers
report(check_inclusion('Up', [(1,), (1,)], [(1,), (1,), (2,)]) == 'ok', 'inclusion respects multiplicities')
report(check_inclusion('Up', [(1,), (1,)], [(1,), (2,)]) == 'violation', 'missing duplicate is a violation')
# inclusion is checked modulo the DBMS's equality, and only that equality
report(check_inclusion('Up', [('A',)], [('a',)]) == 'violation', 'binary: a case difference is a violation')
report(check_inclusion('Up', [('A',)], [('a',)], SQLiteFold('NOCASE')) == 'collation', 'NOCASE: a case difference is a representative choice')
report(check_inclusion('Up', [('A',)], [('a ',)], SQLiteFold('NOCASE')) == 'violation', 'NOCASE does not ignore trailing spaces')
report(check_inclusion('Up', [('\u00c9',)], [('\u00e9',)], SQLiteFold('NOCASE')) == 'violation', 'NOCASE folds ASCII letters only')
report(check_inclusion('Up', [(0.1 + 0.2,)], [(0.3,)]) == 'ok', 'last-bit float noise is not a violation')
report(check_inclusion('Up', [(2**60 + 1,)], [(2**60,)]) == 'violation', 'big integers are compared exactly')
report(check_value('Le', 0, [(2**60 + 1, 1)], [(2**60, 1)]) != 'ok', 'big integers: exact value relation')
report(check_value('Le', 0, [(1, 'A')], [(2, 'a')], fold=SQLiteFold('NOCASE')) == 'ok', 'group key representative may differ modulo collation')
rows = lambda *vals: [(1, v) for v in vals]
report(check_value('Le', 1, rows(1, 5), rows(2, 5)) == 'ok', 'Le holds')
report(check_value('Le', 1, rows(1, 5), rows(0, 5)) != 'ok', 'Le violated')
report(check_value('AwayZero', 1, rows(-3, 0, 4), rows(-6, 0, 8)) == 'ok', 'AwayZero holds on both signs')
report(check_value('AwayZero', 1, rows(-3,), rows(-2,)) != 'ok', 'AwayZero violated for a negative value')
report(check_value('TowardOne', 1, rows(0.25, 4), rows(0.5, 2)) == 'ok', 'TowardOne holds')
report(check_value('AwayOne', 1, rows(0.5, 2), rows(0.25, 4)) == 'ok', 'AwayOne holds')
report(check_value('Le', 1, rows(None,), rows(3,)) != 'ok', 'NULL-ness must not change')
report(check_value('Le', 1, rows(1,), rows(1, 2)) != 'ok', 'row count must not change')
report(check_value('Le', 1, [(1, 'a')], [(1, 'b')]) == 'incomparable', 'non-numeric column is incomparable')
report(check_value('Le', 0, [(1, 0.30000000000000004)], [(2, 0.3)]) == 'ok',
       'floating-point noise in another column does not break the row matching')
report(check_value('Le', 0, [(1, 0.31)], [(2, 0.3)]) != 'ok', 'a real change in another column is reported')
report(check_value('Le', 1, rows(Decimal('82.160004')), rows(82.16)) != 'ok', 'strict tolerance by default')
report(check_value('Le', 1, rows(Decimal('82.160004')), rows(82.16), single_precision=True) == 'ok',
       'single-precision tolerance when asked')

print('%d failures' % failures)
sys.exit(1 if failures else 0)
