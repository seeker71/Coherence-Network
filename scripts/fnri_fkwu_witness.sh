#!/usr/bin/env bash
# fnri_fkwu_witness.sh — lightweight fkwu_run.sh witness for form-native resource interfaces.
#
# Complements scripts/verify_form_native_sovereignty.sh (full standard-receipt loop with
# toolchain-free PATH). This script only exercises the fkwu_run.sh flatten lane.
#
# Exit 0 when witness verdict is 32767 and resolve/know lines match.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXPECTED=32767

echo "== fnri fkwu_run witness (runtime: fkwu only) =="
FKWU_VERDICT="$(bash "$ROOT/scripts/fkwu_fnri.sh" witness)"
echo "fkwu_fnri witness -> $FKWU_VERDICT"
if [ "$FKWU_VERDICT" != "$EXPECTED" ]; then
  echo "FAIL: expected fkwu witness $EXPECTED, got $FKWU_VERDICT" >&2
  exit 1
fi

RESOLVE="$(bash "$ROOT/scripts/fkwu_fnri.sh" resolve macos-arm64 host:process)"
echo "fkwu_fnri resolve macos-arm64 host:process -> $RESOLVE"
case "$RESOLVE" in
  macos-arm64\|host:process\|libproc+sysctl+proc_pidinfo\|read_file\|filesystem) ;;
  *) echo "FAIL: unexpected resolve line: $RESOLVE" >&2; exit 1 ;;
esac

KNOW="$(bash "$ROOT/scripts/fkwu_fnri.sh" know standard-receipt)"
echo "fkwu_fnri know standard-receipt -> $KNOW"
[ "$KNOW" = "docs/coherence-substrate/standard-receipt.form" ] || {
  echo "FAIL: unexpected knowledge path: $KNOW" >&2; exit 1
}

if [ -x "$ROOT/scripts/verify_form_native_sovereignty.sh" ]; then
  echo "== standard-receipt sovereignty verify (optional full loop) =="
  if SOVEREIGNTY_ALLOW_BOOTSTRAP="${SOVEREIGNTY_ALLOW_BOOTSTRAP:-0}" \
     bash "$ROOT/scripts/verify_form_native_sovereignty.sh" 2>&1; then
    echo "sovereignty verify: PASS"
  else
    echo "SKIP/FAIL: sovereignty verify — warm caches with SOVEREIGNTY_ALLOW_BOOTSTRAP=1 or validate.sh" >&2
  fi
fi

echo "PASS: fnri fkwu witness $EXPECTED"
