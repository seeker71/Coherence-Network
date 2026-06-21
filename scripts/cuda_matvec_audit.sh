#!/usr/bin/env bash
# cuda_matvec_audit.sh — GPU witness for the Form CUDA matvec emitter (jte-matvec-cuda in
# form/form-stdlib/jit-tensor-emit.fk): bin-go prints the Form-emitted __global__ CUDA, CuPy/NVRTC
# compiles it with --fmad=false (no FMA contraction — mul-then-add stays TWO roundings, not a fused
# one), one thread per output row dispatches over deterministic input cells, and BIT-EXACT value
# parity against a CPU right-fold reference (same op order, fp32 accumulation) gates the timing rows.
# A row only counts when its output word is bit-identical to the CPU reference word.
#
# This is the CUDA/RTX twin of scripts/metal_matvec_audit.sh. Why CuPy/NVRTC and not nvcc: nvcc on
# Windows requires MSVC cl.exe as its host compiler (absent on this host); NVRTC compiles the kernel
# string in-process with no host compiler, and CuPy bundles the CUDA runtime — so the carrier runs on
# a stock Windows + RTX host with only Python and the NVIDIA driver. The emitter intelligence lives in
# the Form recipe; CuPy/NVRTC + the driver are the dumb carrier (host-resource-access idiom).
#
# Parity-harness shape (deterministic seed, fp32 accumulation, GPU-vs-CPU compare) adapted from
# Modular MAX's open GPU kernel tests (Apache-2.0 w/ LLVM exceptions; max/kernels/test/gpu/linalg/
# test_gemv.mojo), TIGHTENED from their epsilon assert_almost_equal to a BIT-EXACT gate: our one-
# thread-per-row sequential right-fold + --fmad=false preserves the recipe's exact op order, where
# their warp.sum reduction reassociates the sum and can only be checked within a tolerance.
#
# Run:  scripts/cuda_matvec_audit.sh [rows cols iters]   (defaults 256 256 20)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
ROWS="${1:-256}"; COLS="${2:-256}"; ITERS="${3:-20}"

# go kernel — the mouth that prints the Form-emitted CUDA (bin-go.exe on Windows, bin-go elsewhere)
GO_BIN="$FORMDIR/form-kernel-go/bin-go.exe"
[[ -x "$GO_BIN" ]] || GO_BIN="$FORMDIR/form-kernel-go/bin-go"
if [[ ! -x "$GO_BIN" ]]; then
    echo "  building go kernel..." >&2
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go.exe .) && GO_BIN="$FORMDIR/form-kernel-go/bin-go.exe"
fi

# host carrier prerequisites — Python + CuPy + a CUDA device; named SKIP otherwise (the Metal lane's
# Darwin/swiftc gate, ported to the CUDA toolchain)
PY="$(command -v python || command -v py || true)"
[[ -n "$PY" ]] || { echo "SKIP  no python on this host — the CUDA witness needs Python + CuPy + an NVIDIA GPU"; exit 2; }
if ! "$PY" -c "import cupy" >/dev/null 2>&1; then
    echo "SKIP  CuPy not importable — install with:  py -3 -m pip install --user cupy-cuda12x"
    echo "      (the NVRTC carrier needs CuPy; the NVIDIA driver is already present per nvidia-smi)"
    exit 2
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/fkcuda.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the CUDA; the kernel is only the mouth ────────────────────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '(print "==CUDA==")\n(print (jte-matvec-cuda "form_matvec_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==CUDA==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/matvec.cu"
if ! grep -q "__global__ void form_matvec_f32" "$work/matvec.cu"; then
    echo "FAIL  emission did not produce the CUDA kernel — see $work/emit.out"; exit 1
fi
echo "emitted CUDA matvec: $(wc -c < "$work/matvec.cu" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. CuPy/NVRTC carrier — compile (--fmad=false), one thread per row, bit-exact parity ───────────
cat > "$work/runner.py" <<'PYEOF'
import sys, time
import numpy as np
import cupy as cp

