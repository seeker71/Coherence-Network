#!/usr/bin/env bash
# metal_multi_layer_stack_audit.sh — the MULTI-LAYER causal llama DECODE STACK running on Metal (M4 Max GPU
# witness): the DEPTH structure of real local llama inference on silicon, proven BIT-IDENTICAL to the full
# causal recompute, and tracking the four-way-proven fp64 recipe within fp32 epsilon.
#
# A real llama3.2:3b is DEPTH: 28 decoder blocks, each layer with its OWN weights and its OWN KV cache —
# x¹=block₀(x⁰); x²=block₁(x¹); …. multi-layer-stack.fk's lblk-stack-causal/lblk-stack-generate are the
# ALGORITHM (fp64, proven FOUR-WAY 255 by tests/multi-layer-stack-band.fk, #3z/#3423): they fold the causal
# llama block across depth two ways — full causal recompute, and KV-cached incremental decode each layer its
# own cache — and are proven BIT-IDENTICAL there (lblk-generate-causal == lblk-block-causal per layer, #3408;
# lblk-block-causal four-way #3365). The single block already runs forward on the M4 GPU (#3355/#3376) and the
# KV-cached decode STEP runs on the M4 GPU (#3412, scripts/metal_llama_block_decode_audit.sh). This script
# proves they STACK on silicon: the named next stone from #3423's receipt — "emit the multi-layer stack to
# Metal: stack the #3412 decode kernel, each layer its own device cache buffer."
#
# This script is only the carrier. It REUSES the two already-proven Form-emitted kernels verbatim — the decode
# step (jte-llama-block-decode-step-msl, #3412) and the full causal block (jte-llama-block-fwd-causal-msl,
# #3376) — no new MSL. The depth stacking is the FOLD ORDER the Form recipe lblk-stack-* already dictates,
# carried by host dispatches: one dispatch of the per-block kernel per (layer) for recompute, per (position,
# layer) for cached decode, threading layer ℓ's output into layer ℓ+1 and giving each layer its own device
# cache buffer. On the M4 Max GPU over TWO DISTINCT layers (L0 = causal-attention-band weights, L1 = a second
# bundle, so the stack genuinely threads per-layer weights forward) it runs:
#   A. the RECOMPUTE stack — full causal kernel once per layer over the whole S-token sequence -> y_recompute
#   B. the DECODE   stack — for each position p, run each layer's decode kernel in depth order, each layer
#      appending to its OWN persistent cache slot p and reading its prefix 0..p -> y_decode  (the genuine
#      autoregressive multi-layer generation loop on silicon)
# and gates them to the proven recipe + the independent libm reference:
#   1. y_decode == y_recompute BIT-FOR-BIT  — the multi-layer KV-cache equivalence (lblk-stack-generate ==
#      lblk-stack-causal) realized ON THE GPU across depth: every layer's cached decode reproduces its full
#      recompute exactly, so the depth fold of the cached path equals the depth fold of the recompute path
#   2. y_recompute (fp32) tracks the Form recipe lblk-stack-causal (fp64, four-way proven) within fp32 epsilon
#   3. the 2-layer token-0 output matches the libm pin 1936158 AND DIFFERS from the 1-layer pin 1893731 —
#      depth actually did work (the stack is not one block applied once)
# The autoregressive invariant this exercises THROUGH depth: appending a future token never changes an earlier
# token's STACKED output (every layer is causal, every cache entry frozen at its (layer, position)), so the
# S=3 loop proves the multi-layer cache threads correctly past the boundary. Transcendentals stay the recipe's
# OWN (Newton sqrt, fexp Taylor, RoPE's fsin/fcos/fln Taylor), never Metal's.
#
# Carriers: form-kernel-go (the mouth), swiftc + Metal.framework (the driver-organ idiom, an allowed host
# carrier per host-kernel.form host-resource-access); the emitter intelligence + the fold order live in the body.
#
# Run:  scripts/metal_multi_layer_stack_audit.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkmls.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits BOTH per-block kernels (decode step + full causal block), reused verbatim across layers ──
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==DEC==")\n(print (jte-llama-block-decode-step-msl "form_llama_decode_step_f32"))\n(print "==END==")\n(print "==CAU==")\n(print (jte-llama-block-fwd-causal-msl "form_llama_block_causal_fwd_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==DEC==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/decode.metal"
sed -n '/^==CAU==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/causal.metal"
grep -q 'kernel void form_llama_decode_step_f32' "$work/decode.metal" || { echo "FAIL no decode kernel"; exit 1; }
grep -q 'kernel void form_llama_block_causal_fwd_f32' "$work/causal.metal" || { echo "FAIL no causal kernel"; exit 1; }
echo "emitted decode-step MSL: $(wc -c < "$work/decode.metal" | tr -d ' ') bytes  |  full causal MSL: $(wc -c < "$work/causal.metal" | tr -d ' ') bytes (both reused verbatim per layer)"

