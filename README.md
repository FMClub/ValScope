# Valscope

## Project Overview
Valscope is an SQL query mutation testing framework for generating diverse SQL queries and mutating them to test the robustness and correctness of database systems. The framework can generate random SQL queries, create seed queries, perform AST (Abstract Syntax Tree) mutations, and supports multiple database dialects such as MySQL, TiDB, etc.

## Features

- **Random SQL Generation**: Capable of generating various complex SQL queries, including subqueries, JOIN operations, aggregate functions, etc.
- **Seed Query Generation**: Creates seed query sets for mutation based on generated SQL
- **AST Mutation**: Performs multiple pattern mutations on the abstract syntax tree of SQL queries
- **Multi-database Dialect Support**: Compatible with multiple database systems such as MySQL, TiDB, MariaDB, OceanBase, etc.
- **Performance Monitoring**: Provides execution logs and performance metrics collection
- **Memory Optimization**: Uses batch processing and iterator pattern to optimize memory usage

## Code Structure

```
Pinolo_Extension-main/
├── ast_nodes/         # AST node definitions
├── data_structures/   # Data structure definitions
├── documents/         # Documentation files
├── generated_sql/     # Generated SQL files
├── invalid_mutation/  # Invalid mutation storage
├── mutator/           # Mutator implementations
└── sql_generation/    # SQL generation module
```

## Main Modules

### 1. Entry Module
- **main.py**: The main entry point of the project, responsible for initializing configurations, coordinating the workflow of various modules, executing loop tests, recording logs, and monitoring performance. Supports setting runtime duration, database dialects, and other parameters, and provides memory management and error handling mechanisms.

### 2. AST Operation Module
- **generateAST.py**: Responsible for generating and manipulating SQL abstract syntax trees, providing functionality to parse SQL text into AST and convert AST back to SQL text. Contains the `Change` class for handling AST node creation, modification, and conversion.
- **changeAST.py**: Implements AST mutation operations, contains the `MutateSolve` class responsible for reading seed queries, applying mutation strategies, and processing mutation results. Supports batch processing mode to optimize memory usage.

### 3. SQL Generation Module
- **generate_random_sql.py**: A powerful random SQL generator that can create complex SQL queries, including SELECT and INSERT statements, supporting advanced features such as subqueries, JOIN operations, aggregate functions, window functions, etc. Uses ColumnUsageTracker to track column usage and ensure semantic correctness of generated SQL.
- **get_seedQuery.py**: Seed query generator, responsible for filtering and converting suitable seed query sets for mutation testing from generated random SQL.

### 4. Mutator Module
- **mutator/set_mutator.py**: Implements set-related mutation operations, such as modifying WHERE conditions, adjusting JOIN types, changing grouping methods, etc., mainly mutating the structure of SQL queries.
- **mutator/value_mutator.py**: Implements value-related mutation operations, such as modifying literal values, function parameters, comparison operators, etc., mainly mutating specific values in SQL queries.

### 5. Data Structures Module
- **data_structures/table.py**: Defines table structures and related operations
- **data_structures/column.py**: Defines column structures, data types, and properties
- **data_structures/db_dialect.py**: Implements database dialect management, supporting syntax features of multiple database systems such as MySQL, TiDB, MariaDB, OceanBase, etc.
- **data_structures/function.py**: Defines function-related data structures and types
- **data_structures/dependency.py**: Handles dependency relationships between SQL elements

### 6. AST Nodes Module
- **ast_nodes/ast_node.py**: Defines the base class and common operations for AST nodes
- **ast_nodes/select_node.py**: AST node corresponding to SELECT statements
- **ast_nodes/from_node.py**: AST node corresponding to FROM clauses and table references
- **ast_nodes/arithmetic_node.py**: AST node corresponding to arithmetic expressions
- **ast_nodes/comparison_node.py**: AST node corresponding to comparison expressions
- **ast_nodes/logical_node.py**: AST node corresponding to logical expressions
- **ast_nodes/function_call_node.py**: AST node corresponding to function calls
- **ast_nodes/group_by_node.py**: AST node corresponding to GROUP BY clauses
- **ast_nodes/with_node.py**: AST node corresponding to WITH clauses (CTEs)
- **ast_nodes/subquery_node.py**: AST node corresponding to subqueries

## How to Run

