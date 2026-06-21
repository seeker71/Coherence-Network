#!/usr/bin/env bash
# cuda_affine_train_audit.sh — GPU witness for the Form CUDA affine-layer TRAINING-STEP emitter
# (jte-affine-train-cuda in form/form-stdlib/jit-tensor-emit.fk): one SGD step of y = W·x + b, one
# GPU thread per output row i. bin-go prints the Form-emitted __global__ CUDA, CuPy/NVRTC compiles it
# with --fmad=false, and BIT-EXACT parity against a CPU reference in the recipe's own op order gates
# the run — every updated W word, every updated b word, and every per-row loss word must match.
#
# This is the CUDA/RTX twin of scripts/metal_backprop_audit.sh. The algorithm is transformer-backprop.fk's
# tbp-step (fp64, proven three-way); this carrier proves the GPU lowering of its f32 form is the recipe's
# result to the last bit. Each thread owns row i and reads its whole row before writing it (dW = outer(g,x)
# and db = g are row-local), so there is no cross-thread aliasing. Why CuPy/NVRTC and not nvcc: nvcc on
# Windows needs MSVC cl.exe (absent); NVRTC compiles the kernel string in-process with no host compiler.
#
# Parity-harness shape adapted from Modular MAX's open GPU kernel tests (Apache-2.0; max/kernels/test/
# gpu/linalg), tightened from epsilon to bit-exact (one thread per row + --fmad=false keeps the recipe's
# exact two-rounding op order, so the GPU word equals the CPU word, not merely within tolerance).
#
# Run:  scripts/cuda_affine_train_audit.sh [rows cols iters]   (defaults 128 128 20)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
ROWS="${1:-128}"; COLS="${2:-128}"; ITERS="${3:-20}"

GO_BIN="$FORMDIR/form-kernel-go/bin-go.exe"
[[ -x "$GO_BIN" ]] || GO_BIN="$FORMDIR/form-kernel-go/bin-go"
if [[ ! -x "$GO_BIN" ]]; then
    echo "  building go kernel..." >&2
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go.exe .) && GO_BIN="$FORMDIR/form-kernel-go/bin-go.exe"
fi

PY="$(command -v python || command -v py || true)"
[[ -n "$PY" ]] || { echo "SKIP  no python on this host — the CUDA witness needs Python + CuPy + an NVIDIA GPU"; exit 2; }
if ! "$PY" -c "import cupy" >/dev/null 2>&1; then
    echo "SKIP  CuPy not importable — install with:  py -3 -m pip install --user 'cupy-cuda12x[ctk]'"
    exit 2
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/fkcudatrain.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the CUDA training-step kernel ─────────────────────────────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '(print "==CUDA==")\n(print (jte-affine-train-cuda "form_affine_train_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==CUDA==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/train.cu"
if ! grep -q "__global__ void form_affine_train_f32" "$work/train.cu"; then
    echo "FAIL  emission did not produce the CUDA training kernel — see $work/emit.out"; exit 1
fi
echo "emitted CUDA affine-train: $(wc -c < "$work/train.cu" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. CuPy/NVRTC carrier — one SGD step, bit-exact parity on W, b, and loss ────────────────────────
cat > "$work/runner.py" <<'PYEOF'
import sys, time
import numpy as np
import cupy as cp

cu_path, rows, cols, iters = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
# C linkage so NVRTC does not mangle the name for RawKernel's symbol lookup. The recipe stays
# quote-free (no `extern "C"` in the emitted Form string); declaring linkage is a host/ABI concern.
code = 'extern "C" {\n' + open(cu_path).read() + '\n}\n'

def val(n): return np.float32(n) / np.float32(256.0)   # exactly representable in f32
w0 = np.empty((rows, cols), dtype=np.float32)
b0 = np.empty(rows, dtype=np.float32)
x  = np.empty(cols, dtype=np.float32)
t  = np.empty(rows, dtype=np.float32)
for i in range(rows):
    for j in range(cols):
        w0[i, j] = val((i * 31 + j * 17) % 1000 - 500)
    b0[i] = val((i * 7) % 1000 - 500)
    t[i]  = val((i * 53) % 1000 - 500)
