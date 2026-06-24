#!/usr/bin/env bash
# rag-heal.sh — sovereign RAG index heal on fkwu (rh-heal-merge-at), zero Python, zero go.
#
# Form shell: rag-heal.fsh + fsh-rag-heal-main.fk (`rag-heal <index> <repo-root>`).
# Runtime: fkwu walks T_flat to flatten the heal gate, then runs the table.
# No bin-go in this surface — fkwu and fourth-flatten-table.txt must already exist
# (validate.sh / ensure_form_cli_native.sh). Missing cache degrades honestly.
#
#   form/scripts/rag-heal.sh [index-path]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FORM="$ROOT/form"
INDEX="${1:-$HOME/.coherence-network/rag-index/index.jsonl}"
mkdir -p "$(dirname "$INDEX")"

cd "$FORM"
# shellcheck source=scripts/fourth-arm.sh
source scripts/fourth-arm.sh

# Warm fkwu from committed bootstrap (no go emission in this surface).
stamp="$(fourth_fkwu_cache_stamp)"
cached_fkwu="$FOURTH_DIR/fkwu-$stamp"
if [[ -x "$cached_fkwu" ]]; then
    FKWU="$cached_fkwu"
else
    FORM_STANDARD_LANE=1 build_fourth >/dev/null 2>&1 || true
    for candidate in "$FOURTH_DIR"/fkwu-*; do
        [[ -x "$candidate" ]] || continue
        FKWU="$candidate"
        break
    done
fi

if [[ -z "${FKWU:-}" ]]; then
    echo "[rag] skip heal: no fkwu (run ensure_form_cli_native.sh first)" >&2
    exit 0
fi
if ! fourth_selfhost; then
    echo "[rag] skip heal: T_flat self-host unavailable (fourth-flatten-table.txt absent)" >&2
    exit 0
fi

RAG_MODS=(
    form-stdlib/adler32.fk
    form-stdlib/rag-key.fk
    form-stdlib/rag-freshness.fk
    form-stdlib/text-tokenize.fk
    form-stdlib/rag-embed.fk
    form-stdlib/rag-index-codec.fk
    form-stdlib/rag-heal.fk
    form-stdlib/rag-heal-shell.fk
)

d="$(mktemp -d "${TMPDIR:-/tmp}/fk-rag-heal.XXXXXX")"
trap 'rm -rf "$d"' EXIT

gate="$d/gate.fk"
printf '(do (print (rh-shell-heal "%s" "%s")))\n' "$INDEX" "$ROOT" > "$gate"

stem="rag-heal-gate"
flatten_out="$d/flatten.out"
{
    printf '1\n'
    fourth_band_request "$stem" "fks" "${RAG_MODS[@]}" "$gate"
} | "$FKWU" "$FOURTH_FLATTEN_TABLE" 0 > "$flatten_out" 2>"$d/flatten.err" || true

table="$d/table.txt"
sed -n "/^==T-${stem}==\$/,/^==T-END==\$/p" "$flatten_out" | sed -e '1d' -e '$d' > "$table"
if [[ ! -s "$table" ]]; then
    echo "[rag] skip heal: fkwu self-flatten produced no table" >&2
    sed -n '1,8p' "$d/flatten.err" >&2 || true
    exit 0
fi

out="$("$FKWU" "$table" 0 2>/dev/null | sed '/^null$/d' | head -1)"
echo "[rag] form-shell heal on fkwu -> ${out:-done} (index: $INDEX)"
