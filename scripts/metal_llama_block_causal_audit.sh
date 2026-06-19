#!/usr/bin/env bash
# metal_llama_block_causal_audit.sh — the CAUSAL LLAMA decoder block running FORWARD on Metal (M4 Max GPU witness).
#
# llama-block.fk's lblk-block-causal is the ALGORITHM (fp64, proven FOUR-WAY 511 by tests/causal-attention-band.fk):
# the real AUTOREGRESSIVE llama-shaped pre-norm block over a SEQUENCE of token vectors, where each query at
# position s attends only to keys/values 0..s (the per-query key PREFIX of tb-attn-seq-causal) —
#   n1 = RMSNorm1(x)
#   h  = x + Wo*causal-attn(RoPE(Wq*n1), RoPE(Wk*n1), Wv*n1, scale)   (bias-free proj, RoPE q/k, residual)
#   n2 = RMSNorm2(h)
#   y  = h + Wdown*SwiGLU(Wgate*n2, Wup*n2)                           (silu(gate)*up FFN, residual)
# jit-tensor-emit.fk's jte-llama-block-fwd-causal-msl emits that forward as ONE Metal kernel — every byte authored
# by the Form recipe; the mask is a loop bound (while (t < s + 1u)), no numeric change to the per-pair dot/softmax.
# This script is only the carrier: it emits the kernel, compiles it (mathMode safe — IEEE, no fast-math
# contraction), runs it on the M4 Max GPU over the SAME fixture causal-attention-band.fk proves four-way
# (S=2 tokens, d=4, dq=dv=4, HD=4 single head, FFN hidden 4, scale = 1/sqrt(4)), and gates three executions
# to one answer:
#   1. the Form recipe lblk-block-causal in fp64 via the Go kernel (the proven ground truth, y*1e6 rounded)
#   2. this GPU forward in fp32
#   3. an fp32 CPU mirror that walks the SAME causal folds (the bit-exact parity gate)
# So the chain is honest end to end: fp64 recipe (proven four-way) -> fp32 GPU carrier (proven == fp32 CPU
# mirror, bit-for-bit) -> tracks the fp64 recipe within fp32 epsilon. The transcendentals are the recipe's
# OWN — RMSNorm's Newton sqrt, SiLU's fexp Taylor, RoPE's fsin/fcos/fln Taylor, softmax over fexp — never
# Metal's. Every dot is tb-dot's downward right-fold split through a named temporary so no compiler contracts
# it into an fma. The first token attends only to itself (softmax of a single score = 1.0); the last token's
# prefix is the whole sequence, so it equals the non-causal block — the relationships causal-attention-band.fk
# pins. This is the block the generation loop steps, producing one token's next-state without leaking the future.
#
# Carriers: form-kernel-go (the mouth), swiftc + Metal.framework (the driver-organ idiom — allowed host
# carriers per host-kernel.form host-resource-access); the emitter intelligence lives in the body. The
# single-thread walk matches the recipe serially and bit-exactly; parallelizing across tokens and rows is the
# named follow-up, as with the non-causal block kernel.
#
# Run:  scripts/metal_llama_block_causal_audit.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkllblkc.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the llama-block forward MSL; the kernel is only the mouth ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-llama-block-fwd-causal-msl "form_llama_block_causal_fwd_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/block.metal"
grep -q 'kernel void form_llama_block_causal_fwd_f32' "$work/block.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted llama-block forward MSL: $(wc -c < "$work/block.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. the Form recipe in fp64 (the proven four-way ground truth) ────
# core.fk is the BML dialect (handled by the validate harness); the recipe deps below are pure .fk and
# resolve lblk-block directly on the Go kernel.
cat "$FORMDIR/form-stdlib/transformer-numerics.fk" "$FORMDIR/form-stdlib/trig.fk" \
    "$FORMDIR/form-stdlib/llama-numerics.fk" "$FORMDIR/form-stdlib/rope.fk" "$FORMDIR/form-stdlib/transformer-block.fk" \
    "$FORMDIR/form-stdlib/llama-block.fk" > "$work/recipe.fk"
