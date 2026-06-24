#!/usr/bin/env bash
# metal_gqa_llama_block_decode_audit.sh — the KV-CACHED CAUSAL GQA DECODE STEP running on Metal (M4 Max GPU
# witness): the autoregressive generation inner loop for the REAL llama3.2 (grouped-query attention — n_q query
# heads sharing n_kv < n_q KV heads) on silicon, proven BIT-IDENTICAL to the full causal GQA recompute.
#
# kv-gqa-llama-block.fk's lgqa-generate-causal is the ALGORITHM (fp64, proven FOUR-WAY 255 by
# tests/kv-gqa-llama-block-band.fk): the real llama3.2 GQA decoder, generated one token at a time over a growing
# KV cache that stores the SMALLER n_kv*HD-wide k/v per position, proven there BIT-IDENTICAL to the full causal
# GQA recompute lgqa-block-causal (#3590, four-way 15). jit-tensor-emit.fk's jte-gqa-llama-block-decode-step-msl
# emits ONE GQA decode step as a Metal kernel — for the new token at position p it RMSNorms, projects q (to
# dq=n_q*HD) and k/v (to KVD=n_kv*HD), RoPEs q/k by p, APPENDS the RoPE'd k_p/v_p into cache slot p, and for each
# query head attends its HD-wide q-slice over the grown prefix cache[0..p] of KV head (h / (n_q/n_kv)). Only the
# NEW token is projected each step; earlier positions' k/v are reused from the cache (O(n) per token, not the
# O(n^2) whole-block recompute). This is the GROUPED-QUERY generalization of jte-llama-block-decode-step-msl
# (#3412, single-head) and the GPU realization of the GQA cached decode.
#
# This script is only the carrier. It emits BOTH kernels — the GQA decode step AND the full causal GQA block
# (jte-gqa-llama-block-fwd-causal-msl, the kernel that runs the whole sequence at once, already proven on the M4
# GPU, brick 3zi / #3590) — compiles them mathMode-safe (IEEE, no fma contraction), and on the M4 Max GPU runs:
#   A. the full causal GQA kernel ONCE over the whole S-token sequence            -> y_full
#   B. the decode kernel S times, threading ONE persistent (n_kv*HD-wide) cache across the S dispatches (cache
#      slot p written by step p, read 0..p) -> y_decode  (the genuine autoregressive GQA generation loop on silicon)
# and gates them to the proven recipe:
#   1. y_decode == y_full BIT-FOR-BIT  — the GQA KV cache equivalence (lgqa-generate-causal == lgqa-block-causal)
#      realized ON THE GPU: incremental cached decode reproduces the whole-sequence recompute exactly, because a
#      cached k_i/v_i depends only on position i and the fold order is identical
#   2. y_decode (fp32) tracks the Form recipe lgqa-block-causal (fp64, four-way proven) within fp32 epsilon
# The autoregressive invariant this exercises: appending a future token never changes an earlier token's output
# (each narrower cache slot is frozen at its position), so the S=3 loop proves the cache threads correctly past the
# boundary THROUGH the grouping — the GPU witness of kv-gqa-llama-block-band.fk's S=2 + S=3 inductive proof. The
# grouping arithmetic (kvh = h / group) is what lets 2 query heads share 1 KV head, exactly the (h/group) mapping
# llama3.2 runs at 24 -> 8. The transcendentals are the recipe's OWN (Newton sqrt, fexp Taylor, RoPE's fsin/fcos/
# fln Taylor), never Metal's. RoPE is base-10000 — the cfg10 special case (band claim 1: lgqa-block-causal(cfg10)
# == lblk-block-causal bit-for-bit).
#
# Carriers: form-kernel-go (the mouth), swiftc + Metal.framework (the driver-organ idiom, an allowed host carrier
# per host-kernel.form host-resource-access); the emitter intelligence lives in the body.
#
# Run:  scripts/metal_gqa_llama_block_decode_audit.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkgqadec.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits BOTH kernels (GQA decode step + full causal GQA block) ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==DEC==")\n(print (jte-gqa-llama-block-decode-step-msl "form_gqa_llama_decode_step_f32"))\n(print "==END==")\n(print "==CAU==")\n(print (jte-gqa-llama-block-fwd-causal-msl "form_gqa_llama_block_causal_fwd_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==DEC==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/decode.metal"
sed -n '/^==CAU==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/causal.metal"
grep -q 'kernel void form_gqa_llama_decode_step_f32' "$work/decode.metal" || { echo "FAIL no decode kernel"; exit 1; }
grep -q 'kernel void form_gqa_llama_block_causal_fwd_f32' "$work/causal.metal" || { echo "FAIL no causal kernel"; exit 1; }
echo "emitted GQA decode-step MSL: $(wc -c < "$work/decode.metal" | tr -d ' ') bytes  |  full causal GQA MSL: $(wc -c < "$work/causal.metal" | tr -d ' ') bytes (every byte authored by the Form recipe)"

