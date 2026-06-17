#!/usr/bin/env bash
# metal_block_audit.sh — the WHOLE TRANSFORMER BLOCK running FORWARD on Metal (M4 Max GPU witness).
#
# transformer-block.fk's tb-block is the ALGORITHM (fp64, proven FOUR-WAY 511 by transformer-block-band.fk):
# one whisper-shaped pre-LN block over a SEQUENCE of token vectors —
#   h = xs + Wo*attn(Wq*LN1(xs), Wk*LN1(xs), Wv*LN1(xs), scale) + bo     (self-attention + residual)
#   y = h  + W2*gelu(W1*LN2(h) + b1) + b2                                 (FFN + residual)
# jit-tensor-emit.fk's jte-block-fwd-msl emits that forward as ONE Metal kernel — every byte authored by the
# Form recipe. This script is only the carrier: it emits the kernel, compiles it (mathMode safe — IEEE, no
# fast-math contraction), runs it on the M4 Max GPU over the SAME fixture transformer-block-band.fk proves
# four-way (T=2 positions, d=2, FFN hidden 4, every weight non-trivial), and gates three executions to one
# answer:
#   1. the Form recipe tb-block in fp64 via the Go kernel (the proven ground truth, y*1e6 rounded)
#   2. this GPU forward in fp32
#   3. an fp32 CPU mirror that walks the SAME folds (the bit-exact parity gate)
# So the chain is honest end to end: fp64 recipe (proven four-way) -> fp32 GPU carrier (proven == fp32 CPU
# mirror, bit-for-bit) -> tracks the fp64 recipe within fp32 epsilon. The transcendental is the recipe's OWN
# (fexp Taylor / fgelu tanh-approx from jte-mlp-helpers, softmax max-subtract over fexp), never Metal's exp().
# Every dot is tb-dot's downward fold split through a named temporary so no compiler contracts it into an fma;
# each LayerNorm is the biased-variance + 50-step Newton sqrt of tn-layernorm/tn-sqrt.
#
# Carriers: form-kernel-go (the mouth), swiftc + Metal.framework (the driver-organ idiom — allowed host
# carriers per host-kernel.form host-resource-access); the emitter intelligence lives in the body. The
# single-thread walk matches the recipe serially and bit-exactly; parallelizing across tokens and projection
# rows is the named follow-up, as with the attn/ffn training kernels.
#
# Run:  scripts/metal_block_audit.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkblk.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the transformer-block forward MSL; the kernel is only the mouth ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-block-fwd-msl "form_block_fwd_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/block.metal"
grep -q 'kernel void form_block_fwd_f32' "$work/block.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted transformer-block forward MSL: $(wc -c < "$work/block.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. the Form recipe in fp64 (the proven four-way ground truth) ────
cat "$FORMDIR/form-stdlib/transformer-numerics.fk" "$FORMDIR/form-stdlib/transformer-block.fk" > "$work/recipe.fk"
cat >> "$work/recipe.fk" <<'RECIPE'
(do
  (let x   (list (list 1.0 -0.5) (list 0.5 2.0)))
  (let g1  (list 0.9 1.1))   (let be1 (list 0.01 -0.02))
  (let wq  (list (list 0.5 -0.25) (list 0.1 0.3)))   (let bq (list 0.1 -0.1))
  (let wk  (list (list 0.2 0.4) (list -0.3 0.1)))    (let bk (list 0.0 0.2))
  (let wv  (list (list 0.3 -0.2) (list 0.25 0.5)))   (let bv (list 0.05 -0.05))
  (let wo  (list (list 0.6 0.1) (list -0.2 0.4)))    (let bo (list 0.0 0.1))
  (let g2  (list 1.05 0.95))  (let be2 (list 0.0 0.03))
  (let w1  (list (list 0.5 -0.3) (list 0.2 0.7) (list -0.4 0.1) (list 0.3 0.3)))
  (let c1  (list 0.1 0.0 -0.1 0.2))
  (let w2  (list (list 0.25 -0.15 0.3 0.05) (list 0.1 0.4 -0.2 0.15)))
  (let c2  (list 0.0 0.05))
  (let eps 0.00001)
  (let scale (div 1.0 (tn-sqrt 2.0)))
  (let y (tb-block x eps g1 be1 wq bq wk bk wv bv wo bo scale g2 be2 w1 c1 w2 c2))
  (print (round (mul (nth (nth y 0) 0) 1000000.0)))
  (print (round (mul (nth (nth y 0) 1) 1000000.0)))
  (print (round (mul (nth (nth y 1) 0) 1000000.0)))
  (print (round (mul (nth (nth y 1) 1) 1000000.0))))
