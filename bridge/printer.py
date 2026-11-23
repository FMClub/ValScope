"""Term -> SQL: the printer of algebra terms (not verified; every printed query is read
back and compared with its term, sql_bridge._roundtrip_ok), and the probe queries that
expose the types of the expressions a value query uses."""
import sqlglot
from sqlglot import exp

from common import CMP_SQL, SET_SQL, Unsupported, _quote, parse_sexp
from collation_law import _cached_parse


class Printer:
    """Mixin of sql_bridge.Translation: it reads the tables of atoms filled by the parser
    (self.exprs, self.preds, self.tables, ...)."""

    # ------------------------------------------------------------ term -> SQL
    # ------------------------------------------------ DISTINCT around a join
    def _join_columns(self, j):
        """All columns of the joined base tables of j, qualified by their aliases, or None
        if a table is not a base table of the known schema."""
        if not isinstance(j, list) or not j:
            return None
        if j[0] == 'T':
            tree = _cached_parse(self._law_cache, self.tables[int(j[1])], self.dialect, 'table')
            if tree is None:
                return None
            node = (tree.args.get('from_') or tree.args.get('from')).this
            if not isinstance(node, exp.Table) or not isinstance(node.this, exp.Identifier):
                return None
            cols = self.schema.get(node.name.lower())
            return ['%s.%s' % (node.alias_or_name, c) for c in cols] if cols else None
        if j[0] == 'Inner':
            a, b = self._join_columns(j[2]), self._join_columns(j[3])
        elif j[0] == 'Left':
            a, b = self._join_columns(j[3]), self._join_columns(j[4])
        else:
            return None
        return a + b if a is not None and b is not None else None

    # ------------------------------------------------ lifting correlated filters
    def _qualifiers(self, x):
        """Table qualifiers used by the atoms of x, minus the aliases x defines itself."""
        used, defined = set(), set()

        def walk(t):
            if not isinstance(t, list) or not t:
                return
            if isinstance(t[0], list):
                for y in t:
                    walk(y)
                return
            tag = t[0]
            if tag in ('EAtom', 'Atom'):
                text = (self.exprs if tag == 'EAtom' else self.preds)[int(t[1])]
                tree = _cached_parse(self._law_cache, text, self.dialect)
                if tree is None:
                    used.add(None)
                    return
                inner = {n.alias_or_name for n in tree.find_all(exp.Table, exp.Subquery)}
                defined.update(inner)
                used.update(c.table for c in tree.find_all(exp.Column) if c.table)
            elif tag == 'T':
                defined.add(self.aliases[int(t[1])])
            elif tag == 'Named':
                defined.add(self.named[int(t[1])])
            for y in t[1:]:
                walk(y)
        walk(x)
        return used - defined

    def lift(self, t):
        """Distinct(Where p X), X a table, as the input of a projection or a filter, with p
        referring to tables outside X (a correlated subquery): rewritten to
        Where p (Distinct X), and merged with an enclosing filter.  Same rows modulo the
        collation (Approx.compat: p gives equal truth values on equivalent rows); SQL can
        print it, while a derived table cannot see the outer tables."""
        if not isinstance(t, list) or not t or isinstance(t[0], list):
            return [self.lift(y) for y in t] if isinstance(t, list) else t
        t = [t[0]] + [self.lift(y) for y in t[1:]]
        if t[0] == 'Where' and isinstance(t[2], list) and t[2][0] == 'Distinct':
            # a filter above DISTINCT around a join is moved below it (same rows modulo the
            # collation, by Approx.compat), so that it is printed as one WHERE ... GROUP BY
            inner = t[2][1]
            if isinstance(inner, list) and inner[0] == 'Where' and inner[2][0] in ('Inner', 'Left'):
                return ['Distinct', ['Where', ['And', inner[1], t[1]], inner[2]]]
            if isinstance(inner, list) and inner[0] in ('Inner', 'Left'):
                return ['Distinct', ['Where', t[1], inner]]
        if t[0] in ('Proj', 'Where'):
            x = t[2]
            if isinstance(x, list) and x[0] == 'Distinct' and isinstance(x[1], list) and x[1][0] == 'Where' \
                    and isinstance(x[1][2], list) and x[1][2][0] in ('T', 'Named'):
                p, inner = x[1][1], x[1][2]
                alias = (self.aliases if inner[0] == 'T' else self.named)[int(inner[1])]
                if self._qualifiers(p) - {alias}:
                    lifted = ['Where', p, ['Distinct', inner]]
                    if t[0] == 'Where':
                        return ['Where', ['And', t[1], p], ['Distinct', inner]]
                    return ['Proj', t[1], lifted]
        return t

    def to_sql(self, term):
        tree = parse_sexp(term) if isinstance(term, str) else term
        tree = self.lift(tree)
        if tree[0] in ('SInter', 'SExcept'):
            self._arm = 0
            return self._st_sql(tree)
        if tree[0] in ('VProj', 'VGroup', 'VGlobal', 'VUnionAll'):
            self._arm = 0
            return self._vt_sql(tree)
        return self._q_sql(tree)

    def _st_sql(self, t):
        """SQL of an INTERSECT / EXCEPT of value terms (VSet.v); an operand that is not one
        is a UNION ALL of value queries, printed without DISTINCT."""
        if t[0] not in ('SInter', 'SExcept'):
            return self._vt_sql(t, ('one', False))
        op = 'INTERSECT' if t[0] == 'SInter' else 'EXCEPT'
        left, right = self._st_sql(t[1]), self._st_sql(t[2])
        if self.dialect == 'sqlite':
            if t[2][0] in ('SInter', 'SExcept', 'VUnionAll'):
                raise Unsupported('SQLite: a compound right operand of %s' % op)
            return '%s %s %s' % (left, op, right)
        return '(%s) %s (%s)' % (left, op, right)

    def _vt_sql(self, t, mask=None):
        """SQL of a value term; `mask` (VDistinct.v: mask) says which parts are under DISTINCT."""
        mask = self.value_mask if mask is None else mask
        if mask[0] == 'union' and t[0] == 'VUnionAll':
            return self._compound_sql('UNION ALL', t, self._vt_sql(t[1], mask[1]), self._vt_sql(t[2], mask[2]))
        return self._arms_sql(t, mask == ('one', True))

    def _arms_sql(self, t, distinct):
        """SQL of a UNION ALL of arms; under DISTINCT, SELECT DISTINCT for one arm and UNION
        (DISTINCT over their UNION ALL) for several."""
        if t[0] != 'VUnionAll':
            sql = self._v_sql(t)
            if distinct:
                assert sql.startswith('SELECT ')
                sql = 'SELECT DISTINCT ' + sql[len('SELECT '):]
            return sql
        return self._compound_sql('UNION' if distinct else 'UNION ALL', t,
                                  self._arms_sql(t[1], False), self._arms_sql(t[2], False))

    def _compound_sql(self, op, t, left, right):
        if self.dialect == 'sqlite':
            # no parentheses around compound operands in SQLite; compounds are
            # left-associative, so a compound right operand becomes a derived table
            if t[2][0] == 'VUnionAll':
                right = 'SELECT * FROM (%s)' % right
            return '%s %s %s' % (left, op, right)
        return '(%s) %s (%s)' % (left, op, right)

    def type_probe(self):
        """For a value query: (sql, number_of_keys) of its first arm (see type_probes)."""
        return self.type_probes()[0]

    def type_probes(self):
        """For a value query: one (sql, number_of_keys) per arm.  The query returns no
        rows; its columns are the grouping keys followed by every row-level expression
        used in the select items, so a caller can inspect their types."""
        probes = [self._type_probe_arm(v) for v in self._value_arms(parse_sexp(self.term))]
        lin = getattr(self, 'lineage', None)          # the derived table whose mutants are used
        return probes + (lin.inner.type_probes() if lin is not None else [])

    def _type_probe_arm(self, v):
        keys, items, _, source = self._v_parts(v)
        atoms = []

        def collect(t):
            if isinstance(t, list):
                if t and t[0] == 'EAtom':
                    atoms.append(t)
                else:
                    for x in t[1:]:
                        collect(x)
        for item in items:          # a list of items, not a tagged node
            collect(item)
        where = None
        if source[0] == 'Where':
            where, source = self._p_sql(source[1]), source[2]
        cols = [self._e_sql(k) for k in keys] + [self._e_sql(a) for a in atoms]
        # also the plain columns inside those expressions: `c % 2` is DOUBLE even
        # when c is a single-precision FLOAT
        seen = set()
        for atom in atoms:
            try:
                tree_ = sqlglot.parse_one(self.exprs[int(atom[1])], read=self.dialect)
            except Exception:
                continue
            for column in tree_.find_all(exp.Column):
                text = self._text(column)
                if text not in seen:
                    seen.add(text)
                    cols.append(text)
        if not cols:
            return None, 0
        sql = 'SELECT %s FROM %s' % (', '.join(cols), self._from_sql(source))
        return sql + (' WHERE ' + where if where else '') + ' LIMIT 0', len(keys)

    def numeric_probe(self):
        """SQLite only.  The value model computes with numbers, but an SQLite column can
        hold text in any row, and aggregates then follow SQLite's own rules (AVG converts
        text to a number, MAX orders text above every number).  This query counts the
        rows where an expression used in a select item is text or a blob; a value query
        is inside the model only when it returns 0.  For a UNION ALL, the counts of the
        arms are added."""
        probes = [p for p in (self._numeric_probe_arm(v) for v in self._value_arms(parse_sexp(self.term))) if p]
        lin = getattr(self, 'lineage', None)          # the derived table whose mutants are used
        if lin is not None:
            probes += [p for p in (lin.inner._numeric_probe_arm(v)
                                   for v in lin.inner._value_arms(parse_sexp(lin.inner.term))) if p]
        if not probes:
            return None
        return probes[0] if len(probes) == 1 else 'SELECT ' + ' + '.join('(%s)' % p for p in probes)

    def _numeric_probe_arm(self, v):
        keys, items, _, source = self._v_parts(v)
        atoms = []

        def collect(t):
            if isinstance(t, list):
                if t and t[0] == 'EAtom':
                    atoms.append(self._e_sql(t))
                else:
                    for x in t[1:]:
                        collect(x)
        for node in list(items) + list(keys):     # lists of items / keys, not tagged nodes
            collect(node)
        if not atoms:
            return None
        where = None
        if source[0] == 'Where':
            where, source = self._p_sql(source[1]), source[2]
        bad = ' OR '.join("typeof(%s) IN ('text', 'blob')" % a for a in atoms)
        cond = '(%s)' % bad if where is None else '(%s) AND (%s)' % (where, bad)
        return 'SELECT COUNT(*) FROM %s WHERE %s' % (self._from_sql(source), cond)

    def reprint(self):
        """SQL of the unmutated term: the query the mutants are compared with."""
        return self.to_sql(self.term)

    @staticmethod
    def _atom_text(text):
        """An atom is put back into a context it was not written in (a mutant may
        multiply it, compare it, ...), so anything that is not a plain name or
        number is parenthesised."""
        plain = text.replace('.', '').replace('_', '').replace('`', '')
        return text if plain.isalnum() else '(%s)' % text

    def _e_sql(self, e):
        tag = e[0]
        if tag == 'EAtom':
            return self._atom_text(self.exprs[int(e[1])])
        if tag == 'Int':
            return e[1]
        if tag == 'Null':
            return 'NULL'
        if tag in ('Add', 'Mul'):
            return '(%s %s %s)' % (self._e_sql(e[1]), '+' if tag == 'Add' else '*', self._e_sql(e[2]))
        raise Unsupported('expression %s' % tag)

    def _p_sql(self, p):
        if p == 'True':
            return '1 = 1'
        if p == 'False':
            return '1 = 0'
        tag = p[0]
        if tag == 'Cmp':
            return '%s %s %s' % (self._e_sql(p[2]), CMP_SQL[p[1]], self._e_sql(p[3]))
        if tag == 'IsNull':
            return '%s IS NULL' % self._e_sql(p[1])
        if tag == 'Not':
            return 'NOT (%s)' % self._p_sql(p[1])
        if tag in ('And', 'Or'):
            return '(%s) %s (%s)' % (self._p_sql(p[1]), tag.upper(), self._p_sql(p[2]))
        if tag == 'Exists':
            return 'EXISTS (%s)' % self._q_sql(p[1])
        if tag == 'In':
            return '%s IN (%s)' % (self._e_sql(p[1]), self._q_sql(p[2]))
        if tag == 'InT':
            return '(%s) IN (%s)' % (', '.join(self._e_sql(e) for e in p[1]), self._q_sql(p[2]))
        if tag == 'Atom':
            return '(%s)' % self.preds[int(p[1])]
        if tag in ('Like', 'Regex'):
            pat = bytes.fromhex(p[2]).decode() if len(p) > 2 else ''
            return '%s %s %s' % (self._e_sql(p[1]), 'LIKE' if tag == 'Like' else 'REGEXP', _quote(pat))
        raise Unsupported('predicate %s' % tag)

    def _single_table(self, f):
        """The only table atom below f, or None."""
        found = []

        def walk(t):
            if isinstance(t, list):
                if t and t[0] in ('T', 'Named'):
                    found.append((t[0], int(t[1])))
                    return
                elif t and t[0] in ('Exists', 'In', 'InT'):     # tables of subqueries do not count
                    return
                else:
                    for x in t[1:]:
                        walk(x)
        walk(f)
        return found[0] if len(found) == 1 else None

    def _from_sql(self, f, nested=False):
        tag = f[0]
        if tag == 'T':
            return self.tables[int(f[1])]
        if tag == 'Named':
            return '(%s) AS %s' % (self._q_sql(f[2]), self.named[int(f[1])])
        if tag in ('Inner', 'Left'):
            on, left, right = (f[1], f[2], f[3]) if tag == 'Inner' else (f[2], f[3], f[4])
            if tag == 'Inner' and on == 'True':
                # CROSS JOIN, not INNER JOIN ... ON 1 = 1: the same rows, and in SQLite it also
                # keeps the join order that the query as written asks for
                text = '%s CROSS JOIN %s' % (self._from_sql(left), self._from_sql(right, nested=True))
            else:
                text = '%s %s JOIN %s ON %s' % (self._from_sql(left), 'INNER' if tag == 'Inner' else 'LEFT',
                                               self._from_sql(right, nested=True), self._p_sql(on))
            return '(%s)' % text if nested else text
        if tag in ('Distinct', 'Where'):
            # DISTINCT / WHERE over one table can be printed as a derived table that
            # keeps the table's alias, so qualified references outside stay valid
            idx = self._single_table(f)
            distinct, where, inner = False, None, f
            if inner[0] == 'Distinct':
                distinct, inner = True, inner[1]
            if inner[0] == 'Where':
                where, inner = self._p_sql(inner[1]), inner[2]
            if idx is not None and inner[0] in ('T', 'Named') and (inner[0], int(inner[1])) == idx:
                alias = self.aliases[idx[1]] if idx[0] == 'T' else self.named[idx[1]]
                sql = 'SELECT %s* FROM %s' % ('DISTINCT ' if distinct else '', self._from_sql(inner))
                if where:
                    sql += ' WHERE ' + where
                return '(%s) AS %s' % (sql, alias)
        if tag in SET_SQL and self.dialect != 'sqlite':
            # a set operation whose arms all read one table (`t WHERE c1 UNION ALL t WHERE
            # c2`): a derived table that keeps the table's alias, as above
            alias = self._one_table_alias(f)
            if alias is not None:
                return '(%s) AS %s' % (self._one_table_arms(f), alias)
        raise Unsupported('%s in FROM position' % tag)

    def _one_table_alias(self, f):
        """The alias of the table T i when every arm of the set operations of f is T i
        itself, or DISTINCT and WHERE over it; None otherwise."""
        tables = set()

        def arm(x):
            if x[0] in SET_SQL:
                return arm(x[1]) and arm(x[2])
            if x[0] == 'Distinct':
                x = x[1]
            if x[0] == 'Where':
                x = x[2]
            if x[0] != 'T':
                return False
            tables.add(int(x[1]))
            return True
        return self.aliases[next(iter(tables))] if arm(f) and len(tables) == 1 else None

    def _one_table_arms(self, f):
        if f[0] in SET_SQL:
            return '(%s) %s (%s)' % (self._one_table_arms(f[1]), SET_SQL[f[0]], self._one_table_arms(f[2]))
        distinct, where = False, None
        if f[0] == 'Distinct':
            distinct, f = True, f[1]
        if f[0] == 'Where':
            where, f = self._p_sql(f[1]), f[2]
        sql = 'SELECT %s* FROM %s' % ('DISTINCT ' if distinct else '', self._from_sql(f))
        return sql + (' WHERE ' + where if where else '')

    def _q_sql(self, q):
        tag = q[0]
        if tag == 'QAtom':
            text = self.qatoms[int(q[1])]
            return 'SELECT * FROM (%s) AS qa%s' % (text, q[1]) if self.dialect == 'sqlite' else text
        if tag == 'Named':
            return self._q_sql(q[2])
        if tag in SET_SQL:
            if self.dialect == 'sqlite' and tag in ('IntersectAll', 'ExceptAll'):
                raise Unsupported('SQLite has no %s' % SET_SQL[tag])
            if self.dialect == 'sqlite':
                # no parentheses around compound operands in SQLite; compounds are
                # left-associative, so a compound right operand becomes a derived table
                right = self._q_sql(q[2])
                if q[2][0] in SET_SQL:
                    right = 'SELECT * FROM (%s)' % right
                return '%s %s %s' % (self._q_sql(q[1]), SET_SQL[tag], right)
            return '(%s) %s (%s)' % (self._q_sql(q[1]), SET_SQL[tag], self._q_sql(q[2]))
        distinct, items, where = False, '*', None
        if q[0] == 'Distinct':
            distinct, q = True, q[1]
            if q[0] in SET_SQL or q[0] in ('QAtom', 'Distinct'):
                # DISTINCT around a query that is not a single SELECT
                self.derived = getattr(self, 'derived', 0) + 1
                return 'SELECT DISTINCT * FROM (%s) AS vs_d%d' % (self._q_sql(q), self.derived)
        if q[0] == 'Proj':
            # select-list atoms keep their exact text (it may end in "AS alias")
            items, q = ', '.join(self.exprs[int(e[1])] if e[0] == 'EAtom' else self._e_sql(e)
                                 for e in q[1]), q[2]
            if q[0] == 'Distinct':
                # DISTINCT around a join: GROUP BY every column of the joined tables keeps
                # one row per distinct joined row, which is what the projection then reads
                inner, pred = q[1], None
                if inner[0] == 'Where':
                    pred, inner = inner[1], inner[2]
                cols = self._join_columns(inner) if inner[0] in ('Inner', 'Left') else None
                if cols:
                    sql = 'SELECT %s%s FROM %s' % ('DISTINCT ' if distinct else '', items, self._from_sql(inner))
                    if pred is not None:
                        sql += ' WHERE ' + self._p_sql(pred)
                    return sql + ' GROUP BY ' + ', '.join(cols)
        if q[0] == 'Where':
            where, q = self._p_sql(q[1]), q[2]
        sql = 'SELECT %s%s FROM %s' % ('DISTINCT ' if distinct else '', items, self._from_sql(q))
        return sql + (' WHERE ' + where if where else '')

    def _a_sql(self, a):
        tag = a[0]
        if tag == 'ACol':
            return self._e_sql(a[1])
        if tag == 'AConst':
            return a[1]
        names = {'ACount': 'COUNT(%s)', 'ACountD': 'COUNT(DISTINCT %s)', 'ASum': 'SUM(%s)',
                 'AMin': 'MIN(%s)', 'AMax': 'MAX(%s)', 'AAvg': 'AVG(%s)',
                 'AVar': 'VAR_SAMP(%s)', 'AStd': 'STDDEV_SAMP(%s)'}
        if tag in names:
            return names[tag] % self._e_sql(a[1])
        if tag in ('AAdd', 'AMul'):
            return '(%s %s %s)' % (self._a_sql(a[1]), '+' if tag == 'AAdd' else '*', self._a_sql(a[2]))
        if tag == 'AMono':
            name = [n for n, i in self.mono_ids.items() if i == int(a[1])][0]
            return '%s(%s)' % (name, self._a_sql(a[2]))
        if tag == 'AOpaque':
            return self._atom_text(self.opaque_items[int(a[1])])
        raise Unsupported('select item %s' % tag)

    @staticmethod
    def _v_parts(v):
        """(keys, items, having, source) of a value query term."""
        if v[0] == 'VGroup':
            return v[1], v[2], v[3], v[4]
        if v[0] == 'VGlobal':
            return [], v[1], v[2], v[3]
        return [], v[1], 'True', v[2]

    def _v_sql(self, v):
        keys, items, having, source = self._v_parts(v)
        where = None
        if source[0] == 'Where':
            where, source = self._p_sql(source[1]), source[2]
        aliases = self.item_alias_arms[min(getattr(self, '_arm', 0), len(self.item_alias_arms) - 1)]
        self._arm = getattr(self, '_arm', 0) + 1
        cols = ', '.join('%s AS %s' % (self._a_sql(a), aliases[j]) for j, a in enumerate(items))
        sql = 'SELECT %s FROM %s' % (cols, self._from_sql(source))
        if where:
            sql += ' WHERE ' + where
        if keys:
            sql += ' GROUP BY ' + ', '.join(self._e_sql(k) for k in keys)
        if having != 'True' and not keys and self.dialect == 'sqlite' and getattr(self, 'wrap_global_having', False):
            # SQLite before 3.39 rejects HAVING without GROUP BY.  The aggregate query (one
            # row) keeps that row exactly when the predicate is TRUE, which is a WHERE on
            # the predicate's value computed as an extra column (_validated: the standard
            # form is the one checked by the round trip; test_bridge runs both forms)
            outer = ', '.join('vs_g.%s' % aliases[j] for j in range(len(items)))
            return 'SELECT %s FROM (%s, (%s) AS vs_h%s) AS vs_g WHERE vs_g.vs_h' % (
                outer, sql[:len('SELECT ') + len(cols)], self._p_sql(having), sql[len('SELECT ') + len(cols):])
        if having != 'True':
            sql += ' HAVING ' + self._p_sql(having)
        return sql
