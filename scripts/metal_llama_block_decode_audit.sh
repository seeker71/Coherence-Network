#!/usr/bin/env bash
# metal_llama_block_decode_audit.sh — the KV-CACHED DECODE STEP running on Metal (M4 Max GPU witness): the
# autoregressive generation inner loop on silicon, proven BIT-IDENTICAL to the full causal recompute.
#
# kv-llama-block.fk's lblk-generate-causal is the ALGORITHM (fp64, proven FOUR-WAY 255 by tests/kv-llama-block-band.fk):
# the real autoregressive llama decoder, generated one token at a time over a growing KV cache, proven there
# BIT-IDENTICAL to the full causal recompute lblk-block-causal (#3365, four-way 511). jit-tensor-emit.fk's
# jte-llama-block-decode-step-msl emits ONE decode step as a Metal kernel — for the new token at position p it
# RMSNorms, projects q/k/v, RoPEs q/k by p, APPENDS the RoPE'd k_p/v_p into cache slot p, attends the query over
# the grown prefix cache[0..p], then runs Wo/residual/RMSNorm2/SwiGLU/residual. Only the NEW token is projected
# each step; earlier positions' k/v are reused from the cache (O(n) per token, not the O(n^2) whole-block recompute).
#
# This script is only the carrier. It emits BOTH kernels — the decode step AND the full causal block
# (jte-llama-block-fwd-causal-msl, the kernel that runs the whole sequence at once, already proven on the M4 GPU,
# brick 3u / #3376) — compiles them mathMode-safe (IEEE, no fma contraction), and on the M4 Max GPU runs:
#   A. the full causal kernel ONCE over the whole S-token sequence            -> y_full
#   B. the decode kernel S times, threading ONE persistent cache across the S dispatches (cache slot p written
#      by step p, read 0..p) -> y_decode  (the genuine autoregressive generation loop on silicon)
# and gates them to the proven recipe:
#   1. y_decode == y_full BIT-FOR-BIT  — the KV cache equivalence (lblk-generate-causal == lblk-block-causal)
#      realized ON THE GPU: incremental cached decode reproduces the whole-sequence recompute exactly, because a
#      cached k_i/v_i depends only on position i and the fold order is identical
#   2. y_decode (fp32) tracks the Form recipe lblk-block-causal (fp64, four-way proven) within fp32 epsilon
# The autoregressive invariant this exercises: appending a future token never changes an earlier token's output
# (each cache slot is frozen at its position), so the S=3 loop proves the cache threads correctly past the
# boundary — the GPU witness of kv-llama-block-band.fk's S=2 + S=3 inductive proof. The transcendentals are the
# recipe's OWN (Newton sqrt, fexp Taylor, RoPE's fsin/fcos/fln Taylor), never Metal's.
#
# Carriers: form-kernel-go (the mouth), swiftc + Metal.framework (the driver-organ idiom, an allowed host
# carrier per host-kernel.form host-resource-access); the emitter intelligence lives in the body.
#
# Run:  scripts/metal_llama_block_decode_audit.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkdec.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits BOTH kernels (decode step + full causal block) ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==DEC==")\n(print (jte-llama-block-decode-step-msl "form_llama_decode_step_f32"))\n(print "==END==")\n(print "==CAU==")\n(print (jte-llama-block-fwd-causal-msl "form_llama_block_causal_fwd_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==DEC==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/decode.metal"
sed -n '/^==CAU==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/causal.metal"
grep -q 'kernel void form_llama_decode_step_f32' "$work/decode.metal" || { echo "FAIL no decode kernel"; exit 1; }
grep -q 'kernel void form_llama_block_causal_fwd_f32' "$work/causal.metal" || { echo "FAIL no causal kernel"; exit 1; }
echo "emitted decode-step MSL: $(wc -c < "$work/decode.metal" | tr -d ' ') bytes  |  full causal MSL: $(wc -c < "$work/causal.metal" | tr -d ' ') bytes (every byte authored by the Form recipe)"

# ── 2. the Form recipe lblk-block-causal in fp64 over the SAME 3-token fixture (the proven four-way ground truth) ──
cat "$FORMDIR/form-stdlib/transformer-numerics.fk" "$FORMDIR/form-stdlib/trig.fk" \
    "$FORMDIR/form-stdlib/llama-numerics.fk" "$FORMDIR/form-stdlib/rope.fk" "$FORMDIR/form-stdlib/transformer-block.fk" \
    "$FORMDIR/form-stdlib/llama-block.fk" > "$work/recipe.fk"
