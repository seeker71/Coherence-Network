#!/bin/sh
# fnri_fkwu_witness.sh — fnri witness/know proven via form-cli-band (fourth arm 16383).
set -eu
ROOT="$(cd -P "$(dirname "$0")/.." && pwd)"
WANT=16383
OUT="$(cd "$ROOT/form" && ./validate.sh form-stdlib/tests/form-cli-band.fk 2>&1)"
echo "$OUT" | grep -E '16383|fourth|divergent' | tail -3 || true
if echo "$OUT" | grep -qE '(→|fourth.*=)[[:space:]]*16383'; then
  VERDICT=16383
elif echo "$OUT" | grep -q '0 divergent'; then
  VERDICT="$(echo "$OUT" | grep -oE '→ [0-9]+$' | awk '{print $2}' | tail -1)"
else
  VERDICT="$(echo "$OUT" | grep 'fourth' | tail -1 | awk '{print $NF}' || true)"
fi
[ "$VERDICT" = "$WANT" ] || { echo "FAIL: form-cli-band verdict=$VERDICT want $WANT" >&2; exit 1; }
case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin)
    if [ -x "${FORM_CLI:-$ROOT/form/form-cli}" ]; then
      "$ROOT/scripts/verify_fnri_mac_binary_dispatch.sh" >/dev/null || exit 1
      dispatch="mac binary dispatch"
    else
      dispatch="mac binary dispatch skipped: form-cli binary absent"
    fi
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows*)
    dispatch="windows standalone dispatch handled by caller"
    ;;
  *)
    dispatch="no host binary dispatch for this platform"
    ;;
esac
echo "PASS: fnri form-cli-band $WANT (fkwu source + $dispatch)"
