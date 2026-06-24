#!/bin/sh
# fnri_fkwu_witness.sh — fnri witness/know proven via form-cli-band (fourth arm 4095).
set -eu
ROOT="$(cd -P "$(dirname "$0")/.." && pwd)"
WANT=4095
OUT="$(cd "$ROOT/form" && ./validate.sh form-stdlib/tests/form-cli-band.fk 2>&1 | grep 'fourth' | tail -1 || true)"
echo "$OUT"
VERDICT="$(echo "$OUT" | awk '{print $NF}')"
[ "$VERDICT" = "$WANT" ] || { echo "FAIL: form-cli-band fourth=$VERDICT want $WANT" >&2; exit 1; }
echo "PASS: fnri form-cli-band $WANT (fkwu source)"
