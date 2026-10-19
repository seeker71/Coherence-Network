#!/usr/bin/env bash
# fkwu_run.sh — enter the c-bootstrapped fkwu runtime.
#
# Production/source lane: `--src` compiles the pinned c-bootstrap when needed,
# prepends the pinned Form stdlib core, and enters fkwu's Form/BML source door.
# The native entry owns grammar discovery and JIT execution; no sibling kernel
# or separate flattening path enters this lane.
#
# Usage:
#   fkwu_run.sh --src <module.fk>...
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM_SOURCE_ROOT="$ROOT/form"
[ -d "$FORM_SOURCE_ROOT/form-stdlib" ] || FORM_SOURCE_ROOT="$ROOT/form/form"

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
    cp "$FORM_SOURCE_ROOT/form-stdlib/core.fk" "$source_file" || exit 3
    for recipe in "$@"; do
        if [ ! -f "$recipe" ]; then
            echo "fkwu_run: source not found: $recipe" >&2
            exit 2
        fi
        printf '\n' >> "$source_file"
        sed 's/\r$//' "$recipe" >> "$source_file"
    done
    "$FKWU" "$source_file"
    exit "$?"
fi

echo "fkwu_run: direct --src realization is the only runtime path" >&2
exit 2