# ── 2. the Form recipe lgqa-block-causal in fp64 over the SAME GQA fixture, extended to S=3 (the inductive step) ──
cat "$FORMDIR/form-stdlib/trig.fk" \
    "$FORMDIR/form-stdlib/transformer-numerics.fk" "$FORMDIR/form-stdlib/llama-numerics.fk" \
    "$FORMDIR/form-stdlib/rope.fk" "$FORMDIR/form-stdlib/transformer-block.fk" \
    "$FORMDIR/form-stdlib/transformer-mh.fk" "$FORMDIR/form-stdlib/gqa-attn.fk" \
    "$FORMDIR/form-stdlib/llama-block.fk" "$FORMDIR/form-stdlib/llama-gqa-block.fk" > "$work/recipe.fk"
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
  (let cfg10 (rope-cfg 10000.0 32.0 1.0 4.0 8192.0))
  (let sc2 (div 1.0 (tn-sqrt 2.0)))
  (let y (lgqa-block-causal x g1 eps wq wk wv wo sc2 2 1 2 cfg10 g2 wg wu wd))
  (let r0 (nth y 0)) (let r1 (nth y 1)) (let r2 (nth y 2))
  (print (round (mul (nth r0 0) 1000000.0)))
  (print (round (mul (nth r0 1) 1000000.0)))
  (print (round (mul (nth r0 2) 1000000.0)))
  (print (round (mul (nth r0 3) 1000000.0)))
  (print (round (mul (nth r1 0) 1000000.0)))
  (print (round (mul (nth r1 1) 1000000.0)))
  (print (round (mul (nth r1 2) 1000000.0)))
  (print (round (mul (nth r1 3) 1000000.0)))
  (print (round (mul (nth r2 0) 1000000.0)))
  (print (round (mul (nth r2 1) 1000000.0)))
  (print (round (mul (nth r2 2) 1000000.0)))
  (print (round (mul (nth r2 3) 1000000.0))))
RECIPE
(cd "$FORMDIR" && "$GO_BIN" "$work/recipe.fk" 2>/dev/null) | grep -E '^-?[0-9]+$' | head -12 > "$work/recipe.out"
echo "Form recipe lgqa-block-causal (fp64, four-way proven) y*1e6: $(tr '\n' ' ' < "$work/recipe.out")"

# ── 3. Swift carrier: compile both kernels, run full-causal GQA once + the GQA decode loop S times, gate ──
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
let decPso = try dev.makeComputePipelineState(function: decLib.makeFunction(name: "form_gqa_llama_decode_step_f32")!)
let cauPso = try dev.makeComputePipelineState(function: cauLib.makeFunction(name: "form_gqa_llama_block_causal_fwd_f32")!)
let q = dev.makeCommandQueue()!

// dims (kv-gqa-llama-block-band.fk / llama-gqa-block-causal-band claim-8 fixture: 2 query heads share 1 KV head,
// the real GQA grouping; extended to S=3 — the inductive step)
let S = 3, d = 4, n_q = 2, n_kv = 1, HD = 2, hid = 4
let dq = n_q*HD, KVD = n_kv*HD
let scale: Float = 1.0 / Float(2.0).squareRoot()   // 1/sqrt(2)
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
var ud = UInt32(d), udq = UInt32(dq), uKVD = UInt32(KVD), uhid = UInt32(hid), uHD = UInt32(HD), unkv = UInt32(n_kv)

func readF(_ b: MTLBuffer, _ n: Int) -> [Float] { let p = b.contents().bindMemory(to: Float.self, capacity: n); var o = [Float](repeating: 0, count: n); for i in 0..<n { o[i] = p[i] }; return o }

