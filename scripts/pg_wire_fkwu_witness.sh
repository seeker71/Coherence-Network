#!/usr/bin/env bash
# pg_wire_fkwu_witness.sh — prove the 4th kernel (fkwu) reads from live Postgres via Form pg-wire.
#
# Retires the Rust-libpq standing wall: form-stdlib/pg-wire.fk speaks the Postgres v3 wire protocol in
# Form over the kernel's own sockets (socket_connect/send/recv/close), so the SAME recipe runs on the
# C-bootstrapped 4th kernel — no Rust pg_*, no Go in the runtime. This witness stands up a local Postgres
# (trust auth, one row), flattens pg-wire.fk + an inline SELECT band into an fkwu table, runs it on fkwu,
# and asserts the row value comes back. Carrier only — the protocol is Form.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT/form" || exit 3
export GO_BIN="$ROOT/form/form-kernel-go/bin-go"; export TMPDIR="${TMPDIR:-/tmp}"
WANT="pg-wire-witness-$$"

# 1. ensure a local Postgres on TCP with trust auth + a known row
command -v pg_ctlcluster >/dev/null 2>&1 || { echo "no local postgres tooling — skipping"; exit 3; }
PGCONF="$(ls -d /etc/postgresql/*/main 2>/dev/null | head -1)"
if [ -n "$PGCONF" ]; then
  grep -q "^listen_addresses *= *'localhost'" "$PGCONF/postgresql.conf" 2>/dev/null || echo "listen_addresses = 'localhost'" >> "$PGCONF/postgresql.conf"
  grep -qE "127.0.0.1/32 +trust" "$PGCONF/pg_hba.conf" 2>/dev/null || sed -i "1i host all all 127.0.0.1/32 trust" "$PGCONF/pg_hba.conf"
  pg_ctlcluster "$(basename "$(dirname "$PGCONF")")" main start >/dev/null 2>&1 || pg_ctlcluster "$(basename "$(dirname "$PGCONF")")" main restart >/dev/null 2>&1 || true
fi
sleep 2
su postgres -c "psql -tAc \"CREATE TABLE IF NOT EXISTS port_kv(k text primary key, v text); INSERT INTO port_kv VALUES ('wk','$WANT') ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v;\"" >/dev/null 2>&1 \
  || { echo "could not seed postgres — skipping"; exit 3; }

# 2. ensure the 4th kernel; flatten pg-wire.fk + an inline SELECT band; run on fkwu
# shellcheck disable=SC1091
set +u; . scripts/fourth-arm.sh; set -u
command -v clang >/dev/null 2>&1 || { echo "fkwu needs clang (C bootstrap) — skipping"; exit 3; }
build_fourth >/dev/null 2>&1
FKWU=""; for f in form-stdlib/.cache/fourth/fkwu-*; do [ -x "$f" ] && FKWU="$f"; done
[ -n "$FKWU" ] || { echo "fkwu did not build — skipping"; exit 3; }

d="$(mktemp -d)"
cat > "$d/band.fk" <<EOF
(do
  (let conn (socket_connect "127.0.0.1" 5432))
  (socket_send conn (pw-startup "postgres" "postgres"))
  (let hs (socket_recv conn 65535))
  (socket_send conn (pw-query "SELECT v FROM port_kv WHERE k='wk'"))
  (let r (socket_recv conn 65535))
  (socket_close conn)
  (pw-first-value r))
EOF
cat "${FOURTH_CHAIN[@]}" > "$d/driver.fk"
mod=" (read_file \"$FOURTH_SHIM\") (read_file \"form-stdlib/str-byte-at.fk\") (read_file \"form-stdlib/pg-wire.fk\")"
printf '(print (fks-table-file (flt-band-sources-fns (list%s) (read_file "%s/band.fk")) (flt-band-sources-pool (list%s) (read_file "%s/band.fk"))))\n' \
  "$mod" "$d" "$mod" "$d" >> "$d/driver.fk"
"$GO_BIN" "$d/driver.fk" 2>/dev/null > "$d/t.tbl"
GOT="$("$FKWU" "$d/t.tbl" 0 2>&1 | head -1)"
rm -rf "$d"

echo "fkwu read from Postgres via Form pg-wire: '$GOT'"
if [ "$GOT" = "$WANT" ]; then
  echo "⟐ PROVEN: the 4th kernel (fkwu, C-bootstrap) reads live Postgres in pure Form — no Rust libpq, no Go."
  exit 0
else
  echo "✗ mismatch — wanted '$WANT'"; exit 1
fi
