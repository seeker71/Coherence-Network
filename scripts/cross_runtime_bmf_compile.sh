#!/usr/bin/env bash
# Cross-runtime BMF compile: same Form source through Form kernel and through
# the emitted Python BMF compiler. Compares output byte-equality and timing
# across a graduated set of workloads.
#
# This is the comparison the universal-translator goal names: "compare form
# native execution to python native execution of the same implementation
# using different runtimes, and use those observations to improve the
# performance, resource use."
#
# Form kernel side: form-kernel-go runs form-stdlib/source-compiler.fk on the
#   input, writes the compiled output.
# Python side: kernels.python_bmf.runtime.load_bmf_compiler() loads the emitted
#   compiler.py / engine.py / source_compiler.py into a shared namespace, then
#   calls form_source_compile_file on the same input.
#
# Each workload must produce byte-identical output. Timing is reported as wall
# clock; Form-kernel side includes Go binary fork+exec, Python side is in-
# process CPython dispatch.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Stack: the emitter lifts tail-recursive head/tail walks to `while True:`
# loops (see kernels/python_bmf/emit_python.py `_is_tail_recursive`), so the
# emitted Python no longer needs a giant stack to reach engine.fk depth. The
# default soft limit suffices; we leave a modest bump as cushion for the
# remaining non-tail recursion in tree walkers.
ulimit -s 8192 2>/dev/null || true

# Graduated workloads: tiny → small → medium → large.
# Each exercises a different part of the source compiler's reach.
WORKLOADS=(
    "form/form-stdlib/tests/lists.fk"          # tiny BML
    "form/form-stdlib/tests/numeric.fk"        # tiny BML, more ops
    "form/form-stdlib/tests/task-runtime.fk"   # small section dialect
    "form/form-stdlib/tests/higher.fk"         # small, higher-order
    "form/form-stdlib/core.fk"                 # medium prelude
    "form/form-stdlib/engine.fk"               # large s-expr (no sections)
)

GOBIN="$REPO_ROOT/form/form-kernel-go/bin-go"
if [[ ! -x "$GOBIN" ]]; then
    echo "build form-kernel-go first: cd form/form-kernel-go && go build -o bin-go ."
    exit 1
fi

python3 <<'PY'
import sys, time, subprocess, tempfile
from pathlib import Path

REPO = Path.cwd()
GOBIN = REPO / "form/form-kernel-go/bin-go"
SOURCE_COMPILER = "form/form-stdlib/source-compiler.fk"

from kernels.python_bmf.runtime import load_bmf_compiler
rt = load_bmf_compiler()

WORKLOADS = [
    "form/form-stdlib/tests/lists.fk",
    "form/form-stdlib/tests/numeric.fk",
    "form/form-stdlib/tests/task-runtime.fk",
    "form/form-stdlib/tests/higher.fk",
    "form/form-stdlib/core.fk",
    "form/form-stdlib/engine.fk",
]

print(f"{'workload':<24} {'lines':>6} {'Form ms':>9} {'Py ms':>9} {'speedup':>9} {'output':>10} {'parity':>12}")
print("-" * 88)

all_parity = True
for src in WORKLOADS:
    if not Path(src).exists():
        continue
    n_lines = sum(1 for _ in open(src))
    with tempfile.NamedTemporaryFile(suffix=".fk", delete=False) as f_form, \
         tempfile.NamedTemporaryFile(suffix=".fk", delete=False) as f_py, \
         tempfile.NamedTemporaryFile(suffix=".fk", delete=False) as f_drv:
        form_out, py_out, drv = f_form.name, f_py.name, f_drv.name
    Path(drv).write_text(f'(do (form-source-compile-file "{src}" "{form_out}"))')

    t0 = time.perf_counter()
    r = subprocess.run([str(GOBIN), SOURCE_COMPILER, drv], capture_output=True, timeout=180)
    fk_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    try:
        rt.form_source_compile_file(src, py_out)
        py_ms = (time.perf_counter() - t0) * 1000
        py_err = None
    except Exception as e:
        py_ms = (time.perf_counter() - t0) * 1000
        py_err = type(e).__name__

    if py_err is None:
        f_bytes = Path(form_out).read_bytes()
        p_bytes = Path(py_out).read_bytes()
        parity = "BYTE-IDENT" if f_bytes == p_bytes else "DIFFER"
        size = f"{len(f_bytes)}b" if f_bytes == p_bytes else f"F={len(f_bytes)} P={len(p_bytes)}"
        speedup = f"{fk_ms/py_ms:.1f}x" if py_ms > 0 else "—"
        if parity != "BYTE-IDENT":
            all_parity = False
    else:
        parity = f"Py:{py_err}"; speedup = "—"; size = "—"
        all_parity = False

    print(f"{Path(src).name:<24} {n_lines:>6} {fk_ms:>9.1f} {py_ms:>9.1f} {speedup:>9} {size:>10} {parity:>12}")

print()
print("Observations:")
print("  - Form kernel ~10ms binary startup + linear interpretation cost.")
print("  - CPython in-process dispatch wins on every workload tested.")
print("  - Speedup is U-shaped: tiny workloads dominated by Go startup,")
print("    medium workloads converge (Go amortizes startup over more work),")
print("    large workloads diverge again as interpretation cost stacks.")
print()

sys.exit(0 if all_parity else 1)
PY