# ── 2. the Form recipe lblk-stack-causal in fp64 over the 2-layer / 3-token fixture (the proven four-way ground truth) ──
cat "$FORMDIR/form-stdlib/transformer-numerics.fk" "$FORMDIR/form-stdlib/trig.fk" \
    "$FORMDIR/form-stdlib/llama-numerics.fk" "$FORMDIR/form-stdlib/rope.fk" "$FORMDIR/form-stdlib/transformer-block.fk" \
    "$FORMDIR/form-stdlib/llama-block.fk" "$FORMDIR/form-stdlib/kv-cache.fk" "$FORMDIR/form-stdlib/kv-llama-block.fk" \
    "$FORMDIR/form-stdlib/multi-layer-stack.fk" > "$work/recipe.fk"
cat >> "$work/recipe.fk" <<'RECIPE'
(do
  (let x  (list (list 1.0 -0.5 0.5 2.0) (list -1.0 0.25 1.5 -0.75) (list 0.5 1.0 -0.5 0.25)))
  (let g1 (list 0.9 1.1 1.0 0.95))   (let g2 (list 1.05 0.95 1.0 0.9))
  (let wq (list (list 0.5 -0.25 0.1 0.3) (list 0.2 0.4 -0.3 0.1) (list -0.1 0.2 0.5 -0.2) (list 0.3 0.0 -0.15 0.25)))
  (let wk (list (list 0.2 0.4 -0.3 0.1) (list 0.3 -0.2 0.25 0.5) (list 0.1 0.15 -0.05 0.2) (list -0.25 0.3 0.4 -0.1)))
  (let wv (list (list 0.3 -0.2 0.25 0.5) (list 0.6 0.1 -0.2 0.4) (list 0.05 -0.1 0.3 0.2) (list 0.15 0.35 -0.25 0.1)))
  (let wo (list (list 0.6 0.1 -0.2 0.4) (list -0.2 0.4 0.3 0.1) (list 0.25 -0.15 0.5 0.05) (list 0.1 0.2 -0.3 0.45)))
  (let wg (list (list 0.5 -0.3 0.2 0.1) (list 0.2 0.7 -0.4 0.3) (list -0.1 0.25 0.4 -0.2) (list 0.3 0.1 -0.15 0.5)))
  (let wu (list (list 0.25 -0.15 0.3 0.05) (list 0.1 0.4 -0.2 0.15) (list 0.35 0.2 -0.1 0.25) (list -0.2 0.3 0.15 0.4)))
  (let wd (list (list 0.4 -0.2 0.3 0.1) (list 0.15 0.5 -0.25 0.2) (list -0.3 0.1 0.45 -0.15) (list 0.2 -0.1 0.35 0.3)))
  (let g1b (list 1.0 0.9 1.05 1.1))  (let g2b (list 0.95 1.1 0.9 1.0))
  (let wqb (list (list 0.1 0.3 -0.2 0.4) (list -0.3 0.2 0.5 -0.1) (list 0.4 -0.1 0.2 0.3) (list 0.0 0.25 -0.35 0.15)))
  (let wkb (list (list 0.3 -0.2 0.4 0.1) (list 0.15 0.5 -0.1 0.2) (list -0.05 0.3 0.25 -0.15) (list 0.4 -0.25 0.1 0.35)))
  (let wvb (list (list 0.2 0.4 -0.15 0.3) (list 0.5 -0.1 0.2 0.45) (list -0.2 0.35 0.1 -0.05) (list 0.25 0.15 -0.3 0.2)))
  (let wob (list (list 0.4 -0.3 0.2 0.5) (list 0.1 0.45 -0.15 0.2) (list -0.25 0.3 0.4 0.05) (list 0.35 -0.1 0.25 -0.2)))
  (let wgb (list (list 0.3 0.2 -0.4 0.1) (list 0.5 -0.3 0.15 0.25) (list -0.1 0.4 0.3 -0.2) (list 0.2 0.05 -0.25 0.45)))
  (let wub (list (list 0.15 0.35 -0.2 0.1) (list 0.4 -0.15 0.25 0.3) (list -0.25 0.2 0.35 -0.1) (list 0.3 0.1 -0.05 0.4)))
  (let wdb (list (list 0.35 -0.15 0.25 0.2) (list 0.2 0.4 -0.3 0.1) (list -0.2 0.15 0.5 -0.25) (list 0.1 -0.05 0.3 0.45)))
  (let eps 0.00001)
  (let HD 4)
  (let scale (div 1.0 (tn-sqrt 4.0)))
  (let L0 (list g1 wq wk wv wo g2 wg wu wd))
  (let L1 (list g1b wqb wkb wvb wob g2b wgb wub wdb))
  (let y (lblk-stack-causal x (list L0 L1) eps scale HD))
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
echo "Form recipe lblk-stack-causal (fp64, four-way proven, 2 layers) y*1e6: $(tr '\n' ' ' < "$work/recipe.out")"

# ── 3. Swift carrier: compile both per-block kernels, stack 2 distinct layers two ways on the GPU, gate ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let decPath = args[1], cauPath = args[2]
let rec: [Double] = (3...14).map { Double(args[$0])! }   // fp64 recipe ground truth (y*1e6, 12 values, 3 tokens, 2-layer stack)

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

// dims (multi-layer-stack-band.fk fixture, S=3 — the inductive step through depth)
let S = 3, d = 4, dq = 4, dv = 4, hid = 4, HD = 4
let scale: Float = 1.0 / Float(4.0).squareRoot()
let eps: Float = 0.00001

// --- per-layer weight bundles (L0 = causal-attention-band; L1 = distinct) ---
struct Layer {
  let wq, wk, wv, wo, g1, wg, wu, wd, g2: [Float]
}
let L0 = Layer(
  wq: [0.5, -0.25, 0.1, 0.3,  0.2, 0.4, -0.3, 0.1,  -0.1, 0.2, 0.5, -0.2,  0.3, 0.0, -0.15, 0.25],
  wk: [0.2, 0.4, -0.3, 0.1,  0.3, -0.2, 0.25, 0.5,  0.1, 0.15, -0.05, 0.2,  -0.25, 0.3, 0.4, -0.1],
  wv: [0.3, -0.2, 0.25, 0.5,  0.6, 0.1, -0.2, 0.4,  0.05, -0.1, 0.3, 0.2,  0.15, 0.35, -0.25, 0.1],
  wo: [0.6, 0.1, -0.2, 0.4,  -0.2, 0.4, 0.3, 0.1,  0.25, -0.15, 0.5, 0.05,  0.1, 0.2, -0.3, 0.45],
  g1: [0.9, 1.1, 1.0, 0.95],
  wg: [0.5, -0.3, 0.2, 0.1,  0.2, 0.7, -0.4, 0.3,  -0.1, 0.25, 0.4, -0.2,  0.3, 0.1, -0.15, 0.5],
  wu: [0.25, -0.15, 0.3, 0.05,  0.1, 0.4, -0.2, 0.15,  0.35, 0.2, -0.1, 0.25,  -0.2, 0.3, 0.15, 0.4],
  wd: [0.4, -0.2, 0.3, 0.1,  0.15, 0.5, -0.25, 0.2,  -0.3, 0.1, 0.45, -0.15,  0.2, -0.1, 0.35, 0.3],
  g2: [1.05, 0.95, 1.0, 0.9])
let L1 = Layer(
  wq: [0.1, 0.3, -0.2, 0.4,  -0.3, 0.2, 0.5, -0.1,  0.4, -0.1, 0.2, 0.3,  0.0, 0.25, -0.35, 0.15],
  wk: [0.3, -0.2, 0.4, 0.1,  0.15, 0.5, -0.1, 0.2,  -0.05, 0.3, 0.25, -0.15,  0.4, -0.25, 0.1, 0.35],
  wv: [0.2, 0.4, -0.15, 0.3,  0.5, -0.1, 0.2, 0.45,  -0.2, 0.35, 0.1, -0.05,  0.25, 0.15, -0.3, 0.2],
  wo: [0.4, -0.3, 0.2, 0.5,  0.1, 0.45, -0.15, 0.2,  -0.25, 0.3, 0.4, 0.05,  0.35, -0.1, 0.25, -0.2],
  g1: [1.0, 0.9, 1.05, 1.1],
  wg: [0.3, 0.2, -0.4, 0.1,  0.5, -0.3, 0.15, 0.25,  -0.1, 0.4, 0.3, -0.2,  0.2, 0.05, -0.25, 0.45],
  wu: [0.15, 0.35, -0.2, 0.1,  0.4, -0.15, 0.25, 0.3,  -0.25, 0.2, 0.35, -0.1,  0.3, 0.1, -0.05, 0.4],
  wd: [0.35, -0.15, 0.25, 0.2,  0.2, 0.4, -0.3, 0.1,  -0.2, 0.15, 0.5, -0.25,  0.1, -0.05, 0.3, 0.45],
  g2: [0.95, 1.1, 0.9, 1.0])
let layers = [L0, L1]

let x:  [Float] = [1.0, -0.5, 0.5, 2.0,  -1.0, 0.25, 1.5, -0.75,  0.5, 1.0, -0.5, 0.25]

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: max(1,a.count)*4, options: .storageModeShared)! }
func zBuf(_ n: Int) -> MTLBuffer { dev.makeBuffer(bytes: [Float](repeating: 0, count: max(1,n)), length: max(1,n)*4, options: .storageModeShared)! }
func readF(_ b: MTLBuffer, _ n: Int) -> [Float] { let p = b.contents().bindMemory(to: Float.self, capacity: n); var o = [Float](repeating: 0, count: n); for i in 0..<n { o[i] = p[i] }; return o }

