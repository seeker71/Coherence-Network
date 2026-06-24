#!/usr/bin/env bash
# regen_fkwu_bootstrap.sh — maintainer-only: emit form-stdlib/bootstrap/fkwu-uni.c via bin-go.
# The standard lane uses the committed C artifact; this script runs when FOURTH_EMIT_CHAIN changes.
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
GB="$FORM/form-kernel-go/bin-go"
[[ -x "$GB" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
cd "$FORM"
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh
export GO_BIN="$GB"
mkdir -p form-stdlib/bootstrap
d="$(mktemp -d)"
echo '(fkc-emit-universal)' > "$d/emit.fk"
"$GB" "${FOURTH_EMIT_CHAIN[@]}" "$d/emit.fk" > form-stdlib/bootstrap/fkwu-uni.c 2>"$d/uni.err"
[[ -s form-stdlib/bootstrap/fkwu-uni.c ]] || { sed -n '1,12p' "$d/uni.err" >&2; rm -rf "$d"; exit 1; }
fourth_emit_chain_stamp > form-stdlib/bootstrap/fkwu-uni.stamp
rm -rf "$d"
echo "regen: form-stdlib/bootstrap/fkwu-uni.c ($(wc -c < form-stdlib/bootstrap/fkwu-uni.c | tr -d ' ') bytes) stamp=$(cat form-stdlib/bootstrap/fkwu-uni.stamp)"
