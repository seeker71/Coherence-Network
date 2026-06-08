#!/usr/bin/env bash
#
# application-graph-live-db-test.sh — live DB proof for Form-native mutable
# application graph writes.
#
# Stands up a throwaway Postgres unless PG_DSN is supplied, runs the application
# graph mutation carrier through the Rust kernel, and asserts that native Form
# code can create/update/delete graph_nodes, graph_node_revisions, and
# graph_edges with read-back evidence. This proves the next movement after the
# native mutation A/B observation gate: live DB execution in a rollback-safe
# fixture database, not a public front-door flip.
#
# Usage:
#   form/scripts/application-graph-live-db-test.sh
#   PG_DSN="host=... port=... user=... dbname=..." form/scripts/application-graph-live-db-test.sh
#
# Exit 0 on PASS or environment SKIP, 1 on a failed live verdict.
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
  PGDIR="$(mktemp -d "${TMPDIR:-/tmp}/form-app-graph-pg.XXXXXX")"
  PROVISIONED=1
  initdb -D "$PGDIR/data" -U postgres --auth=trust >/dev/null 2>&1
  PGPORT=$((54409 + (RANDOM % 1000)))
  pg_ctl -D "$PGDIR/data" -o "-p $PGPORT -k $PGDIR" -l "$PGDIR/log" start >/dev/null 2>&1
  sleep 2
  psql -h 127.0.0.1 -p "$PGPORT" -U postgres -c "CREATE DATABASE app_graph_live_test;" >/dev/null 2>&1
  PG_DSN="host=127.0.0.1 port=$PGPORT user=postgres dbname=app_graph_live_test"
fi

SRCDIR="$(mktemp -d "${TMPDIR:-/tmp}/appgraphlive.XXXXXX")"
printf '(do (form-source-compile-file "form-stdlib/core.fk" "%s/core.fk"))\n' "$SRCDIR" > "$SRCDIR/drv.fk"
form-kernel-go/bin-go form-stdlib/json.fk form-stdlib/cache.fk \
  form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk "$SRCDIR/drv.fk" >/dev/null 2>&1

TEST="$SRCDIR/application-graph-live-db.fk"
sed "s|PG_DSN_PLACEHOLDER|${PG_DSN}|" form-stdlib/integration/application-graph-live-db.fk > "$TEST"

OUT="$("$RS_BIN" "$SRCDIR/core.fk" form-stdlib/application-graph-node-port.fk "$TEST" 2>&1 | tail -1)"
echo "verdict: $OUT"
if [[ "$OUT" == "1111111" ]]; then
  echo "application graph live DB: PASS — Form-native mutable graph writes executed and read back in throwaway Postgres."
  exit 0
else
  echo "application graph live DB: FAIL — expected 1111111." >&2
  exit 1
fi
