#!/usr/bin/env bash
# parity_suite.sh — verify that every Python demo runs identically
# through CPython, TS evalPython, and the form-kernel-rust native binary.
#
# The bi-directional execution claim Urs named — "ALL of the current
# python code that is talking to the substrate bi-directionally shall
# be converted into native form code and that shall be the primary
# execution pipeline" — requires three-way parity for every shipped
# Python file. This suite is the regression gate.
#
# Add new files to PARITY_FILES below as they're ripened.
# Run from form/form-kernel-ts/.

set -euo pipefail

PARITY_FILES=(
    "examples/python_demo.py"
    "examples/python_assign_demo.py"
    "examples/python_imperative_demo.py"
    "examples/python_substrate_demo.py"
    "examples/python_range_demo.py"
    "examples/python_builtins_demo.py"
    "examples/python_lambda_demo.py"
    "examples/python_string_demo.py"
    "examples/python_float_demo.py"
    "examples/python_import_demo.py"
)

# Locate the native binary. The script lives at
#   form/form-kernel-ts/seedbank/python-adapter/scripts/parity_suite.sh
# the rust kernel at
#   form/form-kernel-rust/target/release/form-kernel-rust
# → four levels up from `scripts/` (scripts → python-adapter → seedbank
# → form-kernel-ts → form/), then down into form-kernel-rust.
ADAPTER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUST_BIN="$ADAPTER_DIR/../../../form-kernel-rust/target/release/form-kernel-rust"
if [[ ! -x "$RUST_BIN" ]]; then
    echo "error: form-kernel-rust binary not found at $RUST_BIN" >&2
    echo "build it first: cd $ADAPTER_DIR/../../../form-kernel-rust && cargo build --release" >&2
    exit 1
fi
# Always run subcommands from the adapter directory so the relative
# `src/main.ts` path the README documents stays honest.
cd "$ADAPTER_DIR"

PASS=0
FAIL=0

# Each file: ALL three runtimes must produce the same final expression's
# value. The Python files end with a bare expression whose value is the
# "result" — CPython prints it via tail-print trick, the kernel returns
# it from the .fk top-level (do ...) form.
for f in "${PARITY_FILES[@]}"; do
    if [[ ! -f "$f" ]]; then
        echo "  SKIP $f (file missing)"
        continue
    fi
    # CPython: read file, evaluate last expression, print result. Uses
    # a small Python wrapper that captures the final expression's value.
    py_result=$(python3 -c "
import ast
src = open('$f').read()
tree = ast.parse(src)
if tree.body and isinstance(tree.body[-1], ast.Expr):
    last = tree.body[-1]
    body = tree.body[:-1]
    namespace = {}
    if body:
        exec(compile(ast.Module(body=body, type_ignores=[]), '$f', 'exec'), namespace)
    print(eval(compile(ast.Expression(body=last.value), '$f', 'eval'), namespace))
else:
    exec(open('$f').read())
" 2>&1 | tail -1)

    # Compile to .fk and run via native binary.
    fk_path="${f%.py}.fk"
    npx tsx src/main.ts python-compile "$f" "$fk_path" >/dev/null 2>&1
    rust_result=$("$RUST_BIN" "$fk_path" 2>&1 | tail -1)

    # Walk the parsed Python tree through the TS evaluator directly.
    # Distinct path from python-run (which shells to the Rust binary)
    # — this is the third runtime that makes parity genuinely three-way.
    ts_result=$(npx tsx src/main.ts python-eval "$f" 2>&1 | tail -1)

    if [[ "$py_result" == "$rust_result" && "$py_result" == "$ts_result" ]]; then
        echo "  ✓ $f  → $py_result"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $f"
        echo "      cpython: $py_result"
        echo "      rust:    $rust_result"
        echo "      ts:      $ts_result"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "parity_suite: $PASS passing, $FAIL failing"
exit $FAIL
