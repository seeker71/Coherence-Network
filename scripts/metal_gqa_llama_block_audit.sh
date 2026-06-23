#!/usr/bin/env bash
# metal_gqa_llama_block_audit.sh — the WHOLE GQA CAUSAL LLAMA BLOCK forward running on Metal (M4 Max GPU witness).
#
# llama-gqa-block.fk's lgqa-block-causal is the ALGORITHM (fp64, proven FOUR-WAY 15 by
# tests/llama-gqa-block-causal-band.fk): the real llama3.2 decoder block —
#   n1 = RMSNorm1(x) ; h = x + Wo*GQA-causal(RoPE(Wq*n1), RoPE(Wk*n1), Wv*n1, n_q, n_kv, HD, scale) ;
#   n2 = RMSNorm2(h) ; y = h + Wdown*SwiGLU(Wgate*n2, Wup*n2)
# with GROUPED-QUERY attention: n_q query heads share n_kv < n_q KV heads, query head h reads KV head
# (h / (n_q/n_kv)). This is the attention real llama3.2:3b runs (24 query heads, 8 KV heads, head_dim 128).
# jit-tensor-emit.fk's jte-gqa-llama-block-fwd-causal-msl emits that whole block as ONE Metal kernel — the GQA
# generalization of jte-llama-block-fwd-causal-msl (#3376, single-head). Every byte authored by the Form recipe;
# RMSNorm1/RMSNorm2 + the SwiGLU FFN are jte-llama-blk-rms1/rms2/ffn verbatim, only the projection widths (k/v to
# the smaller n_kv*HD) and the attention loop (per query head, causal mask) change. This script is only the
# carrier: it emits the kernel, compiles it (mathMode safe — IEEE, no fast-math contraction), runs it on the M4
# Max GPU over the SAME fixture llama-gqa-block-causal-band.fk claim 8 proves four-way (S=2, d=4, n_q=2 query
# heads, n_kv=1 KV head, HD=2 — the real grouping where 2 query heads share 1 KV head, scale 1/sqrt(2)), and
# gates three executions to one answer:
#   1. the Form recipe lgqa-block-causal in fp64 via the Go kernel (the proven ground truth, y*1e6 rounded)
#   2. this GPU block forward in fp32
#   3. an fp32 CPU mirror that walks the SAME block folds (the bit-exact parity gate)
# So the chain is honest end to end: fp64 recipe (proven four-way) -> fp32 GPU carrier (proven == fp32 CPU
# mirror, bit-for-bit) -> tracks the fp64 recipe within fp32 epsilon. The softmax exp / SiLU sigmoid is the
# recipe's OWN fexp Taylor (never Metal's); RoPE's sin/cos/pow are trig.fk's own Taylor; each RMSNorm is the
# biased mean-square + 50-step Newton sqrt; every dot is the downward right-fold split through a named temporary
# so no compiler contracts it into an fma. RoPE is base-10000 — the cfg10 special case of lgqa's rope-scaled
# (band claim 1: lgqa-block-causal(cfg10) == lblk-block-causal bit-for-bit); the llama3 theta-500000 rope-scaling
# MSL is the named next stone. The grouping arithmetic (kvh = h / group) is what lets 2 query heads share 1 KV
# head — both query heads 0,1 -> kv0, exactly the (h / group) mapping llama3.2 runs at 24 -> 8.
#
# Carriers: form-kernel-go (the mouth), swiftc + Metal.framework (the driver-organ idiom — allowed host
# carriers per host-kernel.form host-resource-access); the emitter intelligence lives in the body. The
# single-thread walk matches the recipe serially and bit-exactly; parallelizing across query heads/tokens is
# the named follow-up.
#
# Run:  scripts/metal_gqa_llama_block_audit.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkgqablk.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the GQA block MSL; the kernel is only the mouth ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-gqa-llama-block-fwd-causal-msl "form_gqa_llama_block_causal_fwd_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/blk.metal"
grep -q 'kernel void form_gqa_llama_block_causal_fwd_f32' "$work/blk.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted GQA causal llama block MSL: $(wc -c < "$work/blk.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. the Form recipe in fp64 (the proven four-way ground truth) — llama-gqa-block-causal-band.fk claim-8 fixture ────
cat "$FORMDIR/form-stdlib/trig.fk" \
    "$FORMDIR/form-stdlib/transformer-numerics.fk" "$FORMDIR/form-stdlib/llama-numerics.fk" \
    "$FORMDIR/form-stdlib/rope.fk" "$FORMDIR/form-stdlib/transformer-block.fk" \
    "$FORMDIR/form-stdlib/transformer-mh.fk" "$FORMDIR/form-stdlib/gqa-attn.fk" \
    "$FORMDIR/form-stdlib/llama-block.fk" "$FORMDIR/form-stdlib/llama-gqa-block.fk" > "$work/recipe.fk"
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
  (let cfg10 (rope-cfg 10000.0 32.0 1.0 4.0 8192.0))
  (let sc2 (div 1.0 (tn-sqrt 2.0)))
  (let y (lgqa-block-causal x g1 eps wq wk wv wo sc2 2 1 2 cfg10 g2 wg wu wd))
  (let r0 (nth y 0)) (let r1 (nth y 1))
  (print (round (mul (nth r0 0) 1000000.0)))
  (print (round (mul (nth r0 1) 1000000.0)))
  (print (round (mul (nth r0 2) 1000000.0)))
  (print (round (mul (nth r0 3) 1000000.0)))
  (print (round (mul (nth r1 0) 1000000.0)))
  (print (round (mul (nth r1 1) 1000000.0)))
  (print (round (mul (nth r1 2) 1000000.0)))
  (print (round (mul (nth r1 3) 1000000.0))))
