#!/usr/bin/env bash
# fkwu_run.sh — run a Form recipe on the 4th kernel (fkwu) with a staged-input bundle.
#
# Native-entry lane: flatten via fkwu+T_flat when warm (no bin-go on this surface).
# Maintainer regen when T_flat is absent: scripts/regen_form_cli_bootstrap.sh (off-receipt).
#
# Usage:  fkwu_run.sh <bundle-file> <module.fk>... <band.fk>
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/form" || exit 3
export TMPDIR="${TMPDIR:-/tmp}"

BUNDLE="${1:?bundle file}"; shift
RECIPES=("$@"); [ "${#RECIPES[@]}" -ge 1 ] || { echo "need at least one recipe"; exit 2; }

resolve_path() {
    local p="$1"
    if [ -e "$p" ]; then printf '%s\n' "$p"; return 0; fi
    if [ -e "${p#form/}" ]; then printf '%s\n' "${p#form/}"; return 0; fi
    if [ -e "$ROOT/$p" ]; then printf '%s\n' "$ROOT/$p"; return 0; fi
    echo "fkwu_run: file not found: $p  (paths are relative to form/ or the repo root)" >&2
    return 1
}
BUNDLE="$(resolve_path "$BUNDLE")" || exit 2
_resolved=()
for r in "${RECIPES[@]}"; do
    case "$r" in */core.fk|core.fk) echo "fkwu_run: dropping core.fk (the shim mirrors it)" >&2; continue;; esac
    rp="$(resolve_path "$r")" || exit 2
    _resolved+=("$rp")
done
RECIPES=("${_resolved[@]}")
[ "${#RECIPES[@]}" -ge 1 ] || { echo "need at least one recipe (after dropping core.fk)"; exit 2; }

# shellcheck disable=SC1091
set +u; . scripts/fourth-arm.sh; set -u

stamp="$(fourth_fkwu_cache_stamp)"
cached_fkwu="$FOURTH_DIR/fkwu-$stamp"
if [[ -x "$cached_fkwu" ]]; then
    FKWU="$cached_fkwu"
else
    FORM_STANDARD_LANE=1 build_fourth >/dev/null 2>&1 || build_fourth >/dev/null 2>&1 || true
fi
FKWU=""; for f in form-stdlib/.cache/fourth/fkwu-*; do [ -x "$f" ] && FKWU="$f"; done
[ -n "$FKWU" ] || { echo "fkwu did not build — run ensure_form_cli_native.sh or add bootstrap/fkwu-<platform>"; exit 3; }

key="$(fourth_hash16 "${RECIPES[@]}" "${FOURTH_FLATTEN_CHAIN[@]}" "$FOURTH_FLATTEN_TABLE")"
TBL="form-stdlib/.cache/fourth/run-$key.txt"
if [ ! -s "$TBL" ]; then
    stem="fkwu-run-$key"
    if fourth_selfhost && fourth_flatten_sources "$stem" fks "$TBL" "${RECIPES[@]}"; then
        :
    else
        echo "fkwu_run: flatten unavailable — need fourth-flatten-table.txt (T_flat self-host) or maintainer regen" >&2
        exit 3
    fi
fi

exec "$FKWU" "$TBL" 0 "$BUNDLE"
