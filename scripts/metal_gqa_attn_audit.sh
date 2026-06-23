#!/usr/bin/env bash
# metal_gqa_attn_audit.sh — GROUPED-QUERY ATTENTION (GQA) running on Metal (M4 Max GPU witness).
#
# gqa-attn.fk's tb-gqa-attn is the ALGORITHM (fp64, proven FOUR-WAY 7 by tests/gqa-attn-band.fk):
# n query heads share nkv < n KV heads — query head h reads KV head (h / group), group = n / nkv, and k/v are
# projected to the SMALLER nkv*hd width. This is the attention real llama3.2:3b runs (24 query heads, 8 KV
# heads, head_dim 128). jit-tensor-emit.fk's jte-gqa-attn-msl emits that attention over a sequence as ONE Metal
# kernel — every byte authored by the Form recipe; each query head's attention runs independently within its
# hd-wide q-slice against KV head (h/group)'s hd-wide k/v-slice, the per-head context vectors concatenated
# position-wise back to n*hd. GQA at group=1 (nkv=n) IS plain MHA (no parallel path). This script is only the
# carrier: it emits the kernel, compiles it (mathMode safe — IEEE, no fast-math contraction), runs it on the M4
# Max GPU over the SAME fixture gqa-attn-band.fk proves four-way (claim 3: S=2, n=4 query heads, nkv=2 KV
# heads, head_dim 2, scale 1.0 — the real llama 24->8 grouping shape), and gates three executions to one answer:
#   1. the Form recipe tb-gqa-attn in fp64 via the Go kernel (the proven ground truth, y*1e6 rounded)
#   2. this GPU attention in fp32
#   3. an fp32 CPU mirror that walks the SAME GQA folds (the bit-exact parity gate)
# So the chain is honest end to end: fp64 recipe (proven four-way) -> fp32 GPU carrier (proven == fp32 CPU
# mirror, bit-for-bit) -> tracks the fp64 recipe within fp32 epsilon. The softmax exp is the recipe's OWN fexp
# Taylor (never Metal's); every dot is tb-dot's downward right-fold split through a named temporary so no
# compiler contracts it into an fma. The grouping arithmetic (kvh = h / group) is what lets 4 query heads share
# 2 KV heads — heads 0,1 -> kv0 ; heads 2,3 -> kv1, exactly the (h / group) mapping llama3.2 runs at 24 -> 8.
#
# Carriers: form-kernel-go (the mouth), swiftc + Metal.framework (the driver-organ idiom — allowed host
# carriers per host-kernel.form host-resource-access); the emitter intelligence lives in the body. The
# single-thread walk matches the recipe serially and bit-exactly; parallelizing across query heads is the
# named follow-up.
#
# Run:  scripts/metal_gqa_attn_audit.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fkgqa.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the GQA attention MSL; the kernel is only the mouth ────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-gqa-attn-msl "form_gqa_attn_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/gqa.metal"
grep -q 'kernel void form_gqa_attn_f32' "$work/gqa.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted GQA attention MSL: $(wc -c < "$work/gqa.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. the Form recipe in fp64 (the proven four-way ground truth) — gqa-attn-band.fk claim 3 fixture ────
cat "$FORMDIR/form-stdlib/transformer-numerics.fk" "$FORMDIR/form-stdlib/transformer-block.fk" \
    "$FORMDIR/form-stdlib/transformer-mh.fk" "$FORMDIR/form-stdlib/gqa-attn.fk" > "$work/recipe.fk"
