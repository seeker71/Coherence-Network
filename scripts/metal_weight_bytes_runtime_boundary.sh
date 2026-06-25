#!/usr/bin/env bash
# metal_weight_bytes_runtime_boundary.sh
#
# Build once, then prove a Form-emitted Metal inference kernel can load model
# weight bytes at runtime without HTTP, Ollama, shell, or toolchain lookup.
# Build-time carriers emit the Form-authored MSL and compile the Swift/Metal
# driver. Runtime receives only a compiled executable plus a binary weight file.
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

work="$(mktemp -d "${TMPDIR:-/tmp}/fkmetal-weights.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# Build phase: emit the existing Form-authored Metal matvec kernel. The runtime
# artifact embeds only this source string; model weights are not baked in.
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
printf '\n(print "==MSL==")\n(print (jte-matvec-msl "form_model_matvec_f32"))\n(print "==END==")\n' >> "$work/driver.fk"
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/model.metal"
grep -q 'kernel void form_model_matvec_f32' "$work/model.metal" || {
    echo "FAIL emission produced no matvec kernel"
    cat "$work/emit.out"
    exit 1
}

msl_b64="$(base64 < "$work/model.metal" | tr -d '\n')"
msl_bytes="$(wc -c < "$work/model.metal" | tr -d ' ')"

weights="$work/model-weights.bin"
# Binary model fixture, little-endian:
#   u32 rows=2, u32 cols=3,
#   f32 W=[1, 2, -1, 0.5, -3, 4],
#   f32 x=[2, -1, 0.25]
printf '\x02\x00\x00\x00\x03\x00\x00\x00\x00\x00\x80\x3f\x00\x00\x00\x40\x00\x00\x80\xbf\x00\x00\x00\x3f\x00\x00\x40\xc0\x00\x00\x80\x40\x00\x00\x00\x40\x00\x00\x80\xbf\x00\x00\x80\x3e' > "$weights"

cat > "$work/runtime.swift" <<SWIFT
import Foundation
import Metal

let deniedToolNames = ["go", "rustc", "cargo", "python", "python3", "sh", "bash", "zsh", "clang", "swiftc", "curl", "ollama"]
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

guard CommandLine.arguments.count == 2 else {
    print("FAIL usage: artifact <model-weight-bytes>")
    exit(1)
}
let modelPath = CommandLine.arguments[1]
let modelData = try Data(contentsOf: URL(fileURLWithPath: modelPath))

func readU32(_ offset: Int) -> UInt32 {
    let b0 = UInt32(modelData[offset])
    let b1 = UInt32(modelData[offset + 1]) << 8
    let b2 = UInt32(modelData[offset + 2]) << 16
    let b3 = UInt32(modelData[offset + 3]) << 24
    return b0 | b1 | b2 | b3
}

func readF32(_ offset: Int) -> Float {
    return Float(bitPattern: readU32(offset))
}

let rows = Int(readU32(0))
let cols = Int(readU32(4))
let expectedByteCount = 8 + ((rows * cols) + cols) * MemoryLayout<Float>.stride
if rows != 2 || cols != 3 || modelData.count != expectedByteCount {
    print("FAIL malformed model bytes rows=\\(rows) cols=\\(cols) bytes=\\(modelData.count)")
    exit(1)
}

var floats: [Float] = []
for index in 0..<((rows * cols) + cols) {
    floats.append(readF32(8 + index * MemoryLayout<Float>.stride))
}
let weights = Array(floats[0..<(rows * cols)])
let input = Array(floats[(rows * cols)..<floats.count])

guard let dev = MTLCreateSystemDefaultDevice() else {
    print("SKIP no Metal device")
    exit(2)
}
guard let data = Data(base64Encoded: "$msl_b64"),
      let src = String(data: data, encoding: .utf8) else {
    print("FAIL embedded Metal source did not decode")
    exit(1)
}

let opts = MTLCompileOptions()
opts.mathMode = .safe
let lib = try dev.makeLibrary(source: "#include <metal_stdlib>\\nusing namespace metal;\\n" + src, options: opts)
guard let fn = lib.makeFunction(name: "form_model_matvec_f32") else {
    print("FAIL embedded Metal library missing kernel")
    exit(1)
}
let pso = try dev.makeComputePipelineState(function: fn)
guard let queue = dev.makeCommandQueue() else {
    print("FAIL Metal command queue unavailable")
    exit(1)
}