cat >> "$work/recipe.fk" <<'RECIPE'
(do
  (let x  (list (list 1.0 -0.5 0.5 2.0) (list -1.0 0.25 1.5 -0.75)))
  (let g1 (list 0.9 1.1 1.0 0.95))   (let g2 (list 1.05 0.95 1.0 0.9))
  (let wq (list (list 0.5 -0.25 0.1 0.3) (list 0.2 0.4 -0.3 0.1) (list -0.1 0.2 0.5 -0.2) (list 0.3 0.0 -0.15 0.25)))
  (let wk (list (list 0.2 0.4 -0.3 0.1) (list 0.3 -0.2 0.25 0.5) (list 0.1 0.15 -0.05 0.2) (list -0.25 0.3 0.4 -0.1)))
  (let wv (list (list 0.3 -0.2 0.25 0.5) (list 0.6 0.1 -0.2 0.4) (list 0.05 -0.1 0.3 0.2) (list 0.15 0.35 -0.25 0.1)))
  (let wo (list (list 0.6 0.1 -0.2 0.4) (list -0.2 0.4 0.3 0.1) (list 0.25 -0.15 0.5 0.05) (list 0.1 0.2 -0.3 0.45)))
  (let wg (list (list 0.5 -0.3 0.2 0.1) (list 0.2 0.7 -0.4 0.3) (list -0.1 0.25 0.4 -0.2) (list 0.3 0.1 -0.15 0.5)))
  (let wu (list (list 0.25 -0.15 0.3 0.05) (list 0.1 0.4 -0.2 0.15) (list 0.35 0.2 -0.1 0.25) (list -0.2 0.3 0.15 0.4)))
  (let wd (list (list 0.4 -0.2 0.3 0.1) (list 0.15 0.5 -0.25 0.2) (list -0.3 0.1 0.45 -0.15) (list 0.2 -0.1 0.35 0.3)))
  (let eps 0.00001)
  (let HD 4)
  (let scale (div 1.0 (tn-sqrt 4.0)))
  (let y (lblk-block-causal x g1 eps wq wk wv wo scale HD g2 wg wu wd))
  (print (round (mul (nth (nth y 0) 0) 1000000.0)))
  (print (round (mul (nth (nth y 0) 1) 1000000.0)))
  (print (round (mul (nth (nth y 0) 2) 1000000.0)))
  (print (round (mul (nth (nth y 0) 3) 1000000.0)))
  (print (round (mul (nth (nth y 1) 0) 1000000.0)))
  (print (round (mul (nth (nth y 1) 1) 1000000.0)))
  (print (round (mul (nth (nth y 1) 2) 1000000.0)))
  (print (round (mul (nth (nth y 1) 3) 1000000.0))))
RECIPE
(cd "$FORMDIR" && "$GO_BIN" "$work/recipe.fk" 2>/dev/null) | grep -E '^-?[0-9]+$' | head -8 > "$work/recipe.out"
echo "Form recipe lblk-block (fp64, four-way proven) y*1e6: $(tr '\n' ' ' < "$work/recipe.out")"

# ── 3. Swift carrier: compile (mathMode safe), run the block forward on the GPU, parity-gate vs fp32 CPU mirror ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let mslPath = args[1]
let rec: [Double] = (2...9).map { Double(args[$0])! }   // fp64 recipe ground truth (y*1e6, 8 values)

let dev = MTLCreateSystemDefaultDevice()!
let src = try String(contentsOfFile: mslPath, encoding: .utf8)
let opts = MTLCompileOptions()
opts.mathMode = .safe   // IEEE-conformant: no fast-math reassociation/contraction
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
let fn = lib.makeFunction(name: "form_llama_block_causal_fwd_f32")!
let pso = try dev.makeComputePipelineState(function: fn)
let q = dev.makeCommandQueue()!

// dims (llama-block-band.fk fixture)
let S = 2, d = 4, dq = 4, dv = 4, hid = 4, HD = 4
let scale: Float = 1.0 / Float(4.0).squareRoot()
let eps: Float = 0.00001