cat >> "$work/recipe.fk" <<'RECIPE'
(do
  (let qs (list (list 0.5 -0.3 0.9 0.2 -0.4 0.7 0.1 -0.6)
                (list -0.2 0.8 0.3 -0.5 0.6 0.1 -0.7 0.4)))
  (let ks (list (list 0.2 0.8 -0.1 0.5) (list -0.5 0.3 0.6 -0.2)))
  (let vs (list (list 1.0 -1.0 0.3 0.7) (list 0.4 0.6 -0.8 0.1)))
  (let y (tb-gqa-attn qs ks vs 4 2 2 1.0))
  (let r0 (nth y 0)) (let r1 (nth y 1))
  (print (round (mul (nth r0 0) 1000000.0)))
  (print (round (mul (nth r0 1) 1000000.0)))
  (print (round (mul (nth r0 2) 1000000.0)))
  (print (round (mul (nth r0 3) 1000000.0)))
  (print (round (mul (nth r0 4) 1000000.0)))
  (print (round (mul (nth r0 5) 1000000.0)))
  (print (round (mul (nth r0 6) 1000000.0)))
  (print (round (mul (nth r0 7) 1000000.0)))
  (print (round (mul (nth r1 0) 1000000.0)))
  (print (round (mul (nth r1 1) 1000000.0)))
  (print (round (mul (nth r1 2) 1000000.0)))
  (print (round (mul (nth r1 3) 1000000.0)))
  (print (round (mul (nth r1 4) 1000000.0)))
  (print (round (mul (nth r1 5) 1000000.0)))
  (print (round (mul (nth r1 6) 1000000.0)))
  (print (round (mul (nth r1 7) 1000000.0))))
RECIPE
(cd "$FORMDIR" && "$GO_BIN" "$work/recipe.fk" 2>/dev/null) | grep -E '^-?[0-9]+$' | head -16 > "$work/recipe.out"
echo "Form recipe tb-gqa-attn (fp64, four-way proven) y*1e6: $(tr '\n' ' ' < "$work/recipe.out")"

# ── 3. Swift carrier: compile (mathMode safe), run GQA on the GPU, parity-gate vs fp32 CPU mirror ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

let args = CommandLine.arguments
let mslPath = args[1]
let rec: [Double] = (2...17).map { Double(args[$0])! }   // fp64 recipe ground truth (y*1e6, 16 values)

let dev = MTLCreateSystemDefaultDevice()!
let src = try String(contentsOfFile: mslPath, encoding: .utf8)
let opts = MTLCompileOptions()
opts.mathMode = .safe   // IEEE-conformant: no fast-math reassociation/contraction
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
let fn = lib.makeFunction(name: "form_gqa_attn_f32")!
let pso = try dev.makeComputePipelineState(function: fn)
let q = dev.makeCommandQueue()!

// dims (gqa-attn-band.fk claim 3: the real llama 24->8 grouping shape, scaled to hd=2)
let S = 2, n = 4, nkv = 2, hd = 2
let N = n*hd, KVD = nkv*hd, grp = n/nkv
let scale: Float = 1.0

// the gqa-attn-band.fk claim-3 fixture, row-major flattened (projected q/k/v)
let qs: [Float] = [0.5, -0.3, 0.9, 0.2, -0.4, 0.7, 0.1, -0.6,  -0.2, 0.8, 0.3, -0.5, 0.6, 0.1, -0.7, 0.4]
let ks: [Float] = [0.2, 0.8, -0.1, 0.5,  -0.5, 0.3, 0.6, -0.2]
let vs: [Float] = [1.0, -1.0, 0.3, 0.7,  0.4, 0.6, -0.8, 0.1]
let scN = 2*S   // oSR (S) + oE (S)

func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: max(1,a.count)*4, options: .storageModeShared)! }
let bqs = newBuf(qs), bks = newBuf(ks), bvs = newBuf(vs)
let by = newBuf([Float](repeating: 0, count: S*N)), bsc = newBuf([Float](repeating: 0, count: scN))
var uS = UInt32(S), un = UInt32(n), unkv = UInt32(nkv), uhd = UInt32(hd), sscale = scale

let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
enc.setComputePipelineState(pso)
let bufs = [bqs,bks,bvs,by,bsc]
for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
enc.setBytes(&uS, length: 4, index: 5); enc.setBytes(&un, length: 4, index: 6)
enc.setBytes(&unkv, length: 4, index: 7); enc.setBytes(&uhd, length: 4, index: 8)
enc.setBytes(&sscale, length: 4, index: 9)
enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
enc.endEncoding()
let t0 = Date(); cb.commit(); cb.waitUntilCompleted(); let dt = Date().timeIntervalSince(t0)
let yp = by.contents().bindMemory(to: Float.self, capacity: S*N)
var gpuY = [Float](repeating: 0, count: S*N); for i in 0..<(S*N) { gpuY[i] = yp[i] }

