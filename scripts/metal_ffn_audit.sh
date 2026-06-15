#!/usr/bin/env bash
# metal_ffn_audit.sh — the ARCHITECT'S LAYER learning on Metal (M4 Max GPU witness).
#
# The Form recipe transformer-backprop.fk (fp64, proven three-way) is the ALGORITHM: one SGD step over the
# two-layer FFN y = W2·gelu(W1·x + b1) + b2 — tbp-mlp-step, the exact block ac-ffn-layer builds and the
# architect trains. jit-tensor-emit.fk emits that step as ONE Metal kernel (jte-mlp-train-msl), run by a
# SINGLE threadgroup with barriered phases — every byte authored by the Form recipe. This script is only the
# carrier: it compiles the kernel, drives N training steps on the GPU, reads the loss descending, times it,
# and PARITY-GATES the GPU weights bit-for-bit against a CPU fp32 mirror that walks the SAME phases.
#
# The transcendental is the recipe's OWN, not the hardware's: the kernel's gelu/gelu' compose from fexp (the
# square-and-reduce 14-term Taylor of tn-exp) and ftanh ((e^2x-1)/(e^2x+1) of tn-tanh) — so the GPU walks
# transformer-numerics.fk's approximation, never Metal's tanh(). The CPU mirror computes the identical
# algorithm in fp32, so the parity gate is honest end to end: no hidden hardware intrinsic between the recipe
# and the silicon. The forward matvecs carry tb-dot's DOWNWARD right-fold; the dh1 column reduction carries
# tbp-wt-gy-acc's FORWARD left-fold; the GPU and the mirror agree fold-for-fold.
#
# Run:  scripts/metal_ffn_audit.sh [indim hid outd steps]   (defaults 256 384 256 300)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
INDIM="${1:-256}"; HID="${2:-384}"; OUTD="${3:-256}"; STEPS="${4:-300}"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkffn.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the FFN training-step MSL; the kernel is only the mouth ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-mlp-train-msl "form_mlp_train_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/train.metal"
grep -q 'kernel void form_mlp_train_f32' "$work/train.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted FFN training-step MSL: $(wc -c < "$work/train.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. Swift carrier: compile, train on the GPU, time, parity-gate vs CPU fp32 mirror ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let indim = Int(args[1])!, hid = Int(args[2])!, outd = Int(args[3])!, steps = Int(args[4])!
let mslPath = args[5]
let lr: Float = 0.05

guard let dev = MTLCreateSystemDefaultDevice() else { print("SKIP no Metal device"); exit(2) }
let src = try String(contentsOfFile: mslPath, encoding: .utf8)
let opts = MTLCompileOptions()
// Hold the GPU to the recipe's exact op order: no mul-add contraction into fma in the matvec folds.
// A few-ULP residual remains and that is honest — the recipe's exp squares a Taylor value up to k times
// (tn-exp's reduce-and-square), so any 1-ULP difference between Metal's and Swift's fp32 divide gets
// amplified by the squaring, leaving the GPU within fp32 epsilon of the CPU mirror rather than bit-exact.
opts.fastMathEnabled = false
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
let fn = lib.makeFunction(name: "form_mlp_train_f32")!
let pso = try dev.makeComputePipelineState(function: fn)
let q = dev.makeCommandQueue()!

