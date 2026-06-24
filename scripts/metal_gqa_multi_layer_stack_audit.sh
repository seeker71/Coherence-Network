#!/usr/bin/env bash
# metal_gqa_multi_layer_stack_audit.sh — the MULTI-LAYER causal GQA llama DECODE STACK running on Metal (M4 Max
# GPU witness): the DEPTH structure of REAL llama3.2 inference on silicon — GROUPED-QUERY attention (n_q query
# heads sharing n_kv < n_q KV heads) stacked across N decoder blocks, each layer its OWN weights and OWN
# (narrower n_kv*HD-wide) KV cache — proven BIT-IDENTICAL to the full causal GQA recompute, and tracking the
# four-way-proven fp64 recipe within fp32 epsilon.
#
# A real llama3.2:3b is DEPTH × GROUPING: 28 decoder blocks, each with 24 query heads sharing 8 KV heads, each
# layer with its OWN weights and its OWN narrower KV cache — x¹=block₀(x⁰); x²=block₁(x¹); …. gqa-multi-layer-
# stack.fk's lgqa-stack-causal / lgqa-stack-generate are the ALGORITHM (fp64, proven FOUR-WAY 255 by
# tests/gqa-multi-layer-stack-band.fk, #3zl/#3616): they fold the causal GQA block across depth two ways — full
# causal recompute, and KV-cached incremental decode each layer its own narrower cache — and are proven
# BIT-IDENTICAL there (lgqa-generate-causal == lgqa-block-causal per layer, #3601; lgqa-block-causal four-way
# #3590). The single GQA block already runs forward on the M4 GPU (#3587/#3590) and the GQA KV-cached decode
# STEP runs on the M4 GPU (#3612, scripts/metal_gqa_llama_block_decode_audit.sh). This script proves they STACK
# on silicon: the named next stone from #3616's receipt — "emit the multi-layer GQA decode stack to Metal:
# stack the #3612 GQA decode-step kernel, each layer its own device cache buffer."
#
# This script is only the carrier. It REUSES the two already-four-way-proven Form-emitted GQA kernels verbatim —
# the decode step (jte-gqa-llama-block-decode-step-msl, gqa-llama-block-decode-emit fks 7) and the full causal
# GQA block (jte-gqa-llama-block-fwd-causal-msl, llama-gqa-block-fwd-causal-emit fks 7) — no new MSL. The depth
# stacking is the FOLD ORDER the Form recipe lgqa-stack-* already dictates, carried by host dispatches: one
# dispatch of the per-block kernel per (layer) for recompute, per (position, layer) for cached decode, threading
# layer ℓ's output into layer ℓ+1 and giving each layer its own narrower (n_kv*HD-wide) device cache buffer. On
# the M4 Max GPU over TWO DISTINCT layers (L0 = the GQA-band weights, L1 = a second bundle, so the stack
# genuinely threads per-layer weights forward), with the REAL GQA grouping (n_q=2 query heads sharing n_kv=1 KV
# head, HD=2 — the (h/group) sharing llama3.2 runs at 24→8), it runs:
#   A. the RECOMPUTE stack — full causal GQA kernel once per layer over the whole S-token sequence -> y_recompute
#   B. the DECODE   stack — for each position p, run each layer's GQA decode kernel in depth order, each layer
#      appending to its OWN persistent narrower cache slot p and reading its prefix 0..p -> y_decode  (the
#      genuine autoregressive multi-layer GQA generation loop on silicon)
# and gates them to the proven recipe + the fp64 ground truth:
#   1. y_decode == y_recompute BIT-FOR-BIT  — the multi-layer GQA KV-cache equivalence (lgqa-stack-generate ==
#      lgqa-stack-causal) realized ON THE GPU across depth: every layer's cached decode reproduces its full
#      recompute exactly, so the depth fold of the cached path equals the depth fold of the recompute path
#   2. y_recompute (fp32) tracks the Form recipe lgqa-stack-causal (fp64, four-way proven) within fp32 epsilon
#   3. the 2-layer token-0 output matches the fp64 pin 2838153 AND DIFFERS from the 1-layer pin 2147164 —
#      depth actually did work (the stack is not one GQA block applied once)
# The autoregressive invariant this exercises THROUGH depth AND grouping: appending a future token never changes
# an earlier token's STACKED GQA output (every layer is causal, every narrower cache entry frozen at its
# (layer, position)), so the S=3 loop proves the multi-layer GQA cache threads correctly past the boundary. The
# grouping arithmetic (kvh = h / group) lets 2 query heads share 1 KV head per layer, exactly the (h/group)
# mapping llama3.2 runs at 24→8. RoPE is base-10000 (the cfg10 case the per-layer GQA kernel bakes, matching
# scripts/metal_gqa_llama_block_decode_audit.sh). Transcendentals stay the recipe's OWN (Newton sqrt, fexp
# Taylor, RoPE's fsin/fcos/fln Taylor), never Metal's.
#
# Carriers: form-kernel-go (the mouth), swiftc + Metal.framework (the driver-organ idiom, an allowed host
# carrier per host-kernel.form host-resource-access); the emitter intelligence + the fold order live in the body.
#
# Run:  scripts/metal_gqa_multi_layer_stack_audit.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkgqamls.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits BOTH per-block GQA kernels (decode step + full causal block), reused verbatim across layers ──
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==DEC==")\n(print (jte-gqa-llama-block-decode-step-msl "form_gqa_llama_decode_step_f32"))\n(print "==END==")\n(print "==CAU==")\n(print (jte-gqa-llama-block-fwd-causal-msl "form_gqa_llama_block_causal_fwd_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==DEC==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/decode.metal"
sed -n '/^==CAU==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/causal.metal"
grep -q 'kernel void form_gqa_llama_decode_step_f32' "$work/decode.metal" || { echo "FAIL no decode kernel"; exit 1; }
grep -q 'kernel void form_gqa_llama_block_causal_fwd_f32' "$work/causal.metal" || { echo "FAIL no causal kernel"; exit 1; }
echo "emitted GQA decode-step MSL: $(wc -c < "$work/decode.metal" | tr -d ' ') bytes  |  full causal GQA MSL: $(wc -c < "$work/causal.metal" | tr -d ' ') bytes (both reused verbatim per layer)"

