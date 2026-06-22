#!/usr/bin/env bash
# fkwu_run.sh — run a Form recipe on the 4th kernel (fkwu) with a staged-input bundle.
#
# The native-entry lane, done right: a recipe is flattened ONCE into an fkwu node-table (content-cached),
# and fkwu — the universal walker emitted from Form and compiled native from C, NO Go/Rust/Python in its
# runtime path — executes it, reading the staged bundle through input_byte (the same channel fkwu fills
# from argv[3]). Data crosses as data; the carrier never synthesizes Form source. Go (bin-go) appears
# only as the build-time FLATTENER, never in the run.
#
# Usage:  fkwu_run.sh <bundle-file> <module.fk>... <band.fk>
#   modules are preludes (loaded as function rows); the LAST .fk is the band whose final expr runs.
#   the bundle file's bytes are staged into input_byte (NUL-terminated read).
# Prints the band's output. Builds fkwu on first use (cached). Exit 3 if the lane can't be built here.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/form" || exit 3
export GO_BIN="$ROOT/form/form-kernel-go/bin-go"; export TMPDIR="${TMPDIR:-/tmp}"
[ -x "$GO_BIN" ] || ( cd form-kernel-go && go build -o bin-go . ) >/dev/null 2>&1 || true

BUNDLE="${1:?bundle file}"; shift
RECIPES=("$@"); [ "${#RECIPES[@]}" -ge 1 ] || { echo "need at least one recipe"; exit 2; }

# the fourth-arm lane tooling owns build_fourth + the flatten driver shape
# shellcheck disable=SC1091
set +u; . scripts/fourth-arm.sh; set -u
command -v clang >/dev/null 2>&1 || { echo "fkwu lane needs clang (the C bootstrap); not present"; exit 3; }
build_fourth >/dev/null 2>&1
FKWU=""; for f in form-stdlib/.cache/fourth/fkwu-*; do [ -x "$f" ] && FKWU="$f"; done
[ -n "$FKWU" ] || { echo "fkwu did not build — lane unavailable"; exit 3; }

# flatten the recipe list to a node-table, cached by recipe + flattener content
key="$( { cat "${RECIPES[@]}" "${FOURTH_CHAIN[@]}" "$GO_BIN"; } 2>/dev/null | { command -v sha256sum >/dev/null 2>&1 && sha256sum || shasum; } | cut -c1-16)"
TBL="form-stdlib/.cache/fourth/run-$key.txt"
if [ ! -s "$TBL" ]; then
    last="${RECIPES[$((${#RECIPES[@]}-1))]}"; mods=("${RECIPES[@]:0:$((${#RECIPES[@]}-1))}")
    modexpr=" (read_file \"$FOURTH_SHIM\")"; for m in "${mods[@]}"; do modexpr="$modexpr (read_file \"$m\")"; done
    d="$(mktemp -d)"; cat "${FOURTH_CHAIN[@]}" > "$d/driver.fk"
    printf '(print (fks-table-file (flt-band-sources-fns (list%s) (read_file "%s")) (flt-band-sources-pool (list%s) (read_file "%s"))))\n' \
        "$modexpr" "$last" "$modexpr" "$last" >> "$d/driver.fk"
    "$GO_BIN" "$d/driver.fk" 2>/dev/null > "$TBL.tmp" && mv -f "$TBL.tmp" "$TBL" || { rm -f "$TBL.tmp"; rm -rf "$d"; echo "flatten failed"; exit 1; }
    rm -rf "$d"
fi

exec "$FKWU" "$TBL" 0 "$BUNDLE"
