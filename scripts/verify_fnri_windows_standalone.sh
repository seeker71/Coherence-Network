#!/bin/sh
# Composted: windows fnri receipt via form-cli (validate four-way still via form/validate.sh).
set -eu
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
FORM="$ROOT/form"
WANT=32767
cd "$FORM"
bash ./validate.sh \
  form-stdlib/core.fk form-stdlib/resource-port.fk \
  form-stdlib/bml-native-interface-package-import.fk form-stdlib/hati-os-targets.fk \
  form-stdlib/form-native-resource-interfaces.fk \
  form-stdlib/tests/form-native-resource-interfaces-band.fk \
  | tee fnri-platform.out
grep -q '0 divergent' fnri-platform.out || { echo "FAIL: kernels diverged" >&2; exit 1; }
grep -q "$WANT" fnri-platform.out || { echo "FAIL: missing $WANT" >&2; exit 1; }
"$ROOT/scripts/fnri_fkwu_witness.sh" || exit 1
"$ROOT/scripts/verify_fsh_fnri_bootstrap.sh" >/dev/null || { echo "FAIL: bootstrap receipt" >&2; exit 1; }
printf '{"claim":"fnri-witness","platform":"windows","carrier":"form-cli","witness":%s}\n' "$WANT"