for j in range(cols):
    x[j] = val((j * 13) % 1000 - 500)
lr = np.float32(1.0 / 256.0)   # exactly representable

# CPU reference — the recipe's own op order, all fp32, FMA contraction off (two roundings per mul/add)
def f32(v): return np.float32(v)
t0 = time.perf_counter()
wr = w0.copy(); br = b0.copy(); lossr = np.empty(rows, dtype=np.float32)
for i in range(rows):
    acc = f32(0.0); j = cols
    while j > 0:
        j -= 1
        p = f32(f32(wr[i, j]) * f32(x[j])); acc = f32(p + acc)
    y = f32(acc + f32(br[i]))
    d = f32(y - f32(t[i]))
    lossr[i] = f32(d * d)
    g = f32(f32(2.0) * d)
    k = cols
    while k > 0:
        k -= 1
        wr[i, k] = f32(f32(wr[i, k]) - f32(f32(lr * g) * f32(x[k])))
    br[i] = f32(f32(br[i]) - f32(lr * g))
cpu_ms = (time.perf_counter() - t0) * 1e3

# GPU — fresh buffers (the kernel updates W, b in place), NVRTC compile with FMA contraction off
kern = cp.RawKernel(code, "form_affine_train_f32", options=("--fmad=false",))
def run():
    dw = cp.asarray(w0.reshape(-1)); db = cp.asarray(b0)
    dx = cp.asarray(x); dt = cp.asarray(t); dl = cp.empty(rows, dtype=cp.float32)
    block = 256; grid = (rows + block - 1) // block
    kern((grid,), (block,), (dw, db, dx, dt, dl, np.uint32(rows), np.uint32(cols), lr))
    cp.cuda.runtime.deviceSynchronize()
    return cp.asnumpy(dw).reshape(rows, cols), cp.asnumpy(db), cp.asnumpy(dl)

wg, bg, lg = run()  # warm + result
ew = int((wg.view(np.uint32) == wr.view(np.uint32)).sum())
eb = int((bg.view(np.uint32) == br.view(np.uint32)).sum())
el = int((lg.view(np.uint32) == lossr.view(np.uint32)).sum())
maxw = float(np.max(np.abs(wg - wr))); maxb = float(np.max(np.abs(bg - br))); maxl = float(np.max(np.abs(lg - lossr)))

start = cp.cuda.Event(); end = cp.cuda.Event(); gpus = []
for _ in range(iters):
    start.record(); run(); end.record(); end.synchronize()
    gpus.append(cp.cuda.get_elapsed_time(start, end))
gpus.sort()
dev = cp.cuda.runtime.getDeviceProperties(cp.cuda.runtime.getDevice())["name"].decode()

print(f"parity_bitexact W={ew}/{rows*cols} b={eb}/{rows} loss={el}/{rows}")
print(f"max_abs_diff W={maxw} b={maxb} loss={maxl}")
print(f"gpu_kernel_ms_median={gpus[len(gpus)//2]:.4f} iters={iters}  cpu_ref_ms={cpu_ms:.3f}")
print(f"device={dev}")
ok = (ew == rows * cols) and (eb == rows) and (el == rows)
sys.exit(0 if ok else 1)
PYEOF

echo
echo "witness (${ROWS}x${COLS} affine-train SGD step, ${ITERS} timed dispatches after one warm):"
"$PY" "$work/runner.py" "$work/train.cu" "$ROWS" "$COLS" "$ITERS" | sed 's/^/  /'
rc=${PIPESTATUS[0]}
echo
if [[ "$rc" != "0" ]]; then
    echo "FAIL  CUDA training-step parity broken. Emitter: form-stdlib/jit-tensor-emit.fk (jte-affine-train-cuda)"
    exit 1
fi
echo "ok — bit-exact parity held on W, b, and loss; the learning kernel ran on the GPU and equals the recipe."
echo "emitter recipe: form-stdlib/jit-tensor-emit.fk (jte-affine-train-cuda); algorithm: transformer-backprop.fk tbp-step"
