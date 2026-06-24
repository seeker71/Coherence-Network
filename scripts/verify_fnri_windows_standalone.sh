#!/usr/bin/env bash
# verify_fnri_windows_standalone.sh — fnri standard-receipt windows runtime row.
#
# Four-way validate + standalone fkwu on form-native-resource-interfaces (32767).
# Intended for windows-host.yml (Git Bash on windows-latest) and local Git Bash.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
WANT=32767
cd "$FORM"
VALIDATE="$(pwd)/validate.sh"
PRELUDE=(
  form-stdlib/core.fk
  form-stdlib/resource-port.fk
  form-stdlib/bml-native-interface-package-import.fk
  form-stdlib/hati-os-targets.fk
  form-stdlib/form-native-resource-interfaces.fk
  form-stdlib/tests/form-native-resource-interfaces-band.fk
)

bash "$VALIDATE" "${PRELUDE[@]}" | tee fnri-platform.out
grep -q '0 divergent' fnri-platform.out || { echo "FAIL: kernels diverged (fnri)" >&2; exit 1; }
grep -q 'fourth arm: 1 band(s) four-way' fnri-platform.out || { echo "FAIL: fkwu fourth arm missing (fnri)" >&2; exit 1; }
grep -q "$WANT" fnri-platform.out || { echo "FAIL: expected verdict $WANT in validate output" >&2; exit 1; }

FKWU="$(ls form-stdlib/.cache/fourth/fkwu-* 2>/dev/null | head -1)"
[ -n "$FKWU" ] || { echo "FAIL: no fkwu binary in fourth cache" >&2; exit 1; }
T="$(ls form-stdlib/.cache/fourth/t-form-native-resource-interfaces-*.txt 2>/dev/null | head -1)"
[ -n "$T" ] || { echo "FAIL: no flattened table for form-native-resource-interfaces" >&2; exit 1; }

V="$("$FKWU" "$T" 0 2>/dev/null | head -1 | tr -d '[:space:]')"
echo "STANDALONE fkwu: form-native-resource-interfaces => $V (want $WANT)"
[ "$V" = "$WANT" ] || { echo "FAIL: standalone fkwu gave $V, want $WANT" >&2; exit 1; }

printf '{"claim":"fnri-witness","platform":"windows","body":"fkwu","toolchain_free_runtime":"observed","witness":%s,"host":"%s"}\n' \
  "$V" "$(uname -s 2>/dev/null || echo windows) $(uname -m 2>/dev/null || echo unknown)"
echo "FNRI WINDOWS RECEIPT ROW: fkwu standalone $WANT on $(uname -s 2>/dev/null) $(uname -m 2>/dev/null)"
