#!/usr/bin/env bash
# End-to-end run: build and check the proofs, build the mutator, run the tests, then
# test a database and print the results.
#
#   scripts/demo.sh mariadb     # MariaDB / MySQL (run scripts/setup_mariadb.sh first)
#   scripts/demo.sh sqlite      # an SQLite database built on the fly; needs no server
#
# Environment (mariadb): HOST, PORT, DB_USER, PASSWORD, DATABASE as for setup_mariadb.sh.
# N (default 200) is the number of queries of each kind.  Output goes to out/.
set -euo pipefail
target=${1:-sqlite}
N=${N:-200}
HOST=${HOST:-127.0.0.1}; PORT=${PORT:-3306}; DB_USER=${DB_USER:-root}; PASSWORD=${PASSWORD-123456}
DATABASE=${DATABASE:-test}
cd "$(dirname "$0")/.."
mkdir -p out

# ---- check the dependencies first, with the command that installs what is missing
missing=0
need() {   # need <command> <how to install>
  if ! command -v "$1" > /dev/null; then echo "missing: $1    install: $2" >&2; missing=1; fi
}
need coqc 'sudo apt-get install -y coq   (Coq 8.18 or newer, see docs/USAGE.md 2.2)'
need coq_makefile 'sudo apt-get install -y coq'
need ocamlfind 'sudo apt-get install -y ocaml ocaml-findlib'
need make 'sudo apt-get install -y make'
need python3 'sudo apt-get install -y python3 python3-pip'
if command -v python3 > /dev/null; then
  python3 -c 'import sqlglot' 2> /dev/null || { echo "missing: python package sqlglot    install: python3 -m pip install -r requirements.txt" >&2; missing=1; }
  if [ "$target" = mariadb ]; then
    python3 -c 'import pymysql' 2> /dev/null || { echo "missing: python package pymysql    install: python3 -m pip install -r requirements.txt" >&2; missing=1; }
  fi
  v=$(python3 -c 'import sqlglot; print(sqlglot.__version__)' 2> /dev/null || true)
  if [ -n "$v" ] && ! python3 -c "import sys; v = tuple(map(int, '$v'.split('.')[:2])); sys.exit(not ((26, 33) <= v <= (30, 33)))"; then
    echo "warning: sqlglot $v; the bridge is tested with sqlglot 26.33 to 30.33 (requirements.txt pins 30.33.0)" >&2
  fi
fi
[ "$missing" = 0 ] || exit 1

# the counters of a run, and its violations (see docs/USAGE.md, section 10)
summary() {
  grep "^{" "$1" | tr -d "{}'" | tr ',' '\n' | sed 's/^ */   /'
  grep -A2 "^VIOLATION\|^TRANSLATION MISMATCH" "$1" | cut -c1-300 | sed 's/^/   /' || true
}

echo "== 1. check the proofs and extract the verified engine (make)"
make -s > out/make.log 2>&1 || { tail -n 30 out/make.log; exit 1; }
# ask Rocq which axioms the three soundness theorems depend on
printf 'From ValScope Require Import Registry.\nPrint Assumptions mutate_sound.\nPrint Assumptions vmutate_sound.\nPrint Assumptions hmutate_sound.\n' > out/Assumptions.v
coqc -R theories ValScope out/Assumptions.v > out/assumptions.log
awk '/^Closed under/ {print "   set-semantic mutator (mutate_sound): no axioms"; next}
     /^Axioms:/ {n++; next}
     /^[A-Za-z]/ && n {split($1, a, "."); ax[n] = ax[n] " " a[length(a)]}
     END {for (i = 1; i <= n; i++) print "   " (i == 1 ? "value mutator (vmutate_sound)" : "HAVING mutator (hmutate_sound)") ": axioms of Coq Reals:" ax[i]}' out/assumptions.log
echo "== 2. build the command-line mutator (make cli)"
make -s cli > out/make-cli.log 2>&1 || { tail -n 30 out/make-cli.log; exit 1; }
./cli/valscope_mutate --rules | awk '{print $1}' | sort | uniq -c | sed 's/^/   rules: /'
echo "== 3. bridge and checker tests (no database)"
python3 bridge/test_bridge.py > out/test.log; tail -n 1 out/test.log

case "$target" in
  mariadb)
    conn=(--host "$HOST" --port "$PORT" --user "$DB_USER" --password "$PASSWORD" --database "$DATABASE")
    echo "== 4. generate $N set-semantic and $N value queries for the sample schema"
    python3 bridge/gen_fragment.py "$N" 1 > out/queries.sql
    python3 bridge/gen_fragment.py --value "$N" 2 > out/vqueries.sql
    echo "== 5. set-semantic rules on MariaDB"
    python3 bridge/run_on_db.py out/queries.sql "${conn[@]}" --out out/violations.jsonl > out/run-set.log; summary out/run-set.log
    echo "== 6. value-semantic and HAVING rules on MariaDB"
    python3 bridge/run_on_db.py out/vqueries.sql --value "${conn[@]}" --out out/violations.jsonl > out/run-value.log; summary out/run-value.log
    echo "== 7. queries of the original Python generator (data/python-generator-queries.sql)"
    python3 bridge/run_on_db.py data/python-generator-queries.sql "${conn[@]}" --out out/violations.jsonl > out/run-python-queries.log; summary out/run-python-queries.log
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
    python3 bridge/run_on_db.py out/queries.sql --sqlite out/demo.db --out out/violations.jsonl > out/run-set.log; summary out/run-set.log
    echo "== 6. value-semantic and HAVING rules"
    python3 bridge/run_on_db.py out/vqueries.sql --value --sqlite out/demo.db --out out/violations.jsonl > out/run-value.log; summary out/run-value.log
    echo "== 7. negative control (--flip): must report many violations"
    python3 bridge/run_on_db.py out/queries.sql --flip --sqlite out/demo.db | grep -o "'VIOLATIONS': [0-9]*" || echo "   no violations: the checks are not working"
    ;;
  *) echo "usage: scripts/demo.sh mariadb|sqlite" >&2; exit 2 ;;
esac
echo "== done. Logs in out/; violations (if any) in out/violations.jsonl"
