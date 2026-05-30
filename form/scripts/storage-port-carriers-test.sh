#!/usr/bin/env bash
#
# storage-port-carriers-test.sh — prove ONE storage-port test passes identically
# across ALL three carriers (memory, segmented file log, live Postgres).
#
# The executable substitutability proof: the same carrier-agnostic storage-test
# runs over every backend and all return the identical verdict. Run on the Rust
# kernel (the pg_* carrier floor). Self-provisions a throwaway Postgres unless
# PG_DSN is supplied. See docs/coherence-substrate/ports-interface-and-structure.md.
#
# Usage:
#   form/scripts/storage-port-carriers-test.sh                 # self-provision PG
#   PG_DSN="host=... port=... user=... dbname=..." form/scripts/...   # existing PG
#
# Exit 0 on the expected verdict (111111), 1 otherwise.
set -euo pipefail

FORMDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$FORMDIR"

RS_BIN="form-kernel-rust/target/release/form-kernel-rust"
if [[ ! -x "$RS_BIN" ]]; then
  echo "building rust kernel..." >&2
  (cd form-kernel-rust && cargo build --release --quiet)
fi

PROVISIONED=0
PGDIR=""
SRCDIR=""
cleanup() {
  [[ -n "$SRCDIR" ]] && rm -rf "$SRCDIR"
  if [[ "$PROVISIONED" -eq 1 && -n "$PGDIR" ]]; then
    pg_ctl -D "$PGDIR/data" stop -m fast >/dev/null 2>&1 || true
    rm -rf "$PGDIR"
  fi
}
trap cleanup EXIT

if [[ -z "${PG_DSN:-}" ]]; then
  if ! command -v initdb >/dev/null 2>&1; then
    echo "SKIP: no PG_DSN set and initdb not found — cannot self-provision." >&2
    exit 0
  fi
  PGDIR="$(mktemp -d "${TMPDIR:-/tmp}/form-pg.XXXXXX")"
  PROVISIONED=1
  initdb -D "$PGDIR/data" -U postgres --auth=trust >/dev/null 2>&1
  PGPORT=54402
  pg_ctl -D "$PGDIR/data" -o "-p $PGPORT -k $PGDIR" -l "$PGDIR/log" start >/dev/null 2>&1
  sleep 2
  psql -h 127.0.0.1 -p "$PGPORT" -U postgres -c "CREATE DATABASE port_test;" >/dev/null 2>&1
  PG_DSN="host=127.0.0.1 port=$PGPORT user=postgres dbname=port_test"
fi

SRCDIR="$(mktemp -d "${TMPDIR:-/tmp}/spcarriers.XXXXXX")"
printf '(do (form-source-compile-file "form-stdlib/core.fk" "%s/core.fk"))\n' "$SRCDIR" > "$SRCDIR/drv.fk"
form-kernel-go/bin-go form-stdlib/json.fk form-stdlib/cache.fk \
  form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk "$SRCDIR/drv.fk" >/dev/null 2>&1

TEST="$SRCDIR/all.fk"
sed "s|PG_DSN_PLACEHOLDER|${PG_DSN}|" form-stdlib/integration/storage-port-all-carriers.fk > "$TEST"

OUT="$("$RS_BIN" "$SRCDIR/core.fk" \
  form-stdlib/cell-log-store.fk form-stdlib/storage-port.fk \
  form-stdlib/storage-port-file.fk form-stdlib/storage-port-db.fk "$TEST" 2>&1 | tail -1)"
echo "verdict: $OUT"
if [[ "$OUT" == "111111" ]]; then
  echo "storage port: PASS — one test, identical verdict across memory / file / Postgres."
  exit 0
else
  echo "storage port: FAIL — expected 111111 (all three carriers pass + agree)." >&2
  exit 1
fi
