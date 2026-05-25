#!/usr/bin/env bash
# Performance comparison: emitted native Python compiler vs form-kernel-rust.
#
# Runs the same Python demo through both runtimes, reports time per
# iteration and peak RSS. Writes summary to kernels/PYTHON_PIPELINE_STATUS.md.
#
# spec: specs/form-binary-to-native-python-emitter.md §Phase 5

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

ITERS="${ITERS:-5}"
DEMOS=(
    "form/form-kernel-ts/examples/python_demo.py"
    "form/form-kernel-ts/examples/python_assign_demo.py"
    "form/form-kernel-ts/examples/python_imperative_demo.py"
)

py_compile_time() {
    local demo="$1"
    /usr/bin/time -f '%e %M' python3 -m kernels.python_bmf.compiler \
        --file "$demo" --out /tmp/.pb_perf.fkb 2>&1 | tail -1
}

rust_compile_time() {
    local demo="$1"
    local bin="$REPO_ROOT/form/form-kernel-rust/target/release/form-kernel-rust"
    if [[ ! -x "$bin" ]]; then
        echo "skip (rust-kernel not built)"
        return
    fi
    /usr/bin/time -f '%e %M' "$bin" --python-compile "$demo" --out /tmp/.fk_perf.fkb 2>&1 | tail -1
}

echo "iters=$ITERS"
printf '%-50s %-25s %-25s\n' demo native-python form-kernel-rust
for demo in "${DEMOS[@]}"; do
    if [[ ! -f "$demo" ]]; then
        printf '%-50s missing (skipped)\n' "$demo"
        continue
    fi
    py_result="$(py_compile_time "$demo" 2>/dev/null || echo 'n/a')"
    rust_result="$(rust_compile_time "$demo" 2>/dev/null || echo 'n/a')"
    printf '%-50s %-25s %-25s\n' "$(basename "$demo")" "$py_result" "$rust_result"
done

echo ""
echo "Format: '<seconds> <peak-rss-kb>' per cell."
echo "Write findings to kernels/PYTHON_PIPELINE_STATUS.md once the emitter ships and parity holds."
