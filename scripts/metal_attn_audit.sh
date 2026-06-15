#!/usr/bin/env bash
# metal_attn_audit.sh — the ARCHITECT'S ATTENTION layer learning on Metal (M4 Max GPU witness).
#
# tbp-layer-step on an "attn" layer is the algorithm (fp64, proven three-way): one SGD step over the cross-
# attention-residual block h = x + Wo·attend(Wq·LN(x), ks, vs, scale) for a fixed (keys, values) context,
# updating Wq and Wo. jte-attn-train-msl emits that step as a Metal kernel — every byte authored by the Form
# recipe — composing every attention-core gradient (softmax-back, the dv partition, the dq weighted-key sum)
# plus the pre-LN and the residual highway. This script compiles the kernel, trains Wq/Wo on the M4 Max to
# steer attention onto a target, reads the loss descending, and PARITY-GATES the GPU weights against an fp32
# CPU mirror of the same step (same tb-dot downward folds, same forward attention sums, same recipe-own fexp
# softmax). The keys/values are small in the architect's blocks, so the kernel runs the whole step in one
# thread; parallelizing across keys and projection rows is the named follow-up.
#
# Run:  scripts/metal_attn_audit.sh [steps]   (defaults 400; a d=4, 3-key attention layer)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
STEPS="${1:-400}"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkattn.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the attention training-step MSL ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-attn-train-msl "form_attn_train_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/train.metal"
grep -q 'kernel void form_attn_train_f32' "$work/train.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted attention training-step MSL: $(wc -c < "$work/train.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. Swift carrier: compile, train Wq/Wo on the GPU, time, parity-gate vs CPU fp32 mirror ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let dmodel = 4, dq = 4, dv = 4, nk = 3
let steps = Int(CommandLine.arguments[1])!
let mslPath = CommandLine.arguments[2]
let lr: Float = 0.1, eps: Float = 0.00001, scale: Float = 1.0

guard let dev = MTLCreateSystemDefaultDevice() else { print("SKIP no Metal device"); exit(2) }
let opts = MTLCompileOptions(); opts.fastMathEnabled = false
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + (try String(contentsOfFile: mslPath, encoding: .utf8)), options: opts)
let pso = try dev.makeComputePipelineState(function: lib.makeFunction(name: "form_attn_train_f32")!)
let q = dev.makeCommandQueue()!

// the recipe's own fp32 exp (mirrors the emitted fexp; softmax uses it)
func fexpSmall(_ x: Float) -> Float { var n: Float = 1, t: Float = 1, a: Float = 1; while n <= 14 { t = t*(x/n); a = a+t; n += 1 }; return a }
func fexp(_ x0: Float) -> Float { var x = x0, k = 0; while (x < 0 ? -x : x) > 0.5 { x = x/2; k += 1 }; var v = fexpSmall(x); while k > 0 { v = v*v; k -= 1 }; return v }

// deterministic small setup: a fixed context, input, target; weights a mild pattern.
var wq = (0..<(dq*dmodel)).map { Float(0.05) * (Float($0 % 7) - 3.0) }
var wo = (0..<(dmodel*dv)).map { Float(0.05) * (Float($0 % 5) - 2.0) }
let x: [Float] = [1.0, 0.5, -0.5, 0.2]
let t: [Float] = [0.6, -0.3, 0.9, 0.1]
let ks: [Float] = [1,0,0,0, 0,1,0,0, 0,0,1,0]          // 3 keys, dim 4
let vs: [Float] = [0.5,0,0,0, 0,0.5,0,0, 0,0,0.5,0]    // 3 values, dim 4

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: max(1,a.count)*4, options: .storageModeShared)! }
func z(_ n: Int) -> [Float] { [Float](repeating: 0, count: n) }
let bwq = newBuf(wq), bwo = newBuf(wo), bx = newBuf(x), bt = newBuf(t), bks = newBuf(ks), bvs = newBuf(vs)
let bloss = newBuf(z(1)), bn = newBuf(z(dmodel)), bq = newBuf(z(dq)), balpha = newBuf(z(nk))
let batt = newBuf(z(dv)), bgy = newBuf(z(dmodel)), bdatt = newBuf(z(dv)), bdqg = newBuf(z(dq)), bes = newBuf(z(nk))
var ud = UInt32(dmodel), uq = UInt32(dq), uv = UInt32(dv), uk = UInt32(nk), scl = scale, lrv = lr, epsv = eps

func step() {
    let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
    enc.setComputePipelineState(pso)
    enc.setBuffer(bwq,offset:0,index:0); enc.setBuffer(bwo,offset:0,index:1)
    enc.setBuffer(bx,offset:0,index:2); enc.setBuffer(bt,offset:0,index:3)
    enc.setBuffer(bks,offset:0,index:4); enc.setBuffer(bvs,offset:0,index:5)
    enc.setBuffer(bloss,offset:0,index:6); enc.setBuffer(bn,offset:0,index:7); enc.setBuffer(bq,offset:0,index:8)
    enc.setBuffer(balpha,offset:0,index:9); enc.setBuffer(batt,offset:0,index:10); enc.setBuffer(bgy,offset:0,index:11)
    enc.setBuffer(bdatt,offset:0,index:12); enc.setBuffer(bdqg,offset:0,index:13); enc.setBuffer(bes,offset:0,index:14)
    enc.setBytes(&ud,length:4,index:15); enc.setBytes(&uq,length:4,index:16); enc.setBytes(&uv,length:4,index:17)
    enc.setBytes(&uk,length:4,index:18); enc.setBytes(&scl,length:4,index:19); enc.setBytes(&lrv,length:4,index:20); enc.setBytes(&epsv,length:4,index:21)
    enc.dispatchThreads(MTLSize(width:1,height:1,depth:1), threadsPerThreadgroup: MTLSize(width:1,height:1,depth:1))
    enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
}
func gpuLoss() -> Double { Double(bloss.contents().bindMemory(to: Float.self, capacity: 1)[0]) }