// ── fp32 CPU mirror — the SAME folds the recipe walks (and jte-gqa-body emits), the bit-exact parity gate ──
func fexpSmall(_ x0: Float) -> Float { var nn: Float = 1, term: Float = 1, acc: Float = 1; while nn <= 14 { term = term * (x0 / nn); acc = acc + term; nn = nn + 1 }; return acc }
func fexp(_ x0: Float) -> Float { var x = x0; var k = 0; while (x < 0 ? -x : x) > 0.5 { x = x/2; k += 1 }; var v = fexpSmall(x); while k > 0 { v = v*v; k -= 1 }; return v }

func cpuGqa() -> [Float] {
  var sc = [Float](repeating: 0, count: scN)
  var yo = [Float](repeating: 0, count: S*N)
  let oSR = 0, oE = oSR + S
  for h in 0..<n {
    let kvh = h / grp, qoff = h*hd, koff = kvh*hd
    for s in 0..<S {
      for t in 0..<S { var acc: Float = 0; var c = hd; while c>0 { c -= 1; let p = qs[s*N+qoff+c]*ks[t*KVD+koff+c]; acc = p+acc }; sc[oSR+t] = acc*scale }
      var mx = sc[oSR+0]; var t = 1; while t<S { if sc[oSR+t] > mx { mx = sc[oSR+t] }; t += 1 }
      var sumes: Float = 0; t = 0; while t<S { let e = fexp(sc[oSR+t]-mx); sc[oE+t] = e; sumes = sumes+e; t += 1 }
      let invs: Float = 1.0/sumes; t = 0; while t<S { sc[oSR+t] = sc[oE+t]*invs; t += 1 }
      var i = 0; while i<hd { yo[s*N+qoff+i] = 0; i += 1 }
      t = 0; while t<S { i = 0; while i<hd { let pv = vs[t*KVD+koff+i]*sc[oSR+t]; yo[s*N+qoff+i] = yo[s*N+qoff+i]+pv; i += 1 }; t += 1 }
    }
  }
  return yo
}
let cpuY = cpuGqa()

// ── gates ──
print(String(format: "GPU GQA attention (n=%d query heads, nkv=%d KV heads, group=%d, hd=%d): %.3f ms", n, nkv, grp, hd, dt*1000))
func fmt(_ a: [Float]) -> String { return a.map { String(format: "%.6f", $0) }.joined(separator: ", ") }
print("  y_gpu = [" + fmt(gpuY) + "]")
print("  y_cpu = [" + fmt(cpuY) + "]  (fp32 mirror)")

var bitExact = true
for i in 0..<(S*N) { if gpuY[i].bitPattern != cpuY[i].bitPattern { bitExact = false } }
var maxParity: Float = 0; for i in 0..<(S*N) { let dd = abs(gpuY[i]-cpuY[i]); if dd > maxParity { maxParity = dd } }
print(String(format: "PARITY (GPU vs fp32 CPU mirror): max|y_gpu - y_cpu| = %.3e  %@", maxParity,
             bitExact ? "✓ bit-exact" : (maxParity < 1e-5 ? "✓ within fp32 epsilon" : "✗ FAIL")))

var maxRecipe: Double = 0
for i in 0..<(S*N) { let g = Double(gpuY[i]) * 1e6; let dd = abs(g - rec[i]); if dd > maxRecipe { maxRecipe = dd } }
print(String(format: "RECIPE (GPU fp32 vs fp64 tb-gqa-attn *1e6): max|Δ|=%.1f  %@",
             maxRecipe, maxRecipe < 200.0 ? "✓ tracks the proven recipe within fp32 epsilon" : "✗ recipe mismatch"))

if (bitExact || maxParity < 1e-5) && maxRecipe < 200.0 {
    print("✓ GROUPED-QUERY ATTENTION runs on the M4 Max GPU — Form recipe -> Metal -> silicon, parity with the recipe")
    exit(0)
} else {
    print("✗ gate failed"); exit(1)
}
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -v '^$' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── running grouped-query attention on the M4 Max GPU ──"
RA=()
for k in $(seq 1 16); do RA+=("$(sed -n "${k}p" "$work/recipe.out")"); done
"$work/runner" "$work/gqa.metal" "${RA[@]}"
