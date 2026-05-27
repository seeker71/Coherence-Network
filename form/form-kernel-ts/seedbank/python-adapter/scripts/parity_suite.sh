#!/usr/bin/env bash
# parity_suite.sh — verify that every Python demo runs identically
# through CPython, a chosen third runtime, and the form-kernel-rust
# native binary.
#
# The bi-directional execution claim Urs named — "ALL of the current
# python code that is talking to the substrate bi-directionally shall
# be converted into native form code and that shall be the primary
# execution pipeline" — requires three-way parity for every shipped
# Python file. This suite is the regression gate.
#
# === The third-runtime selector ===
#
# The bootstrap exists to prove the Form-native pipeline matches CPython
# before we can rely on it. Three-way parity (CPython + TS bootstrap +
# Rust kernel) is the current gate. PARITY_THIRD_RUNTIME chooses which
# third runtime fills the seam:
#
#   PARITY_THIRD_RUNTIME=ts-eval     (default)
#     Today's TS bootstrap: parse via lang-python.ts, walk via evalPython.
#     The path that is named for compost in
#     kernels/BOOTSTRAP_COMPOST_MANIFEST.md — Phase A.
#
#   PARITY_THIRD_RUNTIME=kernel-bmf  (the destination)
#     Form-native: source bytes → BMF source objects → rules in
#     form-stdlib/grammars/python-bmf.fk → Form recipe → native walker.
#     Invokes `kernel-bmf-run <file.py>` which sibling agents on
#     `template-machinery` + `python-bmf-driven-parse` are bringing up.
#     When kernel-bmf-run can compile a file, that file's row promotes;
#     the env-var flip happens demo-by-demo. When all files pass under
#     kernel-bmf, the ts-eval path is residue per the compost manifest.
#
# Add new files to PARITY_FILES below as they're ripened.
# Run from form/form-kernel-ts/.

set -euo pipefail

# Third-runtime selector — see header for the migration story.
PARITY_THIRD_RUNTIME="${PARITY_THIRD_RUNTIME:-ts-eval}"

PARITY_FILES=(
    # First row that passes under PARITY_THIRD_RUNTIME=kernel-bmf — covers
    # the 9 arms G4 ships (INT, IDENT, BINOP, COMPARE, RETURN, ASSIGN, DEF,
    # CALL, IF, MODULE) via the G1+G3 bridge in form-stdlib/python-bmf-lift.fk.
    "examples/python_bridge_demo.py"
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
    "examples/endpoint_coherence_weight_demo.py"
    "examples/python_class_demo.py"
    "examples/python_dict_demo.py"
    "examples/endpoint_nodeid_distance_demo.py"
    "examples/endpoint_weighted_average_demo.py"
    "examples/python_inheritance_demo.py"
    "examples/endpoint_lattice_stats_demo.py"
    "examples/python_typing_compose_demo.py"
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

# Put this script's own directory on PATH so `command -v kernel-bmf-run`
# finds the sibling binary without operator-side installation. The
# kernel-bmf-run script lives next to this one when G6 of
# kernels/PYTHON_BMF_CONTRACT.md is closed.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PATH="$SCRIPT_DIR:$PATH"

# Resolve the third-runtime invoker. The interface is:
#   third_runtime_run <file.py>  →  prints the final expression's value to stdout
#
# ts-eval: walks the parsed Python tree through the TS evaluator directly.
#          A distinct path from python-run (which shells to the Rust binary)
#          — this is what makes parity genuinely three-way today.
#
# kernel-bmf: invokes a Form-native binary `kernel-bmf-run` that reads
#             .py via form-stdlib/grammars/python-bmf.fk and executes via
#             the native walker. Sibling agents on `template-machinery`
#             + `python-bmf-driven-parse` are bringing this up. When the
#             binary lands on $PATH, this selector becomes the default
#             per kernels/BOOTSTRAP_COMPOST_MANIFEST.md.
case "$PARITY_THIRD_RUNTIME" in
    ts-eval)
        third_runtime_run() {
            npx tsx src/main.ts python-eval "$1" 2>&1 | tail -1
        }
        ;;
    kernel-bmf)
        if ! command -v kernel-bmf-run >/dev/null 2>&1; then
            echo "PARITY_THIRD_RUNTIME=kernel-bmf selected but kernel-bmf-run not on PATH." >&2
            echo "" >&2
            echo "The Form-native path interface:" >&2
            echo "  kernel-bmf-run <source.py>  →  prints the final expression's value" >&2
            echo "" >&2
            echo "Sibling agents on \`template-machinery\` + \`python-bmf-driven-parse\` are" >&2
            echo "bringing this binary up. See kernels/BOOTSTRAP_COMPOST_MANIFEST.md for the" >&2
            echo "migration shape. Until then, run with PARITY_THIRD_RUNTIME=ts-eval (default)." >&2
            exit 2
        fi
        third_runtime_run() {
            kernel-bmf-run "$1" 2>&1 | tail -1
        }
        ;;
    *)
        echo "unknown PARITY_THIRD_RUNTIME: $PARITY_THIRD_RUNTIME" >&2
        echo "valid: ts-eval | kernel-bmf" >&2
        exit 2
        ;;
esac

echo "parity_suite: third runtime = $PARITY_THIRD_RUNTIME"
echo ""

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

    # Third runtime — selected by PARITY_THIRD_RUNTIME. Today's default
    # (ts-eval) walks the parsed Python tree through the TS evaluator;
    # the destination (kernel-bmf) invokes the Form-native walker via
    # kernel-bmf-run. Either way, this is the third path that makes
    # parity genuinely three-way.
    third_result=$(third_runtime_run "$f")

    if [[ "$py_result" == "$rust_result" && "$py_result" == "$third_result" ]]; then
        echo "  ✓ $f  → $py_result"
        PASS=$((PASS + 1))
    else
        echo "  ✗ $f"
        echo "      cpython:                       $py_result"
        echo "      rust:                          $rust_result"
        echo "      $PARITY_THIRD_RUNTIME:$(printf '%*s' $((28 - ${#PARITY_THIRD_RUNTIME})) ' ')$third_result"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "parity_suite: $PASS passing, $FAIL failing (third runtime: $PARITY_THIRD_RUNTIME)"
exit $FAIL