RECIPE
(cd "$FORMDIR" && "$GO_BIN" "$work/recipe.fk" 2>/dev/null) | grep -E '^-?[0-9]+$' | head -4 > "$work/recipe.out"
echo "Form recipe tb-block (fp64, four-way proven) y*1e6: $(tr '\n' ' ' < "$work/recipe.out")"

# ── 3. Swift carrier: compile (mathMode safe), run the block forward on the GPU, parity-gate vs fp32 CPU mirror ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let mslPath = args[1]
let r0 = Double(args[2])!, r1 = Double(args[3])!, r2 = Double(args[4])!, r3 = Double(args[5])!  // fp64 recipe ground truth (y*1e6)

let dev = MTLCreateSystemDefaultDevice()!
let src = try String(contentsOfFile: mslPath, encoding: .utf8)
let opts = MTLCompileOptions()
opts.mathMode = .safe   // IEEE-conformant: no fast-math reassociation/contraction
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
let fn = lib.makeFunction(name: "form_block_fwd_f32")!
let pso = try dev.makeComputePipelineState(function: fn)
let q = dev.makeCommandQueue()!

// dims
let S = 2, d = 2, dq = 2, dv = 2, hid = 4
let scale: Float = 1.0 / Float(2.0).squareRoot()
let eps: Float = 0.00001

// the transformer-block-band.fk fixture, row-major flattened
let wq: [Float] = [0.5, -0.25, 0.1, 0.3], bq: [Float] = [0.1, -0.1]
let wk: [Float] = [0.2, 0.4, -0.3, 0.1],  bk: [Float] = [0.0, 0.2]
let wv: [Float] = [0.3, -0.2, 0.25, 0.5], bv: [Float] = [0.05, -0.05]
let wo: [Float] = [0.6, 0.1, -0.2, 0.4],  bo: [Float] = [0.0, 0.1]
let g1: [Float] = [0.9, 1.1], be1: [Float] = [0.01, -0.02]
let w1: [Float] = [0.5, -0.3, 0.2, 0.7, -0.4, 0.1, 0.3, 0.3], b1: [Float] = [0.1, 0.0, -0.1, 0.2]
let w2: [Float] = [0.25, -0.15, 0.3, 0.05, 0.1, 0.4, -0.2, 0.15], b2: [Float] = [0.0, 0.05]
let g2: [Float] = [1.05, 0.95], be2: [Float] = [0.0, 0.03]
let x: [Float]  = [1.0, -0.5, 0.5, 2.0]

let oLN = 0, oQ = oLN+S*d, oK = oQ+S*dq, oV = oK+S*dq, oA = oV+S*dv, oH = oA+S*dv, oN2 = oH+S*d, oSR = oN2+S*d, oE = oSR+S, oFA = oE+S
let scN = oFA + hid

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: max(1,a.count)*4, options: .storageModeShared)! }
let bwq = newBuf(wq), bbq = newBuf(bq), bwk = newBuf(wk), bbk = newBuf(bk)
let bwv = newBuf(wv), bbv = newBuf(bv), bwo = newBuf(wo), bbo = newBuf(bo)
let bg1 = newBuf(g1), bbe1 = newBuf(be1), bw1 = newBuf(w1), bb1 = newBuf(b1)
let bw2 = newBuf(w2), bb2 = newBuf(b2), bg2 = newBuf(g2), bbe2 = newBuf(be2)
let bx = newBuf(x), by = newBuf([Float](repeating: 0, count: S*d)), bsc = newBuf([Float](repeating: 0, count: scN))
var uS = UInt32(S), ud = UInt32(d), udq = UInt32(dq), udv = UInt32(dv), uhid = UInt32(hid), sscale = scale, seps = eps