// ── CPU fp32 mirror of the SAME attention step (same folds, same fexp softmax) ──
func ln(_ h: [Float]) -> [Float] {
    var sm: Float = 0; for v in h { sm += v }; let mean = sm/Float(dmodel)
    var va: Float = 0; for v in h { let dm = v-mean; va += dm*dm }; let varv = va/Float(dmodel)
    let sd = varv+eps; var g = sd; var it = 50; while it > 0 { g = 0.5*(g + sd/g); it -= 1 }; let inv = 1/g
    return h.map { ($0-mean)*inv }
}
func cpuStep() {
    let n = ln(x)
    var qv = z(dq); for r in 0..<dq { var acc: Float = 0; var c = dmodel; while c > 0 { c -= 1; acc = wq[r*dmodel+c]*n[c] + acc }; qv[r] = acc }
    var alpha = z(nk); for k in 0..<nk { var acc: Float = 0; var c = dq; while c > 0 { c -= 1; acc = qv[c]*ks[k*dq+c] + acc }; alpha[k] = acc*scale }
    var mx = alpha[0]; for k in 1..<nk { if alpha[k] > mx { mx = alpha[k] } }
    var es = z(nk); var sumes: Float = 0; for k in 0..<nk { let e = fexp(alpha[k]-mx); es[k] = e; sumes += e }
    let invs = 1/sumes; for k in 0..<nk { alpha[k] = es[k]*invs }
    var att = z(dv); for k in 0..<nk { for i in 0..<dv { att[i] = att[i] + vs[k*dv+i]*alpha[k] } }
    var gy = z(dmodel)
    for o in 0..<dmodel { var acc: Float = 0; var c = dv; while c > 0 { c -= 1; acc = wo[o*dv+c]*att[c] + acc }; let hh = x[o] + acc; gy[o] = 2*(hh - t[o]) }
    var datt = z(dv); for o in 0..<dmodel { for j in 0..<dv { datt[j] = datt[j] + gy[o]*wo[o*dv+j] } }
    for k in 0..<nk { var acc: Float = 0; var c = dv; while c > 0 { c -= 1; acc = datt[c]*vs[k*dv+c] + acc }; es[k] = acc }   // dalpha into es
    var gdot: Float = 0; var c = nk; while c > 0 { c -= 1; gdot = es[c]*alpha[c] + gdot }
    for k in 0..<nk { es[k] = alpha[k]*(es[k] - gdot) }   // ds into es
    var dqg = z(dq); for k in 0..<nk { for r in 0..<dq { dqg[r] = dqg[r] + es[k]*ks[k*dq+r] } }
    for r in 0..<dq { dqg[r] = dqg[r]*scale }
    for r in 0..<dq { var cc = 0; while cc < dmodel { wq[r*dmodel+cc] = wq[r*dmodel+cc] - lr*dqg[r]*n[cc]; cc += 1 } }
    for o in 0..<dmodel { var cc = 0; while cc < dv { wo[o*dv+cc] = wo[o*dv+cc] - lr*gy[o]*att[cc]; cc += 1 } }
}

step()
let l0 = gpuLoss()
print(String(format: "  step %5d   gpu_loss %.6f", 0, l0))
let t0 = Date()
let marks = [10, 25, 50, 100, 200, steps]
for s in 1...steps { step(); if marks.contains(s) { print(String(format: "  step %5d   gpu_loss %.6f", s, gpuLoss())) } }
let dt = Date().timeIntervalSince(t0)
print(String(format: "GPU: %d steps of attention(d=%d, %d keys, train Wq+Wo) in %.1f ms  (%.4f ms/step)  loss %.6f -> %.6g",
             steps, dmodel, nk, dt*1000, dt*1000/Double(steps), l0, gpuLoss()))

for _ in 0..<(steps+1) { cpuStep() }   // +1: GPU did a warm step before timing
let gwq = bwq.contents().bindMemory(to: Float.self, capacity: dq*dmodel)
let gwo = bwo.contents().bindMemory(to: Float.self, capacity: dmodel*dv)
var maxd: Float = 0
for i in 0..<(dq*dmodel) { let d = abs(gwq[i]-wq[i]); if d > maxd { maxd = d } }
for i in 0..<(dmodel*dv) { let d = abs(gwo[i]-wo[i]); if d > maxd { maxd = d } }
print(String(format: "PARITY: gpu_loss=%.9g  max|W_gpu-W_cpu|=%.3e", gpuLoss(), maxd))
let ok = maxd < 1e-4
print(ok ? (maxd == 0 ? "  ✓ bit-exact: the GPU runs the recipe's attention training step in fp32, parity with the CPU mirror"
                      : "  ✓ within fp32 epsilon (GPU vs CPU rounding of the recipe's softmax exp) — attention trains on the silicon")
         : "  ✗ parity failure")
exit(ok ? 0 : 1)
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── training the attention layer on the M4 Max GPU (loss should fall toward 0) ──"
"$work/runner" "$STEPS" "$work/train.metal"