func newBuffer(_ values: [Float]) -> MTLBuffer {
    return dev.makeBuffer(bytes: values, length: max(1, values.count) * MemoryLayout<Float>.stride, options: .storageModeShared)!
}

let bw = newBuffer(weights)
let bx = newBuffer(input)
let by = newBuffer([Float](repeating: 0, count: rows))
var uRows = UInt32(rows)
var uCols = UInt32(cols)

let commandBuffer = queue.makeCommandBuffer()!
let enc = commandBuffer.makeComputeCommandEncoder()!
enc.setComputePipelineState(pso)
enc.setBuffer(bw, offset: 0, index: 0)
enc.setBuffer(bx, offset: 0, index: 1)
enc.setBuffer(by, offset: 0, index: 2)
enc.setBytes(&uRows, length: 4, index: 3)
enc.setBytes(&uCols, length: 4, index: 4)
enc.dispatchThreads(MTLSize(width: rows, height: 1, depth: 1), threadsPerThreadgroup: MTLSize(width: rows, height: 1, depth: 1))
enc.endEncoding()

let started = Date()
commandBuffer.commit()
commandBuffer.waitUntilCompleted()
let elapsedMs = Date().timeIntervalSince(started) * 1000.0

let out = by.contents().bindMemory(to: Float.self, capacity: rows)
var gpuY: [Float] = []
for index in 0..<rows {
    gpuY.append(out[index])
}

var expected: [Float] = []
for row in 0..<rows {
    var acc: Float = 0.0
    var j = cols
    while j > 0 {
        j -= 1
        let p = weights[row * cols + j] * input[j]
        acc = p + acc
    }
    expected.append(acc)
}

var maxDelta: Float = 0.0
for index in 0..<rows {
    maxDelta = max(maxDelta, abs(gpuY[index] - expected[index]))
}

func render(_ values: [Float]) -> String {
    return "[" + values.map { String(format: "%.6f", Double(\$0)) }.joined(separator: ",") + "]"
}

print("runtime_path_sanitized=true")
print("denied_toolchain_names_visible_on_path=0")
print("http_or_ollama=absent")
print("metal_device=" + dev.name)
print("embedded_msl_bytes=$msl_bytes")
print("model_bytes_loaded=\\(modelData.count)")
print("weight_bytes_loaded=\\(rows * cols * MemoryLayout<Float>.stride)")
print("input_bytes_loaded=\\(cols * MemoryLayout<Float>.stride)")
print("rows=\\(rows)")
print("cols=\\(cols)")
print(String(format: "dispatch_ms=%.3f", elapsedMs))
print("gpu_y=" + render(gpuY))
print("expected_y=" + render(expected))
print(String(format: "max_delta=%.9f", Double(maxDelta)))

if maxDelta <= 0.000001 {
    print("PASS form-native-metal-weight-bytes-runtime")
    exit(0)
}

print("FAIL Metal output differed from runtime byte-loaded model")
exit(1)
SWIFT

artifact="$work/form_metal_weight_bytes_runtime"
xcrun swiftc -O -framework Metal "$work/runtime.swift" -o "$artifact"
codesign -s - "$artifact" >/dev/null 2>&1 || true

echo "build_phase:"
echo "  emitted_msl_bytes=$msl_bytes"
echo "  model_weight_bytes=$weights"
echo "  artifact=$artifact"
echo "linked_libraries:"
otool -L "$artifact" | sed 's/^/  /'

mkdir -p "$work/empty-bin" "$work/home" "$work/tmp"
echo "runtime_phase:"
echo "  env=-i PATH=<empty-bin> HOME=<temp-home> TMPDIR=<temp-tmp>"
env -i PATH="$work/empty-bin" HOME="$work/home" TMPDIR="$work/tmp" "$artifact" "$weights" | tee "$work/runtime.out"
grep -q 'PASS form-native-metal-weight-bytes-runtime' "$work/runtime.out"
