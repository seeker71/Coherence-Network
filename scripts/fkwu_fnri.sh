#!/usr/bin/env bash
# fkwu_fnri.sh — fnri witness/resolve/know on c-bootstrap fkwu via fkwu_run.sh.
#
# Runtime: fkwu + native JIT only (no Go/Rust/clang in the loop). Build-time Go
# flatten runs once when the table cache is cold — same honest floor as fkwu_run.sh.
#
# Usage:
#   fkwu_fnri.sh witness
#   fkwu_fnri.sh resolve <target> <protocol>
#   fkwu_fnri.sh know <slug>
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CMD="${1:?usage: fkwu_fnri.sh witness | resolve <target> <protocol> | know <slug>}"
shift || true

EXPECTED_WITNESS=32767
PRELUDES=(
  form-stdlib/resource-port.fk
  form-stdlib/bml-native-interface-package-import.fk
  form-stdlib/hati-os-targets.fk
  form-stdlib/form-native-resource-interfaces.fk
)

CACHE="$ROOT/form/form-stdlib/.cache/fnri-run"
mkdir -p "$CACHE"
bundle="$(mktemp "${TMPDIR:-/tmp}/fkwu-fnri.XXXXXX")"
trap 'rm -f "$bundle"' EXIT
: >"$bundle"

case "$CMD" in
  witness)
    TMPFK="$CACHE/witness-$$.fk"
    printf '%s\n' '; ephemeral fnri witness band' '(do (fnri-witness-verdict))' >"$TMPFK"
    ;;
  resolve)
    TARGET="${1:?resolve needs target}"; PROTO="${2:?resolve needs protocol}"
    TMPFK="$CACHE/resolve-$$.fk"
    printf '%s\n' '; ephemeral fnri resolve band' "(do (fnri-resolve-line \"$TARGET\" \"$PROTO\"))" >"$TMPFK"
    ;;
  know)
    SLUG="${1:?know needs slug}"
    TMPFK="$CACHE/know-$$.fk"
    printf '%s\n' '; ephemeral fnri know band' "(do (fnri-know-line \"$SLUG\"))" >"$TMPFK"
    ;;
  *) echo "fkwu_fnri: unknown command: $CMD" >&2; exit 2 ;;
esac

REL="${TMPFK#$ROOT/form/}"
out="$(bash "$ROOT/scripts/fkwu_run.sh" "$bundle" "${PRELUDES[@]}" "$REL" 2>/dev/null | head -1)"
rm -f "$TMPFK"
printf '%s\n' "$out"