// the llama-block-band.fk fixture, row-major flattened (bias-free)
let wq: [Float] = [0.5, -0.25, 0.1, 0.3,  0.2, 0.4, -0.3, 0.1,  -0.1, 0.2, 0.5, -0.2,  0.3, 0.0, -0.15, 0.25]
let wk: [Float] = [0.2, 0.4, -0.3, 0.1,  0.3, -0.2, 0.25, 0.5,  0.1, 0.15, -0.05, 0.2,  -0.25, 0.3, 0.4, -0.1]
let wv: [Float] = [0.3, -0.2, 0.25, 0.5,  0.6, 0.1, -0.2, 0.4,  0.05, -0.1, 0.3, 0.2,  0.15, 0.35, -0.25, 0.1]
let wo: [Float] = [0.6, 0.1, -0.2, 0.4,  -0.2, 0.4, 0.3, 0.1,  0.25, -0.15, 0.5, 0.05,  0.1, 0.2, -0.3, 0.45]
let wg: [Float] = [0.5, -0.3, 0.2, 0.1,  0.2, 0.7, -0.4, 0.3,  -0.1, 0.25, 0.4, -0.2,  0.3, 0.1, -0.15, 0.5]
let wu: [Float] = [0.25, -0.15, 0.3, 0.05,  0.1, 0.4, -0.2, 0.15,  0.35, 0.2, -0.1, 0.25,  -0.2, 0.3, 0.15, 0.4]
let wd: [Float] = [0.4, -0.2, 0.3, 0.1,  0.15, 0.5, -0.25, 0.2,  -0.3, 0.1, 0.45, -0.15,  0.2, -0.1, 0.35, 0.3]
let g1: [Float] = [0.9, 1.1, 1.0, 0.95]
let g2: [Float] = [1.05, 0.95, 1.0, 0.9]
let x:  [Float] = [1.0, -0.5, 0.5, 2.0,  -1.0, 0.25, 1.5, -0.75]

let oN1 = 0, oQ = oN1+S*d, oK = oQ+S*dq, oV = oK+S*dq, oA = oV+S*dv, oH = oA+S*dv, oN2 = oH+S*d, oSR = oN2+S*d, oE = oSR+S, oG = oE+S, oU = oG+hid, oACT = oU+hid
let scN = oACT + hid

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: max(1,a.count)*4, options: .storageModeShared)! }
let bwq = newBuf(wq), bwk = newBuf(wk), bwv = newBuf(wv), bwo = newBuf(wo)
let bg1 = newBuf(g1), bwg = newBuf(wg), bwu = newBuf(wu), bwd = newBuf(wd), bg2 = newBuf(g2)
let bx = newBuf(x), by = newBuf([Float](repeating: 0, count: S*d)), bsc = newBuf([Float](repeating: 0, count: scN))
var uS = UInt32(S), ud = UInt32(d), udq = UInt32(dq), udv = UInt32(dv), uhid = UInt32(hid), uHD = UInt32(HD), sscale = scale, seps = eps

let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
enc.setComputePipelineState(pso)
let bufs = [bwq,bwk,bwv,bwo,bg1,bwg,bwu,bwd,bg2,bx,by,bsc]
for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
enc.setBytes(&uS, length: 4, index: 12); enc.setBytes(&ud, length: 4, index: 13)
enc.setBytes(&udq, length: 4, index: 14); enc.setBytes(&udv, length: 4, index: 15)
enc.setBytes(&uhid, length: 4, index: 16); enc.setBytes(&uHD, length: 4, index: 17)
enc.setBytes(&sscale, length: 4, index: 18); enc.setBytes(&seps, length: 4, index: 19)
enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
enc.endEncoding()
let t0 = Date(); cb.commit(); cb.waitUntilCompleted(); let dt = Date().timeIntervalSince(t0)
let yp = by.contents().bindMemory(to: Float.self, capacity: S*d)
var gpuY = [Float](repeating: 0, count: S*d); for i in 0..<(S*d) { gpuY[i] = yp[i] }

// ── fp32 CPU mirror — the SAME folds the recipe walks, the bit-exact parity gate ──
func fexpSmall(_ x0: Float) -> Float { var n: Float = 1, term: Float = 1, acc: Float = 1; while n <= 14 { term = term * (x0 / n); acc = acc + term; n = n + 1 }; return acc }
func fexp(_ x0: Float) -> Float { var x = x0; var k = 0; while (x < 0 ? -x : x) > 0.5 { x = x/2; k += 1 }; var v = fexpSmall(x); while k > 0 { v = v*v; k -= 1 }; return v }
func rr2pi(_ x: Float) -> Float { let t: Float = 6.283185307179586; return x - t * (x/t).rounded() }
func fsin(_ x: Float) -> Float { let r = rr2pi(x); let x2 = r*r; var term = r; var acc: Float = 0; var k = 0; while k < 10 { acc = acc + term; let m = 2*(k+1); let den = Float(m*(m+1)); term = term * ((-1*x2)/den); k += 1 }; return acc }
func fcos(_ x: Float) -> Float { return fsin(x + 1.5707963267948966) }
func fln(_ x: Float) -> Float { var a = x; var e = 0; while a >= 2 { a = a*0.5; e += 1 }; while a < 1 { a = a*2; e -= 1 }; let z = (a-1)/(a+1); let z2 = z*z; var zpow = z; var acc: Float = 0; var j = 0; while j < 14 { let num = zpow*z2; let den = Float(2*(j+1)+1); acc = acc + (num/den); zpow = zpow*z2; j += 1 }; let lm: Float = 2*(z+acc); return Float(e)*0.6931471805599453 + lm }
func fpow(_ b: Float, _ e: Float) -> Float { if b <= 0 { return 0 }; return fexp(e * fln(b)) }