cu_path, rows, cols, iters = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
# C linkage so NVRTC does not mangle the name for RawKernel's symbol lookup. The recipe stays
# quote-free (no `extern "C"` in the emitted Form string); declaring linkage is a host/ABI concern.
code = 'extern "C" {\n' + open(cu_path).read() + '\n}\n'

# deterministic inputs, exactly representable in f32 (|n|<=500 needs <=9 significand bits), so the
# chain starts at identical bits on both sides; val(n) = n/256 is the identity quantization.
def val(n): return np.float32(n) / np.float32(256.0)
w = np.empty((rows, cols), dtype=np.float32)
x = np.empty(cols, dtype=np.float32)
for i in range(rows):
    for j in range(cols):
        w[i, j] = val((i * 31 + j * 17) % 1000 - 500)
for j in range(cols):
    x[j] = val((j * 13) % 1000 - 500)

# CPU reference — the recipe's own op order: per row, fp32 product then downward right-fold add
# (mul then add as two roundings), exactly what the emitted kernel does with FMA contraction off.
t0 = time.perf_counter()
ref = np.empty(rows, dtype=np.float32)
for i in range(rows):
    prod = (w[i] * x).astype(np.float32)        # one fp32 rounding per product
    acc = np.float32(0.0)
    j = cols
    while j > 0:
        j -= 1
        acc = np.float32(prod[j] + acc)          # one fp32 rounding per add
    ref[i] = acc
cpu_ms = (time.perf_counter() - t0) * 1e3

# GPU — NVRTC compile with FMA contraction OFF so `acc = p + acc` is not fused into the multiply
kern = cp.RawKernel(code, "form_matvec_f32", options=("--fmad=false",))
dw = cp.asarray(w.reshape(-1)); dx = cp.asarray(x); dy = cp.empty(rows, dtype=cp.float32)
block = 256; grid = (rows + block - 1) // block

def once():
    kern((grid,), (block,), (dw, dx, dy, np.uint32(rows), np.uint32(cols)))
    cp.cuda.runtime.deviceSynchronize()

once()  # warm: NVRTC JIT + first touch
yg = cp.asnumpy(dy)

exact = int((yg.view(np.uint32) == ref.view(np.uint32)).sum())
max_abs = float(np.max(np.abs(yg - ref))) if rows else 0.0

start = cp.cuda.Event(); end = cp.cuda.Event(); gpus = []
for _ in range(iters):
    start.record(); once(); end.record(); end.synchronize()
    gpus.append(cp.cuda.get_elapsed_time(start, end))
gpus.sort()
dev = cp.cuda.runtime.getDeviceProperties(cp.cuda.runtime.getDevice())["name"].decode()

print(f"parity_bitexact_rows={exact}/{rows} max_abs_diff={max_abs}")
print(f"gpu_kernel_ms_median={gpus[len(gpus)//2]:.4f} iters={iters}")
print(f"cpu_rightfold_ms={cpu_ms:.3f}")
print(f"device={dev}")
sys.exit(0 if exact == rows else 1)
PYEOF

echo
echo "witness (${ROWS}x${COLS} matvec, ${ITERS} timed dispatches after one warm):"
"$PY" "$work/runner.py" "$work/matvec.cu" "$ROWS" "$COLS" "$ITERS" | sed 's/^/  /'
rc=${PIPESTATUS[0]}
echo
if [[ "$rc" != "0" ]]; then
    echo "FAIL  CUDA value parity broken — timing rows do not count. Emitter: form-stdlib/jit-tensor-emit.fk (jte-matvec-cuda)"
    exit 1
fi
echo "conditions: $(uname -m) $(uname -s), NVRTC in-process compile (--fmad=false), one thread per output row," \
     "cpu row is the recipe's own conversion chain (fp32 product -> downward right-fold add, two roundings)"
echo "ok — bit-exact parity held and the rows are real; the emitter recipe is form-stdlib/jit-tensor-emit.fk (jte-matvec-cuda)"
