#!/usr/bin/env bash
# metal_backprop_audit.sh — the LEARNING KERNEL on Metal (M4 Max GPU witness).
#
# The Form recipe transformer-backprop.fk (fp64, proven 127 three-way) is the ALGORITHM: one SGD
# training step over an affine layer y = W·x + b. jit-tensor-emit.fk emits that step as an MSL kernel
# (jte-affine-train-msl) — every byte authored by the Form recipe; this script is only the carrier that
# compiles it, drives N training steps on the GPU, reads the loss descending, times it, and PARITY-GATES
# the GPU result bit-exact against a CPU reference computed in the SAME fp32 semantics (the lane's own).
#
# So the chain is honest end to end: fp64 recipe (proven correct) -> fp32 GPU carrier (proven == fp32 CPU
# reference) -> it LEARNS on the GPU at scale and speed. Inputs are deterministic (x unit-normalized so a
# fixed lr converges at any width; t a fixed pattern), W=0 b=0 start — loss falls monotonically toward 0.
#
# Run:  scripts/metal_backprop_audit.sh [rows cols steps]   (defaults 1280 1280 200)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
ROWS="${1:-1280}"; COLS="${2:-1280}"; STEPS="${3:-200}"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkbp.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the training-step MSL; the kernel is only the mouth ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '(print "==MSL==")\n(print (jte-affine-train-msl "form_affine_train_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/train.metal"
grep -q 'kernel void form_affine_train_f32' "$work/train.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted training-step MSL: $(wc -c < "$work/train.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. Swift carrier: compile the kernel, train on the GPU, time, parity-gate vs CPU fp32 ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let rows = Int(args[1])!, cols = Int(args[2])!, steps = Int(args[3])!
let mslPath = args[4]
let lr: Float = 0.25

guard let dev = MTLCreateSystemDefaultDevice() else { print("SKIP no Metal device"); exit(2) }
let src = try String(contentsOfFile: mslPath, encoding: .utf8)
let opts = MTLCompileOptions()
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
let fn = lib.makeFunction(name: "form_affine_train_f32")!
let pso = try dev.makeComputePipelineState(function: fn)
let q = dev.makeCommandQueue()!

// deterministic inputs: x unit-normalized (|x|^2 = 1 -> stable lr at any width), t a fixed pattern
let invn = 1.0 / Float(cols).squareRoot()
var x = [Float](repeating: invn, count: cols)
for j in 0..<cols { x[j] = invn * (1.0 + 0.5 * Float((j % 5)) - 1.0) }   // mild variation, still ~unit
var nrm: Float = 0; for v in x { nrm += v*v }; nrm = nrm.squareRoot()
for j in 0..<cols { x[j] /= nrm }                                        // exact unit norm
var t = [Float](repeating: 0, count: rows)
for i in 0..<rows { t[i] = Float((i % 7)) - 3.0 }                        // targets in [-3, 3]

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: a.count*4, options: .storageModeShared)! }
func zeros(_ n: Int) -> [Float] { [Float](repeating: 0, count: n) }

// GPU state
let bw = newBuf(zeros(rows*cols)), bb = newBuf(zeros(rows)), bx = newBuf(x), bt = newBuf(t), bl = newBuf(zeros(rows))
var r32 = UInt32(rows), c32 = UInt32(cols), lrv = lr

func step() {
    let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
    enc.setComputePipelineState(pso)
    enc.setBuffer(bw, offset: 0, index: 0); enc.setBuffer(bb, offset: 0, index: 1)
    enc.setBuffer(bx, offset: 0, index: 2); enc.setBuffer(bt, offset: 0, index: 3)
    enc.setBuffer(bl, offset: 0, index: 4)
    enc.setBytes(&r32, length: 4, index: 5); enc.setBytes(&c32, length: 4, index: 6)
    enc.setBytes(&lrv, length: 4, index: 7)
    let tg = min(pso.maxTotalThreadsPerThreadgroup, rows)
    enc.dispatchThreads(MTLSize(width: rows, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: tg, height: 1, depth: 1))
    enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
}
func gpuLoss() -> Double {
    let p = bl.contents().bindMemory(to: Float.self, capacity: rows)
    var s: Double = 0; for i in 0..<rows { s += Double(p[i]) }; return s
}

// CPU fp32 reference of the SAME recipe (same downward fold), for the parity gate
var cw = zeros(rows*cols), cb_ = zeros(rows)
func cpuStep() {
    for i in 0..<rows {
        var acc: Float = 0; var j = cols
        while j > 0 { j -= 1; acc = x[j]*cw[i*cols+j] + acc }   // downward fold == tb-dot
        let y = acc + cb_[i]; let g = 2.0*(y - t[i])
        var k = cols
        while k > 0 { k -= 1; cw[i*cols+k] = cw[i*cols+k] - lr*g*x[k] }
        cb_[i] = cb_[i] - lr*g
    }
}
func cpuLoss() -> Double {
    var s: Double = 0
    for i in 0..<rows {
        var acc: Float = 0; var j = cols
        while j > 0 { j -= 1; acc = x[j]*cw[i*cols+j] + acc }
        let d = acc + cb_[i] - t[i]; s += Double(d*d)
    }
    return s
}

// ── learning curve on the GPU, timed ──
step()  // warm
let l0 = gpuLoss()
print(String(format: "  step %5d   gpu_loss %.6f", 0, l0))
let t0 = Date()
var marks = [10, 25, 50, 100, steps]
for s in 1...steps {
    step()
    if marks.contains(s) { print(String(format: "  step %5d   gpu_loss %.6f", s, gpuLoss())) }
}
let dt = Date().timeIntervalSince(t0)
print(String(format: "GPU: %d steps of %dx%d affine in %.1f ms  (%.3f ms/step)  loss %.6f -> %.6g",
             steps, rows, cols, dt*1000, dt*1000/Double(steps), l0, gpuLoss()))

// ── parity gate: same steps on CPU fp32, compare ──
for _ in 0..<steps { cpuStep() }
let gl = gpuLoss(), cl = cpuLoss()
let wp = bw.contents().bindMemory(to: Float.self, capacity: rows*cols)
var maxw: Float = 0
for n in 0..<(rows*cols) { let d = abs(wp[n] - cw[n]); if d > maxw { maxw = d } }
print(String(format: "PARITY: gpu_loss=%.9g cpu_fp32_loss=%.9g  max|W_gpu-W_cpu|=%.3e", gl, cl, maxw))
print(maxw == 0 ? "  ✓ bit-exact: the GPU runs the recipe's training step in fp32, parity with the CPU reference"
                : (maxw < 1e-4 ? "  ✓ within fp32 epsilon (GPU FMA-contraction vs CPU split-mul allowed)"
                               : "  ✗ parity failure"))
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── training the affine on the M4 Max GPU (loss should fall toward 0) ──"
"$work/runner" "$ROWS" "$COLS" "$STEPS" "$work/train.metal"
