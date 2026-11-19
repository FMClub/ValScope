#!/usr/bin/env bash
# End-to-end run: build and check the proofs, build the mutator, run the tests, then
# test a database and print the results.
#
#   scripts/demo.sh mariadb     # MariaDB / MySQL (run scripts/setup_mariadb.sh first)
#   scripts/demo.sh sqlite      # an SQLite database built on the fly; needs no server
#
# Environment (mariadb): HOST, PORT, DB_USER, PASSWORD as for setup_mariadb.sh.
# N (default 200) is the number of queries of each kind.  Output goes to out/.
set -euo pipefail
target=${1:-sqlite}
N=${N:-200}
HOST=${HOST:-127.0.0.1}; PORT=${PORT:-3306}; DB_USER=${DB_USER:-root}; PASSWORD=${PASSWORD-123456}
cd "$(dirname "$0")/.."
mkdir -p out

echo "== 1. check the proofs and extract the verified engine (make)"
make -s > out/make.log 2>&1 || { tail -n 30 out/make.log; exit 1; }
grep -A1 "^Axioms\|Closed under" out/make.log | head -n 12
echo "== 2. build the command-line mutator (make cli)"
make -s cli > out/make-cli.log 2>&1 || { tail -n 30 out/make-cli.log; exit 1; }
./cli/valscope_mutate --rules | awk '{print $1}' | sort | uniq -c | sed 's/^/   rules: /'
echo "== 3. bridge and checker tests (no database)"
python3 bridge/test_bridge.py > out/test.log; tail -n 1 out/test.log

case "$target" in
  mariadb)
    conn=(--host "$HOST" --port "$PORT" --user "$DB_USER" --password "$PASSWORD" --database test)
    echo "== 4. generate $N set-semantic and $N value queries for the sample schema"
    python3 bridge/gen_fragment.py "$N" 1 > out/queries.sql
    python3 bridge/gen_fragment.py --value "$N" 2 > out/vqueries.sql
    echo "== 5. set-semantic rules on MariaDB"
    python3 bridge/run_on_db.py out/queries.sql "${conn[@]}" --out out/violations.jsonl | tee out/run-set.log | tail -n 6
    echo "== 6. value-semantic and HAVING rules on MariaDB"
    python3 bridge/run_on_db.py out/vqueries.sql --value "${conn[@]}" --out out/violations.jsonl | tee out/run-value.log | tail -n 6
    echo "== 7. queries of the original Python generator (data/python-generator-queries.sql)"
    python3 bridge/run_on_db.py data/python-generator-queries.sql "${conn[@]}" --out out/violations.jsonl | tee out/run-python-queries.log | tail -n 6
    echo "== 8. negative control (--flip): must report many violations"
    python3 bridge/run_on_db.py out/queries.sql --flip "${conn[@]}" | grep -o "'VIOLATIONS': [0-9]*" || echo "   no violations: the checks are not working"
    ;;
  sqlite)
    rm -f out/demo.db
    echo "== 4. build a random SQLite database (out/demo.db) and generate queries"
    python3 bridge/gen_sqlite_db.py out/demo.db 1004 > /dev/null
    python3 bridge/gen_fragment.py --sqlite "$N" 1 > out/queries.sql
    python3 bridge/gen_fragment.py --sqlite --value "$N" 2 > out/vqueries.sql
    echo "== 5. set-semantic rules on SQLite $(python3 -c 'import sqlite3; print(sqlite3.sqlite_version)')"
    python3 bridge/run_on_db.py out/queries.sql --sqlite out/demo.db --out out/violations.jsonl | tee out/run-set.log | tail -n 6
    echo "== 6. value-semantic and HAVING rules"
    python3 bridge/run_on_db.py out/vqueries.sql --value --sqlite out/demo.db --out out/violations.jsonl | tee out/run-value.log | tail -n 6
    echo "== 7. negative control (--flip): must report many violations"
    python3 bridge/run_on_db.py out/queries.sql --flip --sqlite out/demo.db | grep -o "'VIOLATIONS': [0-9]*" || echo "   no violations: the checks are not working"
    ;;
  *) echo "usage: scripts/demo.sh mariadb|sqlite" >&2; exit 2 ;;
esac
echo "== done. Logs in out/; violations (if any) in out/violations.jsonl"
