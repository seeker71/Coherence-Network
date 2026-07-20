#!/usr/bin/env bash
# fkwu_run.sh — enter the c-bootstrapped fkwu runtime.
#
# Production/source lane: `--src` compiles the pinned c-bootstrap when needed,
# prepends the pinned Form stdlib core, and executes source directly. No sibling
# kernel and no flattening enters this lane.
#
# The legacy staged-input/table interface remains below for the non-production
# tools that still consume input_byte bundles while they are lifted. It is not
# selected by form-cli eval or by the API execution bridge.
#
# Usage:
#   fkwu_run.sh --src <module.fk>...
#   fkwu_run.sh <bundle-file> <module.fk>... <band.fk>  # legacy tools only
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "${1:-}" = "--src" ]; then
    shift
    [ "$#" -ge 1 ] || { echo "fkwu_run: --src needs at least one .fk source" >&2; exit 2; }
    runtime_source="$ROOT/form/runtime/fkwu-uni.c"
    runtime_header="$ROOT/form/runtime/fkwu-optable.h"
    [ -f "$runtime_source" ] && [ -f "$runtime_header" ] || {
        echo "fkwu_run: pinned c-bootstrap source is absent from form/runtime" >&2
        exit 3
    }

    if [ -x "$ROOT/form/fkwu" ]; then
        FKWU="$ROOT/form/fkwu"
    else
        cache="$ROOT/form/.cache/fkwu-runtime"
        mkdir -p "$cache" || exit 3
        if command -v shasum >/dev/null 2>&1; then
            stamp="$(shasum -a 256 "$runtime_source" "$runtime_header" | shasum -a 256 | awk '{print substr($1,1,16)}')"
        elif command -v sha256sum >/dev/null 2>&1; then
            stamp="$(sha256sum "$runtime_source" "$runtime_header" | sha256sum | awk '{print substr($1,1,16)}')"
        else
            echo "fkwu_run: need shasum or sha256sum to bind the runtime build" >&2
            exit 3
        fi
        FKWU="$cache/fkwu-$stamp"
        if [ ! -x "$FKWU" ]; then
            compiler="${CC:-cc}"
            command -v "$compiler" >/dev/null 2>&1 || {
                echo "fkwu_run: C bootstrap compiler unavailable: $compiler" >&2
                exit 3
            }
            tmp_bin="$FKWU.$$"
            case "$(uname -s 2>/dev/null || true)" in
                MINGW*|MSYS*|CYGWIN*)
                    "$compiler" -O2 -o "$tmp_bin" "$runtime_source" \
                        -lws2_32 -lwinmm -lavicap32 -luser32 -lwlanapi -lbthprops -lwinhttp || exit 3 ;;
                *) "$compiler" -O2 -o "$tmp_bin" "$runtime_source" || exit 3 ;;
            esac
            chmod +x "$tmp_bin" && mv "$tmp_bin" "$FKWU"
        fi
    fi

    work="$(mktemp -d "${TMPDIR:-/tmp}/fkwu-source.XXXXXXXX")" || exit 3
    source_file="$work/program.fk"
    cleanup_source_run() { rm -rf "$work"; }
    trap cleanup_source_run EXIT HUP INT TERM
    cp "$ROOT/form/form-stdlib/core.fk" "$source_file" || exit 3
    for recipe in "$@"; do
        if [ ! -f "$recipe" ]; then
            echo "fkwu_run: source not found: $recipe" >&2
            exit 2
        fi
        printf '\n' >> "$source_file"
        sed 's/\r$//' "$recipe" >> "$source_file"
    done
    "$FKWU" --src "$source_file"
    exit "$?"
fi

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

if [ -n "${FORM_FKWU_BIN:-}" ] && [ -x "${FORM_FKWU_BIN}" ]; then
    FKWU="${FORM_FKWU_BIN}"
else
    stamp="$(fourth_fkwu_cache_stamp)"
    cached_fkwu="$FOURTH_DIR/fkwu-$stamp"
    if [[ -x "$cached_fkwu" ]]; then
        FKWU="$cached_fkwu"
    else
        FORM_STANDARD_LANE=1 build_fourth >/dev/null 2>&1 || build_fourth >/dev/null 2>&1 || true
    fi
    FKWU=""; for f in form-stdlib/.cache/fourth/fkwu-*; do [ -x "$f" ] && FKWU="$f"; done
fi
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
