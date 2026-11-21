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
    # RIGHT JOIN is the LEFT JOIN with the operands swapped; its left input is mutated
    ("SELECT x.a FROM t AS x RIGHT JOIN u AS y ON x.a = y.a WHERE y.b > 1", 'Up', 'cmp-weaken',
     'FROM u AS y LEFT JOIN t AS x ON x.a = y.a WHERE y.b >= 1'),
    # INTERSECT ALL / EXCEPT ALL, and the rules between them and the DISTINCT forms
    ("SELECT a FROM t INTERSECT SELECT a FROM u", 'Up', 'INTERSECT->INTERSECT-ALL', '(SELECT a FROM t) INTERSECT ALL (SELECT a FROM u)'),
    ("SELECT a FROM t EXCEPT ALL SELECT a FROM u", 'Down', 'EXCEPT-ALL->EXCEPT', '(SELECT a FROM t) EXCEPT (SELECT a FROM u)'),
    ("SELECT t.a FROM t EXCEPT ALL SELECT u.a FROM u WHERE u.b > 1", 'Up', 'cond->FALSE', 'FROM u WHERE 1 = 0'),
    # (a, b) IN (subquery) is monotone in the subquery
    ("SELECT t.a FROM t WHERE (t.a, t.b) IN (SELECT u.a, u.b FROM u WHERE u.c > 1)", 'Up', 'cond->TRUE',
     '(t.a, t.b) IN (SELECT u.a, u.b FROM u WHERE 1 = 1)'),
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

# order-dependent aggregates with an ORDER BY over their own values are determined
for sql in ["SELECT t.g AS g, GROUP_CONCAT(t.c ORDER BY t.c) AS l FROM t GROUP BY t.g",
            "SELECT t.a FROM t WHERE t.a IN (SELECT u.d FROM u GROUP BY u.d)",
            "SELECT t.a FROM t WHERE t.a IN (SELECT MAX(u.c) + 1 FROM u)",
            "SELECT d.x FROM (SELECT (SELECT COUNT(u.c) FROM u) AS n, t.a AS x FROM t) AS d",
            "SELECT t.a FROM t WHERE t.a IN (SELECT u.g FROM u GROUP BY u.g HAVING MAX(u.c) > 1 AND u.g > 0)",
            "SELECT t.a FROM t WHERE t.b IN (SELECT GROUP_CONCAT(DISTINCT u.c ORDER BY u.c SEPARATOR ';') FROM u)",
            "SELECT d.k FROM (SELECT LN(t.c) + 3 AS k, COUNT(*) AS n FROM t GROUP BY LN(t.c)) AS d"]:
    try:
        Translation(sql, kind='value' if sql.startswith('SELECT t.g') else 'set')
        report(True, 'determined aggregate / grouping accepted: %s' % sql)
    except Unsupported as e:
        report(False, 'determined aggregate / grouping rejected (%s): %s' % (e, sql))

# LIMIT whose result is determined: every output column is ordered, or one row
for sql in ["SELECT (SELECT u.c FROM u ORDER BY u.c LIMIT 1) AS x FROM t",
            "SELECT (SELECT u.c AS k FROM u ORDER BY k DESC LIMIT 1) AS x FROM t",
            "SELECT (SELECT u.c, u.d FROM u ORDER BY 2, 1 LIMIT 1) AS x FROM t",
            "SELECT (SELECT MAX(u.c) FROM u LIMIT 1) AS x FROM t"]:
    try:
        Translation(sql)
        report(True, 'determined LIMIT accepted: %s' % sql)
    except Unsupported as e:
        report(False, 'determined LIMIT rejected (%s): %s' % (e, sql))

# the analysed fragment of LIKE / REGEXP: patterns outside it stay opaque predicates
for sql in ["SELECT t.a FROM t WHERE t.c LIKE 'a\\_b'", "SELECT t.a FROM t WHERE t.c REGEXP '[ab]+'",
            "SELECT t.a FROM t WHERE t.c LIKE t.d"]:
    tr = Translation(sql)
    report('(Atom 0)' in tr.term and 'Like' not in tr.term and 'Regex' not in tr.term, 'opaque pattern: %s' % sql)

# LEFT JOIN pads with the width of its right input
tr = Translation("SELECT x.a FROM t AS x LEFT JOIN (SELECT u.a, u.b FROM u) AS y ON x.a = y.a")
report(tr.term.count('(Left 2 ') == 1, 'LEFT JOIN padding = width of the derived table')