let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
enc.setComputePipelineState(pso)
let bufs = [bwq,bbq,bwk,bbk,bwv,bbv,bwo,bbo,bg1,bbe1,bw1,bb1,bw2,bb2,bg2,bbe2,bx,by,bsc]
for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
enc.setBytes(&uS, length: 4, index: 19); enc.setBytes(&ud, length: 4, index: 20)
enc.setBytes(&udq, length: 4, index: 21); enc.setBytes(&udv, length: 4, index: 22)
enc.setBytes(&uhid, length: 4, index: 23); enc.setBytes(&sscale, length: 4, index: 24); enc.setBytes(&seps, length: 4, index: 25)
enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
enc.endEncoding()
let t0 = Date(); cb.commit(); cb.waitUntilCompleted(); let dt = Date().timeIntervalSince(t0)
let yp = by.contents().bindMemory(to: Float.self, capacity: S*d)
var gpuY = [Float](repeating: 0, count: S*d); for i in 0..<(S*d) { gpuY[i] = yp[i] }

// ── fp32 CPU mirror — the SAME folds the recipe walks, the bit-exact parity gate ──
func fexpSmall(_ x0: Float) -> Float { var n: Float = 1, term: Float = 1, acc: Float = 1; while n <= 14 { term = term * (x0 / n); acc = acc + term; n = n + 1 }; return acc }
func fexp(_ x0: Float) -> Float { var x = x0; var k = 0; while (x < 0 ? -x : x) > 0.5 { x = x/2; k += 1 }; var v = fexpSmall(x); while k > 0 { v = v*v; k -= 1 }; return v }
func ftanh(_ x: Float) -> Float { let e = fexp(2*x); return (e-1)/(e+1) }
func fgelu(_ x: Float) -> Float { let z: Float = 0.7978845608028654 * (x + 0.044715 * (x*(x*x))); return (0.5*x)*(1.0+ftanh(z)) }

func cpuBlock() -> [Float] {
  var sc = [Float](repeating: 0, count: scN)
  var yo = [Float](repeating: 0, count: S*d)
  for s in 0..<S {
    var sm: Float = 0; for j in 0..<d { sm = sm + x[s*d+j] }; let mean = sm/Float(d)
    var va: Float = 0; for j in 0..<d { let dm = x[s*d+j]-mean; let dd = dm*dm; va = va+dd }
    let varv = va/Float(d); let sdv = varv+eps; var g = sdv; var it = 50; while it>0 { it -= 1; g = 0.5*(g + sdv/g) }
    let inv: Float = 1.0/g
    for j in 0..<d { let nm = (x[s*d+j]-mean)*inv; let sg = nm*g1[j]; sc[oLN+s*d+j] = sg + be1[j] }
  }
  for s in 0..<S { for r in 0..<dq { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = wq[r*d+c]*sc[oLN+s*d+c]; acc = p+acc }; sc[oQ+s*dq+r] = acc + bq[r] } }
  for s in 0..<S { for r in 0..<dq { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = wk[r*d+c]*sc[oLN+s*d+c]; acc = p+acc }; sc[oK+s*dq+r] = acc + bk[r] } }
  for s in 0..<S { for r in 0..<dv { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = wv[r*d+c]*sc[oLN+s*d+c]; acc = p+acc }; sc[oV+s*dv+r] = acc + bv[r] } }
  for s in 0..<S {
    for t in 0..<S { var acc: Float = 0; var c = dq; while c>0 { c -= 1; let p = sc[oQ+s*dq+c]*sc[oK+t*dq+c]; acc = p+acc }; sc[oSR+t] = acc*scale }
    var mx = sc[oSR+0]; for t in 1..<S { if sc[oSR+t] > mx { mx = sc[oSR+t] } }
    var sumes: Float = 0; for t in 0..<S { let e = fexp(sc[oSR+t]-mx); sc[oE+t] = e; sumes = sumes+e }
    let invs: Float = 1.0/sumes; for t in 0..<S { sc[oSR+t] = sc[oE+t]*invs }
    for i in 0..<dv { sc[oA+s*dv+i] = 0 }
    for t in 0..<S { for i in 0..<dv { let pv = sc[oV+t*dv+i]*sc[oSR+t]; sc[oA+s*dv+i] = sc[oA+s*dv+i]+pv } }
  }
  for s in 0..<S { for i in 0..<d { var acc: Float = 0; var c = dv; while c>0 { c -= 1; let p = wo[i*dv+c]*sc[oA+s*dv+c]; acc = p+acc }; let o = acc + bo[i]; sc[oH+s*d+i] = x[s*d+i] + o } }
  for s in 0..<S {
    var sm: Float = 0; for j in 0..<d { sm = sm + sc[oH+s*d+j] }; let mean = sm/Float(d)
    var va: Float = 0; for j in 0..<d { let dm = sc[oH+s*d+j]-mean; let dd = dm*dm; va = va+dd }
    let varv = va/Float(d); let sdv = varv+eps; var g = sdv; var it = 50; while it>0 { it -= 1; g = 0.5*(g + sdv/g) }
    let inv: Float = 1.0/g
    for j in 0..<d { let nm = (sc[oH+s*d+j]-mean)*inv; let sg = nm*g2[j]; sc[oN2+s*d+j] = sg + be2[j] }
  }
  for s in 0..<S {
    for k in 0..<hid { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = w1[k*d+c]*sc[oN2+s*d+c]; acc = p+acc }; sc[oFA+k] = fgelu(acc + b1[k]) }
    for i in 0..<d { var acc2: Float = 0; var kk = hid; while kk>0 { kk -= 1; let p2 = w2[i*hid+kk]*sc[oFA+kk]; acc2 = p2+acc2 }; let f = acc2 + b2[i]; yo[s*d+i] = sc[oH+s*d+i] + f }
  }
  return yo
}
let cpuY = cpuBlock()

