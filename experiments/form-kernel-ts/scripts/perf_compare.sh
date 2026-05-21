#!/usr/bin/env bash
# perf_compare.sh — time the same Python workload through three runtimes:
#   1. CPython (the existing Python framework — the baseline)
#   2. form-kernel-rust native binary (the destination)
#   3. form-kernel-ts evalPython (the TS bootstrap path)
#
# Produces a markdown-shaped report on stdout. The "same order of
# magnitude" target Urs named is measured here.
#
# Usage: ./perf_compare.sh <file.py>
# Run from experiments/form-kernel-ts/.

set -euo pipefail

FILE="${1:-examples/python_demo.py}"
ITERS="${ITERS:-3}"

# Locate binaries (paths assume the standard layout — kernel must be
# release-built first via `cd ../form-kernel-rust && cargo build --release`).
RUST_BIN="$(cd "$(dirname "$0")/.." && pwd)/../form-kernel-rust/target/release/form-kernel-rust"
if [[ ! -x "$RUST_BIN" ]]; then
    echo "error: form-kernel-rust binary not found at $RUST_BIN" >&2
    echo "build it first: cd ../form-kernel-rust && cargo build --release" >&2
    exit 1
fi

# 1. Compile Python → .fk once so the timing measures execution only.
TMP_FK="$(mktemp -t perf_compare.XXXXXX.fk)"
trap 'rm -f "$TMP_FK"' EXIT
npx tsx src/main.ts python-compile "$FILE" "$TMP_FK" 2>/dev/null

# Capture results once to verify parity.
CPY_RESULT="$(python3 -c "
$(cat "$FILE")
print(count_primes(30) + fact(8) + fib(15) + ackermann(2, 3))" 2>&1 | tail -1)"
RUST_RESULT="$("$RUST_BIN" "$TMP_FK" 2>&1 | tail -1)"
TS_RESULT="$(npx tsx src/main.ts "$TMP_FK" 2>&1 | tail -1)"

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

PY_NS=$(time_runtime "python3 -c \"
$(cat "$FILE")
print(count_primes(30) + fact(8) + fib(15) + ackermann(2, 3))\"")
RUST_NS=$(time_runtime "\"$RUST_BIN\" \"$TMP_FK\"")
TS_NS=$(time_runtime "npx tsx src/main.ts \"$TMP_FK\"")

# Format as milliseconds with 2 decimal places.
fmt_ms() { python3 -c "print(f'{$1/1_000_000:.2f} ms')"; }
PY_MS=$(fmt_ms "$PY_NS")
RUST_MS=$(fmt_ms "$RUST_NS")
TS_MS=$(fmt_ms "$TS_NS")

# Ratios vs CPython.
ratio() { python3 -c "print(f'{$1/$2:.2f}×')"; }
RUST_RATIO=$(ratio "$RUST_NS" "$PY_NS")
TS_RATIO=$(ratio "$TS_NS" "$PY_NS")

cat <<EOF
# perf_compare — Python → kernel pipeline timing

Workload: $FILE
Result (all three runtimes): cpy=$CPY_RESULT rust=$RUST_RESULT ts=$TS_RESULT
Iterations per runtime: $ITERS

| Runtime                     | Time/iter | vs CPython |
|-----------------------------|-----------|------------|
| CPython 3.x                 | $PY_MS    | 1.00×      |
| form-kernel-rust (release)  | $RUST_MS  | $RUST_RATIO |
| form-kernel-ts (tsx + node) | $TS_MS    | $TS_RATIO |

Notes:
- The TS row includes tsx startup (~150ms cold) — apples-to-apples for
  end-to-end "command-line invocation" timing, but not for steady-state
  evaluator throughput.
- The Rust row is the destination measurement: native binary executing
  a compiled Python program with zero host runtime in the path.
- "Same order of magnitude as Python" target: Rust ratio < 10×.
EOF