# round-trip validation: every printed query must parse back to its term.  Inject the
# two printer bugs found earlier and check that the mutants they spoil are dropped.
import sql_bridge  # noqa: E402
_atom, _p = Translation.__dict__['_atom_text'], Translation._p_sql
try:
    Translation._atom_text = staticmethod(lambda text: text)          # parentheses lost
    before = sql_bridge.STATS['roundtrip_rejected']
    _, mutants, _ = mutate_value_sql("SELECT SUM(t.x - 50) AS s FROM t")
    report(not any('t.x - 50 * 2' in m for _, _, _, m in mutants) and
           sql_bridge.STATS['roundtrip_rejected'] > before, 'round trip drops a mutant printed without parentheses')

    def lose_not(self, p):
        return _p(self, p[1]) if p != 'True' and p != 'False' and p[0] == 'Not' else _p(self, p)
    Translation._atom_text = _atom
    Translation._p_sql = lose_not                                    # NOT lost
    try:
        mutate_sql("SELECT t.a FROM t WHERE NOT (t.b > 1)")
        report(False, 'round trip rejects an original whose NOT is lost')
    except Unsupported:
        report(True, 'round trip rejects an original whose NOT is lost')
finally:
    Translation._atom_text, Translation._p_sql = _atom, _p

# the collation law: an operation that tells collation-equivalent values apart must
# not be applied to the representative chosen by a de-duplication
LAW = [
    ("SELECT LENGTH(d.c) AS n FROM (SELECT DISTINCT t.c FROM t) AS d", 'mysql', False,
     'LENGTH above DISTINCT'),
    ("SELECT d.c FROM (SELECT DISTINCT t.c FROM t) AS d WHERE d.c LIKE 'a%'", 'mysql', False,
     'LIKE above DISTINCT'),
    ("SELECT HEX(d.m) AS h FROM (SELECT MAX(t.c) AS m FROM t) AS d", 'mysql', False,
     'HEX above an opaque MAX'),
    ("SELECT d.c / 2 AS h FROM (SELECT DISTINCT t.c FROM t) AS d", 'sqlite', False,
     'SQLite division above DISTINCT (1 and 1.0 are equal)'),
    ("SELECT d.c / 2 AS h FROM (SELECT DISTINCT t.c FROM t) AS d", 'mysql', True,
     'division above DISTINCT on MySQL'),
    ("SELECT LENGTH(t.c) AS n FROM t WHERE t.a > 1", 'mysql', True, 'LENGTH without de-duplication'),
    ("SELECT LENGTH(t.c) AS n FROM t UNION SELECT LENGTH(u.c) FROM u", 'mysql', True,
     'LENGTH below the UNION'),
    ("SELECT d.c FROM (SELECT DISTINCT t.c FROM t) AS d WHERE d.c = 'a'", 'mysql', True,
     'comparison above DISTINCT (respects the collation)'),
]
for sql, dialect, accepted, what in LAW:
    try:
        Translation(sql, dialect)
        ok = accepted
    except Unsupported as e:
        ok = not accepted and 'outside the model' in str(e)
    report(ok, 'collation law: %s %s' % ('accepted' if accepted else 'rejected', what))
# a mutant that adds DISTINCT below LENGTH is dropped; DISTINCT above it is kept
_, mutants, _ = mutate_sql("SELECT LENGTH(t.c) AS n FROM t WHERE t.a > 1")
report(not any('DISTINCT * FROM t' in m for _, _, m in mutants) and
       any(m.startswith('SELECT DISTINCT LENGTH') for _, _, m in mutants),
       'collation law: DISTINCT-add below LENGTH dropped, above kept')

# DISTINCT around a join, printed with GROUP BY over every column of the joined tables
# (needs the schema); the printed SQL parses back to the same term
SCHEMA = {'t': ['a', 'b'], 'u': ['a', 'c']}
for sql in ["SELECT x.a, y.c FROM t AS x INNER JOIN u AS y ON x.a = y.a WHERE x.b > 1",
            "SELECT DISTINCT x.a FROM t AS x LEFT JOIN u AS y ON x.a = y.a"]:
    before = sql_bridge.STATS['roundtrip_rejected']
    _, mutants, skipped = mutate_sql(sql, schema=SCHEMA)
    report(skipped == 0 and any('GROUP BY x.a, x.b, y.a, y.c' in m for _, _, m in mutants)
           and sql_bridge.STATS['roundtrip_rejected'] == before, 'DISTINCT around a join printed: %s' % sql)
_, _, skipped = mutate_sql("SELECT x.a, y.c FROM t AS x INNER JOIN u AS y ON x.a = y.a")
report(skipped > 0, 'without the schema DISTINCT around a join stays unprintable')

