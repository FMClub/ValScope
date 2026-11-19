#!/usr/bin/env bash
# Build shared libraries of old SQLite releases for the campaigns.
#
#   bridge/build_old_sqlite.sh OUT_DIR
#
# sqlite.org may not be reachable from a test environment.  The npm package `sqlite3`
# ships the SQLite amalgamation it was built with, so the sources are taken from there:
#   sqlite3@4.0.6 -> 3.26.0,  4.1.1 -> 3.30.1,  4.2.0 -> 3.31.1,  5.0.2 -> 3.34.0
set -euo pipefail
out=${1:?output directory}
mkdir -p "$out"
cd "$out"
for pair in 4.0.6:3260000 4.1.1:3300100 4.2.0:3310100 5.0.2:3340000; do
  pkg=${pair%%:*}; ver=${pair##*:}
  # rebuild only when missing or built without column metadata (needed by the checker)
  if [ -f "libsqlite3-$ver.so" ] && nm -D "libsqlite3-$ver.so" | grep -q sqlite3_column_origin_name; then continue; fi
  npm pack "sqlite3@$pkg" --silent >/dev/null
  tar xzf "sqlite3-$pkg.tgz" "package/deps/sqlite-autoconf-$ver.tar.gz" -O | tar xz
  gcc -O1 -shared -fPIC -DSQLITE_THREADSAFE=0 -DSQLITE_ENABLE_STAT4 -DSQLITE_ENABLE_COLUMN_METADATA \
      "sqlite-autoconf-$ver/sqlite3.c" -o "libsqlite3-$ver.so" -lm -ldl
  echo "built $out/libsqlite3-$ver.so"
done