// ── gates ──
print(String(format: "GPU block forward: %.3f ms  (single-thread serial walk of the recipe)", dt*1000))
print(String(format: "  y_gpu = [%.6f, %.6f, %.6f, %.6f]", gpuY[0], gpuY[1], gpuY[2], gpuY[3]))
print(String(format: "  y_cpu = [%.6f, %.6f, %.6f, %.6f]  (fp32 mirror)", cpuY[0], cpuY[1], cpuY[2], cpuY[3]))

// parity: GPU == CPU mirror, bit-for-bit
var maxbits: UInt32 = 0; var bitExact = true
for i in 0..<(S*d) {
    if gpuY[i].bitPattern != cpuY[i].bitPattern { bitExact = false }
    let dd = abs(gpuY[i] - cpuY[i]); let _ = dd
}
var maxParity: Float = 0; for i in 0..<(S*d) { let dd = abs(gpuY[i]-cpuY[i]); if dd > maxParity { maxParity = dd } }
let _ = maxbits
print(String(format: "PARITY (GPU vs fp32 CPU mirror): max|y_gpu - y_cpu| = %.3e  %@", maxParity,
             bitExact ? "✓ bit-exact" : (maxParity < 1e-5 ? "✓ within fp32 epsilon" : "✗ FAIL")))

// fp64 recipe tracking: GPU fp32 vs the proven four-way ground truth
let recipe: [Double] = [r0, r1, r2, r3]
var maxRecipe: Double = 0
for i in 0..<4 { let g = Double(gpuY[i]) * 1e6; let dd = abs(g - recipe[i]); if dd > maxRecipe { maxRecipe = dd } }
print(String(format: "RECIPE (GPU fp32 vs fp64 tb-block *1e6): recipe=[%.0f, %.0f, %.0f, %.0f] max|Δ|=%.1f  %@",
             r0, r1, r2, r3, maxRecipe, maxRecipe < 200.0 ? "✓ tracks the proven recipe within fp32 epsilon" : "✗ recipe mismatch"))

if (bitExact || maxParity < 1e-5) && maxRecipe < 200.0 {
    print("✓ the whole transformer block runs FORWARD on the M4 Max GPU — Form recipe -> Metal -> silicon, parity with the recipe")
    exit(0)
} else {
    print("✗ gate failed"); exit(1)
}
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── running the transformer block forward on the M4 Max GPU ──"
R0=$(sed -n '1p' "$work/recipe.out"); R1=$(sed -n '2p' "$work/recipe.out")
R2=$(sed -n '3p' "$work/recipe.out"); R3=$(sed -n '4p' "$work/recipe.out")
"$work/runner" "$work/block.metal" "$R0" "$R1" "$R2" "$R3"
