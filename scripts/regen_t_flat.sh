#!/usr/bin/env bash
# regen_t_flat.sh — maintainer bootstrap for form-stdlib/fourth-flatten-table.txt
#
# T_flat is the flattened fourth-flatten-driver.fk (fks string-pool table). fkwu
# walks it for self-host band flatten. Must use fks — fkc pool-free tables break
# the driver's read_line / print_str entry (fn-0 no longer runs the driver).
#
# After regen, smoke-tests adler32 marker framing on fkwu before committing.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
GB="$FORM/form-kernel-go/bin-go"
[[ -x "$GB" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
cd "$FORM"
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh
export GO_BIN="$GB"
d="$(mktemp -d)"
trap 'rm -rf "$d"' EXIT
fourth_flatten_expr fks \
  form-stdlib/minimal-surface.fk \
  form-stdlib/hati-os-kernel.fk \
  form-stdlib/fkc-table-serialize.fk \
  form-stdlib/form-parse.fk \
  form-stdlib/form-flatten.fk \
  form-stdlib/fourth-flatten-driver.fk >"$d/expr.fk"
"$GB" "${FOURTH_FLATTEN_CHAIN[@]}" "$d/expr.fk" >"$d/T.txt" 2>"$d/go.err"
[[ -s "$d/T.txt" ]] || { sed -n '1,20p' "$d/go.err" >&2; exit 1; }
build_fourth
srcs=()
while IFS= read -r f; do srcs+=("$f"); done < <(fourth_prep_srcs adler32)
markers="$(
  { printf '1\n'; fourth_band_request adler32 fks "${srcs[@]}"; } \
    | "$FKWU" "$d/T.txt" 0 2>/dev/null | grep -c '^==T-adler32==' || true
)"
[[ "${markers:-0}" -ge 1 ]] || {
  echo "regen_t_flat: fkwu smoke failed — no ==T-adler32== marker (wrong fkc bootstrap?)" >&2
  exit 1
}
mv -f "$d/T.txt" "$FOURTH_FLATTEN_TABLE"
fourth_hash16 "${FOURTH_FLATTEN_CHAIN[@]}" form-stdlib/fourth-flatten-driver.fk >form-stdlib/fourth-flatten-table.stamp
rm -rf form-stdlib/.cache/fourth/t-*.txt 2>/dev/null || true
echo "regen: $FOURTH_FLATTEN_TABLE ($(wc -c <"$FOURTH_FLATTEN_TABLE" | tr -d ' ') bytes) stamp=$(cat form-stdlib/fourth-flatten-table.stamp)"
