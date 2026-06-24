#!/usr/bin/env bash
# fkwu_awk.sh — run a native awk query over a file ON FKWU (the c-bootstrap
# universal kernel), no host awk and no read_file in the compute loop. The live
# sovereign replacement for `awk '<prog>' <file>`: the file is staged into fkwu's
# input_byte door (it carries no read_file — host file reads are a standing wall),
# the awk program rides on the first staged line, and sh-bi-awk (the four-way
# native awk) computes per line. The verb's logic runs on the sovereign kernel;
# the host carrier only reads the file's bytes and stages them.
#
# Usage:  fkwu_awk.sh <file> '<awk-program>'
#   e.g.  fkwu_awk.sh form/fourth-arm-bands.txt '$1=="shell-awk"{print $3}'   -> 127
#
# First breath: single-value field queries (the verdict is the first stdout line;
# fkwu appends its arm/JIT profile after). The native awk covers {print $N} /
# $N==RHS / $N==RHS{print $M}; richer programs grow with sh-bi-awk. Needs clang +
# the Go flattener once (the fkwu lane); exits 3 if the lane can't build here.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILE="${1:?usage: fkwu_awk.sh <file> '<awk-program>'}"
PROG="${2:?usage: fkwu_awk.sh <file> '<awk-program>'}"
[ -r "$FILE" ] || { echo "fkwu_awk: cannot read file: $FILE" >&2; exit 2; }

# stage: the awk program on line 0, then the file's lines (the carrier's only host
# act is reading the bytes; the compute is fkwu-native).
bundle="$(mktemp "${TMPDIR:-/tmp}/fkwu-awk.XXXXXX")"
trap 'rm -f "$bundle"' EXIT
{ printf '%s\n' "$PROG"; cat "$FILE"; } > "$bundle"

# the shell-grammar preludes (s-expr; the shim mirrors core.fk, which the lane drops)
PRELUDES=(
  form-stdlib/input-stream.fk
  form-stdlib/form-ontology-loader.fk form-stdlib/line-grammar.fk form-stdlib/bmf-core.fk
  form-stdlib/bmf-grammar.fk form-stdlib/grammar-loader.fk form-stdlib/shell-grammar.fk
  form-stdlib/voice-traits.fk form-stdlib/feature-vector.fk form-stdlib/nearest-shape.fk
  form-stdlib/voice-diarize.fk form-stdlib/shell-exec.fk
)
# the verdict is the first stdout line (fkwu prints the value, then its arm profile)
bash "$ROOT/scripts/fkwu_run.sh" "$bundle" "${PRELUDES[@]}" form-stdlib/fkwu-awk.fk 2>/dev/null | head -1
