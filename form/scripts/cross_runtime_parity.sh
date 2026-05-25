#!/usr/bin/env bash
# Cross-runtime parity: compare Form-side and Python-side scanner output.
#
# Both runtimes scan the same Python file; we diff the token streams.
# Any divergence shows up as a real difference — that's the first
# cross-runtime proof on the path to a full .fkb-output comparison.
#
# Usage:
#   form/scripts/cross_runtime_parity.sh <python_source_file>

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

PY_SRC="${1:-form/form-kernel-ts/seedbank/python-adapter/examples/python_demo.py}"
WORK_DIR="$REPO_ROOT/form/.cache/cross_runtime"
mkdir -p "$WORK_DIR"

GO_BIN="$REPO_ROOT/form/form-kernel-go/bin-go"
[[ -x "$GO_BIN" ]] || (cd "$REPO_ROOT/form/form-kernel-go" && go build -o bin-go .)

# Source-compile every Form source that uses `section [...]` syntax.
declare -A COMPILED=()
compile_section_file() {
    local src="$1"
    local out="$WORK_DIR/$(basename "$src" .fk).compiled.fk"
    local drv="$WORK_DIR/$(basename "$src" .fk).driver.fk"
    printf '(do (form-source-compile-file "%s" "%s"))\n' "$src" "$out" > "$drv"
    (cd "$REPO_ROOT/form" && "$GO_BIN" "form-stdlib/source-compiler.fk" "$drv" >/dev/null)
    echo "$out"
}

# Match validate.sh's prepare_sources: only files containing
# `^\s*section \[` get source-compiled; everything else loads directly.
prep() {
    local src="$1"
    if grep -Eq '^[[:space:]]*section \[' "$src"; then
        compile_section_file "$src"
    else
        echo "$src"
    fi
}

CORE_R=$(prep "$REPO_ROOT/form/form-stdlib/core.fk")
SRCC_R=$(prep "$REPO_ROOT/form/form-stdlib/source-compiler.fk")
ENGINE_R=$(prep "$REPO_ROOT/form/form-stdlib/engine.fk")
COMPILER_R=$(prep "$REPO_ROOT/form/form-stdlib/compiler.fk")
PYBMF_R=$(prep "$REPO_ROOT/form/form-stdlib/grammars/python-bmf.fk")

SCAN_DRIVER_BODY="$WORK_DIR/scan-driver.fk"
FORM_TOKENS="$WORK_DIR/form_tokens.tsv"
printf '(do (pn-dump-tokens "%s" "%s") 0)\n' "$PY_SRC" "$FORM_TOKENS" > "$SCAN_DRIVER_BODY"

(cd "$REPO_ROOT" && "$GO_BIN" \
    "$CORE_R" \
    "$SRCC_R" \
    "$ENGINE_R" \
    "$COMPILER_R" \
    "$PYBMF_R" \
    "form/form-stdlib/emits/python-bmf-scan-driver.fk" \
    "$SCAN_DRIVER_BODY")

PYTHON_TOKENS="$WORK_DIR/python_tokens.tsv"
python3 -c "
import sys
sys.path.insert(0, '$REPO_ROOT')
from kernels.python_bmf.parser import scan_python_source
text = open('$PY_SRC').read()
atoms = scan_python_source(text, '$PY_SRC', preserve_comments=False)
lines = []
for a in atoms:
    if a.kind in ('py-eof', 'py-blank'):
        # py-blank is a Python-side feature the Form scanner doesn't emit.
        # Excluded from parity comparison; documented as additive enhancement.
        continue
    kind = a.kind
    for suffix in ('-triple-sq', '-triple-dq', '-sq', '-dq'):
        if kind.endswith(suffix):
            kind = kind[: -len(suffix)]
            break
    lines.append(f'{kind}\t{a.value}')
open('$PYTHON_TOKENS', 'w').write('\n'.join(lines) + '\n' if lines else '')
"

echo "Form-side tokens : $(wc -l < "$FORM_TOKENS") lines"
echo "Python tokens    : $(wc -l < "$PYTHON_TOKENS") lines"
echo ""
echo "Diff:"
if diff -u "$FORM_TOKENS" "$PYTHON_TOKENS" > "$WORK_DIR/diff.txt"; then
    echo "  PARITY — both runtimes produce identical token streams."
else
    diff_count=$(grep -cE "^[+-]" "$WORK_DIR/diff.txt" || true)
    echo "  $diff_count divergent lines (see $WORK_DIR/diff.txt)"
    head -30 "$WORK_DIR/diff.txt"
fi
