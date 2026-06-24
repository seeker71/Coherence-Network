#!/usr/bin/env bash
# form_fs_fkwu_receipt.sh — toolchain-free RUN receipt for form-fs on fkwu.
#
# Standard-receipt shape (docs/coherence-substrate/standard-receipt.form):
#   body:         form-fs.fk + form-fs-band.fk on the universal walker
#   c-bootstrap:  pending at BUILD (fkwu from bootstrap uni.c; T_flat selfhost when committed)
#   toolchain-free at RUN: yes — ./fkwu <table> 0 after cache is warm; flatten uses T_flat when present
#
# Usage: scripts/form_fs_fkwu_receipt.sh
# Exit 0 when verdict is 16383 on fkwu; prints JSON receipt line on stdout.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
CACHE="$FORM/form-stdlib/.cache/fourth"
VERDICT_EXPECT=16383

# BUILD lane (one-time cache): Go flattens + clang compiles fkwu — honest floor, not receipt bar.
if command -v go >/dev/null 2>&1; then
  ( cd "$FORM/form-kernel-go" && go build -o bin-go . ) >/dev/null 2>&1 || true
fi
export GO_BIN="$FORM/form-kernel-go/bin-go"
export TMPDIR="${TMPDIR:-/tmp}"

cd "$FORM" || exit 2
# shellcheck disable=SC1091
set +u; . scripts/fourth-arm.sh; set -u
build_fourth
stem=form-fs
tbl="$(fourth_table "$stem")"
[[ -n "$FKWU" && -x "$FKWU" && -s "$tbl" ]] || {
  echo '{"status":"blocked","reason":"fkwu-or-table-missing","honest_floor":"build needs go+clang once"}' 
  exit 3
}

# RUN lane — no Go/Rust/TS/clang in this subprocess tree.
out="$("$FKWU" "$tbl" 0 2>/dev/null | head -1 | tr -d '[:space:]')"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u)"
if [[ "$out" == "$VERDICT_EXPECT" ]]; then
  printf '{"status":"pass","band":"form-fs","verdict":%s,"expected":%s,"runner":"fkwu","toolchain_free_run":true,"c_bootstrap_build":"pending","ts":"%s","fkwu":"%s","table":"%s"}\n' \
    "$out" "$VERDICT_EXPECT" "$ts" "$FKWU" "$tbl"
  exit 0
fi
printf '{"status":"fail","band":"form-fs","verdict":"%s","expected":%s,"runner":"fkwu","toolchain_free_run":true,"c_bootstrap_build":"pending","ts":"%s"}\n' \
  "${out:-null}" "$VERDICT_EXPECT" "$ts"
exit 1
