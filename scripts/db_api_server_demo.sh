#!/usr/bin/env bash
# db_api_server_demo.sh — emit a self-contained native binary (from the Form
# recipe db-api-server.fk) that serves the home page AND a JSON API entirely from
# a SQLite .db file it opens itself, plus its OWN api surface and its OWN binary.
# No libsqlite3, no Python, no stdio in the running binary: the SQLite format is
# parsed inline (sqlite-read.fk lifted into the emitted C), the socket is the only
# kernel organ. The artifact is the binary; this script is the live witness.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
PORT="${PORT:-8231}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
command -v sqlite3 >/dev/null || { echo "need sqlite3 to seed the .db (dev tool only; the binary has no sqlite dep)"; exit 1; }
work="$(mktemp -d "${TMPDIR:-/tmp}/dbapi.XXXXXX")"; trap 'rm -rf "$work"; kill $SRV 2>/dev/null' EXIT

# 1. seed a real SQLite file (the only place sqlite3 is used — at seed time, not run time)
sqlite3 "$work/seed.db" <<'SQL'
CREATE TABLE idea(id INTEGER, slug TEXT, title TEXT);
INSERT INTO idea VALUES (1,'agent-pipeline','Agent Pipeline');
INSERT INTO idea VALUES (2,'form-os','Form OS');
INSERT INTO idea VALUES (3,'living-equation','The Living Equation');
SQL

# 2. emit the C from the Form recipe (Go kernel), compile with clang
{ printf '(do\n'; cat "$FORM/form-stdlib/db-api-server.fk"; printf '\n(print "==C==")\n(print (das-emit))\n(print "==END==")\n0)\n'; } > "$work/driver.fk"
(cd "$FORM" && "$GO" "$work/driver.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/srv.c"
"$CLANG" -O2 -o "$work/srv" "$work/srv.c"
echo "native binary emitted from db-api-server.fk: $(wc -c < "$work/srv" | tr -d ' ') bytes — no libsqlite3, no python, no stdio"

# 3. run it against the real .db and curl every surface
"$work/srv" "$PORT" "$work/seed.db" & SRV=$!
for i in $(seq 1 30); do curl -sS --max-time 1 -o /dev/null "http://127.0.0.1:$PORT/" 2>/dev/null && break; sleep 0.1; done

echo; echo "=== GET /  (home page, rows read from the sqlite file) ==="
curl -sS --max-time 2 "http://127.0.0.1:$PORT/"
echo; echo "=== GET /api/idea  (json, reconstructed from the db) ==="
curl -sS --max-time 2 "http://127.0.0.1:$PORT/api/idea"; echo
echo "=== GET /api/_surface  (the binary's OWN api surface) ==="
curl -sS --max-time 2 "http://127.0.0.1:$PORT/api/_surface"; echo
echo "=== GET /api/_binary  (the binary's OWN executable bytes) ==="
curl -sS --max-time 2 "http://127.0.0.1:$PORT/api/_binary" -o "$work/self.bin" -w "  served %{size_download} bytes\n"
if cmp -s "$work/self.bin" "$work/srv"; then
  echo "  IDENTICAL — the response IS the running binary, byte-for-byte (self-return verified)"
else
  echo "  differ — self-return failed"; exit 1
fi
echo; echo "ok — home + api + own-surface + own-binary, all from one native binary over a sqlite file"