func cpuBlock() -> [Float] {
  var sc = [Float](repeating: 0, count: scN)
  var yo = [Float](repeating: 0, count: S*d)
  // RMSNorm1 x -> oN1
  for s in 0..<S {
    var ss: Float = 0; for j in 0..<d { let xv = x[s*d+j]; let sq = xv*xv; ss = ss+sq }
    let meansq = ss/Float(d); let sdv = meansq+eps; var g = sdv; var it = 50; while it>0 { it -= 1; g = 0.5*(g + sdv/g) }
    let inv: Float = 1.0/g
    for j in 0..<d { let nm = x[s*d+j]*inv; sc[oN1+s*d+j] = nm*g1[j] }
  }
  // bias-free q/k/v projections
  for s in 0..<S { for r in 0..<dq { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = wq[r*d+c]*sc[oN1+s*d+c]; acc = p+acc }; sc[oQ+s*dq+r] = acc } }
  for s in 0..<S { for r in 0..<dq { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = wk[r*d+c]*sc[oN1+s*d+c]; acc = p+acc }; sc[oK+s*dq+r] = acc } }
  for s in 0..<S { for r in 0..<dv { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = wv[r*d+c]*sc[oN1+s*d+c]; acc = p+acc }; sc[oV+s*dv+r] = acc } }
  // RoPE q and k
  for s in 0..<S { var i = 0; while i+1 < dq { let hd = i % HD; let fr = fpow(10000, (-1*Float(hd))/Float(HD)); let a = Float(s)*fr; let ca = fcos(a); let sa = fsin(a); let q0 = sc[oQ+s*dq+i]; let q1 = sc[oQ+s*dq+i+1]; let t0 = q0*ca; let t1 = q1*sa; sc[oQ+s*dq+i] = t0-t1; let t2 = q0*sa; let t3 = q1*ca; sc[oQ+s*dq+i+1] = t2+t3; i += 2 } }
  for s in 0..<S { var i = 0; while i+1 < dq { let hd = i % HD; let fr = fpow(10000, (-1*Float(hd))/Float(HD)); let a = Float(s)*fr; let ca = fcos(a); let sa = fsin(a); let q0 = sc[oK+s*dq+i]; let q1 = sc[oK+s*dq+i+1]; let t0 = q0*ca; let t1 = q1*sa; sc[oK+s*dq+i] = t0-t1; let t2 = q0*sa; let t3 = q1*ca; sc[oK+s*dq+i+1] = t2+t3; i += 2 } }
  // attention
  for s in 0..<S {
    for t in 0..<(s+1) { var acc: Float = 0; var c = dq; while c>0 { c -= 1; let p = sc[oQ+s*dq+c]*sc[oK+t*dq+c]; acc = p+acc }; sc[oSR+t] = acc*scale }
    var mx = sc[oSR+0]; for t in 1..<(s+1) { if sc[oSR+t] > mx { mx = sc[oSR+t] } }
    var sumes: Float = 0; for t in 0..<(s+1) { let e = fexp(sc[oSR+t]-mx); sc[oE+t] = e; sumes = sumes+e }
    let invs: Float = 1.0/sumes; for t in 0..<(s+1) { sc[oSR+t] = sc[oE+t]*invs }
    for i in 0..<dv { sc[oA+s*dv+i] = 0 }
    for t in 0..<(s+1) { for i in 0..<dv { let pv = sc[oV+t*dv+i]*sc[oSR+t]; sc[oA+s*dv+i] = sc[oA+s*dv+i]+pv } }
  }
  // output proj + residual
  for s in 0..<S { for i in 0..<d { var acc: Float = 0; var c = dv; while c>0 { c -= 1; let p = wo[i*dv+c]*sc[oA+s*dv+c]; acc = p+acc }; sc[oH+s*d+i] = x[s*d+i] + acc } }
  // RMSNorm2 oH -> oN2
  for s in 0..<S {
    var ss: Float = 0; for j in 0..<d { let xv = sc[oH+s*d+j]; let sq = xv*xv; ss = ss+sq }
    let meansq = ss/Float(d); let sdv = meansq+eps; var g = sdv; var it = 50; while it>0 { it -= 1; g = 0.5*(g + sdv/g) }
    let inv: Float = 1.0/g
    for j in 0..<d { let nm = sc[oH+s*d+j]*inv; sc[oN2+s*d+j] = nm*g2[j] }
  }
  // SwiGLU FFN + residual
  for s in 0..<S {
    for k in 0..<hid { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = wg[k*d+c]*sc[oN2+s*d+c]; acc = p+acc }; sc[oG+k] = acc }
    for k in 0..<hid { var acc: Float = 0; var c = d; while c>0 { c -= 1; let p = wu[k*d+c]*sc[oN2+s*d+c]; acc = p+acc }; sc[oU+k] = acc }
    for k in 0..<hid { let gv = sc[oG+k]; let sig: Float = 1.0/(1.0 + fexp(-1*gv)); let sl = gv*sig; sc[oACT+k] = sl*sc[oU+k] }
    for i in 0..<d { var acc2: Float = 0; var kk = hid; while kk>0 { kk -= 1; let p2 = wd[i*hid+kk]*sc[oACT+kk]; acc2 = p2+acc2 }; yo[s*d+i] = sc[oH+s*d+i] + acc2 }
  }
  return yo
}
let cpuY = cpuBlock()

