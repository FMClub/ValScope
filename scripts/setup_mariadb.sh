#!/usr/bin/env bash
# Set up the MariaDB / MySQL database that the examples and the demo use.
#
#   scripts/setup_mariadb.sh                 # 127.0.0.1:3306, user root, password 123456, database test
#   HOST=db.example PORT=4000 DB_USER=root PASSWORD= DATABASE=vs_test scripts/setup_mariadb.sh
#
# 1. If no server answers on HOST:PORT and HOST is local, a local MariaDB is started
#    (the package must be installed: sudo apt-get install -y mariadb-server; starting it
#    needs root, so sudo is used when the script does not run as root), and the root
#    password is set to PASSWORD.
# 2. The sample database (tables t1, t2, t3 with rows and indexes, data/mariadb/) is loaded
#    into DATABASE.  If DATABASE exists and has tables, the script asks before dropping it;
#    without a terminal it refuses unless YES=1 is set.
set -euo pipefail
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-3306}
USER=${DB_USER:-root}
PASSWORD=${PASSWORD-123456}
DATABASE=${DATABASE:-test}
here=$(cd "$(dirname "$0")/.." && pwd)

case "$DATABASE" in *[!A-Za-z0-9_]*|'') echo "DATABASE must be a plain name: $DATABASE" >&2; exit 2 ;; esac
client=$(command -v mariadb || command -v mysql || true)
[ -n "$client" ] || { echo "no mariadb / mysql client; install mariadb-client or mariadb-server" >&2; exit 1; }
sql() { "$client" -h"$HOST" -P"$PORT" -u"$USER" ${PASSWORD:+-p"$PASSWORD"} "$@"; }
as_root() { if [ "$(id -u)" = 0 ]; then "$@"; elif command -v sudo > /dev/null; then sudo "$@"; else
  echo "starting a server needs root: run this script as root or install sudo" >&2; exit 1; fi; }

if ! sql -e "SELECT 1" > /dev/null 2>&1; then
  case "$HOST" in 127.0.0.1|localhost) ;; *) echo "cannot connect to $HOST:$PORT as $USER" >&2; exit 1 ;; esac
  command -v mariadbd-safe > /dev/null || { echo "no server on port $PORT and mariadb-server is not installed" >&2; exit 1; }
  echo "starting a local MariaDB on port $PORT"
  as_root mkdir -p /run/mysqld
  as_root chown mysql:mysql /run/mysqld 2> /dev/null || true
  as_root sh -c "nohup mariadbd-safe --port='$PORT' --bind-address=127.0.0.1 > /dev/null 2>&1 &"
  for _ in $(seq 1 30); do
    if sql -e "SELECT 1" > /dev/null 2>&1; then break; fi
    # a fresh installation: root logs in through the unix socket, without a password
    if as_root "$client" -uroot -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$PASSWORD'; FLUSH PRIVILEGES;" 2> /dev/null; then break; fi
    sleep 1
  done
  sql -e "SELECT 1" > /dev/null || { echo "the server did not start" >&2; exit 1; }
fi
echo "server: $(sql -N -e 'SELECT VERSION()')"

tables=$(sql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$DATABASE'")
if [ "$tables" != 0 ] && [ "${YES:-}" != 1 ]; then
  if [ -t 0 ]; then
    read -r -p "database $DATABASE has $tables tables and will be dropped; continue? [y/N] " answer
    case "$answer" in y|Y|yes) ;; *) echo "nothing changed"; exit 1 ;; esac
  else
    echo "database $DATABASE has $tables tables; set YES=1 to drop and recreate it" >&2; exit 1
  fi
fi

# the files name the database `test`; load them into DATABASE
retarget() { sed -E "s/^(DROP DATABASE IF EXISTS|CREATE DATABASE IF NOT EXISTS|USE) test;\$/\\1 $DATABASE;/" "$1"; }
retarget "$here/data/mariadb/schema.sql" | sql --default-character-set=utf8mb4
# indexes.sql collects the output of several generator runs: some indexes are defined twice
# or already exist in schema.sql.  As in the original tool those statements are skipped,
# and the skipped ones are reported.
errors=$(retarget "$here/data/mariadb/indexes.sql" | sql --force --default-character-set=utf8mb4 "$DATABASE" 2>&1 >/dev/null || true)
if [ -n "$errors" ]; then
  echo "skipped index statements: $(printf '%s\n' "$errors" | grep -c '^ERROR') ($(printf '%s\n' "$errors" | grep -o '^ERROR [0-9]*' | sort | uniq -c | tr -s ' ' | paste -sd, -))"
  printf '%s\n' "$errors" | grep -v '^ERROR 1061' | grep '^ERROR' | head -n 5 || true
fi
echo "indexes: $(sql -N "$DATABASE" -e "SELECT COUNT(DISTINCT table_name, index_name) FROM information_schema.statistics WHERE table_schema = '$DATABASE'")"
echo "loaded database $DATABASE: $(sql -N "$DATABASE" -e "SELECT GROUP_CONCAT(CONCAT(table_name, ' (', table_rows, ' rows)') SEPARATOR ', ') FROM information_schema.tables WHERE table_schema = '$DATABASE'")"
