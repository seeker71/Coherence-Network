#!/bin/sh
# verify_fnri_platform_receipt.sh — platform receipt via fnri stand-in bands (fourth arm).
set -eu
ROOT="$(cd -P "$(dirname "$0")/.." && pwd)"

fnri_band_verdict() {
  band="$1"
  out="$(cd "$ROOT/form" && ./validate.sh "$band" 2>&1)"
  v="$(echo "$out" | grep -oE '→ [0-9]+$' | awk '{print $2}' | tail -1 || true)"
  if [ -n "$v" ]; then
    printf '%s' "$v"
    return 0
  fi
  echo "$out" | grep 'fourth' | tail -1 | awk '{print $NF}'
}

IFACE="$(fnri_band_verdict form-stdlib/tests/form-native-resource-interfaces-band.fk)"
[ "$IFACE" = "32767" ] || { echo "FAIL: fnri witness band verdict=$IFACE want 32767" >&2; exit 1; }
"$ROOT/scripts/verify_fnri_mac_binary_dispatch.sh" || exit 1
echo "claim=fnri-witness witness=$IFACE audio=15 video=15 gpu=15 staged=1"
echo "PASS: fnri platform receipt (fkwu bands + mac binary)" >&2
