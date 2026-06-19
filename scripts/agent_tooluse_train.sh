#!/usr/bin/env bash
# agent_tooluse_train.sh — a REAL model on REAL data at full scale, natively.
#
# The MODEL + the training STEP are the Form recipe: transformer-backprop.fk's tbp-mlp-step
# (one SGD step over y = W2·gelu(W1·x + b1) + b2) emitted to ONE Metal kernel by
# jit-tensor-emit.fk's jte-mlp-train-msl — every byte authored by the recipe, gelu/gelu'
# composed from the recipe's own fexp/ftanh (never the hardware's). This script is only the
# CARRIER: it compiles that kernel, then loops the Form-emitted step over the REAL agent
# corpus (scripts/agent_tooluse_featurize.py turns 939 real agent turns into 53 task features
# -> 8 tool labels), and evaluates held-out tool prediction against the majority-class baseline.
# Weights START at a fixed small init and EMERGE from the real data; nothing is baked.
#
# Run:  scripts/agent_tooluse_train.sh [hid epochs lr]    (defaults 64 80 0.02)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
HID="${1:-64}"; EPOCHS="${2:-80}"; LR="${3:-0.02}"
DATA="${DATA:-/tmp/agent_tooluse.dat}"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain — the GPU witness needs an Apple GPU + swiftc"; exit 2
fi
[[ -x "$GO_BIN" ]] || (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
[[ -f "$DATA" ]] || python3 "$ROOT/scripts/agent_tooluse_featurize.py" "$DATA"
work="$(mktemp -d "${TMPDIR:-/tmp}/fktool.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the FFN training-step MSL (identical recipe metal_ffn_audit proves bit-parity for) ──
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-mlp-train-msl "form_mlp_train_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/train.metal"
grep -q 'kernel void form_mlp_train_f32' "$work/train.metal" || { echo "FAIL emission produced no kernel"; cat "$work/emit.out"; exit 1; }
echo "emitted FFN training-step MSL: $(wc -c < "$work/train.metal" | tr -d ' ') bytes, authored by the Form recipe"

# ── 2. Swift carrier: load real data, loop the Form step over the corpus on the GPU, eval held-out ──
cat > "$work/runner.swift" <<'SWIFT'
import Metal
import Foundation

setvbuf(stdout, nil, _IONBF, 0)
let args = CommandLine.arguments
let dataPath = args[1], mslPath = args[2]
let hid = Int(args[3])!, epochs = Int(args[4])!
let lr = Float(args[5])!

// ── parse the real dataset: "n_train n_held indim outd" / tool-names / rows "x.. | t.." ──
let lines = (try String(contentsOfFile: dataPath, encoding: .utf8)).split(separator: "\n").map(String.init)
let hdr = lines[0].split(separator: " ").map { Int($0)! }
let nTrain = hdr[0], nHeld = hdr[1], indim = hdr[2], outd = hdr[3]
let tools = lines[1].split(separator: " ").map(String.init)
var X = [[Float]](), T = [[Float]]()
for r in 0..<(nTrain+nHeld) {
    let parts = lines[2+r].components(separatedBy: " | ")
    X.append(parts[0].split(separator: " ").map { Float($0)! })
    T.append(parts[1].split(separator: " ").map { Float($0)! })
}
func slice(_ a: [[Float]], _ lo: Int, _ hi: Int) -> [[Float]] { Array(a[lo..<hi]) }
let Xtr = slice(X,0,nTrain), Ttr = slice(T,0,nTrain)
let Xhe = slice(X,nTrain,nTrain+nHeld), The = slice(T,nTrain,nTrain+nHeld)

guard let dev = MTLCreateSystemDefaultDevice() else { print("SKIP no Metal device"); exit(2) }
let src = try String(contentsOfFile: mslPath, encoding: .utf8)
let opts = MTLCompileOptions(); opts.fastMathEnabled = false
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\nusing namespace metal;\n" + src, options: opts)
let pso = try dev.makeComputePipelineState(function: lib.makeFunction(name: "form_mlp_train_f32")!)
let q = dev.makeCommandQueue()!

// ── the recipe's own exp/tanh/gelu in fp32 (for CPU-side held-out eval; matches the kernel's fgelu) ──
func fexp_small(_ x: Float) -> Float { var n: Float = 1, term: Float = 1, acc: Float = 1; while n <= 14.0 { term = term*(x/n); acc += term; n += 1 }; return acc }
func fexp(_ x0: Float) -> Float { var x = x0; var k = 0; while abs(x) > 0.5 { x /= 2; k += 1 }; var v = fexp_small(x); while k > 0 { v = v*v; k -= 1 }; return v }
func ftanh(_ x: Float) -> Float { let e = fexp(2*x); return (e-1)/(e+1) }
func fgelu(_ x: Float) -> Float { let z = Float(0.7978845608028654)*(x+Float(0.044715)*(x*(x*x))); return (0.5*x)*(1+ftanh(z)) }

// ── deterministic small init; weights EMERGE from here ──
func z(_ n: Int) -> [Float] { [Float](repeating: 0, count: n) }
var w1 = z(hid*indim); for n in 0..<(hid*indim) { w1[n] = 0.01*(Float(n % 11)-5.0) }
var w2 = z(outd*hid);  for n in 0..<(outd*hid)  { w2[n] = 0.01*(Float(n % 13)-6.0) }
var b1 = z(hid), b2 = z(outd)
func newBuf(_ a: [Float]) -> MTLBuffer { dev.makeBuffer(bytes: a, length: a.count*4, options: .storageModeShared)! }
let bw1 = newBuf(w1), bb1 = newBuf(b1), bw2 = newBuf(w2), bb2 = newBuf(b2)
let bx = newBuf(z(indim)), bt = newBuf(z(outd)), bloss = newBuf(z(outd))
let bh1 = newBuf(z(hid)), ba = newBuf(z(hid)), bgy = newBuf(z(outd)), bdh1 = newBuf(z(hid))
var u_in = UInt32(indim), u_hid = UInt32(hid), u_out = UInt32(outd), lrv = lr
let tgs = min(pso.maxTotalThreadsPerThreadgroup, max(hid, outd))

func step(_ x: [Float], _ t: [Float]) {
    bx.contents().copyMemory(from: x, byteCount: indim*4)
    bt.contents().copyMemory(from: t, byteCount: outd*4)
    let cb = q.makeCommandBuffer()!; let enc = cb.makeComputeCommandEncoder()!
    enc.setComputePipelineState(pso)
    let bufs = [bw1,bb1,bw2,bb2,bx,bt,bloss,bh1,ba,bgy,bdh1]
    for (i,b) in bufs.enumerated() { enc.setBuffer(b, offset: 0, index: i) }
    enc.setBytes(&u_in, length: 4, index: 11); enc.setBytes(&u_hid, length: 4, index: 12)
    enc.setBytes(&u_out, length: 4, index: 13); enc.setBytes(&lrv, length: 4, index: 14)
    enc.dispatchThreadgroups(MTLSize(width:1,height:1,depth:1), threadsPerThreadgroup: MTLSize(width:tgs,height:1,depth:1))
    enc.endEncoding(); cb.commit(); cb.waitUntilCompleted()
}
// read the current GPU weights back into host arrays for CPU-side forward/eval
func pull() { w1 = Array(UnsafeBufferPointer(start: bw1.contents().bindMemory(to: Float.self, capacity: hid*indim), count: hid*indim))
              w2 = Array(UnsafeBufferPointer(start: bw2.contents().bindMemory(to: Float.self, capacity: outd*hid), count: outd*hid))
              b1 = Array(UnsafeBufferPointer(start: bb1.contents().bindMemory(to: Float.self, capacity: hid), count: hid))
              b2 = Array(UnsafeBufferPointer(start: bb2.contents().bindMemory(to: Float.self, capacity: outd), count: outd)) }
func forward(_ x: [Float]) -> [Float] {
    var a = z(hid)
    for k in 0..<hid { var acc: Float = 0; for j in 0..<indim { acc += w1[k*indim+j]*x[j] }; a[k] = fgelu(acc+b1[k]) }
    var y = z(outd)
    for i in 0..<outd { var acc: Float = 0; for k in 0..<hid { acc += w2[i*hid+k]*a[k] }; y[i] = acc+b2[i] }
    return y
}
func setLoss(_ Xs: [[Float]], _ Ts: [[Float]]) -> Double {
    var s = 0.0; for n in 0..<Xs.count { let y = forward(Xs[n]); for i in 0..<outd { let d = Double(y[i]-Ts[n][i]); s += d*d } }
    return s/Double(Xs.count)
}
// multi-label metrics: micro-accuracy (per-bit), exact-set match, "covers all used tools"
func eval(_ Xs: [[Float]], _ Ts: [[Float]], predict: ([Float]) -> [Bool]) -> (micro: Double, exact: Double, cover: Double, perTool: [Double]) {
    var bits = 0, correct = 0, exact = 0, cover = 0; var tc = z(outd).map { _ in 0 }
    for n in 0..<Xs.count {
        let p = predict(Xs[n]); var allRight = true, covered = true
        for i in 0..<outd { let want = Ts[n][i] > 0.5
            if p[i] == want { correct += 1; tc[i] += 1 } else { allRight = false }
            if want && !p[i] { covered = false }
            bits += 1 }
        if allRight { exact += 1 }; if covered { cover += 1 }
    }
    return (Double(correct)/Double(bits), Double(exact)/Double(Xs.count), Double(cover)/Double(Xs.count),
            (0..<outd).map { Double(tc[$0])/Double(Xs.count) })
}

// ── train: loop the Form-emitted step over the REAL corpus, GPU ──
print("REAL agent corpus: \(nTrain) train, \(nHeld) held-out turns  |  FFN(\(indim)->\(hid)->\(outd)), \(hid*indim+hid+outd*hid+outd) params, lr=\(lr)")
print("epoch   train_loss   held_loss   held_micro_acc")
let t0 = Date()
let marks = Set([0,5,10,20,40,epochs])
pull(); if marks.contains(0) {
    let (m,_,_,_) = eval(Xhe,The){ x in forward(x).map{ $0>0.5 } }
    print(String(format: "%4d     %9.4f   %9.4f   %6.1f%%", 0, setLoss(Xtr,Ttr), setLoss(Xhe,The), m*100)) }
for ep in 1...epochs {
    for n in 0..<nTrain { step(Xtr[n], Ttr[n]) }
    if marks.contains(ep) { pull()
        let (m,_,_,_) = eval(Xhe,The){ x in forward(x).map{ $0>0.5 } }
        print(String(format: "%4d     %9.4f   %9.4f   %6.1f%%", ep, setLoss(Xtr,Ttr), setLoss(Xhe,The), m*100)) }
}
let dt = Date().timeIntervalSince(t0)
print(String(format: "trained %d epochs x %d examples = %d GPU steps in %.2f s", epochs, nTrain, epochs*nTrain, dt))

// ── held-out eval: the model vs the majority-class baseline ──
pull()
let (mMic,mEx,mCov,mPer) = eval(Xhe,The){ x in forward(x).map{ $0>0.5 } }
// baseline: predict each tool by its train base-rate >= 0.5 (the no-learning majority guess)
var base = z(outd); for i in 0..<outd { var s: Float = 0; for n in 0..<nTrain { s += Ttr[n][i] }; base[i] = s/Float(nTrain) }
let bPred = (0..<outd).map { base[$0] >= 0.5 }
let (bMic,bEx,bCov,bPer) = eval(Xhe,The){ _ in bPred }
print("\n── held-out (\(nHeld) unseen real turns) ──")
print("                 micro-acc   exact-set   covers-used")
print(String(format: "  model           %6.1f%%      %5.1f%%       %5.1f%%", mMic*100, mEx*100, mCov*100))
print(String(format: "  majority base   %6.1f%%      %5.1f%%       %5.1f%%", bMic*100, bEx*100, bCov*100))
print("  per-tool held accuracy (model vs baseline, base-rate):")
for i in 0..<outd {
    let name = tools[i].padding(toLength: 16, withPad: " ", startingAt: 0)
    print("    \(name)" + String(format: "%5.1f%%  vs %5.1f%%   (rate %.2f)", mPer[i]*100, bPer[i]*100, Double(base[i]))) }
print(mMic > bMic && mEx >= bEx ? "  ✓ the model LEARNED the real signal — beats the no-learning baseline on unseen turns"
                                 : "  · model did not beat baseline at these settings")
SWIFT

swiftc -O -framework Metal "$work/runner.swift" -o "$work/runner" 2>&1 | grep -vE '^$|fastMathEnabled|DeprecatedDeclaration|warning:|deprecated|^ *[0-9]+ \||`-|opts\.|let lib' || true
[[ -x "$work/runner" ]] || { echo "FAIL swiftc did not build the runner"; exit 1; }

echo "── training the tool-use model on the M4 Max GPU (real agent corpus) ──"
"$work/runner" "$DATA" "$work/train.metal" "$HID" "$EPOCHS" "$LR"
