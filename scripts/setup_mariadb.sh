#!/usr/bin/env bash
# Set up the MariaDB / MySQL database that the examples and the demo use.
#
#   scripts/setup_mariadb.sh                 # 127.0.0.1:3306, user root, password 123456
#   HOST=db.example PORT=4000 DB_USER=root PASSWORD= scripts/setup_mariadb.sh
#
# 1. If no server answers on HOST:PORT and HOST is local, a local MariaDB is started
#    (the package must be installed: sudo apt-get install -y mariadb-server) and the
#    root password is set to PASSWORD.
# 2. The sample database `test` (tables t1, t2, t3 with rows and indexes) is loaded from
#    data/mariadb/.  WARNING: an existing database named `test` is dropped.
set -euo pipefail
HOST=${HOST:-127.0.0.1}
PORT=${PORT:-3306}
USER=${DB_USER:-root}
PASSWORD=${PASSWORD-123456}
here=$(cd "$(dirname "$0")/.." && pwd)

client=$(command -v mariadb || command -v mysql || true)
[ -n "$client" ] || { echo "no mariadb / mysql client; install mariadb-client or mariadb-server" >&2; exit 1; }
sql() { "$client" -h"$HOST" -P"$PORT" -u"$USER" ${PASSWORD:+-p"$PASSWORD"} "$@"; }

if ! sql -e "SELECT 1" > /dev/null 2>&1; then
  case "$HOST" in 127.0.0.1|localhost) ;; *) echo "cannot connect to $HOST:$PORT as $USER" >&2; exit 1 ;; esac
  command -v mariadbd-safe > /dev/null || { echo "no server on port $PORT and mariadb-server is not installed" >&2; exit 1; }
  echo "starting a local MariaDB on port $PORT"
  mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld 2> /dev/null || true
  nohup mariadbd-safe --port="$PORT" --bind-address=127.0.0.1 > /dev/null 2>&1 &
  for _ in $(seq 1 30); do
    if sql -e "SELECT 1" > /dev/null 2>&1; then break; fi
    # a fresh installation: root logs in through the unix socket, without a password
    if "$client" -uroot -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$PASSWORD'; FLUSH PRIVILEGES;" 2> /dev/null; then break; fi
    sleep 1
  done
  sql -e "SELECT 1" > /dev/null || { echo "the server did not start" >&2; exit 1; }
fi

echo "server: $(sql -N -e 'SELECT VERSION()')"
sql --default-character-set=utf8mb4 < "$here/data/mariadb/schema.sql"
sql --default-character-set=utf8mb4 test < "$here/data/mariadb/indexes.sql"
echo "loaded database test: $(sql -N test -e "SELECT GROUP_CONCAT(CONCAT(table_name, ' (', table_rows, ' rows)') SEPARATOR ', ') FROM information_schema.tables WHERE table_schema = 'test'")"
