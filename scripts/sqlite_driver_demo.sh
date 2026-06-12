#!/usr/bin/env bash
# sqlite_driver_demo.sh — the 4th kernel's SQLite driver (carrier first). Emit a
# native binary from sqlite-driver.fk that links libsqlite3 and can WRITE (not
# only read): exec / query / digest. Witnesses the kernel digesting the tools it
# depends on (clang, sqlite3, libc) into its own catalog, and a real write+read.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/sqd.XXXXXX")"; trap 'rm -rf "$work"' EXIT

{ printf '(do\n'; cat "$FORM/form-stdlib/sqlite-driver.fk"; printf '\n(print "==C==")\n(print (sqd-emit))\n(print "==END==")\n0)\n'; } > "$work/d.fk"
(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/sqd.c"
"$CLANG" -O2 -o "$work/sqd" "$work/sqd.c" -lsqlite3
echo "sqlite driver emitted from sqlite-driver.fk: $(wc -c < "$work/sqd" | tr -d ' ') bytes (links libsqlite3)"

echo; echo "=== digest — the kernel writes a catalog of the tools it depends on ==="
"$work/sqd" "$work/k.db" digest

echo; echo "=== write a need, then read it back (the driver's WRITE path) ==="
"$work/sqd" "$work/k.db" exec "CREATE TABLE IF NOT EXISTS need(what TEXT, why TEXT); INSERT INTO need VALUES ('emit machine code','drop the clang dependency'),('write-path as a Form recipe','retire the driver into the body');"
"$work/sqd" "$work/k.db" query "SELECT what, why FROM need;"

echo; echo "=== persistence is real — re-open without re-writing ==="
"$work/sqd" "$work/k.db" query "SELECT count(*) FROM need;" | sed 's/^/  needs persisted: /'
echo "ok — driver first: full sqlite read+write from one Form-emitted binary, no Python"