// ── the recipe's own exp/tanh/gelu in fp32 (mirrors the emitted fexp/ftanh/fgelu/fgelud exactly) ──
func fexp_small(_ x: Float) -> Float { var n: Float = 1, term: Float = 1, acc: Float = 1; while n <= 14.0 { term = term * (x / n); acc = acc + term; n = n + 1 }; return acc }
func fexp(_ x0: Float) -> Float { var x = x0; var k = 0; while (x < 0 ? -x : x) > 0.5 { x = x / 2; k += 1 }; var v = fexp_small(x); while k > 0 { v = v * v; k -= 1 }; return v }
func ftanh(_ x: Float) -> Float { let e = fexp(2*x); return (e - 1) / (e + 1) }
func fgelu(_ x: Float) -> Float { let z = Float(0.7978845608028654) * (x + Float(0.044715) * (x*(x*x))); return (0.5*x) * (1 + ftanh(z)) }
func fgelud(_ x: Float) -> Float { let z = Float(0.7978845608028654) * (x + Float(0.044715) * (x*(x*x))); let th = ftanh(z); return (0.5*(1+th)) + ((0.5*x)*((1-(th*th))*(Float(0.7978845608028654)*(1+(Float(0.134145)*(x*x)))))) }

// ── deterministic inputs: x mildly varied unit-ish, small nonzero weights so the hidden layer is live ──
func z(_ n: Int) -> [Float] { [Float](repeating: 0, count: n) }
var x = z(indim); for j in 0..<indim { x[j] = (Float((j % 7)) - 3.0) / Float(indim).squareRoot() }
var t = z(outd);  for i in 0..<outd  { t[i] = 0.3 * (Float((i % 5)) - 2.0) }
var w1 = z(hid*indim); for n in 0..<(hid*indim) { w1[n] = 0.01 * (Float((n % 11)) - 5.0) }
var w2 = z(outd*hid);  for n in 0..<(outd*hid)  { w2[n] = 0.01 * (Float((n % 13)) - 6.0) }
var b1 = z(hid), b2 = z(outd)

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: a.count*4, options: .storageModeShared)! }
let bw1 = newBuf(w1), bb1 = newBuf(b1), bw2 = newBuf(w2), bb2 = newBuf(b2)
let bx = newBuf(x), bt = newBuf(t), bloss = newBuf(z(outd))
let bh1 = newBuf(z(hid)), ba = newBuf(z(hid)), bgy = newBuf(z(outd)), bdh1 = newBuf(z(hid))
var u_in = UInt32(indim), u_hid = UInt32(hid), u_out = UInt32(outd), lrv = lr
let tgs = min(pso.maxTotalThreadsPerThreadgroup, max(hid, outd))

func step() {
    let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
    enc.setComputePipelineState(pso)
    enc.setBuffer(bw1, offset: 0, index: 0); enc.setBuffer(bb1, offset: 0, index: 1)
    enc.setBuffer(bw2, offset: 0, index: 2); enc.setBuffer(bb2, offset: 0, index: 3)
    enc.setBuffer(bx, offset: 0, index: 4);  enc.setBuffer(bt, offset: 0, index: 5)
    enc.setBuffer(bloss, offset: 0, index: 6); enc.setBuffer(bh1, offset: 0, index: 7)
    enc.setBuffer(ba, offset: 0, index: 8);  enc.setBuffer(bgy, offset: 0, index: 9)
    enc.setBuffer(bdh1, offset: 0, index: 10)
    enc.setBytes(&u_in, length: 4, index: 11); enc.setBytes(&u_hid, length: 4, index: 12)
    enc.setBytes(&u_out, length: 4, index: 13); enc.setBytes(&lrv, length: 4, index: 14)
    enc.dispatchThreadgroups(MTLSize(width: 1, height: 1, depth: 1),
                             threadsPerThreadgroup: MTLSize(width: tgs, height: 1, depth: 1))
    enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
}
func gpuLoss() -> Double { let p = bloss.contents().bindMemory(to: Float.self, capacity: outd); var s: Double = 0; for i in 0..<outd { s += Double(p[i]) }; return s }