# a filter that refers to an outer table is lifted out of DISTINCT, so MySQL accepts it
_, mutants, _ = mutate_sql("SELECT x.a FROM t AS x WHERE x.b IN (SELECT y.c FROM u AS y WHERE y.a = x.a)")
report(any('FROM (SELECT DISTINCT * FROM u AS y) AS y WHERE y.a = x.a' in m for _, _, m in mutants) and
       not any('FROM u AS y WHERE y.a = x.a) AS y' in m for _, _, m in mutants),
       'correlated filter lifted out of a DISTINCT derived table')

# UNION ALL of value queries (VUnion.v): one arm is mutated, the other stays
_, mutants, _, _, having = mutate_value(
    "SELECT t.g AS g, SUM(t.x) AS s FROM t GROUP BY t.g HAVING SUM(t.x) > 1 UNION ALL SELECT u.g, COUNT(u.y) FROM u GROUP BY u.g")
report(any(r == 'SUM(c)->SUM(c*k)' and m.endswith('UNION ALL (SELECT u.g AS c0, COUNT(u.y) AS c1 FROM u GROUP BY u.g)')
           for _, r, _, m in mutants) and any(r == 'COUNT->COUNT-DISTINCT' and 'SUM(t.x) AS s' in m for _, r, _, m in mutants)
       and any(r == 'cond->TRUE' for _, r, _ in having), 'UNION ALL of value queries: each arm mutated alone')
try:
    # DISTINCT inside an arm of a UNION ALL is not modelled (only DISTINCT at the top)
    mutate_value("SELECT DISTINCT t.g AS g FROM t UNION ALL SELECT u.g FROM u")
    report(False, 'DISTINCT inside a UNION ALL of value queries must be rejected')
except Unsupported:
    report(True, 'DISTINCT inside a UNION ALL of value queries rejected')

# a mutant that changes the leftmost arm of a set operation changes the collation that
# operation compares with (SQLite: the leftmost arm's columns); such mutants are dropped
_, mutants, _ = mutate_sql("SELECT a.x FROM a INTERSECT SELECT b.y FROM b UNION SELECT c.z FROM c", dialect='sqlite')
report(not any(r == 'INTERSECT->operand' and m.startswith('SELECT b.y') for _, r, m in mutants) and
       any(r == 'INTERSECT->operand' and m.startswith('SELECT a.x FROM a UNION') for _, r, m in mutants),
       'INTERSECT->operand: the right arm may not become the leftmost arm of a UNION')
_, mutants, _ = mutate_sql("SELECT a.x FROM a INTERSECT SELECT b.y FROM b")
report(any(r == 'INTERSECT->operand' and m == 'SELECT b.y FROM b' for _, r, m in mutants),
       'INTERSECT->operand at the top: the right arm is allowed')

