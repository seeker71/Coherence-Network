#!/usr/bin/env bash
#
# pyfkb-run.sh — run a Python file through the Form-native BMF pipeline and
# (optionally) diff its result against CPython. The dogfooding harness for the
# "API code → Form-native execution" goal.
#
# The pipeline is Form-on-kernel, NO Python runtime in the path:
#   .py  →  python-bmf.fk scanner+grammar  →  python-bmf-lift.fk (→ PY-BMF-*
#           recipes)  →  python-bmf-eval.fk (walk to a value)
# driven by a native kernel binary (Rust by default for the current rotation).
#
# Usage:
#   pyfkb-run.sh <file.py>            # print the Form-native result
#   pyfkb-run.sh --parity <file.py>   # run Form-native AND CPython, diff
#   pyfkb-run.sh --kernel go <file.py>
#
# Exit code: 0 on success (and, with --parity, on match); 1 on mismatch/error.
#
# Section preludes (core.fk, compiler.fk, grammars/python-bmf.fk) are authored
# in the BML maintenance dialect, so they are source-compiled via
# form-source-compile-file before the kernel walks them — the same dance
# validate.sh does.
set -euo pipefail

KERNEL="rust"
PARITY=0
while [[ "${1:-}" == --* ]]; do
  case "$1" in
    --parity) PARITY=1; shift ;;
    --kernel) KERNEL="$2"; shift 2 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

PY="${1:?usage: pyfkb-run.sh [--parity] [--kernel rust|go] <file.py>}"
FORMDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$FORMDIR"

GO_BIN="form-kernel-go/bin-go"
RUST_BIN="form-kernel-rust/target/release/form-kernel-rust"
COMPILER_BIN="$RUST_BIN"

# The prelude chain (matches python-bmf-lift-band.fk's header).
PRELUDES=(
  form-stdlib/core.fk
  form-stdlib/json.fk
  form-stdlib/cache.fk
  form-stdlib/form-ontology-loader.fk
  form-stdlib/engine.fk
  form-stdlib/compiler.fk
  form-stdlib/source-compiler.fk
  form-stdlib/grammars/python-bmf.fk
  form-stdlib/python-bmf-eval.fk
  form-stdlib/python-bmf-lift.fk
)

SRCDIR="$(mktemp -d "${TMPDIR:-/tmp}/pyfkb.XXXXXX")"
trap 'rm -rf "$SRCDIR"' EXIT

# Source-compile any prelude that is a BML `section [` file; pass sexpr files
# through unchanged. Build the prepared arg list.
PREPARED=()
for src in "${PRELUDES[@]}"; do
  if grep -Eq '^[[:space:]]*section \[' "$src" 2>/dev/null; then
    safe="${src//\//__}"
    out="$SRCDIR/$safe"
    drv="$SRCDIR/compile-$safe.fk"
    printf '(do (form-source-compile-file "%s" "%s"))\n' "$src" "$out" > "$drv"
    "$COMPILER_BIN" form-stdlib/json.fk form-stdlib/cache.fk \
      form-stdlib/form-ontology-loader.fk form-stdlib/source-compiler.fk \
      "$drv" >/dev/null
    PREPARED+=("$out")
  else
    PREPARED+=("$src")
  fi
done

# Driver: run the target .py through py-bmf-run-text and print its value.
# We read the file and embed it as a Form string literal (escaping \ and ")
# rather than py-bmf-run-file, because the file-scan path
# (python-source-scan-file) currently diverges from the text path — the text
# path is the proven one the band tests exercise. (Aligning scan-file with
# scan-text is a separate, tracked fix.)
DRIVER="$SRCDIR/driver.fk"
{
  printf '(py-bmf-run-text "'
  # escape backslashes and double-quotes; keep real newlines (Form string
  # literals span lines, as the band tests do)
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' "$PY"
  printf '")\n'
} > "$DRIVER"

run_kernel() {
  case "$1" in
    go)   "$GO_BIN" "${PREPARED[@]}" "$DRIVER" 2>/dev/null ;;
    rust) "$RUST_BIN" "${PREPARED[@]}" "$DRIVER" 2>/dev/null ;;
    *) echo "unknown kernel: $1" >&2; exit 2 ;;
  esac
}

FORM_OUT="$(run_kernel "$KERNEL" | tail -1)"

if [[ "$PARITY" -eq 1 ]]; then
  CPY_OUT="$(python3 "$PY" 2>/dev/null | tail -1)"
  echo "form($KERNEL): $FORM_OUT"
  echo "cpython:      $CPY_OUT"
  if [[ "$FORM_OUT" == "$CPY_OUT" ]]; then
    echo "PARITY: match"
  else
    echo "PARITY: MISMATCH"
    exit 1
  fi
else
  echo "$FORM_OUT"
fi