cat >> "$work/recipe.fk" <<'RECIPE'
(do
  (let x  (list (list 1.0 -0.5 0.5 2.0) (list -1.0 0.25 1.5 -0.75) (list 0.5 1.0 -1.5 0.25)))
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
  (print (round (mul (nth (nth y 1) 3) 1000000.0)))
  (print (round (mul (nth (nth y 2) 0) 1000000.0)))
  (print (round (mul (nth (nth y 2) 1) 1000000.0)))
  (print (round (mul (nth (nth y 2) 2) 1000000.0)))
  (print (round (mul (nth (nth y 2) 3) 1000000.0))))
RECIPE
(cd "$FORMDIR" && "$GO_BIN" "$work/recipe.fk" 2>/dev/null) | grep -E '^-?[0-9]+$' | head -12 > "$work/recipe.out"
echo "Form recipe lblk-block-causal (fp64, four-way proven) y*1e6: $(tr '\n' ' ' < "$work/recipe.out")"

# ── 3. Swift carrier: compile both kernels, run full-causal once + the decode loop S times, gate ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let decPath = args[1], cauPath = args[2]
let rec: [Double] = (3...14).map { Double(args[$0])! }   // fp64 recipe ground truth (y*1e6, 12 values, 3 tokens)

let dev = MTLCreateSystemDefaultDevice()!
func makeLib(_ path: String) throws -> MTLLibrary {
  let src = try String(contentsOfFile: path, encoding: .utf8)
  let opts = MTLCompileOptions(); opts.mathMode = .safe   // IEEE: no fast-math reassociation/contraction
  return try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
}
let decLib = try makeLib(decPath), cauLib = try makeLib(cauPath)
let decPso = try dev.makeComputePipelineState(function: decLib.makeFunction(name: "form_llama_decode_step_f32")!)
let cauPso = try dev.makeComputePipelineState(function: cauLib.makeFunction(name: "form_llama_block_causal_fwd_f32")!)
let q = dev.makeCommandQueue()!

// dims (kv-llama-block-band.fk fixture, extended to S=3 — the inductive step)
let S = 3, d = 4, dq = 4, dv = 4, hid = 4, HD = 4
let scale: Float = 1.0 / Float(4.0).squareRoot()
let eps: Float = 0.00001

let wq: [Float] = [0.5, -0.25, 0.1, 0.3,  0.2, 0.4, -0.3, 0.1,  -0.1, 0.2, 0.5, -0.2,  0.3, 0.0, -0.15, 0.25]
let wk: [Float] = [0.2, 0.4, -0.3, 0.1,  0.3, -0.2, 0.25, 0.5,  0.1, 0.15, -0.05, 0.2,  -0.25, 0.3, 0.4, -0.1]
let wv: [Float] = [0.3, -0.2, 0.25, 0.5,  0.6, 0.1, -0.2, 0.4,  0.05, -0.1, 0.3, 0.2,  0.15, 0.35, -0.25, 0.1]
let wo: [Float] = [0.6, 0.1, -0.2, 0.4,  -0.2, 0.4, 0.3, 0.1,  0.25, -0.15, 0.5, 0.05,  0.1, 0.2, -0.3, 0.45]
let wg: [Float] = [0.5, -0.3, 0.2, 0.1,  0.2, 0.7, -0.4, 0.3,  -0.1, 0.25, 0.4, -0.2,  0.3, 0.1, -0.15, 0.5]
let wu: [Float] = [0.25, -0.15, 0.3, 0.05,  0.1, 0.4, -0.2, 0.15,  0.35, 0.2, -0.1, 0.25,  -0.2, 0.3, 0.15, 0.4]
let wd: [Float] = [0.4, -0.2, 0.3, 0.1,  0.15, 0.5, -0.25, 0.2,  -0.3, 0.1, 0.45, -0.15,  0.2, -0.1, 0.35, 0.3]
let g1: [Float] = [0.9, 1.1, 1.0, 0.95]
let g2: [Float] = [1.05, 0.95, 1.0, 0.9]
let x:  [Float] = [1.0, -0.5, 0.5, 2.0,  -1.0, 0.25, 1.5, -0.75,  0.5, 1.0, -1.5, 0.25]

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: max(1,a.count)*4, options: .storageModeShared)! }
func zBuf(_ n: Int) -> MTLBuffer { dev.makeBuffer(bytes: [Float](repeating: 0, count: max(1,n)), length: max(1,n)*4, options: .storageModeShared)! }
let bwq = newBuf(wq), bwk = newBuf(wk), bwv = newBuf(wv), bwo = newBuf(wo)
let bg1 = newBuf(g1), bwg = newBuf(wg), bwu = newBuf(wu), bwd = newBuf(wd), bg2 = newBuf(g2)
var sscale = scale, seps = eps
var ud = UInt32(d), udq = UInt32(dq), udv = UInt32(dv), uhid = UInt32(hid), uHD = UInt32(HD)

func readF(_ b: MTLBuffer, _ n: Int) -> [Float] { let p = b.contents().bindMemory(to: Float.self, capacity: n); var o = [Float](repeating: 0, count: n); for i in 0..<n { o[i] = p[i] }; return o }

