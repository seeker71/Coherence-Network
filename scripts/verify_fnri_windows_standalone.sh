#!/bin/sh
# verify_fnri_windows_standalone.sh — platform receipt row (windows on CI/host, mac cross-check locally).
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
case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin)
    if [ -x "${FORM_CLI:-$ROOT/form/form-cli}" ]; then
      "$ROOT/scripts/verify_fsh_fnri_bootstrap.sh" >/dev/null || { echo "FAIL: bootstrap receipt" >&2; exit 1; }
      "$ROOT/scripts/verify_fnri_mac_binary_dispatch.sh" >/dev/null || exit 1
    else
      echo "skip: mac binary dispatch absent; fkwu/FNRI floor proved above" >&2
    fi
    PLATFORM=mac
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows*)
    # The Windows workflow proves native form-cli in the next step. This step is
    # the standalone fkwu/FNRI floor and must not require form/form-cli first.
    PLATFORM=windows
    ;;
  *)
    PLATFORM=unknown
    ;;
esac
printf '{"claim":"fnri-witness","platform":"%s","carrier":"form-cli","witness":%s}\n' "$PLATFORM" "$WANT"