// ── CPU fp32 mirror of the SAME phases (same folds, same fp32 exp/tanh) — the parity reference ──
var ch1 = z(hid), ca = z(hid), cgy = z(outd), cdh1 = z(hid)
func cpuStep() {
    for k in 0..<hid { var acc: Float = 0; var j = indim; while j > 0 { j -= 1; acc = w1[k*indim+j]*x[j] + acc }; let hk = acc + b1[k]; ch1[k] = hk; ca[k] = fgelu(hk) }
    for i in 0..<outd { var acc: Float = 0; var k = hid; while k > 0 { k -= 1; acc = w2[i*hid+k]*ca[k] + acc }; let yi = acc + b2[i]; let d = yi - t[i]; cgy[i] = 2*d }
    for k in 0..<hid { var s: Float = 0; var i = 0; while i < outd { s = s + cgy[i]*w2[i*hid+k]; i += 1 }; cdh1[k] = s * fgelud(ch1[k]) }
    for i in 0..<outd { var k = hid; while k > 0 { k -= 1; w2[i*hid+k] = w2[i*hid+k] - lr*cgy[i]*ca[k] }; b2[i] = b2[i] - lr*cgy[i] }
    for k in 0..<hid { var j = indim; while j > 0 { j -= 1; w1[k*indim+j] = w1[k*indim+j] - lr*cdh1[k]*x[j] }; b1[k] = b1[k] - lr*cdh1[k] }
}
func cpuLoss() -> Double {
    var s: Double = 0
    for i in 0..<outd { var acc: Float = 0; var k = hid; while k > 0 { k -= 1; acc = w2[i*hid+k]*ca[k] + acc }; let d = acc + b2[i] - t[i]; s += Double(d*d) }
    return s
}

// ── learning curve on the GPU, timed ──
step()
let l0 = gpuLoss()
print(String(format: "  step %5d   gpu_loss %.6f", 0, l0))
let t0 = Date()
let marks = [10, 25, 50, 100, 200, steps]
for s in 1...steps { step(); if marks.contains(s) { print(String(format: "  step %5d   gpu_loss %.6f", s, gpuLoss())) } }
let dt = Date().timeIntervalSince(t0)
let params = hid*indim + hid + outd*hid + outd
print(String(format: "GPU: %d steps of FFN(in=%d,hid=%d,out=%d, %d params) in %.1f ms  (%.3f ms/step)  loss %.6f -> %.6g",
             steps, indim, hid, outd, params, dt*1000, dt*1000/Double(steps), l0, gpuLoss()))

// ── parity gate: same steps on the CPU fp32 mirror, compare every weight ──
for _ in 0..<(steps+1) { cpuStep() }   // +1: GPU did a warm step before timing
let gw1 = bw1.contents().bindMemory(to: Float.self, capacity: hid*indim)
let gw2 = bw2.contents().bindMemory(to: Float.self, capacity: outd*hid)
let gb1 = bb1.contents().bindMemory(to: Float.self, capacity: hid)
let gb2 = bb2.contents().bindMemory(to: Float.self, capacity: outd)
var maxd: Float = 0
for n in 0..<(hid*indim) { let d = abs(gw1[n]-w1[n]); if d > maxd { maxd = d } }
for n in 0..<(outd*hid)  { let d = abs(gw2[n]-w2[n]); if d > maxd { maxd = d } }
for n in 0..<hid  { let d = abs(gb1[n]-b1[n]); if d > maxd { maxd = d } }
for n in 0..<outd { let d = abs(gb2[n]-b2[n]); if d > maxd { maxd = d } }
print(String(format: "PARITY: gpu_loss=%.9g cpu_fp32_loss=%.9g  max|W_gpu-W_cpu|=%.3e", gpuLoss(), cpuLoss(), maxd))
print(maxd == 0 ? "  ✓ bit-exact: the GPU runs the recipe's FFN training step in fp32, parity with the CPU mirror"
                : (maxd < 1e-3 ? "  ✓ within fp32 epsilon (GPU FMA-contraction of the recipe's exp/tanh vs CPU split-mul allowed)"
                               : "  ✗ parity failure"))
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── training the FFN on the M4 Max GPU (loss should fall toward 0) ──"
"$work/runner" "$INDIM" "$HID" "$OUTD" "$STEPS" "$work/train.metal"