// ── A. the full causal kernel ONCE over the whole sequence (the recompute baseline, brick 3u) ──
let bxFull = newBuf(x), byFull = zBuf(S*d)
let scNfull = S*d + S*dq + S*dq + S*dv + S*dv + S*d + S*d + S + S + hid + hid + hid
let bscFull = zBuf(scNfull)
var uS = UInt32(S)
do {
  let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
  enc.setComputePipelineState(cauPso)
  let bufs = [bwq,bwk,bwv,bwo,bg1,bwg,bwu,bwd,bg2,bxFull,byFull,bscFull]
  for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
  enc.setBytes(&uS, length: 4, index: 12); enc.setBytes(&ud, length: 4, index: 13)
  enc.setBytes(&udq, length: 4, index: 14); enc.setBytes(&udv, length: 4, index: 15)
  enc.setBytes(&uhid, length: 4, index: 16); enc.setBytes(&uHD, length: 4, index: 17)
  enc.setBytes(&sscale, length: 4, index: 18); enc.setBytes(&seps, length: 4, index: 19)
  enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
  enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
}
let yFull = readF(byFull, S*d)

// ── B. the decode loop: S dispatches over ONE persistent cache (the genuine autoregressive generation loop) ──
let cacheK = zBuf(S*dq), cacheV = zBuf(S*dv)        // persistent across steps; slot p written by step p
let scNdec = d + dq + dv + d + d + S + S + hid + hid + hid   // single-token scratch, scores sized to S
let bscDec = zBuf(scNdec)
let byStep = zBuf(d)
var yDecode = [Float](repeating: 0, count: S*d)
let t0 = Date()
for p in 0..<S {
  let bxStep = newBuf(Array(x[(p*d)..<(p*d+d)]))     // the single new token x_p
  var up = UInt32(p)
  let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
  enc.setComputePipelineState(decPso)
  let bufs = [bwq,bwk,bwv,bwo,bg1,bwg,bwu,bwd,bg2,bxStep,cacheK,cacheV,byStep,bscDec]
  for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
  enc.setBytes(&up, length: 4, index: 14); enc.setBytes(&ud, length: 4, index: 15)
  enc.setBytes(&udq, length: 4, index: 16); enc.setBytes(&udv, length: 4, index: 17)
  enc.setBytes(&uhid, length: 4, index: 18); enc.setBytes(&uHD, length: 4, index: 19)
  enc.setBytes(&sscale, length: 4, index: 20); enc.setBytes(&seps, length: 4, index: 21)
  enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
  enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
  let yp = readF(byStep, d)
  for i in 0..<d { yDecode[p*d+i] = yp[i] }
}
let dt = Date().timeIntervalSince(t0)

// ── gates ──
print(String(format: "decode loop: %d dispatches over one persistent KV cache, %.3f ms total", S, dt*1000))
func fmt(_ a: [Float]) -> String { "[" + (0..<a.count).map { String(format: "%.6f", a[$0]) }.joined(separator: ", ") + "]" }
print("  y_full   (full causal recompute, one dispatch) = \(fmt(yFull))")
print("  y_decode (KV-cached loop, \(S) dispatches)        = \(fmt(yDecode))")

var bitExact = true
for i in 0..<(S*d) { if yFull[i].bitPattern != yDecode[i].bitPattern { bitExact = false } }
print(String(format: "EQUIVALENCE (decode loop vs full causal recompute on the GPU): %@",
             bitExact ? "✓ BIT-FOR-BIT identical — the KV cache reproduces the recompute exactly on silicon" : "✗ FAIL — decode != recompute"))

var maxRecipe: Double = 0
for i in 0..<(S*d) { let g = Double(yDecode[i]) * 1e6; let dd = abs(g - rec[i]); if dd > maxRecipe { maxRecipe = dd } }
print(String(format: "RECIPE (GPU fp32 decode vs fp64 lblk-block-causal *1e6): max|Δ|=%.1f  %@",
             maxRecipe, maxRecipe < 300.0 ? "✓ tracks the proven four-way recipe within fp32 epsilon" : "✗ recipe mismatch"))

if bitExact && maxRecipe < 300.0 {
    print("✓ the KV-CACHED DECODE STEP runs on the M4 Max GPU — autoregressive generation on silicon, the cache bit-identical to the full causal recompute, tracking the proven recipe")
    exit(0)
} else { print("✗ gate failed"); exit(1) }
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── running the KV-cached decode loop on the M4 Max GPU ──"
mapfile -t R < "$work/recipe.out" 2>/dev/null || { R=(); while IFS= read -r line; do R+=("$line"); done < "$work/recipe.out"; }
"$work/runner" "$work/decode.metal" "$work/causal.metal" "${R[@]}"
