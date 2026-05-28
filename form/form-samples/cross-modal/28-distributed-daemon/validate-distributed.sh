#!/usr/bin/env bash
# validate-distributed.sh — three-way sibling parity for the distributed
# daemon walk. Each sibling kernel runs the same orchestration; their
# stdouts must be byte-identical.
#
# Usage:
#   ./validate-distributed.sh
#
# This walk is not a single-.fk-file workload, so the canonical
# validate.sh in form/ doesn't apply directly — orchestration is what's
# under test. The shape here mirrors validate.sh's run_siblings:
#   - capture each sibling's full stdout,
#   - compare byte-exact,
#   - report pass/fail with the diff if any.
#
# Exits 0 on parity, 1 on divergence.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORM_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

GO_BIN="$FORM_DIR/form-kernel-go/bin-go"
RS_BIN="$FORM_DIR/form-kernel-rust/target/release/form-kernel-rust"
TS_LOADER="$FORM_DIR/form-kernel-ts/node_modules/tsx/dist/loader.mjs"
TS_MAIN="$FORM_DIR/form-kernel-ts/src/main.ts"

for required in "$GO_BIN" "$RS_BIN" "$TS_LOADER" "$TS_MAIN"; do
    if [[ ! -e "$required" ]]; then
        echo "missing kernel artifact: $required" >&2
        echo "build the kernels from form/ first (validate.sh handles this)." >&2
        exit 2
    fi
done

GO_OUT="$(mktemp)"
RS_OUT="$(mktemp)"
TS_OUT="$(mktemp)"
trap 'rm -f "$GO_OUT" "$RS_OUT" "$TS_OUT"' EXIT

echo "running orchestrate.sh through three sibling kernels..."

"$SCRIPT_DIR/orchestrate.sh" "$GO_BIN" > "$GO_OUT" 2>&1
go_status=$?
echo "  go     exit=$go_status"

"$SCRIPT_DIR/orchestrate.sh" "$RS_BIN" > "$RS_OUT" 2>&1
rs_status=$?
echo "  rust   exit=$rs_status"

"$SCRIPT_DIR/orchestrate.sh" node --stack_size=262144 \
    --import "$TS_LOADER" "$TS_MAIN" > "$TS_OUT" 2>&1
ts_status=$?
echo "  ts     exit=$ts_status"

if [[ $go_status -ne 0 || $rs_status -ne 0 || $ts_status -ne 0 ]]; then
    echo ""
    echo "  ✗  at least one kernel exited non-zero — sibling parity not reached."
    echo "  go output:"
    sed 's/^/    /' "$GO_OUT"
    echo "  rust output:"
    sed 's/^/    /' "$RS_OUT"
    echo "  ts output:"
    sed 's/^/    /' "$TS_OUT"
    exit 1
fi

if diff -q "$GO_OUT" "$RS_OUT" >/dev/null && diff -q "$GO_OUT" "$TS_OUT" >/dev/null; then
    echo ""
    echo "  ✓  3-way sibling parity — go == rust == ts (byte-identical)."
    echo ""
    sed 's/^/    /' "$GO_OUT"
    exit 0
fi

echo ""
echo "  ✗  kernels disagree. Investigate which is correct."
echo ""
echo "  go vs rust:"
diff "$GO_OUT" "$RS_OUT" | sed 's/^/    /'
echo "  go vs ts:"
diff "$GO_OUT" "$TS_OUT" | sed 's/^/    /'
exit 1