// per-layer weight buffers (uploaded once, reused across positions)
struct LayerBufs { let bwq, bwk, bwv, bwo, bg1, bwg, bwu, bwd, bg2: MTLBuffer }
func upload(_ L: Layer) -> LayerBufs {
  LayerBufs(bwq: newBuf(L.wq), bwk: newBuf(L.wk), bwv: newBuf(L.wv), bwo: newBuf(L.wo),
            bg1: newBuf(L.g1), bwg: newBuf(L.wg), bwu: newBuf(L.wu), bwd: newBuf(L.wd), bg2: newBuf(L.g2))
}
let lb = layers.map(upload)

var sscale = scale, seps = eps
var ud = UInt32(d), udq = UInt32(dq), udv = UInt32(dv), uhid = UInt32(hid), uHD = UInt32(HD)

// one full-causal dispatch: run the whole S-token sequence `xin` through one layer's weights -> S*d output
func causalLayer(_ B: LayerBufs, _ xin: [Float]) -> [Float] {
  let bx = newBuf(xin), by = zBuf(S*d)
  let scN = S*d + S*dq + S*dq + S*dv + S*dv + S*d + S*d + S + S + hid + hid + hid
  let bsc = zBuf(scN)
  var uS = UInt32(S)
  let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
  enc.setComputePipelineState(cauPso)
  let bufs = [B.bwq,B.bwk,B.bwv,B.bwo,B.bg1,B.bwg,B.bwu,B.bwd,B.bg2,bx,by,bsc]
  for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
  enc.setBytes(&uS, length: 4, index: 12); enc.setBytes(&ud, length: 4, index: 13)
  enc.setBytes(&udq, length: 4, index: 14); enc.setBytes(&udv, length: 4, index: 15)
  enc.setBytes(&uhid, length: 4, index: 16); enc.setBytes(&uHD, length: 4, index: 17)
  enc.setBytes(&sscale, length: 4, index: 18); enc.setBytes(&seps, length: 4, index: 19)
  enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
  enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
  return readF(by, S*d)
}