RECIPE
(cd "$FORMDIR" && "$GO_BIN" "$work/recipe.fk" 2>/dev/null) | grep -E '^-?[0-9]+$' | head -8 > "$work/recipe.out"
echo "Form recipe lgqa-block-causal (fp64, four-way proven) y*1e6: $(tr '\n' ' ' < "$work/recipe.out")"

# ── 3. Swift carrier: compile (mathMode safe), run the GQA block on the GPU, parity-gate vs fp32 CPU mirror ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let mslPath = args[1]
let rec: [Double] = (2...9).map { Double(args[$0])! }   // fp64 recipe ground truth (y*1e6, 8 values: S=2 x d=4)

let dev = MTLCreateSystemDefaultDevice()!
let src = try String(contentsOfFile: mslPath, encoding: .utf8)
let opts = MTLCompileOptions()
opts.mathMode = .safe   // IEEE-conformant: no fast-math reassociation/contraction
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
let fn = lib.makeFunction(name: "form_gqa_llama_block_causal_fwd_f32")!
let pso = try dev.makeComputePipelineState(function: fn)
let q = dev.makeCommandQueue()!

// dims (llama-gqa-block-causal-band.fk claim 8: 2 query heads share 1 KV head — the real GQA grouping)
let S = 2, d = 4, n_q = 2, n_kv = 1, HD = 2, hid = 4
let dq = n_q*HD, KVD = n_kv*HD
let scale: Float = 1.0 / Float(2.0).squareRoot()  // 1/sqrt(2)
let eps: Float = 0.00001

// the band's claim-8 fixture, row-major flattened. wk/wv are the full 4x4 matrices; the kernel reads
// only the first KVD=2 rows (= KV head 0), exactly the recipe's tb-seq-headslice(kvh=0).
let x:  [Float] = [1.0, -0.5, 0.5, 2.0,  -1.0, 0.25, 1.5, -0.75]
let g1: [Float] = [0.9, 1.1, 1.0, 0.95]
let g2: [Float] = [1.05, 0.95, 1.0, 0.9]
let wq: [Float] = [0.5, -0.25, 0.1, 0.3,  0.2, 0.4, -0.3, 0.1,  -0.1, 0.2, 0.5, -0.2,  0.3, 0.0, -0.15, 0.25]
let wk: [Float] = [0.2, 0.4, -0.3, 0.1,  0.3, -0.2, 0.25, 0.5,  0.1, 0.15, -0.05, 0.2,  -0.25, 0.3, 0.4, -0.1]
let wv: [Float] = [0.3, -0.2, 0.25, 0.5,  0.6, 0.1, -0.2, 0.4,  0.05, -0.1, 0.3, 0.2,  0.15, 0.35, -0.25, 0.1]
let wo: [Float] = [0.6, 0.1, -0.2, 0.4,  -0.2, 0.4, 0.3, 0.1,  0.25, -0.15, 0.5, 0.05,  0.1, 0.2, -0.3, 0.45]
let wg: [Float] = [0.5, -0.3, 0.2, 0.1,  0.2, 0.7, -0.4, 0.3,  -0.1, 0.25, 0.4, -0.2,  0.3, 0.1, -0.15, 0.5]
let wu: [Float] = [0.25, -0.15, 0.3, 0.05,  0.1, 0.4, -0.2, 0.15,  0.35, 0.2, -0.1, 0.25,  -0.2, 0.3, 0.15, 0.4]
let wd: [Float] = [0.4, -0.2, 0.3, 0.1,  0.15, 0.5, -0.25, 0.2,  -0.3, 0.1, 0.45, -0.15,  0.2, -0.1, 0.35, 0.3]

