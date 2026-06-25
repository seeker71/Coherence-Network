#!/usr/bin/env bash
# metal_gqa_llama_block_runtime_boundary.sh
#
# Build once, then prove the existing GQA causal llama block fixture runs as one
# standalone native runtime artifact under a sanitized environment. Build-time
# carriers may emit the Form-authored Metal source and compile the Swift/Metal
# driver. Runtime receives a single executable with the Metal kernel embedded;
# PATH points at an empty directory, and no Go/Rust/Python/shell/clang/swiftc
# lookup is available to the artifact.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "SKIP no Darwin/Metal runtime"
    exit 2
fi

if ! command -v xcrun >/dev/null; then
    echo "SKIP no xcrun for build-time swiftc lookup"
    exit 2
fi
if ! xcrun --find swiftc >/dev/null 2>&1; then
    echo "SKIP no swiftc for build phase"
    exit 2
fi

if [[ ! -x "$GO_BIN" ]]; then
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/fkgqablk-rt.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# Build phase: emit the existing Form-authored Metal kernel and the proven
# fixture's fp64 recipe receipt. Nothing from this phase is needed at runtime
# except the compiled executable.
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-gqa-llama-block-fwd-causal-msl "form_gqa_llama_block_causal_fwd_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/blk.metal"
grep -q 'kernel void form_gqa_llama_block_causal_fwd_f32' "$work/blk.metal" || {
    echo "FAIL emission produced no GQA causal llama block kernel"
    cat "$work/emit.out"
    exit 1
}

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
if [[ "$(wc -l < "$work/recipe.out" | tr -d ' ')" != "8" ]]; then
    echo "FAIL recipe receipt did not yield 8 fixture values"
    cat "$work/recipe.out"
    exit 1
fi

msl_b64="$(base64 < "$work/blk.metal" | tr -d '\n')"
expected_csv="$(paste -sd, "$work/recipe.out")"
msl_bytes="$(wc -c < "$work/blk.metal" | tr -d ' ')"

cat > "$work/runtime.swift" <<SWIFT
import Foundation
import Metal

let deniedToolNames = ["go", "rustc", "cargo", "python", "python3", "sh", "bash", "zsh", "clang", "swiftc"]
let env = ProcessInfo.processInfo.environment
let pathValue = env["PATH"] ?? ""
var visible: [String] = []
for dir in pathValue.split(separator: ":").map(String.init) {
    for name in deniedToolNames {
        if FileManager.default.isExecutableFile(atPath: dir + "/" + name) {
            visible.append(name)
        }
    }
}
if !visible.isEmpty {
    print("FAIL sanitized runtime PATH exposes denied tools: " + visible.joined(separator: ","))
    exit(1)
}

guard let dev = MTLCreateSystemDefaultDevice() else {
    print("SKIP no Metal device")
    exit(2)
}
guard let data = Data(base64Encoded: "$msl_b64"),
      let src = String(data: data, encoding: .utf8) else {
    print("FAIL embedded Metal source did not decode")
    exit(1)
}

let expectedRecipeX1e6: [Double] = [$expected_csv]
let opts = MTLCompileOptions()
opts.mathMode = .safe
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\\nusing namespace metal;\\n" + src, options: opts)
guard let fn = lib.makeFunction(name: "form_gqa_llama_block_causal_fwd_f32") else {
    print("FAIL embedded Metal library missing kernel")
    exit(1)
}
let pso = try dev.makeComputePipelineState(function: fn)
guard let queue = dev.makeCommandQueue() else {
    print("FAIL Metal command queue unavailable")
    exit(1)
}

let S = 2, d = 4, nQ = 2, nKV = 1, headDim = 2, hidden = 4
let dq = nQ * headDim
let kvd = nKV * headDim
let scale: Float = 1.0 / Float(2.0).squareRoot()
let eps: Float = 0.00001

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

let oN1 = 0
let oQ = oN1 + S * d
let oK = oQ + S * dq
let oV = oK + S * kvd
let oA = oV + S * kvd
let oH = oA + S * dq
let oN2 = oH + S * d
let oSR = oN2 + S * d
let oE = oSR + S
let oG = oE + S
let oU = oG + hidden
let oACT = oU + hidden
let scratchCount = oACT + hidden

func newBuffer(_ values: [Float]) -> MTLBuffer {
    return dev.makeBuffer(bytes: values, length: max(1, values.count) * MemoryLayout<Float>.stride, options: .storageModeShared)!
}

