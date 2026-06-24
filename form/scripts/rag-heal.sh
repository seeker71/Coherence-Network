#!/usr/bin/env bash
# rag-heal.sh — sovereign RAG index heal via Form (rh-heal-merge), zero Python.
#
# Form shell surface: rag-heal.fsh + fsh-rag-heal-main.fk (native `rag-heal` verb).
# This script runs the heal gate on the bootstrap Go kernel today (bin-go walks
# the same Form recipes); fkwu is the named runtime target once heal bands flatten
# on the fourth arm like fs-list-band.
#
#   form/scripts/rag-heal.sh [index-path]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FORM="$ROOT/form"
INDEX="${1:-$HOME/.coherence-network/rag-index/index.jsonl}"
mkdir -p "$(dirname "$INDEX")"

cd "$FORM"
GO_BIN="${GO_BIN:-form-kernel-go/bin-go}"
[[ -x "$GO_BIN" ]] || (cd form-kernel-go && go build -o bin-go .)

# BML source compile cache (same chain as validate.sh).
SOURCE_CACHE_DIR="form-stdlib/.cache/source-compiled"
mkdir -p "$SOURCE_CACHE_DIR"
compiler_chain=(
    form-stdlib/form-ontology-loader.fk form-stdlib/line-grammar.fk
    form-stdlib/bmf-core.fk form-stdlib/bmf-grammar.fk form-stdlib/bml.fk
    form-stdlib/bml-source.fk form-stdlib/source-compiler.fk
    form-stdlib/grammars/form-bml.fk form-stdlib/form-bml-lower.fk
)
form_hash16() {
    if command -v shasum >/dev/null 2>&1; then cat "$@" | shasum | cut -c1-16
    else cat "$@" | cksum | cut -c1-16; fi
}
compiler_stamp="$(form_hash16 "${compiler_chain[@]}" "$GO_BIN")"
source_compile_dir="$(mktemp -d "${TMPDIR:-/tmp}/form-rag-heal.XXXXXX")"
trap 'rm -rf "$source_compile_dir"' EXIT

prepare_one() {
    local src="$1" key cached out driver
    if grep -Eq '^[[:space:]]*section \[' "$src"; then
        key="$(form_hash16 "$src")-$compiler_stamp"
        cached="$SOURCE_CACHE_DIR/$key.fk"
        if [[ ! -s "$cached" ]]; then
            out="$(mktemp "$SOURCE_CACHE_DIR/.${key}.XXXXXX")"
            driver="$(mktemp "$source_compile_dir/compile.XXXXXX")"
            printf '(do (form-source-compile-file "%s" "%s"))\n' "$src" "$out" > "$driver"
            if "$GO_BIN" "${compiler_chain[@]}" "$driver" >/dev/null && [[ -s "$out" ]]; then
                mv -f "$out" "$cached"
            else
                rm -f "$out" "$driver"
                echo "$src"
                return
            fi
            rm -f "$driver"
        fi
        echo "$cached"
    else
        echo "$src"
    fi
}

RAG_PRELUDES=(
    form-stdlib/core.fk
    form-stdlib/adler32.fk
    form-stdlib/rag-key.fk
    form-stdlib/rag-freshness.fk
    form-stdlib/text-tokenize.fk
    form-stdlib/rag-embed.fk
    form-stdlib/rag-index-codec.fk
    form-stdlib/rag-heal.fk
    form-stdlib/rag-heal-shell.fk
)

prepared=()
for f in "${RAG_PRELUDES[@]}"; do
    prepared+=("$(prepare_one "$f")")
done

gate="$(mktemp "$source_compile_dir/gate.XXXXXX.fk")"
printf '(do (print (rh-shell-heal "%s" "%s")))\n' "$INDEX" "$ROOT" > "$gate"

# Form-native heal (bootstrap bin-go carrier; logic in rag-heal.fk).
out="$("$GO_BIN" "${prepared[@]}" "$gate" 2>/dev/null | sed '/^null$/d' | head -1)"
echo "[rag] form-shell heal -> ${out:-done} (index: $INDEX)"
