#!/usr/bin/env bash
# build-form-cli.sh — produce the standalone native form-cli binary.
#
# Build-time uses the bootstrap kernel (to flatten form-cli + emit the C) and
# clang (to compile) ONCE. The result — form/form-cli — is self-contained: it
# runs directly with NO Go, NO clang, NO C source, NO table file, nothing but the
# native binary and stdin. The form-cli program is baked into the binary as
# fk_prog (see fkc-emit-combined-repl in form-stdlib/hati-os-kernel-emit.fk).
#
#   ./build-form-cli.sh            # -> form/form-cli
#   echo ping | ./form-cli        # -> pong   (no toolchain present)
#   ./form-cli                     # interactive REPL on a real tty
set -euo pipefail
cd "$(dirname "$0")"

S=form-stdlib
GB=form-kernel-go/bin-go
OUT="${1:-form-cli}"

[[ -x "$GB" ]] || ( echo "building bootstrap kernel..."; cd form-kernel-go && go build -o bin-go . )
command -v clang >/dev/null || { echo "clang is required at BUILD time (not at run time)"; exit 1; }

W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT

# the emit chain (plain Form) + the flatten chain.
EMIT_CHAIN="$S/minimal-surface.fk $S/hati-os-kernel.fk $S/hati-os-kernel-emit.fk"
FLAT_CHAIN="$EMIT_CHAIN $S/form-parse.fk $S/form-flatten.fk"
MODS="(list (read_file \"$S/fourth-shim.fk\") (read_file \"$S/core.fk\") (read_file \"$S/form-cli.fk\"))"
BAND="(read_file \"$S/form-cli-repl.fk\")"

# 1. flatten form-cli-repl into its program table (string pool rides behind it).
echo "(fks-table-file (flt-band-sources-fns $MODS $BAND) (flt-band-sources-pool $MODS $BAND))" > "$W/flatten.fk"
"$GB" $FLAT_CHAIN "$W/flatten.fk" > "$W/table.txt"
[[ -s "$W/table.txt" ]] || { echo "flatten produced no table"; exit 1; }

# 2. emit the combined walker with the table baked in (fk_prog).
printf '(fkc-emit-combined-repl "%s")\n' "$(cat "$W/table.txt")" > "$W/emit.fk"
"$GB" $EMIT_CHAIN "$W/emit.fk" > "$W/form-cli.c"
grep -q fk_prog "$W/form-cli.c" || { echo "emit missing baked program"; exit 1; }

# 3. compile once -> the standalone native binary.
clang -O2 -o "$OUT" "$W/form-cli.c"
echo "built $OUT  ($(wc -c < "$OUT") bytes, self-contained — runs with no Go/clang/table)"