// scratch layout (mirrors jte-gqa-blk-off): oN1,oQ,oK,oV,oA,oH,oN2,oSR,oE,oG,oU,oACT
let oN1 = 0
let oQ = oN1 + S*d, oK = oQ + S*dq, oV = oK + S*KVD, oA = oV + S*KVD
let oH = oA + S*dq, oN2 = oH + S*d, oSR = oN2 + S*d, oE = oSR + S
let oG = oE + S, oU = oG + hid, oACT = oU + hid
let scN = oACT + hid

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: max(1,a.count)*4, options: .storageModeShared)! }
let bwq = newBuf(wq), bwk = newBuf(wk), bwv = newBuf(wv), bwo = newBuf(wo)
let bg1 = newBuf(g1), bwg = newBuf(wg), bwu = newBuf(wu), bwd = newBuf(wd), bg2 = newBuf(g2)
let bx = newBuf(x)
let by = newBuf([Float](repeating: 0, count: S*d)), bsc = newBuf([Float](repeating: 0, count: scN))
var uS = UInt32(S), ud = UInt32(d), udq = UInt32(dq), uKVD = UInt32(KVD)
var uhid = UInt32(hid), uHD = UInt32(HD), unkv = UInt32(n_kv), sscale = scale, seps = eps

let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
enc.setComputePipelineState(pso)
let bufs = [bwq,bwk,bwv,bwo,bg1,bwg,bwu,bwd,bg2,bx,by,bsc]
for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
enc.setBytes(&uS, length: 4, index: 12); enc.setBytes(&ud, length: 4, index: 13)
enc.setBytes(&udq, length: 4, index: 14); enc.setBytes(&uKVD, length: 4, index: 15)
enc.setBytes(&uhid, length: 4, index: 16); enc.setBytes(&uHD, length: 4, index: 17)
enc.setBytes(&unkv, length: 4, index: 18); enc.setBytes(&sscale, length: 4, index: 19)
enc.setBytes(&seps, length: 4, index: 20)
enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
enc.endEncoding()
let t0 = Date(); cb.commit(); cb.waitUntilCompleted(); let dt = Date().timeIntervalSince(t0)
let yp = by.contents().bindMemory(to: Float.self, capacity: S*d)
var gpuY = [Float](repeating: 0, count: S*d); for i in 0..<(S*d) { gpuY[i] = yp[i] }

// ── fp32 CPU mirror — the SAME folds the kernel emits (and the recipe walks), the bit-exact parity gate ──
func fexpSmall(_ x0: Float) -> Float { var nn: Float = 1, term: Float = 1, acc: Float = 1; while nn <= 14 { term = term * (x0 / nn); acc = acc + term; nn = nn + 1 }; return acc }
func fexp(_ x0: Float) -> Float { var x = x0; var k = 0; while (x < 0 ? -x : x) > 0.5 { x = x/2; k += 1 }; var v = fexpSmall(x); while k > 0 { v = v*v; k -= 1 }; return v }
func rr2pi(_ x: Float) -> Float { let t: Float = 6.283185307179586; return x - t*(x/t).rounded() }
func fsin(_ x: Float) -> Float { let r = rr2pi(x); let x2 = r*r; var term = r, acc: Float = 0; var k = 0; while k < 10 { acc = acc+term; let m = 2*(k+1); let den = Float(m*(m+1)); term = term*((-1.0*x2)/den); k += 1 }; return acc }
func fcos(_ x: Float) -> Float { return fsin(x + 1.5707963267948966) }
func fln(_ x0: Float) -> Float { var a = x0; var e = 0; while a >= 2 { a *= 0.5; e += 1 }; while a < 1 { a *= 2; e -= 1 }; let z = (a-1)/(a+1); let z2 = z*z; var zpow = z, acc: Float = 0; var j = 0; while j < 14 { let num = zpow*z2; let den = Float(2*(j+1)+1); acc += num/den; zpow = zpow*z2; j += 1 }; let lm: Float = 2*(z+acc); return Float(e)*0.6931471805599453 + lm }
func fpow(_ b: Float, _ e: Float) -> Float { if b <= 0 { return 0 }; return fexp(e*fln(b)) }

