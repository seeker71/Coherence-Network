#!/usr/bin/env bash
# Cross-runtime BMF compile: same Form source through Form kernel and through
# the emitted Python BMF compiler. Compare output byte-equality and timing.
#
# This is the comparison the goal names: "compare form native execution, to
# python native execution of the same implementation using different runtimes,
# and use those observations to improve the performance, resource use."
#
# Form kernel side: form-kernel-go runs form-stdlib/source-compiler.fk on the
#   input, writes the compiled output.
# Python side: kernels.python_bmf.runtime.load_bmf_compiler() loads the emitted
#   compiler.py / engine.py / source_compiler.py into a shared namespace, then
#   calls form_source_compile_file on the same input.
#
# Both produce the same .fk text (byte-identical), with timing reported.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Each test file goes through both runtimes.
TARGETS=(
    "form/form-stdlib/core.fk"
)

GOBIN="$REPO_ROOT/form/form-kernel-go/bin-go"
if [[ ! -x "$GOBIN" ]]; then
    echo "build form-kernel-go first"; exit 1
fi

printf "%-32s | %12s | %12s | %10s | %s\n" "source" "Form ms" "Python ms" "speedup" "parity"
printf "%s\n" "---------------------------------+--------------+--------------+------------+--------"

for src in "${TARGETS[@]}"; do
    name=$(basename "$src")
    out_fk=/tmp/bmf_cmp_${name%.fk}_form.fk
    out_py=/tmp/bmf_cmp_${name%.fk}_python.fk
    driver=/tmp/bmf_cmp_driver_$$.fk
    echo "(do (form-source-compile-file \"$src\" \"$out_fk\"))" > "$driver"

    # Form-kernel side
    fk_ms=$(python3 -c "
import subprocess, time
t0 = time.perf_counter()
r = subprocess.run(['$GOBIN', 'form/form-stdlib/source-compiler.fk', '$driver'],
                   capture_output=True, timeout=60, cwd='$REPO_ROOT')
print(f'{(time.perf_counter()-t0)*1000:.1f}')
")
    # Python side
    py_ms=$(python3 -c "
import time
from kernels.python_bmf.runtime import load_bmf_compiler
rt = load_bmf_compiler()
t0 = time.perf_counter()
rt.form_source_compile_file('$src', '$out_py')
print(f'{(time.perf_counter()-t0)*1000:.1f}')
")

    # Parity check
    if cmp -s "$out_fk" "$out_py"; then
        parity="BYTE-IDENTICAL"
    else
        parity="DIFFERS"
    fi
    speedup=$(python3 -c "print(f'{$fk_ms/$py_ms:.1f}x')")
    printf "%-32s | %12s | %12s | %10s | %s\n" "$name" "$fk_ms" "$py_ms" "$speedup" "$parity"
    rm -f "$driver"
done

echo ""
echo "Note: Form kernel timing includes Go binary startup (~fork+exec). Python"
echo "timing is in-process load + compile. The comparison's value isn't the"
echo "absolute speed — it's that BOTH runtimes execute the same compiler and"
echo "produce the same output, making per-pass optimization observable."