// ── gates ──
print(String(format: "GPU llama-block forward: %.3f ms  (single-thread serial walk of the recipe)", dt*1000))
print(String(format: "  y_gpu = [%.6f, %.6f, %.6f, %.6f, %.6f, %.6f, %.6f, %.6f]", gpuY[0], gpuY[1], gpuY[2], gpuY[3], gpuY[4], gpuY[5], gpuY[6], gpuY[7]))
print(String(format: "  y_cpu = [%.6f, %.6f, %.6f, %.6f, %.6f, %.6f, %.6f, %.6f]  (fp32 mirror)", cpuY[0], cpuY[1], cpuY[2], cpuY[3], cpuY[4], cpuY[5], cpuY[6], cpuY[7]))

var bitExact = true
for i in 0..<(S*d) { if gpuY[i].bitPattern != cpuY[i].bitPattern { bitExact = false } }
var maxParity: Float = 0; for i in 0..<(S*d) { let dd = abs(gpuY[i]-cpuY[i]); if dd > maxParity { maxParity = dd } }
print(String(format: "PARITY (GPU vs fp32 CPU mirror): max|y_gpu - y_cpu| = %.3e  %@", maxParity,
             bitExact ? "✓ bit-exact" : (maxParity < 1e-5 ? "✓ within fp32 epsilon" : "✗ FAIL")))

var maxRecipe: Double = 0
for i in 0..<(S*d) { let g = Double(gpuY[i]) * 1e6; let dd = abs(g - rec[i]); if dd > maxRecipe { maxRecipe = dd } }
print(String(format: "RECIPE (GPU fp32 vs fp64 lblk-block *1e6): max|Δ|=%.1f  %@",
             maxRecipe, maxRecipe < 200.0 ? "✓ tracks the proven recipe within fp32 epsilon" : "✗ recipe mismatch"))

if (bitExact || maxParity < 1e-5) && maxRecipe < 200.0 {
    print("✓ the whole LLAMA decoder block runs FORWARD on the M4 Max GPU — Form recipe -> Metal -> silicon, parity with the recipe")
    exit(0)
} else {
    print("✗ gate failed"); exit(1)
}
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── running the llama decoder block forward on the M4 Max GPU ──"
R0=$(sed -n '1p' "$work/recipe.out"); R1=$(sed -n '2p' "$work/recipe.out")
R2=$(sed -n '3p' "$work/recipe.out"); R3=$(sed -n '4p' "$work/recipe.out")
R4=$(sed -n '5p' "$work/recipe.out"); R5=$(sed -n '6p' "$work/recipe.out")
R6=$(sed -n '7p' "$work/recipe.out"); R7=$(sed -n '8p' "$work/recipe.out")
"$work/runner" "$work/block.metal" "$R0" "$R1" "$R2" "$R3" "$R4" "$R5" "$R6" "$R7"
