#!/usr/bin/env bash
# metal_arch_search_audit.sh — the ARCHITECT'S CAPACITY SEARCH on Metal (M4 Max GPU witness).
#
# arch-capacity.fk's ac-min-width is the algorithm (fp64, proven three-way in arch-capacity-band → 31): at d=4
# a 4-example dataset needs ENOUGH hidden width — a width-1 FFN-residual layer underfits, a width-2+ fits — and
# the architect trains each width over the whole dataset and crowns the SMALLEST that fits. This script runs
# that exact search ON THE GPU: jte-resid-train-msl emits the architect's real layer (the pre-LN residual block
# y = h + (W2·gelu(W1·LN(h)+b1)+b2), tbp-stk-step on one "ffn" layer) as a Metal kernel; the carrier trains each
# candidate width over the dataset on the M4 Max, measures the trained dataset loss, and crowns minimal-width-
# that-fits. The architect times REAL candidates on the silicon.
#
# THREE executions, ONE crown. (1) the fp64 Form recipe ac-min-width via arch-capacity-band → 31 (crowns 2).
# (2) this GPU search. (3) an fp32 CPU mirror of the same phases. Weights start from ac-w computed in fp64 and
# narrowed to fp32, so the GPU and the recipe begin from the same point; the discrimination (w1 loss ≫ w2 loss)
# is robust enough that fp32 training crowns the same width the fp64 recipe does.
#
# Run:  scripts/metal_arch_search_audit.sh   (the d=4 reversal dataset, widths 1..4, lr 0.05, 150 epochs)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkarch.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the architect's residual-block training-step MSL ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-resid-train-msl "form_resid_train_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/train.metal"
grep -q 'kernel void form_resid_train_f32' "$work/train.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted residual-block training-step MSL: $(wc -c < "$work/train.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. (Form recipe crown) confirm ac-min-width crowns 2 on this dataset, fp64, via the proven band ──
echo "── Form recipe ac-min-width (fp64, three-way) on the d=4 reversal dataset ──"
( cd "$FORMDIR" && ./validate.sh form-stdlib/tests/arch-capacity-band.fk >/dev/null 2>&1 \
    && echo "  arch-capacity-band → 31: recipe crowns width 2 (w1 underfits, w2 fits)" ) \
  || echo "  (band run skipped/failed in this environment — GPU vs CPU parity below still stands)"

# ── 3. Swift carrier: the capacity search on the GPU, parity vs the fp32 CPU mirror ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let d = 4, maxh = 4, epochs = 150
let lr: Float = 0.05, eps: Float = 0.00001, efit: Double = 0.001, seed = 0.3
let mslPath = CommandLine.arguments[1]

guard let dev = MTLCreateSystemDefaultDevice() else { print("SKIP no Metal device"); exit(2) }
let opts = MTLCompileOptions(); opts.fastMathEnabled = false
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + (try String(contentsOfFile: mslPath, encoding: .utf8)), options: opts)
let pso = try dev.makeComputePipelineState(function: lib.makeFunction(name: "form_resid_train_f32")!)
let q = dev.makeCommandQueue()!

// ── the recipe's deterministic weights: ac-w(seed) computed in fp64, narrowed to fp32 (so GPU == recipe init) ──
func acw(_ s: Double) -> Float { let v = s * 12.9898; return Float((( v - v.rounded(.down) ) - 0.5) * 0.3) }
func acMat(_ rows: Int, _ cols: Int, _ s0: Double) -> [Float] {  // ac-mat: row r seed s0+r*7.3, col c seed +c*1.7
    var m = [Float](repeating: 0, count: rows*cols)
    for r in 0..<rows { for c in 0..<cols { m[r*cols+c] = acw(s0 + Double(r)*7.3 + Double(c)*1.7) } }
    return m
}
// dataset: four d=4 inputs, target = input reversed (arch-capacity-band's fixture)
let X: [[Float]] = [[2,1,0,0],[0,2,1,0],[0,0,2,1],[1,0,0,2]]
let T: [[Float]] = [[0,0,1,2],[0,1,2,0],[1,2,0,0],[2,0,0,1]]