// ── A. the full causal GQA kernel ONCE over the whole sequence (the recompute baseline, brick 3zi) ──
let bxFull = newBuf(x), byFull = zBuf(S*d)
// scratch (jte-gqa-blk-off): oN1,oQ,oK,oV,oA,oH,oN2,oSR,oE,oG,oU,oACT
let scNfull = S*d + S*dq + S*KVD + S*KVD + S*dq + S*d + S*d + S + S + hid + hid + hid
let bscFull = zBuf(scNfull)
var uS = UInt32(S)
do {
  let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
  enc.setComputePipelineState(cauPso)
  let bufs = [bwq,bwk,bwv,bwo,bg1,bwg,bwu,bwd,bg2,bxFull,byFull,bscFull]
  for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
  enc.setBytes(&uS, length: 4, index: 12); enc.setBytes(&ud, length: 4, index: 13)
  enc.setBytes(&udq, length: 4, index: 14); enc.setBytes(&uKVD, length: 4, index: 15)
  enc.setBytes(&uhid, length: 4, index: 16); enc.setBytes(&uHD, length: 4, index: 17)
  enc.setBytes(&unkv, length: 4, index: 18); enc.setBytes(&sscale, length: 4, index: 19)
  enc.setBytes(&seps, length: 4, index: 20)
  enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
  enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
}
let yFull = readF(byFull, S*d)

// ── B. the GQA decode loop: S dispatches over ONE persistent (KVD-wide) cache (the autoregressive generation loop) ──
let cacheK = zBuf(S*KVD), cacheV = zBuf(S*KVD)      // persistent across steps; slot p written by step p
// single-token scratch (jte-gqa-dec-off): oN1,oQ,oA,oH,oN2,oSR,oE,oG,oU,oACT — scores sized to S
let scNdec = d + dq + dq + d + d + S + S + hid + hid + hid
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
  enc.setBytes(&udq, length: 4, index: 16); enc.setBytes(&uKVD, length: 4, index: 17)
  enc.setBytes(&uhid, length: 4, index: 18); enc.setBytes(&uHD, length: 4, index: 19)
  enc.setBytes(&unkv, length: 4, index: 20); enc.setBytes(&sscale, length: 4, index: 21)
  enc.setBytes(&seps, length: 4, index: 22)
  enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
  enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
  let yp = readF(byStep, d)
  for i in 0..<d { yDecode[p*d+i] = yp[i] }
}
let dt = Date().timeIntervalSince(t0)

// ── gates ──
print(String(format: "GQA decode loop: %d dispatches over one persistent KV cache (n_q=%d query heads, n_kv=%d KV head, group=%d, HD=%d), %.3f ms total", S, n_q, n_kv, n_q/n_kv, HD, dt*1000))
func fmt(_ a: [Float]) -> String { "[" + (0..<a.count).map { String(format: "%.6f", a[$0]) }.joined(separator: ", ") + "]" }
print("  y_full   (full causal GQA recompute, one dispatch) = \(fmt(yFull))")
print("  y_decode (KV-cached GQA loop, \(S) dispatches)        = \(fmt(yDecode))")

var bitExact = true
for i in 0..<(S*d) { if yFull[i].bitPattern != yDecode[i].bitPattern { bitExact = false } }
print(String(format: "EQUIVALENCE (GQA decode loop vs full causal GQA recompute on the GPU): %@",
             bitExact ? "✓ BIT-FOR-BIT identical — the GQA KV cache reproduces the recompute exactly on silicon" : "✗ FAIL — decode != recompute"))

var maxRecipe: Double = 0
for i in 0..<(S*d) { let g = Double(yDecode[i]) * 1e6; let dd = abs(g - rec[i]); if dd > maxRecipe { maxRecipe = dd } }
print(String(format: "RECIPE (GPU fp32 GQA decode vs fp64 lgqa-block-causal *1e6): max|Δ|=%.1f  %@",
             maxRecipe, maxRecipe < 300.0 ? "✓ tracks the proven four-way recipe within fp32 epsilon" : "✗ recipe mismatch"))

if bitExact && maxRecipe < 300.0 {
    print("✓ the KV-CACHED CAUSAL GQA DECODE STEP runs on the M4 Max GPU — real llama3.2 autoregressive generation on silicon, the cache bit-identical to the full causal GQA recompute, tracking the proven recipe")
    exit(0)
} else { print("✗ gate failed"); exit(1) }
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── running the KV-cached GQA decode loop on the M4 Max GPU ──"
RA=()
for k in $(seq 1 12); do RA+=("$(sed -n "${k}p" "$work/recipe.out")"); done
"$work/runner" "$work/decode.metal" "$work/causal.metal" "${RA[@]}"
