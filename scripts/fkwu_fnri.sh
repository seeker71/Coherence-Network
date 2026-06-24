#!/bin/sh
# fkwu_fnri.sh — fnri witness / resolve / know via fkwu (fc-fnri direct, proven source).
set -eu
ROOT="$(cd -P "$(dirname "$0")/.." && pwd)"
CMD="${1:?usage: fkwu_fnri.sh witness | resolve <target> <protocol> | know <slug>}"
shift || true
BUNDLE="$(mktemp "${TMPDIR:-/tmp}/fkwu-fnri.XXXXXX")"
trap 'rm -f "$BUNDLE"' EXIT
case "$CMD" in
  witness) printf 'witness\n' >"$BUNDLE" ;;
  resolve)
    TARGET="${1:?resolve target}"; PROTO="${2:?resolve protocol}"
    printf 'resolve %s %s\n' "$TARGET" "$PROTO" >"$BUNDLE" ;;
  know)
    SLUG="${1:?know slug}"
    printf 'know %s\n' "$SLUG" >"$BUNDLE" ;;
  *) echo "usage: fkwu_fnri.sh witness | resolve <target> <protocol> | know <slug>" >&2; exit 2 ;;
esac
exec "$ROOT/scripts/fkwu_run.sh" "$BUNDLE" \
  form-stdlib/resource-port.fk \
  form-stdlib/bml-native-interface-package-import.fk \
  form-stdlib/hati-os-targets.fk \
  form-stdlib/form-native-resource-interfaces.fk \
  form-stdlib/form-fs.fk \
  form-stdlib/storage-port.fk \
  form-stdlib/host-kernel-carrier.fk \
  form-stdlib/fnri-standin.fk \
  form-stdlib/fnri-receipt.fk \
  form-stdlib/form-cli.fk \
  form-stdlib/tests/fnri-cli-band.fk
