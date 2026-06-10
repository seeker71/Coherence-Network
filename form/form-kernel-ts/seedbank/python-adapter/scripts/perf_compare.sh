#!/usr/bin/env bash
# perf_compare.sh — time the same Python workload through current runtimes:
#   1. CPython (the reference baseline)
#   2. form-kernel-rust over Form-native compiled .fk
#   3. kernel-bmf-run end to end from .py source
#
# Produces a markdown-shaped report on stdout. The "same order of
# magnitude" target Urs named is measured here.
#
# Usage: ./perf_compare.sh <file.py>
# Run from form/form-kernel-ts/.

set -euo pipefail

FILE="${1:-examples/python_demo.py}"
ITERS="${ITERS:-3}"

# Locate binaries (paths assume the standard layout — kernels must be built
# first via `cd form/form-kernel-go && go build -o bin-go .` and
# `cd form/form-kernel-rust && cargo build --release`).
ADAPTER_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FORM_DIR="$(cd "$ADAPTER_DIR/../../.." && pwd)"
RUST_BIN="$FORM_DIR/form-kernel-rust/target/release/form-kernel-rust"
if [[ ! -x "$RUST_BIN" ]]; then
    echo "error: form-kernel-rust binary not found at $RUST_BIN" >&2
    echo "build it first: cd $FORM_DIR/form-kernel-rust && cargo build --release" >&2
    exit 1
fi
if [[ ! -x "$FORM_DIR/form-kernel-go/bin-go" ]]; then
    echo "error: form-kernel-go binary not found at $FORM_DIR/form-kernel-go/bin-go" >&2
    echo "build it first: cd $FORM_DIR/form-kernel-go && go build -o bin-go ." >&2
    exit 1
fi

PATH="$SCRIPT_DIR:$PATH"
cd "$ADAPTER_DIR"

# CPython reference wrapper: same final-expression contract as parity_suite.sh.
TMP_CPY="$(mktemp -t perf_compare.XXXXXX.py)"
TMP_FK="$(mktemp -t perf_compare.XXXXXX.fk)"
trap 'rm -f "$TMP_CPY" "$TMP_FK"' EXIT
cat > "$TMP_CPY" <<'PY'
import ast
import sys

path = sys.argv[1]
src = open(path).read()
tree = ast.parse(src)
namespace = {
    "str_find": lambda s, needle, frm: s.find(needle, frm),
    "str_len": lambda s: len(s),
    "str_concat": lambda a, b: a + b,
    "str_eq": lambda a, b: a == b,
}
if tree.body and isinstance(tree.body[-1], ast.Expr):
    last = tree.body[-1]
    body = tree.body[:-1]
    if body:
        exec(compile(ast.Module(body=body, type_ignores=[]), path, "exec"), namespace)
    print(eval(compile(ast.Expression(body=last.value), path, "eval"), namespace))
else:
    exec(compile(src, path, "exec"), namespace)
PY

# Compile Python -> .fk once so the Rust timing measures execution only.
kernel-bmf-compile "$FILE" "$TMP_FK" 2>/dev/null

# Capture results once to verify parity.
CPY_RESULT="$(python3 "$TMP_CPY" "$FILE" 2>&1 | tail -1)"
RUST_RESULT="$("$RUST_BIN" "$TMP_FK" 2>&1 | tail -1)"
KERNEL_BMF_RESULT="$(kernel-bmf-run "$FILE" 2>&1 | tail -1)"
if [[ "$CPY_RESULT" != "$RUST_RESULT" || "$CPY_RESULT" != "$KERNEL_BMF_RESULT" ]]; then
    echo "error: runtime results diverged for $FILE" >&2
    echo "  CPython:      $CPY_RESULT" >&2
    echo "  Rust .fk:     $RUST_RESULT" >&2
    echo "  kernel-bmf:   $KERNEL_BMF_RESULT" >&2
    exit 1
fi

# 2. Time each runtime over ITERS iterations.
time_runtime() {
    local cmd="$1"
    local total_ns=0
    for ((i=0; i<ITERS; i++)); do
        local start
        start="$(python3 -c 'import time; print(time.perf_counter_ns())')"
        eval "$cmd" >/dev/null 2>&1
        local end
        end="$(python3 -c 'import time; print(time.perf_counter_ns())')"
        total_ns=$((total_ns + end - start))
    done
    echo "$((total_ns / ITERS))"
}

PY_NS=$(time_runtime "python3 \"$TMP_CPY\" \"$FILE\"")
RUST_NS=$(time_runtime "\"$RUST_BIN\" \"$TMP_FK\"")
KERNEL_BMF_NS=$(time_runtime "kernel-bmf-run \"$FILE\"")

# Format as milliseconds with 2 decimal places.
fmt_ms() { python3 -c "print(f'{$1/1_000_000:.2f} ms')"; }
PY_MS=$(fmt_ms "$PY_NS")
RUST_MS=$(fmt_ms "$RUST_NS")
KERNEL_BMF_MS=$(fmt_ms "$KERNEL_BMF_NS")

# Ratios vs CPython.
ratio() { python3 -c "print(f'{$1/$2:.2f}×')"; }
RUST_RATIO=$(ratio "$RUST_NS" "$PY_NS")
KERNEL_BMF_RATIO=$(ratio "$KERNEL_BMF_NS" "$PY_NS")

cat <<EOF
# perf_compare — Python → kernel pipeline timing

Workload: $FILE
Result (all three runtimes): cpy=$CPY_RESULT rust=$RUST_RESULT kernel-bmf=$KERNEL_BMF_RESULT
Iterations per runtime: $ITERS

| Runtime                     | Time/iter | vs CPython |
|-----------------------------|-----------|------------|
| CPython 3.x                 | $PY_MS    | 1.00×      |
| form-kernel-rust (release)  | $RUST_MS  | $RUST_RATIO |
| kernel-bmf-run (.py end-to-end) | $KERNEL_BMF_MS | $KERNEL_BMF_RATIO |

Notes:
- The Rust row is native execution of a Form-native compiled recipe.
- The kernel-bmf row includes source compile/prelude orchestration on each
  command-line invocation; it is an end-to-end smoke measurement, not
  steady-state evaluator throughput.
- "Same order of magnitude as Python" target: Rust ratio < 10×.
EOF
