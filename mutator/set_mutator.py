import sqlglot
import random
import copy
import os
import string

class SetMutator:
    """Class for performing mutation operations on SQL AST"""
    def __init__(self, ast, db_type='UNKNOWN'):
        self.ast = ast
        self.db_type = db_type.upper()  # Store database dialect
        self.mutable_nodes = []  # Store mutable nodes
        self.mutated = False  # Flag indicating whether mutation has been performed
        self.temp_original_nodes = {}  # Temporarily store original node information

    # ------------------------------------------------------------------
    # Polarity analysis
    #
    # flag == 1    : the node sits in a monotone (positive) context, i.e. growing
    #                the node's result can only grow the result of the whole query
    # flag == 0    : antitone (negative) context (under NOT, right side of EXCEPT)
    # flag is None : the effect on the whole query is unknown (scalar subquery,
    #                CASE, function argument, LIMIT, aggregate, window, ALL, ...).
    #                Nothing below such a node may be mutated, because no
    #                inclusion relation can be asserted for the outer query.
    # ------------------------------------------------------------------
    _TABLE_POSITION_PARENTS = ('From', 'Join', 'In', 'Exists', 'Union', 'Intersect',
                               'Except', 'CTE', 'Subquery', 'Lateral')
    _COMPARISONS = ('GT', 'LT', 'GTE', 'LTE', 'EQ')

    @staticmethod
    def _cls(node):
        return node.__class__.__name__

    def _own_scope_nodes(self, select_node, arg_names):
        """Yield nodes of the given clauses of a SELECT without entering nested queries."""
        stack = []
        for arg_name in arg_names:
            value = select_node.args.get(arg_name)
            if isinstance(value, list):
                stack.extend(v for v in value if hasattr(v, 'args'))
            elif hasattr(value, 'args'):
                stack.append(value)
        while stack:
            current = stack.pop()
            yield current
            if self._cls(current) in ('Select', 'Subquery', 'Union', 'Intersect', 'Except'):
                continue
            for value in current.args.values():
                if isinstance(value, list):
                    stack.extend(v for v in value if hasattr(v, 'args'))
                elif hasattr(value, 'args'):
                    stack.append(value)

    def _select_is_row_preserving(self, select_node):
        """A SELECT can only be reasoned about with result-set inclusion if every
        output row stems from one input row: no LIMIT/OFFSET, no aggregate and no
        window function in its own scope."""
        for key in ('limit', 'offset', 'group', 'qualify'):
            if select_node.args.get(key):
                return False
        for inner in self._own_scope_nodes(select_node, ('expressions', 'having', 'order')):
            if isinstance(inner, (sqlglot.expressions.AggFunc, sqlglot.expressions.Window)):
                return False
            if self._cls(inner) == 'Anonymous' and str(inner.name).upper() in (
                    'STD', 'STDDEV', 'VAR', 'VARIANCE', 'BIT_AND', 'BIT_OR', 'BIT_XOR',
                    'AVG', 'COUNT', 'MAX', 'MIN', 'SUM', 'GROUP_CONCAT', 'VAR_SAMP',
                    'VAR_POP', 'STDDEV_SAMP', 'STDDEV_POP', 'JSON_ARRAYAGG', 'JSON_OBJECTAGG'):
                return False
        return True

    def findnode(self, ast):
        """Identify all mutable nodes in the AST"""
        if not ast:
            return

        self.mutable_nodes = []
        # CTE name -> set of polarities under which the CTE is referenced
        self._cte_ref_flags = {}
        cte_nodes = []
        with_node = ast.args.get('with_') or ast.args.get('with') if hasattr(ast, 'args') else None
        if with_node is not None:
            cte_nodes = list(with_node.expressions)
        self._cte_names = {cte.alias.lower() for cte in cte_nodes if cte.alias}

        # Main query first (the WITH clause is skipped), root flag is 1 (positive)
        self._find_mutable_nodes(ast, parent_flag=1)
        # A CTE body inherits the polarity of its references. It is processed only
        # if every reference agrees on one known polarity; CTEs are visited from
        # last to first because a later CTE may reference an earlier one.
        for cte in reversed(cte_nodes):
            flags = self._cte_ref_flags.get((cte.alias or '').lower(), set())
            if len(flags) == 1 and None not in flags:
                self._find_mutable_nodes(cte.this, parent_flag=next(iter(flags)))
        return self.mutable_nodes

    def _find_mutable_nodes(self, node, parent_flag=1, is_in_on_condition=False, in_predicate=False):
        """Recursively find mutable nodes while propagating the polarity flag"""
        if node is None or not hasattr(node, 'args'):
            return
        name = self._cls(node)

        # References to CTEs are recorded even in unknown contexts
        if name == 'Table':
            table_name = str(node.name).lower()
            if table_name in getattr(self, '_cte_names', ()):
                self._cte_ref_flags.setdefault(table_name, set()).add(parent_flag)
            return

        if parent_flag is None:
            # Unknown context: nothing below may be mutated, but CTE references
            # still have to be recorded so that the CTE body is not mutated either.
            for value in node.args.values():
                for child in (value if isinstance(value, list) else [value]):
                    if hasattr(child, 'args'):
                        self._find_mutable_nodes(child, None)
            return

        current_flag = parent_flag
        if name == 'Not':
            current_flag = parent_flag ^ 1

        def visit(child, flag, on=False, pred=False):
            for item in (child if isinstance(child, (list, tuple)) else [child]):
                if hasattr(item, 'args'):
                    self._find_mutable_nodes(item, flag, on, pred)

        def visit_rest(skip):
            for arg_name, value in node.args.items():
                if arg_name not in skip:
                    visit(value, None)

        if name == 'Select':
            if not self._select_is_row_preserving(node):
                visit_rest(())
                return
            self._process_select(node, current_flag)
            visit(node.args.get('from_') or node.args.get('from'), current_flag)
            visit(node.args.get('joins'), current_flag)
            visit(node.args.get('where'), current_flag)
            visit(node.args.get('having'), current_flag)
            # select list, ORDER BY, ... : scalar positions, polarity unknown
            visit_rest(('from_', 'from', 'joins', 'where', 'having', 'with_', 'with'))
        elif name in ('Where', 'Having'):
            if name == 'Where':
                self._process_where(node, current_flag)
            else:
                self._process_having(node, current_flag)
            visit(node.args.get('this'), current_flag, False, True)
        elif name == 'From':
            visit(node.args.get('this'), current_flag)
            visit_rest(('this',))
        elif name == 'Join':
            side = node.args.get('side')
            kind = node.args.get('kind')
            has_condition = bool(node.args.get('on') or node.args.get('using'))
            plain_inner = not side and (not kind or str(kind).upper() in ('INNER', 'CROSS'))
            if plain_inner:
                # INNER JOIN -> LEFT JOIN needs a join condition to stay valid SQL
                if has_condition and kind and str(kind).upper() == 'INNER':
                    self._process_inner_join(node, current_flag)
                if node.args.get('on'):
                    self._process_join(node, current_flag)
                visit(node.args.get('this'), current_flag)
                visit(node.args.get('on'), current_flag, True, True)
                visit_rest(('this', 'on'))
            else:
                # Outer joins are not monotone in their ON condition / inner side
                visit_rest(())
        elif name == 'Subquery':
            parent = node.parent
            if parent is None or self._cls(parent) in self._TABLE_POSITION_PARENTS:
                visit(node.args.get('this'), current_flag)
                visit_rest(('this',))
            else:
                # scalar subquery: its value feeds an arbitrary expression
                visit_rest(())
        elif name in ('And', 'Or', 'Paren', 'Not'):
            if name == 'And' and in_predicate:
                self._process_logical_and(node, current_flag)
            visit(node.args.get('this'), current_flag, is_in_on_condition, in_predicate)
            visit(node.args.get('expression'), current_flag, is_in_on_condition, in_predicate)
        elif name == 'In':
            if in_predicate and node.args.get('query') is not None and not is_in_on_condition:
                visit(node.args.get('query'), current_flag)
                visit_rest(('query',))
            else:
                visit_rest(())
        elif name == 'Exists':
            if in_predicate:
                visit(node.args.get('this'), current_flag)
                visit_rest(('this',))
            else:
                visit_rest(())
        elif name in ('Union', 'Intersect', 'Except'):
            if node.args.get('limit') or node.args.get('offset'):
                visit_rest(())
                return
            if name == 'Intersect':
                self._process_intersect(node, current_flag)
            elif name == 'Except':
                self._process_except(node, current_flag)
            visit(node.args.get('this'), current_flag)
            # The right operand of EXCEPT is an antitone position
            visit(node.args.get('expression'), current_flag ^ 1 if name == 'Except' else current_flag)
            visit_rest(('this', 'expression', 'with_', 'with'))
        elif name in ('CTE', 'With'):
            # handled by findnode once the polarity of all references is known
            return
        elif name == 'Like' and in_predicate:
            # sqlglot keeps NOT LIKE as Like(negate=True) instead of Not(Like)
            self._process_like(node, current_flag ^ 1 if node.args.get('negate') else current_flag)
            visit_rest(())
        elif name == 'RegexpLike' and in_predicate:
            self._process_regexp(node, current_flag)
            visit_rest(())
        elif name in self._COMPARISONS and in_predicate:
            self._process_comparison(node, current_flag)
            visit_rest(())
        else:
            # Any other expression (function call, CASE, arithmetic, ALL/ANY, ...)
            visit_rest(())


    def _process_select(self, node, flag):
        """Process SELECT node"""
        if hasattr(node, 'args') and 'distinct' in node.args:
            # Record DISTINCT mutation point
            distinct_value = node.args['distinct']
            if distinct_value is not None:
                node_info = {
                    'node_id': id(node),
                    'node': node,
                    'mutation_type': 'FixMDistinct',
                    'attr_name': 'args',
                    'sub_attr': 'distinct',
                    'direction': 0,  # Default direction, indicates result reduction
                    'flag': flag  # Use inherited flag value
                }
                self.mutable_nodes.append(node_info)

    def _process_where(self, node, flag):
        """Process WHERE node"""
        node_info = {
            'node_id': id(node),
            'node': node,
            'mutation_type': 'FixMWhere',
            'attr_name': 'this',
            'direction': 1,  # Default direction, indicates result expansion
            'flag': flag  # Use inherited flag value
        }
        self.mutable_nodes.append(node_info)

    def _process_having(self, node, flag):
        """Process HAVING node"""
        node_info = {
            'node_id': id(node),
            'node': node,
            'mutation_type': 'FixMHaving',
            'attr_name': 'this',
            'direction': 1,  # Default direction, indicates result expansion
            'flag': flag  # Use inherited flag value
        }
        self.mutable_nodes.append(node_info)

    def _process_join(self, node, flag):
        """Process JOIN node"""
        if hasattr(node, 'args') and 'on' in node.args:
            node_info = {
                'node_id': id(node),
                'node': node,
                'mutation_type': 'FixMOn',
                'attr_name': 'args',
                'sub_attr': 'on',
                'direction': 1,  # Default direction, indicates result expansion
                'flag': flag  # Use inherited flag value
            }
            self.mutable_nodes.append(node_info)

    def _process_like(self, node, flag):
        """Process LIKE node"""
        # sqlglot stores the pattern of LIKE in the 'expression' argument
        pattern = node.args.get('expression') if hasattr(node, 'args') else None
        if isinstance(pattern, sqlglot.expressions.Literal) and pattern.is_string and not node.args.get('escape'):
            node_info = {
                'node_id': id(node),
                'node': node,
                'mutation_type': 'RdMLike',
                'attr_name': 'args',
                'sub_attr': 'expression',
                'direction': 1,  # Default direction, indicates result expansion
                'flag': flag  # Use inherited flag value
            }
            self.mutable_nodes.append(node_info)

    def _process_regexp(self, node, flag):
        """Process REGEXP node"""
        # sqlglot stores the pattern of REGEXP (RegexpLike) in the 'expression' argument
        pattern = node.args.get('expression') if hasattr(node, 'args') else None
        if isinstance(pattern, sqlglot.expressions.Literal) and pattern.is_string:
            node_info = {
                'node_id': id(node),
                'node': node,
                'mutation_type': 'RdMRegExp',
                'attr_name': 'args',
                'sub_attr': 'expression',
                'direction': 1,  # Default direction, indicates result expansion
                'flag': flag  # Use inherited flag value
            }
            self.mutable_nodes.append(node_info)

    def _process_comparison(self, node, flag):
        """Process comparison operator node"""
        # Determine current operator based on node type
        # Only the strict comparisons and equality have a weaker counterpart:
        # a < b -> a <= b, a > b -> a >= b, a = b -> a >= b
        op_map = {
            'GT': 'gt',
            'LT': 'lt',
            'EQ': 'eq'
        }
        node_class = node.__class__.__name__
        if node_class in op_map:
            node_info = {
                'node_id': id(node),
                'node': node,
                'mutation_type': 'FixMCmpOp',
                'attr_name': 'op',
                'direction': 1,  # Default direction, indicates result expansion
                'flag': flag  # Use inherited flag value
            }
            self.mutable_nodes.append(node_info)

    def _process_union(self, node):
        """Process UNION node"""
        if hasattr(node, 'args') and 'distinct' in node.args:
            node_info = {
                'node_id': id(node),
                'node': node,
                'mutation_type': 'FixMUnionAll',
                'attr_name': 'args',
                'sub_attr': 'distinct',
                'direction': 1,  # Default direction, indicates result expansion
                'flag': 1  # Flag bit, 1 means positive
            }
            self.mutable_nodes.append(node_info)
    
    def _process_logical_and(self, node, flag):
        """Process logical AND expression node"""
        # SQLGlot's AND expression uses this and expression attributes to store left and right operands
        # When AND connects two conditions, there are two sub-expressions that can be mutated
        if hasattr(node, 'this') and hasattr(node, 'expression'):
            # Check if there are two valid sub-expressions
            if node.this is not None and node.expression is not None:
                node_info = {
                    'node_id': id(node),
                    'node': node,
                    'mutation_type': 'FixMLogicalAnd',
                    'attr_name': 'expression',  # Modify the expression attribute to remove the second condition
                    'direction': 1,  # Expand result: removing part of the condition will get more results
                    'flag': flag  # Use inherited flag value
                }
                self.mutable_nodes.append(node_info)
    
    def _process_inner_join(self, node, flag):
        """Process INNER JOIN node"""
        if hasattr(node, 'args') and 'kind' in node.args:
            current_kind = node.args['kind']
            if current_kind == 'INNER':
                node_info = {
                    'node_id': id(node),
                    'node': node,
                    'mutation_type': 'FixMInnerJoin',
                    'attr_name': 'args',
                    'sub_attr': 'kind',
                    'direction': 1,  # Expand result: INNER JOIN -> LEFT JOIN will get more results
                    'flag': flag  # Use inherited flag value
                }
                self.mutable_nodes.append(node_info)
    
    def _process_intersect(self, node, flag):
        """Process INTERSECT node"""
        if hasattr(node, 'args'):
            node_info = {
                'node_id': id(node),
                'node': node,
                'mutation_type': 'FixMIntersect',
                'attr_name': None,  # Directly replace the entire node
                'direction': 1,  # Expand result: INTERSECT -> UNION will get more results
                'flag': flag  # Use inherited flag value
            }
            self.mutable_nodes.append(node_info)
    
    def _process_except(self, node, flag):
        """Process EXCEPT node"""
        if hasattr(node, 'args'):
            node_info = {
                'node_id': id(node),
                'node': node,
                'mutation_type': 'FixMExcept',
                'attr_name': None,  # Directly replace the entire node
                'direction': 1,  # Expand result: A EXCEPT B -> A will get more results
                'flag': flag  # Use inherited flag value
            }
            self.mutable_nodes.append(node_info)
            
    def _process_node_recursive(self, node_value, flag, is_in_on_condition=False):
        """Recursively process node values, support various data types, add special handling for IN nodes in ON conditions"""
        if node_value is None:
            return
        
        # If it's a node object (has args attribute), process recursively
        if hasattr(node_value, 'args'):
            self._find_mutable_nodes(node_value, flag, is_in_on_condition)
        # If it's a list or tuple, recursively process each element
        elif isinstance(node_value, (list, tuple)):
            for item in node_value:
                self._process_node_recursive(item, flag, is_in_on_condition)

    def mutate(self, executor):
        """Perform mutation operations on the AST"""
        if self.mutated:
            return self.ast

        # Find all mutable nodes
        self.findnode(self.ast)

        # If there are no mutable nodes, return directly
        if not self.mutable_nodes:
            return self.ast

        # Save a deep copy of the original AST for result comparison
        initial_ast = copy.deepcopy(self.ast)
        sql = str(initial_ast)

        # Execute the original SQL query to get initial results
        result_data = executor.execute_query(sql)
        if result_data is None:
            # The (preprocessed) original query failed: an error is not an empty
            # result, so no relation can be checked.
            return self.ast
        # Unpack result data
        if isinstance(result_data, tuple) and len(result_data) == 2:
            result = result_data[0]  # Result set
            original_column_names = result_data[1]  # Column name list
        else:
            result = result_data
            original_column_names = []

        # Try to mutate each mutable node
        all_mutable_nodes = self.mutable_nodes.copy()
        for item in all_mutable_nodes:
            # Start each mutation from the original AST
            self.ast = copy.deepcopy(initial_ast)
            temp_ast = self.ast
            self.findnode(temp_ast)
            current_mutable_nodes = self.mutable_nodes

            # findnode() is deterministic, so the node at the same position in
            # the fresh copy is the counterpart of the node in the original AST
            original_pos = all_mutable_nodes.index(item)
            if original_pos >= len(current_mutable_nodes):
                continue
            item = current_mutable_nodes[original_pos]

            # Since we've already ensured item has a value, no need to check if item is None here
            # Execute mutation
            self.ast = self._mutate_node(item)

            # Calculate final_direction before executing SQL query
            final_direction=(item['direction']^item['flag'])^1

            mutated_sql = self.ast.sql()
            #transformed_sql = sqlglot.transpile(mutated_sql, dialect='mysql')[0]
            if mutated_sql == sql:
                # The mutation did not change the query
                continue
            transformed_result_data=executor.execute_query(mutated_sql)
            if transformed_result_data is None:
                # The mutated query failed to execute: skip instead of treating
                # the error as an empty result set
                continue
            # Unpack mutated result data
            if isinstance(transformed_result_data, tuple) and len(transformed_result_data) == 2:
                transformed_result = transformed_result_data[0]  # Result set
                transformed_column_names = transformed_result_data[1]  # Column name list
            else:
                transformed_result = transformed_result_data
                transformed_column_names = []
            # No need to recalculate final_direction as item['direction'] and item['flag'] haven't changed

            # Compare result set sizes
            original_result_size = len(result) if result else 0
            mutated_result_size = len(transformed_result) if transformed_result else 0

            # Convert result sets to lists (preserving duplicate elements and original order) for membership comparison
            # Now results are lists of tuples, process these tuples directly
            original_result_list = []
            if result:
                # Use tuples directly as comparison units, preserving original order
                original_result_list = self._normalize_rows(result)

            mutated_result_list = []
            if transformed_result:
                # Use tuples directly as comparison units, preserving original order
                mutated_result_list = self._normalize_rows(transformed_result)

            # Optimized subset check function that directly compares list elements to check sub/superset relationships
            def is_list_subset(small_list, large_list, small_columns, large_columns):
                """Check if small_list is a subset of large_list, comparing each element exactly while considering column names"""
                # First check length relationship
                if len(small_list) > len(large_list):
                    return False

                # Check if column names are consistent
                if small_columns and large_columns and small_columns != large_columns:
                    return False

                temp_large = large_list.copy()

                # Try to match each element in the small list
                for item in small_list:
                    if item in temp_large:
                        # Remove matched element
                        temp_large.remove(item)
                    else:
                        return False

                # All elements found matches
                return True
            # Check result set relationships
            is_valid = False
            if final_direction == 1:
                 # Expand results: Mutated results should be greater than or equal to original results, and original result set is a subset of mutated result set (considering duplicates and column names)
                size_valid = (original_result_size == 0) or (mutated_result_size >= original_result_size)
                subset_valid = True if original_result_size == 0 else is_list_subset(original_result_list, mutated_result_list, original_column_names, transformed_column_names)
                is_valid = size_valid and subset_valid
            else:
                # Shrink results: Original results should be greater than or equal to mutated results, and mutated result set is a subset of original result set (considering duplicates and column names)
                size_valid = (mutated_result_size == 0) or (original_result_size >= mutated_result_size)
                subset_valid = True if mutated_result_size == 0 else is_list_subset(mutated_result_list, original_result_list, transformed_column_names, original_column_names)
                is_valid = size_valid and subset_valid

            # If not as expected, record SQL pairs
            if not is_valid:
                # Create invalid_mutation folder if it doesn't exist
                import os
                
                # Get current database dialect
                db_type = self.db_type
                
                # Create log directory categorized by dialect
                log_dir = os.path.join('invalid_mutation', db_type)
                if not os.path.exists(log_dir):
                    os.makedirs(log_dir)

                # Get current class name as part of the log filename
                class_name = self.__class__.__name__
                log_filename = os.path.join(log_dir, f"{class_name}_{db_type}_invalid_mutations.log")

                # Get index usage information for the original query
                def _get_query_index_info(self, sql_query):
                    """Execute EXPLAIN SQL to get query index usage information
                    
                    Parameters:
                        sql_query: The SQL query to analyze
                    
                    Returns:
                        str: Text description of index usage
                    """
                    try:
                        # Directly import and use the SeedQueryGenerator class from get_seedQuery
                        from get_seedQuery import SeedQueryGenerator
                        
                        # Create SeedQueryGenerator instance
                        seed_generator = SeedQueryGenerator()
                        
                        # Use SeedQueryGenerator's connect_db method to get database connection
                        connection = seed_generator.connect_db()
                        
                        if not connection:
                            return "Failed to establish database connection"
                        
                        # Execute EXPLAIN query
                        explain_sql = f"EXPLAIN {sql_query}"
                        cursor = connection.cursor()
                        cursor.execute(explain_sql)
                        
                        # Get results
                        explain_results = cursor.fetchall()
                        
                        # Close cursor and connection
                        cursor.close()
                        connection.close()
                        
                        # Format results into readable text
                        index_info = []
                        
                        # Try to get column names
                        try:
                            column_names = [desc[0] for desc in cursor.description]
                            for row in explain_results:
                                row_info = []
                                for i, value in enumerate(row):
                                    if i < len(column_names):
                                        row_info.append(f"{column_names[i]}: {value}")
                                    else:
                                        row_info.append(str(value))
                                index_info.append(", ".join(row_info))
                        except:
                            # If column names cannot be obtained, format row data directly
                            for row in explain_results:
                                index_info.append(str(row))
                        
                        return "\n".join(index_info)
                        
                    except Exception as e:
                        return f"EXPLAIN execution failed: {str(e)}"
                
                try:
                    index_info = _get_query_index_info(self, sql)
                except Exception as e:
                    index_info = f"Failed to get index information: {str(e)}"
                
                # Write to log
                with open(log_filename, 'a', encoding='utf-8') as f:
                    f.write(f"=== Unexpected Mutation ===\n")
                    f.write(f"Original SQL: {sql}\n")
                    f.write(f"Mutated SQL: {mutated_sql}\n")
                    f.write(f"Original query index usage:\n{index_info}\n")
                    f.write(f"Original result set size: {original_result_size}\n")
                    f.write(f"Mutated result set size: {mutated_result_size}\n")
                    f.write(f"Original column names: {original_column_names}\n")
                    f.write(f"Mutated column names: {transformed_column_names}\n")
                    f.write(f"final_direction: {final_direction}\n")
                    f.write(f"direction: {item['direction']}\n")
                    f.write(f"flag: {item['flag']}\n")
                    f.write(f"Original result set: {original_result_list}\n")
                    f.write(f"Mutated result set: {mutated_result_list}\n")
                    f.write(f"Mutation type: {item['mutation_type']}\n")
                    
                    if final_direction == 1:
                        f.write(f"Failure reason: Original result set is not a subset of mutated result set or mutated result set size is smaller than original result set\n")
                    else:
                        f.write(f"Failure reason: Mutated result set is not a subset of original result set or original result set size is smaller than mutated result set\n")
                    
                    f.write(f"Is original result set empty: {original_result_size == 0}\n")
                    f.write(f"Is mutated result set empty: {mutated_result_size == 0}\n\n")

            if final_direction==1:
                pass  # Additional logic for final_direction==1 can be added here
        self.mutated = False
        return self.ast

    def _mutate_node(self, item):
        self.mutated =True
        """Perform mutation operation on a single node, temporarily store original information before mutation"""
        mutation_type = item['mutation_type']
        node = item['node']
        attr_name = item['attr_name']
        direction = item['direction']
        flag = item['flag']  # 1: positive, 0: negative
        node_id = item['node_id']
        # Temporarily store original node information
        if node_id not in self.temp_original_nodes:
            if attr_name and hasattr(node, attr_name) and not isinstance(getattr(node, attr_name), (sqlglot.expressions.Expression)):
                # For simple attributes, store attribute values
                self.temp_original_nodes[node_id] = {
                    'node': node,
                    'attr_name': attr_name,
                    'original_value': getattr(node, attr_name),
                    'is_replaced': False
                }

            else:
                # For complex expressions or attributes that cannot be set directly, store the entire node
                self.temp_original_nodes[node_id] = {
                    'node': node,
                    'attr_name': attr_name,
                    'original_value': node,
                    'is_replaced': True
                }

        # First calculate final_direction, which will be recalculated later for FixMDistinct type
        final_direction=(item['direction']^item['flag'])^1

        # Perform mutation operation
        if mutation_type == 'FixMDistinct':
            # Check if there is a sub_attr parameter (used to access specific keys in the args dictionary)
            sub_attr = item.get('sub_attr')
            if sub_attr and hasattr(node, 'args'):
                # Get current distinct status
                distinct_value = node.args.get(sub_attr)
                if distinct_value is None:
                    # Add DISTINCT: Mutated result set is deduplicated and should be a subset of the original result set
                    item['direction'] = 0
                    node.args[sub_attr] = 'Distinct'
                else:
                    # Remove DISTINCT: Original result set is deduplicated and should be a subset of the mutated result set
                    item['direction'] = 1
                    node.args[sub_attr] = None

            # Recalculate final_direction after setting item['direction']
            final_direction=(item['direction']^item['flag'])^1

        elif mutation_type == 'FixMCmpOp':
            # Weaken the comparison: every row satisfying the original predicate
            # also satisfies the mutated one (NULL operands stay NULL).
            weaker = {
                'GT': sqlglot.expressions.GTE,
                'LT': sqlglot.expressions.LTE,
                'EQ': sqlglot.expressions.GTE,
            }.get(node.__class__.__name__)
            if weaker is not None:
                new_node = weaker(this=node.this.copy(), expression=node.expression.copy())
                self._replace_node(node, new_node)
                item['direction'] = 1  # Expand result set

        elif mutation_type == 'FixMUnionAll':
            # Toggle between UNION and UNION ALL
            # In sqlglot, the Union node's args dictionary has a distinct key, True means UNION (deduplicated), False means UNION ALL (not deduplicated)

            # Check if there is a sub_attr parameter (used to access specific keys in the args dictionary)
            sub_attr = item.get('sub_attr')
            if sub_attr and hasattr(node, 'args') and sub_attr in node.args:
                current_distinct = node.args[sub_attr]
                operation_type = 'UNION' if current_distinct else 'UNION ALL'

                # Toggle the value of the distinct attribute to switch between UNION and UNION ALL
                if flag == 1 or True:  # Always allow switching, no longer restricted by flag
                    new_distinct = not current_distinct
                    node.args[sub_attr] = new_distinct
                    new_operation_type = 'UNION' if new_distinct else 'UNION ALL'

                    # Set direction based on switching direction to ensure correct result set size relationship
                    # UNION -> UNION ALL: Result set may grow (including duplicates)
                    # UNION ALL -> UNION: Result set may shrink (removing duplicates)
                    if current_distinct and not new_distinct:  # UNION -> UNION ALL
                        item['direction'] = 1  # Expand result
                    elif not current_distinct and new_distinct:  # UNION ALL -> UNION
                        item['direction'] = 0  # Shrink result
        elif mutation_type == 'FixMOn':
            # Modify JOIN's ON condition
            if hasattr(node, 'args') and 'on' in node.args and 'kind' in node.args:
                original_on = node.args['on']
                if direction == 1:
                    # Expand results: ON xxx -> ON 1=1
                    new_on = sqlglot.expressions.Paren(
                        this=sqlglot.expressions.EQ(
                            this=sqlglot.expressions.Literal(this='1', is_string=True),
                            expression=sqlglot.expressions.Literal(this='1', is_string=True)
                        )
                    )

                elif direction==0:
                    # Shrink results: ON xxx -> ON 1=0
                    new_on = sqlglot.expressions.Paren(
                        this=sqlglot.expressions.EQ(
                            this=sqlglot.expressions.Literal(this='1', is_string=True),
                            expression=sqlglot.expressions.Literal(this='0', is_string=True)
                        )
                    )


                try:
                    # Try to directly replace the ON node in args
                    node.args['on'] = new_on
                    # Force update the key attribute of the node (if exists)
                    if hasattr(node, 'key'):
                        node.key = f"JOIN_ON_1_{'=' if final_direction == 1 else '!='}_1"
                except Exception as e:
                    pass  # Failed to replace ON clause
            else:
                pass  # Node has no 'on' parameter
        elif mutation_type == 'FixMWhere':
            # Modify WHERE condition
            if direction == 1:
                new_where = sqlglot.expressions.Where(
                    this=sqlglot.expressions.EQ(
                        this=sqlglot.expressions.Literal(this='1', is_string=True),
                        expression=sqlglot.expressions.Literal(this='1', is_string=True)
                    )
                )
                node.replace(new_where)

            elif direction==0:
                new_where = sqlglot.expressions.Where(
                    this=sqlglot.expressions.EQ(
                        this=sqlglot.expressions.Literal(this='1', is_string=True),
                        expression=sqlglot.expressions.Literal(this='0', is_string=True)
                    )
                )
                node.replace(new_where)
        elif mutation_type == 'FixMHaving':
            # Modify HAVING condition
            if direction == 1:
                # Expand results: HAVING xxx -> HAVING 1=1
                from sqlglot.expressions import EQ
                new_having = sqlglot.expressions.Having(
                    this=EQ(
                        this=sqlglot.expressions.Literal(this='1', is_string=True),
                        expression=sqlglot.expressions.Literal(this='1', is_string=True)
                    )
                )
                node.replace(new_having)
            elif direction==0:
                # Shrink results: HAVING xxx -> HAVING 1=0
                from sqlglot.expressions import EQ
                new_having = sqlglot.expressions.Having(
                    this=EQ(
                        this=sqlglot.expressions.Literal(this='1', is_string=True),
                        expression=sqlglot.expressions.Literal(this='0', is_string=True)
                    )
                )
                node.replace(new_having)
        elif mutation_type == 'RdMLike':
            # Generalise the LIKE pattern: '_' -> '%', ordinary characters may
            # become wildcards. Escaped characters are kept untouched.
            pattern_node = node.args.get('expression')
            if pattern_node is not None:
                pattern_str = pattern_node.this
                new_pattern = []
                escaped = False
                for char in pattern_str:
                    if escaped:
                        new_pattern.append(char)
                        escaped = False
                    elif char == '\\':
                        new_pattern.append(char)
                        escaped = True
                    elif char == '_':
                        new_pattern.append('%')
                    elif random.random() < 0.3 and char.isalnum():
                        new_pattern.append(random.choice(['_', '%']))
                    else:
                        new_pattern.append(char)
                node.set('expression', sqlglot.expressions.Literal(this=''.join(new_pattern), is_string=True))
                item['direction'] = 1
        elif mutation_type == 'RdMRegExp':
            # Generalise the REGEXP pattern. Textual rewriting is only safe for
            # patterns without classes, groups, escapes, alternation or counted /
            # lazy quantifiers ('^' inside '[...]' is a negation, '\\+' a literal).
            pattern_node = node.args.get('expression')
            if pattern_node is not None:
                pattern_str = pattern_node.this
                simple = not any(c in pattern_str for c in '[]()\\{}|')
                simple = simple and '^' not in pattern_str[1:] and '$' not in pattern_str[:-1]
                simple = simple and not any(q in pattern_str for q in ('+?', '*?', '??', '++', '*+', '?+'))
                if simple:
                    new_pattern_str = pattern_str.replace('^', '').replace('$', '')
                    new_pattern_str = new_pattern_str.replace('+', '*').replace('?', '*')
                    node.set('expression', sqlglot.expressions.Literal(this=new_pattern_str, is_string=True))
                item['direction'] = 1
        elif mutation_type == 'FixMLogicalAnd':
            # Logical AND expression mutation: a AND b AND c -> a AND b (remove the last condition)
            # sqlglot represents AND as a binary node: keep the left operand only
            if node.this is not None and node.expression is not None:
                self._replace_node(node, node.this.copy())
                item['direction'] = 1  # Expand results: reducing conditions gives more results
        elif mutation_type == 'FixMInnerJoin':
            # INNER JOIN -> LEFT JOIN mutation
            if hasattr(node, 'args') and 'kind' in node.args:
                # Change INNER JOIN to LEFT JOIN
                node.args['kind'] = 'LEFT'
                item['direction'] = 1  # Expand results: LEFT JOIN gives more results
        elif mutation_type == 'FixMIntersect':
            # INTERSECT -> UNION mutation
            # Create new UNION node to replace INTERSECT node
            try:
                # Get left and right expressions of INTERSECT node
                left_expr = None
                right_expr = None
                if hasattr(node, 'args'):
                    if 'this' in node.args:
                        left_expr = node.args['this']
                    if 'expression' in node.args:
                        right_expr = node.args['expression']
                
                if left_expr and right_expr:
                    # Create UNION node, use DISTINCT by default
                    union_node = sqlglot.expressions.Union(
                        this=left_expr.copy(),
                        expression=right_expr.copy(),
                        distinct=True
                    )
                    self._carry_with_clause(node, union_node)
                    # Replace current node
                    self._replace_node(node, union_node)
                    item['direction'] = 1  # Expand results: INTERSECT -> UNION gives more results
            except Exception as e:
                pass
        elif mutation_type == 'FixMExcept':
            # A EXCEPT B -> A mutation (remove EXCEPT operation, keep only left expression)
            # Get left expression of EXCEPT node
            left_expr = None
            if hasattr(node, 'args') and 'this' in node.args:
                left_expr = node.args['this']
            
            if left_expr:
                try:
                    # Replace the entire EXCEPT node with left expression
                    left_expr = left_expr.copy()
                    self._carry_with_clause(node, left_expr)
                    self._replace_node(node, left_expr)
                    item['direction'] = 1  # Expand results: removing EXCEPT operation gives more results
                except Exception as e:
                    pass  # Mutation failed
            else:
                pass  # Cannot get left expression
        final_direction=(item['direction']^item['flag'])^1
        return self.ast


    def _replace_node(self, node, new_node):
        """Replace a node; sqlglot's replace() is a no-op for the root, so the
        root has to be swapped explicitly."""
        if node.parent is None:
            if node is self.ast:
                self.ast = new_node
        else:
            node.replace(new_node)
        return new_node

    @staticmethod
    def _carry_with_clause(old_node, new_node):
        """Keep the WITH clause when a set operation node is replaced."""
        for key in ('with_', 'with'):
            with_clause = old_node.args.get(key)
            if with_clause is not None:
                target = new_node.this if new_node.__class__.__name__ == 'Subquery' else new_node
                target.set(key, with_clause.copy())

    @staticmethod
    def _normalize_value(value):
        """Make values comparable across the result types of the original and
        the mutated query (set operations unify column types, e.g. DATE vs CHAR
        or FLOAT vs DECIMAL), so that only real value differences are reported."""
        import datetime
        from decimal import Decimal
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, (int, float, Decimal)):
            try:
                return round(float(value), 4)
            except (ValueError, OverflowError):
                return str(value)
        if isinstance(value, datetime.timedelta):
            # TIME values: use the same text form the DBMS uses (HH:MM:SS)
            total = int(value.total_seconds())
            sign = '-' if total < 0 else ''
            total = abs(total)
            return f"{sign}{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
        if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
            return str(value)
        if isinstance(value, str):
            try:
                return round(float(value), 4)
            except (ValueError, OverflowError):
                return value
        return value

    def _normalize_rows(self, rows):
        return [tuple(self._normalize_value(v) for v in row) for row in rows]

    def get_mutated_ast(self):
        """Get the mutated AST"""
        if not self.mutated:
            return self.ast
        return self.ast

    def get_mutable_nodes_count(self):
        """Get count of mutable nodes"""
        return len(self.mutable_nodes)