# ── 2. the Form recipe lgqa-stack-causal in fp64 over the 2-layer / 3-token GQA-grouped fixture
#       (n_q=2 n_kv=1 HD=2 base-10000 RoPE — the real GQA grouping the per-layer GPU kernel runs; #3zl four-way) ──
cat "$FORMDIR/form-stdlib/transformer-numerics.fk" "$FORMDIR/form-stdlib/trig.fk" \
    "$FORMDIR/form-stdlib/llama-numerics.fk" "$FORMDIR/form-stdlib/rope.fk" "$FORMDIR/form-stdlib/transformer-block.fk" \
    "$FORMDIR/form-stdlib/transformer-mh.fk" "$FORMDIR/form-stdlib/gqa-attn.fk" \
    "$FORMDIR/form-stdlib/llama-block.fk" "$FORMDIR/form-stdlib/llama-gqa-block.fk" \
    "$FORMDIR/form-stdlib/kv-cache.fk" "$FORMDIR/form-stdlib/kv-llama-block.fk" "$FORMDIR/form-stdlib/kv-gqa-llama-block.fk" \
    "$FORMDIR/form-stdlib/multi-layer-stack.fk" "$FORMDIR/form-stdlib/gqa-multi-layer-stack.fk" > "$work/recipe.fk"