func cpuBlock() -> [Float] {
  var sc = [Float](repeating: 0, count: scN)
  var yo = [Float](repeating: 0, count: S*d)
  // RMSNorm1 of x -> oN1
  do { var s = 0; while s < S { var ss: Float = 0; var j = 0; while j < d { let xv = x[s*d+j]; ss += xv*xv; j += 1 }
       let meansq = ss/Float(d); let sdv = meansq+eps; var g = sdv; var it = 50; while it > 0 { it -= 1; g = 0.5*(g + sdv/g) }
       let inv: Float = 1/g; j = 0; while j < d { sc[oN1+s*d+j] = (x[s*d+j]*inv)*g1[j]; j += 1 }; s += 1 } }
  // q proj (dq), k/v proj (KVD)
  do { var s = 0; while s < S { var r = 0; while r < dq { var acc: Float = 0; var c = d; while c>0 { c -= 1; acc = wq[r*d+c]*sc[oN1+s*d+c] + acc }; sc[oQ+s*dq+r] = acc; r += 1 }; s += 1 } }
  do { var s = 0; while s < S { var r = 0; while r < KVD { var acc: Float = 0; var c = d; while c>0 { c -= 1; acc = wk[r*d+c]*sc[oN1+s*d+c] + acc }; sc[oK+s*KVD+r] = acc; r += 1 }; s += 1 } }
  do { var s = 0; while s < S { var r = 0; while r < KVD { var acc: Float = 0; var c = d; while c>0 { c -= 1; acc = wv[r*d+c]*sc[oN1+s*d+c] + acc }; sc[oV+s*KVD+r] = acc; r += 1 }; s += 1 } }
  // RoPE q (dq), k (KVD)
  do { var s = 0; while s < S { var i = 0; while i+1 < dq { let hd = i % HD; let fr = fpow(10000, (-1.0*Float(hd))/Float(HD)); let a = Float(s)*fr; let ca = fcos(a), sa = fsin(a)
       let q0 = sc[oQ+s*dq+i], q1 = sc[oQ+s*dq+i+1]; sc[oQ+s*dq+i] = q0*ca - q1*sa; sc[oQ+s*dq+i+1] = q0*sa + q1*ca; i += 2 }; s += 1 } }
  do { var s = 0; while s < S { var i = 0; while i+1 < KVD { let hd = i % HD; let fr = fpow(10000, (-1.0*Float(hd))/Float(HD)); let a = Float(s)*fr; let ca = fcos(a), sa = fsin(a)
       let q0 = sc[oK+s*KVD+i], q1 = sc[oK+s*KVD+i+1]; sc[oK+s*KVD+i] = q0*ca - q1*sa; sc[oK+s*KVD+i+1] = q0*sa + q1*ca; i += 2 }; s += 1 } }
  // GQA causal attention -> oA
  do { let NQ = dq/HD, grp = NQ/n_kv; var h = 0; while h < NQ { let kvh = h/grp, qoff = h*HD, koff = kvh*HD
       var s = 0; while s < S {
         var t = 0; while t < s+1 { var acc: Float = 0; var c = HD; while c>0 { c -= 1; acc = sc[oQ+s*dq+qoff+c]*sc[oK+t*KVD+koff+c] + acc }; sc[oSR+t] = acc*scale; t += 1 }
         var mx = sc[oSR+0]; t = 1; while t < s+1 { if sc[oSR+t] > mx { mx = sc[oSR+t] }; t += 1 }
         var sumes: Float = 0; t = 0; while t < s+1 { let e = fexp(sc[oSR+t]-mx); sc[oE+t] = e; sumes += e; t += 1 }
         let invs: Float = 1/sumes; t = 0; while t < s+1 { sc[oSR+t] = sc[oE+t]*invs; t += 1 }
         var i = 0; while i < HD { sc[oA+s*dq+qoff+i] = 0; i += 1 }
         t = 0; while t < s+1 { i = 0; while i < HD { sc[oA+s*dq+qoff+i] = sc[oV+t*KVD+koff+i]*sc[oSR+t] + sc[oA+s*dq+qoff+i]; i += 1 }; t += 1 }
         s += 1 }
       h += 1 } }
  // Wo*attn + residual -> oH
  do { var s = 0; while s < S { var i = 0; while i < d { var acc: Float = 0; var c = dq; while c>0 { c -= 1; acc = wo[i*dq+c]*sc[oA+s*dq+c] + acc }; sc[oH+s*d+i] = x[s*d+i]+acc; i += 1 }; s += 1 } }
  // RMSNorm2 of oH -> oN2
  do { var s = 0; while s < S { var ss: Float = 0; var j = 0; while j < d { let xv = sc[oH+s*d+j]; ss += xv*xv; j += 1 }
       let meansq = ss/Float(d); let sdv = meansq+eps; var g = sdv; var it = 50; while it > 0 { it -= 1; g = 0.5*(g + sdv/g) }
       let inv: Float = 1/g; j = 0; while j < d { sc[oN2+s*d+j] = (sc[oH+s*d+j]*inv)*g2[j]; j += 1 }; s += 1 } }
  // SwiGLU FFN -> y
  do { var s = 0; while s < S {
       var k = 0; while k < hid { var acc: Float = 0; var c = d; while c>0 { c -= 1; acc = wg[k*d+c]*sc[oN2+s*d+c] + acc }; sc[oG+k] = acc; k += 1 }
       k = 0; while k < hid { var acc: Float = 0; var c = d; while c>0 { c -= 1; acc = wu[k*d+c]*sc[oN2+s*d+c] + acc }; sc[oU+k] = acc; k += 1 }
       k = 0; while k < hid { let gv = sc[oG+k]; let sig: Float = 1/(1 + fexp(-1.0*gv)); sc[oACT+k] = (gv*sig)*sc[oU+k]; k += 1 }
       var i = 0; while i < d { var acc2: Float = 0; var kk = hid; while kk>0 { kk -= 1; acc2 = wd[i*hid+kk]*sc[oACT+kk] + acc2 }; yo[s*d+i] = sc[oH+s*d+i]+acc2; i += 1 }
       s += 1 } }
  return yo
}
let cpuY = cpuBlock()

