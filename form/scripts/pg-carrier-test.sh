#!/usr/bin/env bash
#
# pg-carrier-test.sh — integration test for the Form-native Postgres carrier.
#
# Stands up a throwaway local Postgres, renders + runs the substrate schema and a
# content-addressed get-or-insert from a .fk program through the Rust kernel
# (the DB carrier's reference impl), and asserts the verdict. This is the real
# end-to-end proof that Form-native code reads/writes a real Postgres — the DB
# carrier of the storage port (docs/coherence-substrate/cell-store-architecture.md).
#
# Not part of validate.sh's three-way suite: a live-DB side effect can't be
# value-diffed three ways, and only the Rust kernel carries the pg_* natives
# (same posture as the TS-only socket shim). CI runs this separately where a
# Postgres is available; locally it self-provisions one if `initdb` exists.
#
# Usage:
#   form/scripts/pg-carrier-test.sh                 # self-provision a throwaway PG
#   PG_DSN="postgresql://postgres@127.0.0.1:5432/substrate_test" \
#     form/scripts/pg-carrier-test.sh               # use an existing PG
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

# --- provision a Postgres (or use the caller's PG_DSN) ---------------------
PROVISIONED=0
PGDIR=""
cleanup() {
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
  PGPORT=54399
  pg_ctl -D "$PGDIR/data" -o "-p $PGPORT -k $PGDIR" -l "$PGDIR/log" start >/dev/null 2>&1
  sleep 2
  psql -h 127.0.0.1 -p "$PGPORT" -U postgres -c "CREATE DATABASE substrate_test;" >/dev/null 2>&1
  PG_DSN="postgresql://postgres@127.0.0.1:$PGPORT/substrate_test"
fi

# --- compile the core prelude (BML dialect → kernel-walkable) --------------
SRCDIR="$(mktemp -d "${TMPDIR:-/tmp}/pgcarrier.XXXXXX")"
trap 'rm -rf "$SRCDIR"; cleanup' EXIT
printf '(do (form-source-compile-file "form-stdlib/core.fk" "%s/core.fk"))\n' "$SRCDIR" > "$SRCDIR/drv.fk"
form-kernel-go/bin-go form-stdlib/json.fk form-stdlib/cache.fk \
  form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk "$SRCDIR/drv.fk" >/dev/null 2>&1

# --- inject the DSN into the test program ----------------------------------
TEST="$SRCDIR/pg-test.fk"
sed "s|PG_DSN_PLACEHOLDER|${PG_DSN}|" form-stdlib/integration/pg-carrier-integration.fk > "$TEST"

# --- run on the Rust kernel ------------------------------------------------
OUT="$("$RS_BIN" "$SRCDIR/core.fk" form-stdlib/db-schema.fk "$TEST" 2>&1 | tail -1)"
echo "verdict: $OUT"
if [[ "$OUT" == "111111" ]]; then
  echo "PG carrier: PASS — Form-native code read/wrote real Postgres end-to-end."
  exit 0
else
  echo "PG carrier: FAIL — expected 111111." >&2
  exit 1
fi
