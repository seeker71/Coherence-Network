#!/bin/sh
# fnri_fkwu_witness.sh — fnri witness/know proven via form-cli-band (fourth arm 4095).
set -eu
ROOT="$(cd -P "$(dirname "$0")/.." && pwd)"
WANT=4095
OUT="$(cd "$ROOT/form" && ./validate.sh form-stdlib/tests/form-cli-band.fk 2>&1)"
echo "$OUT" | grep -E '4095|fourth|divergent' | tail -3 || true
if echo "$OUT" | grep -qE '(→|fourth.*=)[[:space:]]*4095'; then
  VERDICT=4095
elif echo "$OUT" | grep -q '0 divergent'; then
  VERDICT="$(echo "$OUT" | grep -oE '→ [0-9]+$' | awk '{print $2}' | tail -1)"
else
  VERDICT="$(echo "$OUT" | grep 'fourth' | tail -1 | awk '{print $NF}' || true)"
fi
[ "$VERDICT" = "$WANT" ] || { echo "FAIL: form-cli-band verdict=$VERDICT want $WANT" >&2; exit 1; }
"$ROOT/scripts/verify_fnri_mac_binary_dispatch.sh" >/dev/null || exit 1
echo "PASS: fnri form-cli-band $WANT (fkwu source + mac binary dispatch)"