# MySQL / MariaDB derive a compound's collation from all its arms: removing an arm inside
# an enclosing set operation is outside the model (EXCEPT->left below a UNION)
_, mutants, _ = mutate_sql("(SELECT a.x FROM a EXCEPT SELECT b.y FROM b) UNION SELECT c.z FROM c")
report(not any(r == 'EXCEPT->left' for _, r, _ in mutants), 'MySQL: EXCEPT->left below a UNION is dropped')
_, mutants, _ = mutate_sql("(SELECT a.x FROM a EXCEPT SELECT b.y FROM b) UNION SELECT c.z FROM c", dialect='sqlite')
report(any(r == 'EXCEPT->left' for _, r, _ in mutants), 'SQLite: EXCEPT->left keeps the leftmost arm, kept')
_, mutants, _ = mutate_sql("SELECT a.x FROM a EXCEPT SELECT b.y FROM b")
report(any(r == 'EXCEPT->left' for _, r, _ in mutants), 'MySQL: EXCEPT->left at the top is kept')

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
_, mutants, _ = mutate_value_sql("SELECT VAR_SAMP(t.b) AS s, GROUP_CONCAT(t.c ORDER BY t.c) AS g, SUM(DISTINCT t.d) AS d FROM t")
report(any(r == 'VAR_SAMP->STDDEV_SAMP' for _, r, _, _ in mutants) and
       all("(GROUP_CONCAT(t.c ORDER BY t.c SEPARATOR ',')) AS g" in m for _, _, c, m in mutants if c == 0) and
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
    ("SELECT * FROM t AS x RIGHT JOIN u AS y ON x.a = y.a", 'set', 'RIGHT JOIN with SELECT *'),
    ("SELECT x.a FROM t AS x JOIN v ON 1 = 1 RIGHT JOIN u AS y ON x.a = y.a", 'set', 'RIGHT JOIN after a join'),
    ("SELECT t.a, SUM(t.b) AS s FROM t GROUP BY t.c", 'value', 'non-key column in a grouped select'),
    ("SELECT DISTINCT ON (t.a) t.a AS a FROM t", 'value', 'DISTINCT ON in a value query'),
    ("SELECT t.a AS a FROM t HAVING t.a > 1", 'value', 'HAVING without aggregation'),
    ("SELECT t.g AS g, SUM(t.x) AS s FROM t GROUP BY t.g HAVING s > 1", 'value', 'HAVING on a select alias'),
    ("SELECT a FROM t WHERE b > random()", 'set', 'SQLite random()'),
    ("SELECT a FROM t WHERE b < date('now')", 'set', "date('now')"),
    ("SELECT a FROM t WHERE b IN (SELECT c FROM u LIMIT 2)", 'set', 'LIMIT without ORDER BY in a subquery'),
    ("SELECT a FROM t WHERE b IN (SELECT u.c FROM u ORDER BY u.d LIMIT 2)", 'set', 'LIMIT with ties (c not ordered)'),
    ("SELECT a FROM t WHERE b IN (SELECT u.c FROM u UNION SELECT v.c FROM v LIMIT 2)", 'set', 'LIMIT on a compound without ORDER BY'),
    ("SELECT (SELECT u.c FROM u ORDER BY u.d LIMIT 1) AS x FROM t", 'set', 'scalar subquery with LIMIT over ties'),
    ("WITH RECURSIVE r AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM r WHERE n < 3) SELECT n FROM r",
     'set', 'recursive CTE'),
    ("SELECT a, ROW_NUMBER() OVER () FROM t", 'set', 'window function'),
    ("SELECT j.value FROM t AS x, json_each(x.doc) AS j", 'set', 'table function with column arguments'),
    ("SELECT t.a FROM t WHERE t.b IN (SELECT GROUP_CONCAT(u.c) FROM u)", 'set', 'GROUP_CONCAT without ORDER BY'),
    ("SELECT t.g AS g, GROUP_CONCAT(t.c ORDER BY t.d) AS l FROM t GROUP BY t.g", 'value', 'GROUP_CONCAT ordered by another column'),
    ("SELECT t.a FROM t WHERE t.b = (SELECT JSON_ARRAYAGG(u.c) FROM u)", 'set', 'JSON_ARRAYAGG'),
    ("SELECT d.x FROM (SELECT t.a AS x FROM t GROUP BY t.b) AS d", 'set', 'bare column in a grouped derived table'),
    ("SELECT t.a FROM t WHERE t.a IN (SELECT u.c FROM u GROUP BY u.d)", 'set', 'bare column in a grouped subquery'),
    ("SELECT t.a FROM t WHERE t.a IN (SELECT u.c, COUNT(*) FROM u)", 'set', 'bare column next to an aggregate'),
    ("SELECT t.a FROM t WHERE t.a IN (SELECT u.g FROM u GROUP BY u.g HAVING u.c > 1)", 'set', 'bare column in HAVING'),
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
for sql in ["SELECT t.a FROM t WHERE (t.a, t.b) IN (SELECT u.a FROM u WHERE u.c > 1)",
            "SELECT t.a FROM t WHERE t.a IN (SELECT * FROM u WHERE u.c > 1)",
            "SELECT t.a FROM t WHERE t.a IN (1, 2, 3)"]:
    tr = Translation(sql)
    report('(In ' not in tr.term and '(InT ' not in tr.term and '(Atom ' in tr.term, 'kept opaque: %s' % sql)

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
# values are compared by what they denote when the server types a column differently
import datetime  # noqa: E402
from checker import comparable_types  # noqa: E402
report(check_inclusion('Up', [(b'x', 23)], [('x', Decimal('23'))]) == 'ok', 'BLOB vs TEXT, BIGINT vs DECIMAL')
report(check_inclusion('Up', [('2024-12-09', '00:00:00')], [(datetime.date(2024, 12, 9), datetime.timedelta(0))]) == 'ok',
       'VARCHAR vs DATE / TIME')
report(check_inclusion('Up', [(60.54,)], [(Decimal('60.54'),)]) == 'ok', 'DOUBLE vs DECIMAL (rounded attempt)')
report(check_inclusion('Up', [(b'\x02',)], [(b'2',)]) == 'violation', 'BIT value vs its decimal text stays different')
report(comparable_types([3, 252], [5, 253], [(1, 'a')], [(1.0, 'a')]) is None, 'type families: number, text')
report(comparable_types([3], [253], [(82,)], [('82',)]) is not None, 'type families: number vs text is refused')
report(comparable_types([253], [3], [(None,)], [(82,)]) is None, 'a column that is NULL only fits any type')
# one fold per result column: a case difference is a representative choice only in a
# case-insensitive column
two = [SQLiteFold('BINARY'), SQLiteFold('NOCASE')]
report(check_inclusion('Up', [('x', 'A')], [('x', 'a')], two) == 'collation', 'per column: NOCASE column folds')
report(check_inclusion('Up', [('A', 'x')], [('a', 'x')], two) == 'violation', 'per column: BINARY column does not fold')
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
# the check asks whether SOME one-to-one correspondence satisfies the relation
report(check_value('TowardOne', 1, rows(0.5, 2), rows(3, 1.5)) == 'ok',
       'TowardOne: a correspondence exists that sorting does not find (0.5->3, 2->1.5)')
report(check_value('TowardOne', 1, rows(0.5, 0.6), rows(0.25, 3)) != 'ok',
       'TowardOne: no correspondence exists (0.5 and 0.6 both need the value 3)')
report(check_value('AwayZero', 1, rows(-1, 0, 1), rows(-2, 0, 2)) == 'ok', 'AwayZero: 0 stays 0, signs kept')
report(check_value('AwayZero', 1, rows(-1, 0, 1), rows(-2, 0.5, 2)) != 'ok', 'AwayZero: 0 must stay 0')
report(check_value('Le', 1, rows(None, 1), rows(5, None)) == 'ok', 'NULL corresponds to NULL in any row order')
report(check_value('Le', 1, rows(None, 1), rows(5, 6)) != 'ok', 'a NULL that disappears is reported')
report(check_value('Le', 0, [(1, 'x'), (5, 'y')], [(6, 'x'), (2, 'y')]) != 'ok',
       'values correspond only within rows that agree outside the column')
report(check_value('Le', 1, rows(Decimal('82.160004')), rows(82.16), single_precision=True) == 'ok',
       'single-precision tolerance when asked')

# SQLite reports the collation of each result column (libraries built with
# SQLITE_ENABLE_COLUMN_METADATA, see build_old_sqlite.sh); the checker uses it
import glob  # noqa: E402
from sqlite_exec import SQLiteLib  # noqa: E402
libs = sorted(glob.glob(os.environ.get('SQLITE_LIBS', '/tmp/sqlite-libs') + '/libsqlite3-*.so'))
if libs:
    db = SQLiteLib(libs[0], ':memory:')
    db.executescript("CREATE TABLE t (a TEXT COLLATE NOCASE, b TEXT); INSERT INTO t VALUES ('A', 'a')")
    db.query("SELECT a, b, a || '' FROM t")
    report(db.last_collations == ['NOCASE', 'BINARY', None], 'SQLite column collations %r' % db.last_collations)
    # a compound: the metadata names the leftmost arm only; every arm counts
    db.query("SELECT b FROM t UNION ALL SELECT DISTINCT a FROM t")
    report(db.last_collations == ['NOCASE'], 'SQLite compound: coarsest collation of all arms %r' % db.last_collations)
    db.query("SELECT b, a FROM t UNION SELECT b, b FROM t")
    report(db.last_collations == ['BINARY', 'NOCASE'], 'SQLite compound: per column %r' % db.last_collations)
    db.query("SELECT d.b FROM (SELECT b FROM t UNION SELECT a FROM t) AS d")
    report(db.last_collations == [None], 'SQLite nested compound: metadata not used %r' % db.last_collations)
else:
    print('skip  SQLite column metadata (no library in $SQLITE_LIBS)')

# SQLite: 1 and 1.0 are equal, but their text is not; text of a value above DISTINCT
for sql in ["SELECT UPPER(d.x) AS s FROM (SELECT DISTINCT t.a AS x FROM t) AS d",
            "SELECT CAST(d.x AS TEXT) AS s FROM (SELECT DISTINCT t.a AS x FROM t) AS d"]:
    try:
        Translation(sql, 'sqlite', kind='set')
        report(False, 'SQLite text of a number above DISTINCT accepted: %s' % sql)
    except Unsupported:
        report(True, 'SQLite text of a number above DISTINCT rejected: %s' % sql)
try:
    Translation("SELECT UPPER(t.a) AS s FROM t", 'sqlite', kind='set')
    Translation("SELECT UPPER(d.x) AS s FROM (SELECT DISTINCT t.a AS x FROM t) AS d", 'mysql', kind='set')
    report(True, 'UPPER without DISTINCT below (SQLite) and above DISTINCT (MySQL) accepted')
except Unsupported as e:
    report(False, 'UPPER wrongly rejected: %s' % e)

# bisection (bisect_sqlite.first_change) with a stubbed verdict: commits 0..99, bad from 37
import bisect_sqlite  # noqa: E402
real_verdict = bisect_sqlite.verdict
rec = {'original': 'o', 'mutant': 'm'}
commits = ['c%d' % i for i in range(100)]
for skips, label in [(set(), 'no skips'), ({36, 37, 38, 50, 25}, 'with unjudgeable commits')]:
    bisect_sqlite.verdict = lambda b, sha, r, t, skips=skips: (
        'skip' if int(sha[1:]) in skips else ('bad' if int(sha[1:]) >= 37 else 'good'))
    hi, lo, steps = bisect_sqlite.first_change(None, commits, rec, None, 'bad', {})
    expect = (37, 36) if not skips else (39, 35)
    report((hi, lo) == expect and steps <= 12, 'bisection %s: first bad %d, last good %d, %d steps' % (label, hi, lo, steps))
bisect_sqlite.verdict = real_verdict
groups = []
import io, contextlib  # noqa: E402
out = io.StringIO()
with contextlib.redirect_stdout(out):
    bisect_sqlite.report([
        {'pair': 1, 'rule': 'A', 'fixed_by': {'commit': 'f1' * 20, 'date': 'd', 'subject': 's', 'first_release': 'v1'},
         'introduced_by': {'commit': 'i1' * 20, 'date': 'd', 'subject': 's', 'first_release': 'v0'}, 'fix_exact': True},
        {'pair': 2, 'rule': 'B', 'fixed_by': {'commit': 'f1' * 20, 'date': 'd', 'subject': 's', 'first_release': 'v1'},
         'introduced_by': {'commit': 'i1' * 20, 'date': 'd', 'subject': 's', 'first_release': 'v0'}, 'fix_exact': True},
        {'pair': 3, 'rule': 'A', 'fixed_by': {'commit': 'f1' * 20, 'date': 'd', 'subject': 's', 'first_release': 'v1'},
         'introduced_by': {'commit': 'i2' * 20, 'date': 'd', 'subject': 's', 'first_release': 'v0'}, 'fix_exact': True}])
report('3 pairs, 2 distinct bugs' in out.getvalue(), 'bisection report: same commits one bug, another introducing commit another bug')

# collation law on columns that hold integers only (exact_columns): an operation that reads
# only such columns gives the same result whichever representative a de-duplication kept
sch = {'t': ['a', 'b', 'n'], 'u': ['c', 'm']}
for sql, expect in [
        ("SELECT d.x FROM (SELECT DISTINCT t.n AS x FROM t) AS d WHERE d.x LIKE '1%'", True),
        ("SELECT d.x FROM (SELECT DISTINCT t.a AS x FROM t) AS d WHERE d.x LIKE '1%'", False),
        ("SELECT UPPER(d.n) AS s FROM (SELECT DISTINCT t.n AS n, t.a AS a FROM t) AS d", True),
        ("SELECT UPPER(d.a) AS s FROM (SELECT DISTINCT t.n AS n, t.a AS a FROM t) AS d", False),
        ("SELECT d.x FROM (SELECT DISTINCT t.n AS x FROM t UNION SELECT u.c AS x FROM u) AS d WHERE d.x GLOB '1*'", False),
        ("SELECT d.x FROM (SELECT DISTINCT t.n AS x FROM t UNION SELECT u.m AS x FROM u) AS d WHERE d.x GLOB '1*'", True),
        ("SELECT d.x FROM (SELECT DISTINCT AVG(t.n) AS x FROM t GROUP BY t.a) AS d WHERE CAST(d.x AS TEXT) = '1'", False),
        ("SELECT d.n FROM (SELECT DISTINCT t.a AS n FROM t) AS d WHERE d.n LIKE '1%'", False)]:
    try:
        Translation(sql, 'sqlite', schema=sch, exact_columns={'n', 'm'})
        got = True
    except Unsupported:
        got = False
    report(got == expect, 'exact columns: %s %s' % ('accepted' if got else 'rejected', sql))

# per table: t.c is an integer column, u.c a real one (the name c alone is not exact)
from sql_bridge import ExactColumns  # noqa: E402
ex = ExactColumns({})
ex.by_table = {('t', 'c'): 'integer', ('u', 'c'): 'real'}
for sql, expect in [
        ("SELECT d.c || '' AS s FROM (SELECT DISTINCT t.c AS c FROM t) AS d", True),
        ("SELECT d.c || '' AS s FROM (SELECT DISTINCT t.c AS c FROM t UNION SELECT u.c AS c FROM u) AS d", False),
        ("SELECT d.c || '' AS s FROM (SELECT DISTINCT u.c AS c FROM u UNION SELECT u.c AS c FROM u) AS d", True),
        ("SELECT d.c || '' AS s FROM (SELECT DISTINCT t.a AS c FROM t) AS d", False)]:
    try:
        Translation(sql, 'sqlite', schema={'t': ['a', 'c'], 'u': ['c']}, exact_columns=ex)
        got = True
    except Unsupported:
        got = False
    report(got == expect, 'exact columns per table: %s %s' % ('accepted' if got else 'rejected', sql))

# a sensitive operation inside a subquery matters only if it reads the outer row
for sql, expect in [
        ("SELECT d.x FROM (SELECT DISTINCT t.a AS x FROM t) AS d WHERE d.x IN (SELECT u.c FROM u WHERE u.c LIKE '1%')", True),
        ("SELECT d.x FROM (SELECT DISTINCT t.a AS x FROM t) AS d WHERE EXISTS (SELECT u.c FROM u WHERE u.c = d.x || '')", False),
        ("SELECT d.x FROM (SELECT DISTINCT t.a AS x FROM t) AS d WHERE EXISTS (SELECT u.c FROM u WHERE d.x LIKE u.c)", False),
        ("SELECT d.x FROM (SELECT DISTINCT t.a AS x FROM t) AS d WHERE EXISTS (SELECT u.c FROM u WHERE c LIKE '1%')", False)]:
    try:
        Translation(sql, 'sqlite')
        got = True
    except Unsupported:
        got = False
    report(got == expect, 'collation law, subquery: %s %s' % ('accepted' if got else 'rejected', sql))

# DISTINCT value queries (VDistinct.v): the mutants are those without DISTINCT, printed with
# it; the check is a cover in both directions
trs = []
_, mutants, _, _, having = mutate_value("SELECT DISTINCT t.g AS g, FLOOR(t.x) AS f FROM t", translation=trs)
report(trs[0].value_distinct and mutants and all(m[3].startswith('SELECT DISTINCT ') for m in mutants),
       'DISTINCT value query: mutants printed with DISTINCT')
trs = []
_, mutants, _, _, _ = mutate_value("SELECT t.a AS a, MAX(t.x) AS m FROM t GROUP BY t.a UNION "
                                   "SELECT u.b AS a, MIN(u.y) AS m FROM u GROUP BY u.b", translation=trs)
report(trs[0].value_distinct and mutants and all(') UNION (' in m[3] for m in mutants),
       'UNION of value queries: DISTINCT over UNION ALL, printed as UNION')
trs = []
_, mutants, _, _, _ = mutate_value("SELECT DISTINCT t.a AS a, MAX(t.x) AS m FROM t GROUP BY t.a UNION "
                                   "SELECT u.b AS a, MIN(u.y) AS m FROM u GROUP BY u.b", translation=trs)
report(trs[0].value_distinct and bool(mutants), 'UNION of value queries: a DISTINCT arm is accepted (redundant)')
# rows merge: original (1, 2), (1, 2), (2, 3) -> DISTINCT (1, 2), (2, 3); mutant +1 in column 1
orig = [(1, 2), (2, 3)]
report(check_value('Le', 1, orig, [(1, 3), (2, 4)], cover=True) == 'ok', 'cover: related rows on both sides')
report(check_value('Le', 1, orig, [(1, 3), (1, 5), (2, 4)], cover=True) == 'ok', 'cover: two mutant rows for one original row')
report(check_value('Le', 1, [(1, 2), (1, 4), (2, 3)], [(1, 4), (2, 3)], cover=True) == 'ok',
       'cover: two original rows merged into one mutant row')
report(check_value('Le', 1, orig, [(1, 1), (2, 4)], cover=True).startswith('Le violated'), 'cover: a decreased value is a violation')
report(check_value('Le', 1, orig, [(2, 4)], cover=True) == 'other columns changed', 'cover: a missing group is detected')
report(check_value('Le', 1, orig, [(1, 3), (1, 5), (2, 4)]) != 'ok', 'without cover, three rows for two are a violation')

# SQLite: the collation of a compound column comes from the first arm whose item has one
from sql_bridge import sqlite_collation_sources as sources  # noqa: E402
report(sources("SELECT COALESCE(t.a, 0) AS k FROM t UNION SELECT u.b AS k FROM u") == {('u.b',)},
       'SQLite compound collation: an expression passes it on to the next arm')
report(sources("SELECT DISTINCT * FROM (SELECT COALESCE(t.a, 0) AS k FROM t) AS d UNION SELECT u.b AS k FROM u")
       == {('BINARY (derived column)',)}, 'SQLite compound collation: a derived column of an expression is BINARY')
report(sources("SELECT DISTINCT * FROM (SELECT t.a AS k FROM t) AS d UNION SELECT u.b AS k FROM u") == {('t.a',)},
       'SQLite compound collation: * over a derived table is its item')

# window functions in value queries without aggregation: opaque items when determined
for sql, expect in [
        ("SELECT t.a AS a, RANK() OVER (ORDER BY t.b) AS r, FLOOR(t.x) AS f FROM t", True),
        ("SELECT t.a AS a, SUM(t.x) OVER (PARTITION BY t.a) AS s, FLOOR(t.x) AS f FROM t", True),
        ("SELECT t.a AS a, ROW_NUMBER() OVER (ORDER BY t.b) AS r, FLOOR(t.x) AS f FROM t", False),
        ("SELECT t.a AS a, SUM(t.x) OVER (ORDER BY t.b ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) AS s, "
         "FLOOR(t.x) AS f FROM t", False),
        ("SELECT t.a AS a, SUM(t.x) AS s, RANK() OVER (ORDER BY SUM(t.x)) AS r FROM t GROUP BY t.a", False),
        # MariaDB ranks by the select alias a (the item -t.a, which a mutation changes)
        ("SELECT -t.a AS a, RANK() OVER (ORDER BY a) AS r, FLOOR(t.x) AS f FROM t", False),
        ("SELECT t.a + 0 AS k0, SUM(t.x) OVER (PARTITION BY k0) AS s, FLOOR(t.x) AS f FROM t", False)]:
    try:
        _, mutants, _, _, _ = mutate_value(sql)
        got = all('OVER' in m for _, _, _, m in mutants) and bool(mutants)
    except Unsupported:
        got = False
    report(got == expect, 'window in a value query: %s %s' % ('accepted' if got else 'rejected', sql))

# SQLite: HAVING without GROUP BY is printed as a WHERE over a derived table (old releases
# reject the HAVING); both forms give the same rows, on every predicate value and on an empty table
import sqlite3  # noqa: E402
import sql_bridge as _sb  # noqa: E402
con = sqlite3.connect(':memory:')
con.execute('CREATE TABLE t (a INT, x INT)')
same = True
for data in ([], [(1, 2), (2, None), (3, 5)], [(None, None)]):
    con.execute('DELETE FROM t')
    con.executemany('INSERT INTO t VALUES (?, ?)', data)
    for sql in ['SELECT SUM(t.x) AS k0, COUNT(*) AS k1 FROM t HAVING COUNT(*) > 1',
                'SELECT MAX(t.a) AS k0 FROM t WHERE t.a > 1 HAVING SUM(t.x) IS NULL',
                'SELECT DISTINCT COUNT(t.x) AS k0 FROM t HAVING MIN(t.a) < 3']:
        tr = _sb.Translation(sql, 'sqlite', kind='value')
        plain = tr.to_sql(tr.term)
        tr.wrap_global_having = True
        wrapped = tr.to_sql(tr.term)
        same = same and 'HAVING' in plain and 'HAVING' not in wrapped and \
            sorted(con.execute(plain).fetchall(), key=repr) == sorted(con.execute(wrapped).fetchall(), key=repr)
report(same, 'SQLite: HAVING without GROUP BY printed as WHERE over a derived table gives the same rows')
_, _, _, _, hm = mutate_value('SELECT SUM(t.x) AS k0 FROM t', dialect='sqlite')
report(hm and all('HAVING' not in m for _, _, m in hm), 'SQLite: HAVING mutants of an ungrouped aggregate need no GROUP BY')

# the adaptive campaign: UCB1 tries every arm once, then prefers the arm with more reward
import random  # noqa: E402
import campaign_sqlite  # noqa: E402
bandit = campaign_sqlite.Bandit(campaign_sqlite.ARMS)
for _ in range(4):
    bandit.update(bandit.pick(), 0.0)
report(sorted(bandit.n) == [1, 1, 1, 1], 'adaptive: every setting is tried once first')
rng = random.Random(7)
for _ in range(400):
    i = bandit.pick()
    bandit.update(i, 1.0 if (i == 2 and rng.random() < 0.8) or rng.random() < 0.2 else 0.0)
report(max(range(4), key=lambda i: bandit.n[i]) == 2, 'adaptive: the best setting is chosen most often (%s)' % bandit.n)
shape = campaign_sqlite.term_shape("SELECT t.a FROM t WHERE t.a IN (SELECT u.c FROM u) UNION SELECT t.b FROM t", 'set')
report({'Union', 'In', 'Where'} <= shape, 'adaptive: coverage features of a term (%s)' % sorted(shape))

print('%d failures' % failures)
sys.exit(1 if failures else 0)