cat >> "$work/recipe.fk" <<'RECIPE'
(do
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
  (let cfg10 (rope-cfg 10000.0 32.0 1.0 4.0 8192.0))
  (let sc2 (div 1.0 (tn-sqrt 2.0)))
  (let L0 (list g1 wq wk wv wo g2 wg wu wd))
  (let L1 (list g1b wqb wkb wvb wob g2b wgb wub wdb))
  (let x3 (list (list 1.0 -0.5 0.5 2.0) (list -1.0 0.25 1.5 -0.75) (list 0.5 1.0 -0.5 0.25)))
  (let y (lgqa-stack-causal x3 (list L0 L1) eps sc2 2 1 2 cfg10))
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
echo "Form recipe lgqa-stack-causal (fp64, four-way proven, 2 layers, GQA grouped) y*1e6: $(tr '\n' ' ' < "$work/recipe.out")"

# ── 3. Swift carrier: compile both GQA kernels, stack 2 distinct layers two ways on the GPU, gate ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let decPath = args[1], cauPath = args[2]
let rec: [Double] = (3...14).map { Double(args[$0])! }   // fp64 recipe ground truth (y*1e6, 12 values, 3 tokens, 2-layer GQA stack)

let dev = MTLCreateSystemDefaultDevice()!
func makeLib(_ path: String) throws -> MTLLibrary {
  let src = try String(contentsOfFile: path, encoding: .utf8)
  let opts = MTLCompileOptions(); opts.mathMode = .safe   // IEEE: no fast-math reassociation/contraction
  return try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
}
let decLib = try makeLib(decPath), cauLib = try makeLib(cauPath)
let decPso = try dev.makeComputePipelineState(function: decLib.makeFunction(name: "form_gqa_llama_decode_step_f32")!)
let cauPso = try dev.makeComputePipelineState(function: cauLib.makeFunction(name: "form_gqa_llama_block_causal_fwd_f32")!)
let q = dev.makeCommandQueue()!

// dims (gqa-multi-layer-stack-band.fk REAL GQA grouping: 2 query heads share 1 KV head, HD=2 — the (h/group)
// sharing llama3.2 runs at 24→8; S=3 = the inductive step through depth; base-10000 RoPE the kernel bakes)
let S = 3, d = 4, n_q = 2, n_kv = 1, HD = 2, hid = 4
let dq = n_q*HD, KVD = n_kv*HD
let scale: Float = 1.0 / Float(2.0).squareRoot()   // 1/sqrt(2)
let eps: Float = 0.00001

// --- per-layer weight bundles (L0 = GQA-band weights; L1 = distinct) ---
struct Layer { let wq, wk, wv, wo, g1, wg, wu, wd, g2: [Float] }
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

// per-layer weight buffers (uploaded once, reused across positions) — GQA kernel buffer order [wq,wk,wv,wo,g1,wg,wu,wd,g2]
struct LayerBufs { let bwq, bwk, bwv, bwo, bg1, bwg, bwu, bwd, bg2: MTLBuffer }
func upload(_ L: Layer) -> LayerBufs {
  LayerBufs(bwq: newBuf(L.wq), bwk: newBuf(L.wk), bwv: newBuf(L.wv), bwo: newBuf(L.wo),
            bg1: newBuf(L.g1), bwg: newBuf(L.wg), bwu: newBuf(L.wu), bwd: newBuf(L.wd), bg2: newBuf(L.g2))
}
let lb = layers.map(upload)

var sscale = scale, seps = eps
var ud = UInt32(d), udq = UInt32(dq), uKVD = UInt32(KVD), uhid = UInt32(hid), uHD = UInt32(HD), unkv = UInt32(n_kv)

// one full-causal GQA dispatch: run the whole S-token sequence `xin` through one layer's weights -> S*d output
func causalLayer(_ B: LayerBufs, _ xin: [Float]) -> [Float] {
  let bx = newBuf(xin), by = zBuf(S*d)
  // scratch (jte-gqa-blk-off): oN1,oQ,oK,oV,oA,oH,oN2,oSR,oE,oG,oU,oACT
  let scN = S*d + S*dq + S*KVD + S*KVD + S*dq + S*d + S*d + S + S + hid + hid + hid
  let bsc = zBuf(scN)
  var uS = UInt32(S)
  let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
  enc.setComputePipelineState(cauPso)
  let bufs = [B.bwq,B.bwk,B.bwv,B.bwo,B.bg1,B.bwg,B.bwu,B.bwd,B.bg2,bx,by,bsc]
  for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
  enc.setBytes(&uS, length: 4, index: 12); enc.setBytes(&ud, length: 4, index: 13)
  enc.setBytes(&udq, length: 4, index: 14); enc.setBytes(&uKVD, length: 4, index: 15)
  enc.setBytes(&uhid, length: 4, index: 16); enc.setBytes(&uHD, length: 4, index: 17)
  enc.setBytes(&unkv, length: 4, index: 18); enc.setBytes(&sscale, length: 4, index: 19)
  enc.setBytes(&seps, length: 4, index: 20)
  enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
  enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
  return readF(by, S*d)
}

// one GQA decode-step dispatch: new token `xstep` at position p through one layer, into that layer's own
// narrower (KVD-wide) cache -> d output
func decodeStep(_ B: LayerBufs, _ cacheK: MTLBuffer, _ cacheV: MTLBuffer, _ xstep: [Float], _ p: Int) -> [Float] {
  let bx = newBuf(xstep), by = zBuf(d)
  // single-token scratch (jte-gqa-dec-off): oN1,oQ,oA,oH,oN2,oSR,oE,oG,oU,oACT — scores sized to S
  let scN = d + dq + dq + d + d + S + S + hid + hid + hid
  let bsc = zBuf(scN)
  var up = UInt32(p)
  let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
  enc.setComputePipelineState(decPso)
  let bufs = [B.bwq,B.bwk,B.bwv,B.bwo,B.bg1,B.bwg,B.bwu,B.bwd,B.bg2,bx,cacheK,cacheV,by,bsc]
  for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
  enc.setBytes(&up, length: 4, index: 14); enc.setBytes(&ud, length: 4, index: 15)
  enc.setBytes(&udq, length: 4, index: 16); enc.setBytes(&uKVD, length: 4, index: 17)
  enc.setBytes(&uhid, length: 4, index: 18); enc.setBytes(&uHD, length: 4, index: 19)
  enc.setBytes(&unkv, length: 4, index: 20); enc.setBytes(&sscale, length: 4, index: 21)
  enc.setBytes(&seps, length: 4, index: 22)
  enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
  enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
  return readF(by, d)
}

// ── A. the RECOMPUTE depth stack: full-causal GQA kernel once per layer over the whole sequence, threaded forward ──
var cur = x
for B in lb { cur = causalLayer(B, cur) }
let yRecompute = cur

// ── B. the DECODE depth stack: per position p, run each layer's GQA decode step in depth order, each layer its
//      OWN persistent narrower (KVD-wide) cache; layer ℓ at step p reads the output of layer ℓ-1 at step p (the
//      genuine autoregressive multi-layer GQA generation loop on silicon) ──
let cachesK = layers.map { _ in zBuf(S*KVD) }   // one persistent narrower K cache per layer
let cachesV = layers.map { _ in zBuf(S*KVD) }   // one persistent narrower V cache per layer
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
print(String(format: "GQA decode depth stack: %d positions × %d layers (n_q=%d query heads, n_kv=%d KV head, group=%d, HD=%d), %.3f ms total", S, layers.count, n_q, n_kv, n_q/n_kv, HD, dt*1000))
func fmt(_ a: [Float]) -> String { "[" + (0..<a.count).map { String(format: "%.6f", a[$0]) }.joined(separator: ", ") + "]" }
print("  y_recompute (full causal GQA per layer, \(layers.count) dispatches)         = \(fmt(yRecompute))")
print("  y_decode    (KV-cached GQA, \(S)×\(layers.count) dispatches, per-layer cache) = \(fmt(yDecode))")

var bitExact = true
for i in 0..<(S*d) { if yRecompute[i].bitPattern != yDecode[i].bitPattern { bitExact = false } }
print(String(format: "EQUIVALENCE (GQA decode depth stack vs recompute depth stack on the GPU): %@",
             bitExact ? "✓ BIT-FOR-BIT identical — the multi-layer GQA KV cache reproduces the recompute exactly across depth on silicon" : "✗ FAIL — decode stack != recompute stack"))

var maxRecipe: Double = 0
for i in 0..<(S*d) { let g = Double(yRecompute[i]) * 1e6; let dd = abs(g - rec[i]); if dd > maxRecipe { maxRecipe = dd } }
print(String(format: "RECIPE (GPU fp32 2-layer GQA stack vs fp64 lgqa-stack-causal *1e6): max|Δ|=%.1f  %@",
             maxRecipe, maxRecipe < 300.0 ? "✓ tracks the proven four-way recipe within fp32 epsilon" : "✗ recipe mismatch"))

// depth actually did work: token-0 of the 2-layer GQA stack matches the fp64 pin 2838153 and differs from 1-layer 2147164
let tok0 = Int((Double(yRecompute[0]) * 1e6).rounded())
let depthWorked = (tok0 == 2838153)
print(String(format: "DEPTH (2-layer GQA token-0 *1e6 = %d): %@ (fp64 pin 2838153, ≠ 1-layer 2147164 → depth threaded per-layer weights through the grouping)",
             tok0, depthWorked ? "✓ matches the four-way recipe; the GQA stack is not one block applied once" : "✗ depth mismatch"))

if bitExact && maxRecipe < 300.0 && depthWorked {
    print("✓ the MULTI-LAYER causal GQA llama DECODE STACK runs on the M4 Max GPU — the depth × grouping structure of real llama3.2 inference on silicon, the per-layer narrower KV caches bit-identical to the full recompute, tracking the proven four-way recipe")
    exit(0)
} else { print("✗ gate failed"); exit(1) }
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── running the multi-layer causal GQA llama decode stack on the M4 Max GPU ──"
RA=()
for k in $(seq 1 12); do RA+=("$(sed -n "${k}p" "$work/recipe.out")"); done
"$work/runner" "$work/decode.metal" "$work/causal.metal" "${RA[@]}"