// one decode-step dispatch: new token `xstep` at position p through one layer, into that layer's own cache -> d output
func decodeStep(_ B: LayerBufs, _ cacheK: MTLBuffer, _ cacheV: MTLBuffer, _ xstep: [Float], _ p: Int) -> [Float] {
  let bx = newBuf(xstep), by = zBuf(d)
  let scN = d + dq + dv + d + d + S + S + hid + hid + hid   // single-token scratch, scores sized to S
  let bsc = zBuf(scN)
  var up = UInt32(p)
  let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
  enc.setComputePipelineState(decPso)
  let bufs = [B.bwq,B.bwk,B.bwv,B.bwo,B.bg1,B.bwg,B.bwu,B.bwd,B.bg2,bx,cacheK,cacheV,by,bsc]
  for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
  enc.setBytes(&up, length: 4, index: 14); enc.setBytes(&ud, length: 4, index: 15)
  enc.setBytes(&udq, length: 4, index: 16); enc.setBytes(&udv, length: 4, index: 17)
  enc.setBytes(&uhid, length: 4, index: 18); enc.setBytes(&uHD, length: 4, index: 19)
  enc.setBytes(&sscale, length: 4, index: 20); enc.setBytes(&seps, length: 4, index: 21)
  enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
  enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
  return readF(by, d)
}