let bwq = newBuffer(wq)
let bwk = newBuffer(wk)
let bwv = newBuffer(wv)
let bwo = newBuffer(wo)
let bg1 = newBuffer(g1)
let bwg = newBuffer(wg)
let bwu = newBuffer(wu)
let bwd = newBuffer(wd)
let bg2 = newBuffer(g2)
let bx = newBuffer(x)
let by = newBuffer([Float](repeating: 0, count: S * d))
let bsc = newBuffer([Float](repeating: 0, count: scratchCount))

var uS = UInt32(S)
var ud = UInt32(d)
var udq = UInt32(dq)
var uKVD = UInt32(kvd)
var uhidden = UInt32(hidden)
var uHeadDim = UInt32(headDim)
var uNKV = UInt32(nKV)
var uScale = scale
var uEps = eps

let commandBuffer = queue.makeCommandBuffer()!
let enc = commandBuffer.makeComputeCommandEncoder()!
enc.setComputePipelineState(pso)
let buffers = [bwq, bwk, bwv, bwo, bg1, bwg, bwu, bwd, bg2, bx, by, bsc]
for (index, buffer) in buffers.enumerated() {
    enc.setBuffer(buffer, offset: 0, index: index)
}
enc.setBytes(&uS, length: 4, index: 12)
enc.setBytes(&ud, length: 4, index: 13)
enc.setBytes(&udq, length: 4, index: 14)
enc.setBytes(&uKVD, length: 4, index: 15)
enc.setBytes(&uhidden, length: 4, index: 16)
enc.setBytes(&uHeadDim, length: 4, index: 17)
enc.setBytes(&uNKV, length: 4, index: 18)
enc.setBytes(&uScale, length: 4, index: 19)
enc.setBytes(&uEps, length: 4, index: 20)
enc.dispatchThreads(MTLSize(width: 1, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: 1, height: 1, depth: 1))
enc.endEncoding()

let started = Date()
commandBuffer.commit()
commandBuffer.waitUntilCompleted()
let elapsedMs = Date().timeIntervalSince(started) * 1000.0

let out = by.contents().bindMemory(to: Float.self, capacity: S * d)
var gpuY: [Float] = []
for index in 0..<(S * d) {
    gpuY.append(out[index])
}

var rounded: [Int] = []
var maxRecipeDelta = 0.0
for index in 0..<(S * d) {
    let scaled = Double(gpuY[index]) * 1_000_000.0
    rounded.append(Int(scaled.rounded()))
    let delta = abs(scaled - expectedRecipeX1e6[index])
    if delta > maxRecipeDelta {
        maxRecipeDelta = delta
    }
}

print("runtime_path_sanitized=true")
print("denied_toolchain_names_visible_on_path=0")
print("metal_device=" + dev.name)
print("embedded_msl_bytes=$msl_bytes")
print(String(format: "dispatch_ms=%.3f", elapsedMs))
print("gpu_y_x1e6_round=[" + rounded.map(String.init).joined(separator: ",") + "]")
print(String(format: "max_recipe_delta_x1e6=%.3f", maxRecipeDelta))

if maxRecipeDelta < 200.0 {
    print("PASS standalone-metal-gqa-llama-block-runtime")
    exit(0)
}

print("FAIL recipe delta exceeded fp32 epsilon gate")
exit(1)
SWIFT

artifact="$work/form_gqa_llama_block_runtime_artifact"
xcrun swiftc -O -framework Metal "$work/runtime.swift" -o "$artifact"
codesign -s - "$artifact" >/dev/null 2>&1 || true

echo "build_phase:"
echo "  emitted_msl_bytes=$msl_bytes"
echo "  recipe_x1e6=[$expected_csv]"
echo "  artifact=$artifact"
echo "linked_libraries:"
otool -L "$artifact" | sed 's/^/  /'

mkdir -p "$work/empty-bin" "$work/home" "$work/tmp"
echo "runtime_phase:"
echo "  env=-i PATH=<empty-bin> HOME=<temp-home> TMPDIR=<temp-tmp>"
env -i PATH="$work/empty-bin" HOME="$work/home" TMPDIR="$work/tmp" "$artifact" | tee "$work/runtime.out"
grep -q 'PASS standalone-metal-gqa-llama-block-runtime' "$work/runtime.out"