### 1. Environment Requirements
- Python 3.8+
- Optional database systems:
  - MySQL 8.0+ (Default port: 13306)
  - MariaDB (Default port: 9901)
  - TiDB (Default port: 4000)
  - OceanBase (Default port: 2881)
  - Percona (Default port: 23306)
  - PolarDB (Default port: 8527)
  - PostgreSQL 12.0+ (Connection parameters not fully configured yet)

### DBMS Connection Parameter Configuration Locations

DBMS connection parameters in the project follow this priority order:

1. **Direct parameter passing (highest priority)**: Passing `db_config` parameter directly when calling relevant classes
2. **Default configuration in `get_seedQuery.py`**: Default values set during initialization of the `SeedQueryGenerator` class
3. **Dialect-specific configuration in `get_seedQuery.py`**: Specific parameters set for each database in the `connect_db` method

Specific configuration locations:

- **Main configuration file**: `get_seedQuery.py`
  - Lines 8-17: Default database configuration applicable to all database systems
  - Lines 55-110: Specific configurations for each database system, including port numbers and credentials

- **Command line parameters**: In `main.py`
  - Lines 72-78: Database connection parameters passed when calling the `Generate` class
  - Line 82: Creating `SeedQueryGenerator` instance (uses default values when db_config is not explicitly passed)

- **Database dialect configuration**: `data_structures/db_dialect.py`
  - Defines various database dialect classes and related functionality, but does not contain connection parameter configurations

### 2. Install Dependencies
First, ensure all necessary dependency libraries are installed. The project includes a requirements.txt file, which you can use to install all dependencies:

```bash
pip install -r requirements.txt
```

Main dependencies include:
- sqlglot>=18.0.0: Used for SQL parsing and transformation
- pymysql>=1.1.0: Used for MySQL database connections
- psycopg2-binary>=2.9.9: Used for PostgreSQL database connections

### 3. Running Parameter Configuration
In the main.py file, you can configure the following key parameters:

```python
# Database dialect settings (mysql, tidb, mariadb, oceanbase, percona, etc.)
dialect_str = 'mysql'
# Whether to use value mutator extended functionality
use_value_mutator = True
# Runtime duration (hours)
run_hours = 20
# Whether to use real database table structures (False means using simulated table structures)
is_use_database_tables = False
```

### 4. Database Configuration
If `is_use_database_tables=True` is set, you need to configure database connection information to obtain the actual table structure:

```python
db_config={
    'host': '127.0.0.1',      # Database host address
    'port': 4000,             # Database port
    'database': 'test',       # Database name
    'user': 'root',           # Database username
    'password': '123456',     # Database password
}
```

### 5. SQL Generation Configuration
When calling the Generate function, you can configure the following parameters to adjust the characteristics of the generated SQL:

```python
Generate(
    subquery_depth=2,           # Subquery depth, default is 1
    total_insert_statements=40, # Total number of INSERT statements to generate
    num_queries=1000,           # Number of query statements to generate
    query_type='default',       # Query type
    use_database_tables=is_use_database_tables,
    db_config=db_config
)
```

### 6. Execution Command

```bash
python main.py
```

### 7. Output Description
- **generated_sql/** directory:
  - `queries.sql` - Generated random SQL queries
  - `seedQuery.sql` - Seed queries for mutation
  - `schema.sql` - Simulated or real table structure definitions
  - `indexes.sql` - Index definitions

- **logs/** directory:
  - Execution log files, containing timestamps, execution time, error messages, etc.

- **invalid_mutation/** directory:
  - Stores invalid mutation results categorized by database type

### 8. Adjusting Memory Usage
If you encounter memory issues when processing a large number of queries, you can adjust the batch size in the mutate_main method of changeAST.py:

```python
mutate_main(self, batch_size=100, max_queries=None)
```
Decreasing the batch_size value can reduce memory usage.

## Workflow

1. **Initialization Configuration**: Set database dialect and runtime parameters
2. **Random SQL Generation**: Create diverse SQL queries
3. **Seed Query Generation**: Create seed queries for mutation based on random SQL
4. **AST Mutation Execution**: Perform various mutation operations on seed queries
5. **Result Processing**: Save valid and invalid mutation results
6. **Loop Execution**: Repeat the above process according to the set runtime duration

## Extension Guide

To extend new mutation patterns, you can add new mutator classes in the `mutator/` directory and integrate them in `changeAST.py`.

To support new database dialects, you can add corresponding dialect definitions in `data_structures/db_dialect.py`.