// ── gates ──
print(String(format: "GPU GQA causal llama block (n_q=%d query heads, n_kv=%d KV head, group=%d, HD=%d): %.3f ms", n_q, n_kv, n_q/n_kv, HD, dt*1000))
func fmt(_ a: [Float]) -> String { return a.map { String(format: "%.6f", $0) }.joined(separator: ", ") }
print("  y_gpu = [" + fmt(gpuY) + "]")
print("  y_cpu = [" + fmt(cpuY) + "]  (fp32 mirror)")

var bitExact = true
for i in 0..<(S*d) { if gpuY[i].bitPattern != cpuY[i].bitPattern { bitExact = false } }
var maxParity: Float = 0; for i in 0..<(S*d) { let dd = abs(gpuY[i]-cpuY[i]); if dd > maxParity { maxParity = dd } }
print(String(format: "PARITY (GPU vs fp32 CPU mirror): max|y_gpu - y_cpu| = %.3e  %@", maxParity,
             bitExact ? "✓ bit-exact" : (maxParity < 1e-5 ? "✓ within fp32 epsilon" : "✗ FAIL")))

var maxRecipe: Double = 0
for i in 0..<(S*d) { let g = Double(gpuY[i]) * 1e6; let dd = abs(g - rec[i]); if dd > maxRecipe { maxRecipe = dd } }
print(String(format: "RECIPE (GPU fp32 vs fp64 lgqa-block-causal *1e6): max|Δ|=%.1f  %@",
             maxRecipe, maxRecipe < 200.0 ? "✓ tracks the proven recipe within fp32 epsilon" : "✗ recipe mismatch"))

if (bitExact || maxParity < 1e-5) && maxRecipe < 200.0 {
    print("✓ the WHOLE GQA CAUSAL LLAMA BLOCK runs on the M4 Max GPU — Form recipe -> Metal -> silicon, parity with the recipe")
    exit(0)
} else {
    print("✗ gate failed"); exit(1)
}
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── running the GQA causal llama block on the M4 Max GPU ──"
RA=()
for k in $(seq 1 8); do RA+=("$(sed -n "${k}p" "$work/recipe.out")"); done
"$work/runner" "$work/blk.metal" "${RA[@]}"