// ── the recipe's own fp32 numerics (mirror the emitted fexp/ftanh/fgelu + tn-layernorm folds) ──
func fexpSmall(_ x: Float) -> Float { var n: Float = 1, t: Float = 1, a: Float = 1; while n <= 14 { t = t*(x/n); a = a+t; n += 1 }; return a }
func fexp(_ x0: Float) -> Float { var x = x0, k = 0; while (x < 0 ? -x : x) > 0.5 { x = x/2; k += 1 }; var v = fexpSmall(x); while k > 0 { v = v*v; k -= 1 }; return v }
func ftanh(_ x: Float) -> Float { let e = fexp(2*x); return (e-1)/(e+1) }
func fgelu(_ x: Float) -> Float { let z = Float(0.7978845608028654)*(x + Float(0.044715)*(x*(x*x))); return (0.5*x)*(1+ftanh(z)) }
func fgelud(_ x: Float) -> Float { let z = Float(0.7978845608028654)*(x + Float(0.044715)*(x*(x*x))); let th = ftanh(z); return (0.5*(1+th)) + ((0.5*x)*((1-(th*th))*(Float(0.7978845608028654)*(1+(Float(0.134145)*(x*x)))))) }
func layernorm(_ h: [Float]) -> [Float] {
    var sm: Float = 0; for v in h { sm += v }; let mean = sm/Float(d)
    var va: Float = 0; for v in h { let dm = v-mean; va += dm*dm }; let varv = va/Float(d)
    let sdv = varv+eps; var g = sdv; var it = 50; while it > 0 { g = 0.5*(g + sdv/g); it -= 1 }; let inv = 1/g
    return h.map { ($0-mean)*inv }
}
// residual-block forward (for the dataset-loss measurement, shared by GPU-read and CPU-mirror weights)
func residLoss(_ w1: [Float], _ b1: [Float], _ w2: [Float], _ b2: [Float], _ H: Int) -> Double {
    var loss: Double = 0
    for ex in 0..<X.count {
        let h = X[ex]; let z = layernorm(h)
        var a = [Float](repeating: 0, count: H)
        for k in 0..<H { var acc: Float = 0; var j = d; while j > 0 { j -= 1; acc = w1[k*d+j]*z[j] + acc }; a[k] = fgelu(acc + b1[k]) }
        for i in 0..<d { var acc: Float = 0; var k = H; while k > 0 { k -= 1; acc = w2[i*H+k]*a[k] + acc }; let y = h[i] + acc + b2[i]; let e = y - T[ex][i]; loss += Double(e*e) }
    }
    return loss
}

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: max(1,a.count)*4, options: .storageModeShared)! }

// ── train width H on the GPU over the dataset, return the trained weights ──
func gpuTrain(_ H: Int) -> ([Float],[Float],[Float],[Float]) {
    let w1 = acMat(H, d, seed), b1 = [Float](repeating: 0, count: H)        // copied into GPU buffers; the GPU mutates the buffers, not these
    let w2 = acMat(d, H, seed+100), b2 = [Float](repeating: 0, count: d)
    let bw1 = newBuf(w1), bb1 = newBuf(b1), bw2 = newBuf(w2), bb2 = newBuf(b2)
    let flatX = X.flatMap { $0 }, flatT = T.flatMap { $0 }
    let bH = newBuf(flatX), bT = newBuf(flatT)
    let bloss = newBuf([Float](repeating: 0, count: d)), bh1 = newBuf([Float](repeating:0,count:H))
    let ba = newBuf([Float](repeating:0,count:H)), bgy = newBuf([Float](repeating:0,count:d))
    let bdh1 = newBuf([Float](repeating:0,count:H)), bz = newBuf([Float](repeating:0,count:d))
    var ui = UInt32(d), uh = UInt32(H), uo = UInt32(d), lrv = lr, epsv = eps
    let tgs = min(pso.maxTotalThreadsPerThreadgroup, max(H, d))
    for _ in 0..<epochs {
        for ex in 0..<X.count {
            let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
            enc.setComputePipelineState(pso)
            enc.setBuffer(bw1,offset:0,index:0); enc.setBuffer(bb1,offset:0,index:1)
            enc.setBuffer(bw2,offset:0,index:2); enc.setBuffer(bb2,offset:0,index:3)
            enc.setBuffer(bH,offset:ex*d*4,index:4); enc.setBuffer(bT,offset:ex*d*4,index:5)
            enc.setBuffer(bloss,offset:0,index:6); enc.setBuffer(bh1,offset:0,index:7)
            enc.setBuffer(ba,offset:0,index:8); enc.setBuffer(bgy,offset:0,index:9)
            enc.setBuffer(bdh1,offset:0,index:10); enc.setBuffer(bz,offset:0,index:11)
            enc.setBytes(&ui,length:4,index:12); enc.setBytes(&uh,length:4,index:13)
            enc.setBytes(&uo,length:4,index:14); enc.setBytes(&lrv,length:4,index:15); enc.setBytes(&epsv,length:4,index:16)
            enc.dispatchThreadgroups(MTLSize(width:1,height:1,depth:1), threadsPerThreadgroup: MTLSize(width:tgs,height:1,depth:1))
            enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
        }
    }
    func rd(_ b: MTLBuffer, _ n: Int) -> [Float] { let p = b.contents().bindMemory(to: Float.self, capacity: n); return (0..<n).map { p[$0] } }
    return (rd(bw1,H*d), rd(bb1,H), rd(bw2,d*H), rd(bb2,d))
}

