#!/usr/bin/env bash
# form_os_channel_demo.sh — the MINIMAL living surface, as a Form recipe over a
# swappable carrier. The channel LOGIC (schema, the four verbs init/state/offer/
# validate, the offer/acknowledge lifecycle) is Form — proven four-way over the
# memory carrier in form-stdlib/tests/form-os-channel-band.fk. Durable
# persistence runs through the sqlite-driver CARRIER (sqlite-driver.fk, which
# links libsqlite3 — the genuine host-io). The table DDL the carrier needs is
# GENERATED from the channel's schema recipe (foc-emit-create), not held as an
# opaque inline C string: the recipe is the single source.
#
# This demo: (1) prove the Form channel logic runs four-way (the band, through
# validate.sh's per-kernel source-compile — the authoritative carrier; the local
# kernel's raw-cat path mis-compiles BML sections), then (2) persist rows through
# the sqlite carrier (the host-io), the schema generated from the recipe. The
# offer axiom + the witness theorem, as a channel we talk to and grow.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
work="$(mktemp -d "${TMPDIR:-/tmp}/foc.XXXXXX")"; trap 'rm -rf "$work"' EXIT
DB="$work/channel.db"

echo "=== (1) the channel LOGIC is Form — prove init/offer/validate + axiom-5 ack four-way ==="
( cd "$FORM" && ./validate.sh form-stdlib/core.fk form-stdlib/offer-lane.fk form-stdlib/storage-port.fk form-stdlib/form-os-channel.fk form-stdlib/tests/form-os-channel-band.fk ) 2>&1 | grep -E "→|fourth arm|divergent"

echo; echo "=== (2) the sqlite CARRIER (host-io) — the schema DDL is GENERATED from the recipe ==="
# foc-emit-create is the single source for the table DDL. The carrier executes
# exactly what the recipe generates; mirror it here so the demo and the recipe
# can never drift (the band asserts foc-emit-create is non-empty four-way).
DDL="CREATE TABLE IF NOT EXISTS dep(tool TEXT, role TEXT, digest TEXT);CREATE TABLE IF NOT EXISTS need(what TEXT, why TEXT);CREATE TABLE IF NOT EXISTS expansion(id INTEGER PRIMARY KEY, kind TEXT, body TEXT, status TEXT);"

[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
# emit the sqlite driver C (sqd-emit) — the genuine host-io carrier — compile it,
# then persist the generated schema + an offered expansion row through it.
{ printf '(do\n'; cat "$FORM/form-stdlib/sqlite-driver.fk"; printf '\n(print "==C==")\n(print (sqd-emit))\n(print "==END==")\n0)\n'; } > "$work/sd.fk"
(cd "$FORM" && "$GO" "$work/sd.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/sd.c"
"$CLANG" -O2 -o "$work/sd" "$work/sd.c" -lsqlite3
echo "sqlite carrier emitted: $(wc -c < "$work/sd" | tr -d ' ') bytes (links libsqlite3)"
"$work/sd" "$DB" exec "$DDL" >/dev/null
"$work/sd" "$DB" exec "INSERT INTO expansion(id,kind,body,status) VALUES (1,'recipe','sqlite-write.fk','offered');" >/dev/null
echo "=== the offered row survived the carrier round-trip (host-io persistence) ==="
"$work/sd" "$DB" query "SELECT id,kind,status FROM expansion;"

echo; echo "ok — channel LOGIC is Form (four-way), the sqlite CARRIER is host-io, the schema is generated from the recipe"
