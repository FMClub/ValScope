# Valscope

ValScope is a DBMS testing framework based on a unified SQL query approximation model that combines set-semantic and value-semantic reasoning. By generating, mutating, and verifying SQL queries, it effectively detects logical bugs in DBMSs. It supports multiple database dialects including MySQL, MariaDB, Percona, OceanBase, and PolarDB.

## How to Run

### 1. Environment Requirements
- Python 3.8+
- Optional database systems:
  - MySQL 8.0+ (Default port: 13306)
  - MariaDB (Default port: 9901)
  - OceanBase (Default port: 2881)
  - Percona (Default port: 23306)
  - PolarDB (Default port: 8527)

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