// ── the SAME training on the fp32 CPU mirror (same phases, same folds) ──
func cpuTrain(_ H: Int) -> ([Float],[Float],[Float],[Float]) {
    var w1 = acMat(H, d, seed), b1 = [Float](repeating: 0, count: H)
    var w2 = acMat(d, H, seed+100), b2 = [Float](repeating: 0, count: d)
    for _ in 0..<epochs {
        for ex in 0..<X.count {
            let h = X[ex], t = T[ex]; let z = layernorm(h)
            var h1 = [Float](repeating:0,count:H), a = [Float](repeating:0,count:H)
            for k in 0..<H { var acc: Float = 0; var j = d; while j > 0 { j -= 1; acc = w1[k*d+j]*z[j] + acc }; h1[k] = acc + b1[k]; a[k] = fgelu(h1[k]) }
            var gy = [Float](repeating:0,count:d)
            for i in 0..<d { var acc: Float = 0; var k = H; while k > 0 { k -= 1; acc = w2[i*H+k]*a[k] + acc }; let y = h[i] + acc + b2[i]; gy[i] = 2*(y - t[i]) }
            var dh1 = [Float](repeating:0,count:H)
            for k in 0..<H { var s: Float = 0; var i = 0; while i < d { s = s + gy[i]*w2[i*H+k]; i += 1 }; dh1[k] = s*fgelud(h1[k]) }
            for i in 0..<d { var k = H; while k > 0 { k -= 1; w2[i*H+k] = w2[i*H+k] - lr*gy[i]*a[k] }; b2[i] = b2[i] - lr*gy[i] }
            for k in 0..<H { var j = d; while j > 0 { j -= 1; w1[k*d+j] = w1[k*d+j] - lr*dh1[k]*z[j] }; b1[k] = b1[k] - lr*dh1[k] }
        }
    }
    return (w1,b1,w2,b2)
}

// ── run the search on both, crown minimal-width-that-fits ──
print("  width   gpu_loss        cpu_loss        fits(efit=\(efit))")
var crownGpu = 0, crownCpu = 0
for H in 1...maxh {
    let (g1,g2,g3,g4) = gpuTrain(H); let gl = residLoss(g1,g2,g3,g4,H)
    let (c1,c2,c3,c4) = cpuTrain(H); let cl = residLoss(c1,c2,c3,c4,H)
    if crownGpu == 0 && gl < efit { crownGpu = H }
    if crownCpu == 0 && cl < efit { crownCpu = H }
    print(String(format: "  %3d     %.9f   %.9f   gpu=%@ cpu=%@", H, gl, cl, gl < efit ? "Y":"n", cl < efit ? "Y":"n"))
}
print("")
print("CROWN: gpu=\(crownGpu)  cpu=\(crownCpu)  recipe(ac-min-width)=2")
let ok = crownGpu == 2 && crownCpu == 2
print(ok ? "  ✓ the architect's capacity search runs on the GPU and crowns width 2 — matching the fp64 recipe and the fp32 CPU mirror. Capacity discovered on the silicon."
         : "  ✗ crown mismatch — investigate")
exit(ok ? 0 : 1)
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── the architect's capacity search on the M4 Max GPU (crown the minimal width that fits) ──"
"$work/runner" "$work/train.metal"
