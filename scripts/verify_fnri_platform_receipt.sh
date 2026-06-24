#!/usr/bin/env bash
# verify_fnri_platform_receipt.sh — standard-receipt row for fnri on THIS host.
#
# Observes what is runnable here (mac/linux): four-way validate, fkwu_run witness,
# and form-cli fnri when the binary is present. Emits honest JSON per
# docs/coherence-substrate/standard-receipt.form.
#
# Windows: run via windows-host.yml + verify_fnri_windows_standalone.sh (CI).
# Android: run verify_fnri_android_receipt.sh on a machine with adb + device.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
WANT=32767
PLATFORM="$(uname -s 2>/dev/null || echo unknown)"
ARCH="$(uname -m 2>/dev/null || echo unknown)"

fail() { echo "FAIL: $1" >&2; exit 1; }
note() { echo "  $1" >&2; }

note "fnri platform receipt on $PLATFORM $ARCH"

cd "$FORM"
bash ./validate.sh \
  form-stdlib/core.fk \
  form-stdlib/resource-port.fk \
  form-stdlib/bml-native-interface-package-import.fk \
  form-stdlib/hati-os-targets.fk \
  form-stdlib/form-native-resource-interfaces.fk \
  form-stdlib/tests/form-native-resource-interfaces-band.fk \
  | tee /tmp/fnri-platform-validate.out
grep -q '0 divergent' /tmp/fnri-platform-validate.out || fail "validate diverged"
grep -q "$WANT" /tmp/fnri-platform-validate.out || fail "validate missing $WANT"

bash "$ROOT/scripts/fnri_fkwu_witness.sh" >/tmp/fnri-fkwu-witness.out 2>&1 || fail "fkwu_run witness"
grep -q "PASS: fnri fkwu witness $WANT" /tmp/fnri-fkwu-witness.out || fail "fkwu_run witness text"

CLI_STATUS="pending"
if [ -x "$FORM/form-cli" ]; then
  if printf 'fnri\n' | env PATH="/usr/bin:/bin" "$FORM/form-cli" 2>/dev/null | grep -q 'runtime=fkwu'; then
    CLI_STATUS="observed"
  fi
fi

case "$PLATFORM" in
  Darwin) ROW="mac" ;;
  MINGW*|MSYS*|CYGWIN*) ROW="windows" ;;
  Linux) ROW="android-or-linux" ;;
  *) ROW="unknown" ;;
esac

printf '{"claim":"fnri-witness","template":"docs/coherence-substrate/standard-receipt.form","body":"yes","witness":%s,"c_bootstrap":"pending-or-partial","toolchain_free_runtime":"observed-on-host","platforms":{"%s":"observed","windows":"ci-via-windows-host.yml","android":"device-via-verify_fnri_android_receipt.sh"},"form_cli_fnri":"%s","host":"%s %s"}\n' \
  "$WANT" "$ROW" "$CLI_STATUS" "$PLATFORM" "$ARCH"

note "PASS: fnri platform receipt observed on $PLATFORM ($ROW row)"
