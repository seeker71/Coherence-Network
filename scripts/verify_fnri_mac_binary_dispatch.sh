#!/bin/sh
# verify_fnri_mac_binary_dispatch.sh — mac form-cli binary fnri/receipt dispatch (observed).
set -eu
ROOT="$(cd -P "$(dirname "$0")/.." && pwd)"
WANT_WITNESS=32767
WITNESS="$("$ROOT/scripts/form-cli-run.sh" fnri witness 2>/dev/null | grep -E '^[0-9]+$' | tail -1 || true)"
[ "$WITNESS" = "$WANT_WITNESS" ] || {
  echo "FAIL: form-cli fnri witness=$WITNESS want $WANT_WITNESS" >&2
  exit 1
}
KNOW="$("$ROOT/scripts/form-cli-run.sh" fnri know standard-receipt 2>/dev/null | grep -E '^docs/' | tail -1 || true)"
[ "$KNOW" = "docs/coherence-substrate/standard-receipt.form" ] || {
  echo "FAIL: form-cli fnri know=$KNOW" >&2
  exit 1
}
RECEIPT="$("$ROOT/scripts/form-cli-run.sh" receipt platform 2>/dev/null | grep '^claim=' | tail -1 || true)"
echo "$RECEIPT" | grep -q "witness=$WANT_WITNESS" || {
  echo "FAIL: form-cli receipt platform missing witness=$WANT_WITNESS ($RECEIPT)" >&2
  exit 1
}
echo "PASS: mac form-cli dispatch witness=$WITNESS know=$KNOW" >&2
echo "$RECEIPT"
