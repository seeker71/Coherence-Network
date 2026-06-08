#!/usr/bin/env bash
#
# native-idea-valuation-audit-ledger-test.sh — live DB proof that Form-native
# idea update route runners append Python-parity valuation audit-ledger rows.
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
  PGDIR="$(mktemp -d "${TMPDIR:-/tmp}/form-idea-audit-ledger-pg.XXXXXX")"
  PROVISIONED=1
  initdb -D "$PGDIR/data" -U postgres --auth=trust >/dev/null 2>&1
  PGPORT=$((58409 + (RANDOM % 1000)))
  pg_ctl -D "$PGDIR/data" -o "-p $PGPORT -k $PGDIR" -l "$PGDIR/log" start >/dev/null 2>&1
  sleep 2
  psql -h 127.0.0.1 -p "$PGPORT" -U postgres -c "CREATE DATABASE native_idea_audit_ledger_test;" >/dev/null 2>&1
  PG_DSN="postgresql://postgres@127.0.0.1:$PGPORT/native_idea_audit_ledger_test"
fi

SRCDIR="$(mktemp -d "${TMPDIR:-/tmp}/nativeideaauditledger.XXXXXX")"
printf '(do (form-source-compile-file "form-stdlib/core.fk" "%s/core.fk"))\n' "$SRCDIR" > "$SRCDIR/drv.fk"
form-kernel-go/bin-go form-stdlib/json.fk form-stdlib/cache.fk \
  form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk "$SRCDIR/drv.fk" >/dev/null 2>&1

TEST="$SRCDIR/native-idea-valuation-audit-ledger-live.fk"
sed "s|PG_DSN_PLACEHOLDER|${PG_DSN}|" form-stdlib/integration/native-idea-valuation-audit-ledger-live.fk > "$TEST"

OUT="$("$RS_BIN" "$SRCDIR/core.fk" form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-idea-valuation-audit-ledger.fk "$TEST" 2>&1 | tail -1)"
echo "verdict: $OUT"
if [[ "$OUT" == "11111111" ]]; then
  echo "native idea valuation audit ledger: PASS — Form-native idea update appended hash-chained VALUATION_CHANGE rows in throwaway Postgres."
  exit 0
else
  echo "native idea valuation audit ledger: FAIL — expected 11111111." >&2
  exit 1
fi
