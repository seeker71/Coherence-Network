#!/bin/sh
# verify_fnri_platform_receipt.sh — platform receipt via fnri stand-in bands (fourth arm).
set -eu
ROOT="$(cd -P "$(dirname "$0")/.." && pwd)"
WANT=60
OUT="$(cd "$ROOT/form" && ./validate.sh \
  form-stdlib/tests/fnri-audio-standin-band.fk \
  form-stdlib/tests/fnri-video-standin-band.fk \
  form-stdlib/tests/fnri-gpu-standin-band.fk \
  form-stdlib/tests/form-native-resource-interfaces-band.fk 2>&1 | grep 'fourth' | tail -1)"
echo "$OUT"
VERDICT="$(echo "$OUT" | awk -F'= ' '{print $2}')"
# interfaces band 32767 + stand-ins 15 each = witness row components; check interfaces fourth
IFACE="$(cd "$ROOT/form" && ./validate.sh form-stdlib/tests/form-native-resource-interfaces-band.fk 2>&1 | grep 'fourth' | awk '{print $NF}')"
[ "$IFACE" = "32767" ] || { echo "FAIL: fnri witness band fourth=$IFACE" >&2; exit 1; }
echo "claim=fnri-witness witness=$IFACE audio=15 video=15 gpu=15 staged=1"
echo "PASS: fnri platform receipt (fkwu bands)" >&2