// ── A. the RECOMPUTE depth stack: full-causal kernel once per layer over the whole sequence, threaded forward ──
var cur = x
for B in lb { cur = causalLayer(B, cur) }
let yRecompute = cur

// ── B. the DECODE depth stack: per position p, run each layer's decode step in depth order, each layer its
//      OWN persistent cache; layer ℓ at step p reads the output of layer ℓ-1 at step p (the genuine
//      autoregressive multi-layer generation loop on silicon) ──
let cachesK = layers.map { _ in zBuf(S*dq) }   // one persistent K cache per layer
let cachesV = layers.map { _ in zBuf(S*dv) }   // one persistent V cache per layer
var yDecode = [Float](repeating: 0, count: S*d)
let t0 = Date()
for p in 0..<S {
  var tok = Array(x[(p*d)..<(p*d+d)])           // the single new token x_p (embedding into layer 0)
  for (ell, B) in lb.enumerated() {
    tok = decodeStep(B, cachesK[ell], cachesV[ell], tok, p)   // layer ℓ output at position p feeds layer ℓ+1
  }
  for i in 0..<d { yDecode[p*d+i] = tok[i] }     // top layer output for token p
}
let dt = Date().timeIntervalSince(t0)

// ── gates ──
print(String(format: "decode depth stack: %d positions × %d layers, %.3f ms total", S, layers.count, dt*1000))
func fmt(_ a: [Float]) -> String { "[" + (0..<a.count).map { String(format: "%.6f", a[$0]) }.joined(separator: ", ") + "]" }
print("  y_recompute (full causal per layer, \(layers.count) dispatches)        = \(fmt(yRecompute))")
print("  y_decode    (KV-cached, \(S)×\(layers.count) dispatches, per-layer cache) = \(fmt(yDecode))")

var bitExact = true
for i in 0..<(S*d) { if yRecompute[i].bitPattern != yDecode[i].bitPattern { bitExact = false } }
print(String(format: "EQUIVALENCE (decode depth stack vs recompute depth stack on the GPU): %@",
             bitExact ? "✓ BIT-FOR-BIT identical — the multi-layer KV cache reproduces the recompute exactly across depth on silicon" : "✗ FAIL — decode stack != recompute stack"))

var maxRecipe: Double = 0
for i in 0..<(S*d) { let g = Double(yRecompute[i]) * 1e6; let dd = abs(g - rec[i]); if dd > maxRecipe { maxRecipe = dd } }
print(String(format: "RECIPE (GPU fp32 2-layer stack vs fp64 lblk-stack-causal *1e6): max|Δ|=%.1f  %@",
             maxRecipe, maxRecipe < 300.0 ? "✓ tracks the proven four-way recipe within fp32 epsilon" : "✗ recipe mismatch"))

// depth actually did work: token-0 of the 2-layer stack matches the libm pin 1936158 and differs from 1-layer 1893731
let tok0 = Int((Double(yRecompute[0]) * 1e6).rounded())
let depthWorked = (tok0 == 1936158)
print(String(format: "DEPTH (2-layer token-0 *1e6 = %d): %@ (libm pin 1936158, ≠ 1-layer 1893731 → depth threaded per-layer weights)",
             tok0, depthWorked ? "✓ matches the independent libm reference; the stack is not one block applied once" : "✗ depth mismatch"))

if bitExact && maxRecipe < 300.0 && depthWorked {
    print("✓ the MULTI-LAYER causal llama DECODE STACK runs on the M4 Max GPU — the depth structure of real local llama inference on silicon, the per-layer KV caches bit-identical to the full recompute, tracking the proven four-way recipe")
    exit(0)
} else { print("✗ gate failed"); exit(1) }
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── running the multi-layer causal llama decode stack on the M4 Max GPU ──"
R=(); while IFS= read -r line; do R+=("$line"); done < "$work/recipe.out"
"$work/runner" "$work/decode.metal" "$work/causal.metal" "${R[@]}"
