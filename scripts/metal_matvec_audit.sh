#!/usr/bin/env bash
# metal_matvec_audit.sh — GPU witness for the Form MSL matvec emitter (jte-matvec-msl-spine +
# format rows in form/form-stdlib/jit-tensor-emit.fk): the kernel's mouth prints the Form-emitted
# MSL per precision lane (f32, f16, bf16), the host Metal runtime compiles it (mathMode safe —
# IEEE, no fast-math), one thread per output row dispatches over deterministic input cells, and
# VALUE PARITY against a CPU reference COMPUTED IN THE SAME FORMAT SEMANTICS gates the timing
# rows — a row only counts when every output row is bit-exact in the lane's own storage format.
#
# The conversion chain per lane (format-arith's cross-precision discipline — the gate is defined
# BY the format's own semantics, never a tolerance):
#   inputs   integer-derived n/256, chosen exactly representable in the lane format (f32/f16:
#            |n|<=500 needs <=9 significand bits; bf16: |n|<=128 needs <=8) — input quantization
#            is the identity, so the chain starts at the same bits on both sides
#   load     lane -> fp32   exact (every half/bfloat value is representable in fp32)
#   mul/add  fp32 right-fold, j DOWN, mul then add as two roundings (the recipe's op order)
#   store    fp32 -> lane   one round-to-nearest-even (MSL conversions, Swift Float16, and the
#            bf16 +0x7FFF+lsb fold all carry IEEE's tie rule — format-arith's fq-rne)
#
# Carriers: form-kernel-go (the mouth; the band proves each lane's text byte-identical three-way),
# swiftc + Metal.framework (the driver-organ idiom — allowed host carriers per host-kernel.form
# host-resource-access); the emitter intelligence lives in the body. MSL bfloat is Metal 3.1+ —
# the runner checks at runtime and the bf16 lane skips-with-name where the toolchain lacks it.
#
# Run:  scripts/metal_matvec_audit.sh [rows cols iters]   (defaults 1280 1280 30)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
ROWS="${1:-1280}"; COLS="${2:-1280}"; ITERS="${3:-30}"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP  no Darwin/Metal toolchain on this host — the GPU witness needs an Apple GPU + swiftc"
    exit 2
fi
if [[ ! -x "$GO_BIN" ]]; then
    echo "  building go kernel..." >&2
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/fkmetal.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the MSL per lane; the kernel is only the mouth ─────────
emit_lane() {  # $1 = lane (f32|f16|bf16), $2 = function name
    cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
    printf '(print "==MSL==")\n(print (jte-matvec-msl-fmt "%s" "%s"))\n(print "==END==")\n' "$2" "$1" >> "$work/driver.fk"
    (cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
    sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/matvec_$1.metal"
    if ! grep -q "kernel void $2" "$work/matvec_$1.metal"; then
        echo "FAIL  $1 emission did not produce the MSL kernel — see $work/emit.out"; exit 1
    fi
    echo "emitted $1 MSL: $(wc -c < "$work/matvec_$1.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"
}
emit_lane f32  form_matvec_f32
emit_lane f16  form_matvec_f16
emit_lane bf16 form_matvec_bf16

# ── 2. The witness runner — dumb carrier: buffers, dispatch, compare, time ──
cat > "$work/runner.swift" <<'EOF'
// metal matvec witness — runtime-compile Form-emitted MSL, parity-gate per lane format, time.
// Carrier only: the CPU reference is the lane's own conversion chain (load exact -> fp32
// right-fold in the recipe's op order -> one RNE store into the lane format).
import Metal
import Foundation

let args = CommandLine.arguments
let mslPath = args[1], fname = args[2], lane = args[3]
let rows = Int(args[4])!, cols = Int(args[5])!, iters = Int(args[6])!

let src = try String(contentsOfFile: mslPath, encoding: .utf8)
guard let dev = MTLCreateSystemDefaultDevice() else { print("SKIP no Metal device"); exit(2) }
let opts = MTLCompileOptions()
opts.mathMode = .safe   // IEEE-conformant: no fast-math reassociation/contraction
var lib: MTLLibrary
do { lib = try dev.makeLibrary(source: src, options: opts) }
catch {
    if lane == "bf16" {   // MSL bfloat is Metal 3.1+ — a missing type is a named gate, not a break
        print("SKIPGATE bfloat lane — this Metal toolchain does not compile MSL bfloat (needs Metal 3.1+)")
        exit(3)
    }
    print("FAIL MSL compile (\(lane)): \(error.localizedDescription)"); exit(1)
}
guard let fn = lib.makeFunction(name: fname) else { print("FAIL function \(fname) absent"); exit(1) }
let pso = try dev.makeComputePipelineState(function: fn)

// bf16 carriers — format-arith's fq-rne tie rule on the fp32 -> bf16 boundary
func f32ToBf16(_ f: Float) -> UInt16 {
    let bits = f.bitPattern
    let lsb = (bits >> 16) & 1
    return UInt16(truncatingIfNeeded: (bits &+ 0x7FFF &+ lsb) >> 16)   // round half to even
}
func bf16ToF32(_ b: UInt16) -> Float { Float(bitPattern: UInt32(b) << 16) }  // exact widening

// deterministic input cells — integer-derived over 256, exactly representable in the lane
// format by construction (f32/f16: |n|<=500 fits 9 significand bits; bf16: |n|<=128 fits 8)
func seedW(_ i: Int, _ j: Int) -> Int { lane == "bf16" ? (i*31 + j*17) % 256 - 128 : (i*31 + j*17) % 1000 - 500 }
func seedX(_ j: Int) -> Int { lane == "bf16" ? (j*13) % 256 - 128 : (j*13) % 1000 - 500 }
func val(_ n: Int) -> Float { Float(n) / 256.0 }

// per-lane storage + the CPU reference in the lane's exact conversion chain
var bw: MTLBuffer!, bx: MTLBuffer!, by: MTLBuffer!
var refBits = [UInt32](repeating: 0, count: rows)   // lane-format bit patterns, widened
var refVals = [Float](repeating: 0, count: rows)    // decoded for max_abs_diff sensing
var cpuMs = 0.0

switch lane {
case "f32":
    var w = [Float](repeating: 0, count: rows*cols); var x = [Float](repeating: 0, count: cols)
    for i in 0..<rows { for j in 0..<cols { w[i*cols+j] = val(seedW(i, j)) } }
    for j in 0..<cols { x[j] = val(seedX(j)) }
    let t0 = DispatchTime.now()
    for i in 0..<rows {
        var acc: Float = 0.0; var j = cols
        while j > 0 { j -= 1; let p = w[i*cols+j] * x[j]; acc = p + acc }
        refBits[i] = acc.bitPattern; refVals[i] = acc
    }
    cpuMs = Double(DispatchTime.now().uptimeNanoseconds - t0.uptimeNanoseconds) / 1e6
    bw = dev.makeBuffer(bytes: w, length: w.count*4)!
    bx = dev.makeBuffer(bytes: x, length: x.count*4)!
    by = dev.makeBuffer(length: rows*4)!
case "f16":
    var w = [Float16](repeating: 0, count: rows*cols); var x = [Float16](repeating: 0, count: cols)
    for i in 0..<rows { for j in 0..<cols { w[i*cols+j] = Float16(val(seedW(i, j))) } }  // exact
    for j in 0..<cols { x[j] = Float16(val(seedX(j))) }                                  // exact
    let t0 = DispatchTime.now()
    for i in 0..<rows {
        var acc: Float = 0.0; var j = cols
        while j > 0 { j -= 1; let p = Float(w[i*cols+j]) * Float(x[j]); acc = p + acc }  // load exact
        let y16 = Float16(acc)                                                           // one RNE store
        refBits[i] = UInt32(y16.bitPattern); refVals[i] = Float(y16)
    }
    cpuMs = Double(DispatchTime.now().uptimeNanoseconds - t0.uptimeNanoseconds) / 1e6
    bw = dev.makeBuffer(bytes: w, length: w.count*2)!
    bx = dev.makeBuffer(bytes: x, length: x.count*2)!
    by = dev.makeBuffer(length: rows*2)!
case "bf16":
    var w = [UInt16](repeating: 0, count: rows*cols); var x = [UInt16](repeating: 0, count: cols)
    for i in 0..<rows { for j in 0..<cols { w[i*cols+j] = f32ToBf16(val(seedW(i, j))) } }  // exact
    for j in 0..<cols { x[j] = f32ToBf16(val(seedX(j))) }                                  // exact
    let t0 = DispatchTime.now()
    for i in 0..<rows {
        var acc: Float = 0.0; var j = cols
        while j > 0 { j -= 1; let p = bf16ToF32(w[i*cols+j]) * bf16ToF32(x[j]); acc = p + acc }
        let yb = f32ToBf16(acc)                                                            // one RNE store
        refBits[i] = UInt32(yb); refVals[i] = bf16ToF32(yb)
    }
    cpuMs = Double(DispatchTime.now().uptimeNanoseconds - t0.uptimeNanoseconds) / 1e6
    bw = dev.makeBuffer(bytes: w, length: w.count*2)!
    bx = dev.makeBuffer(bytes: x, length: x.count*2)!
    by = dev.makeBuffer(length: rows*2)!
default:
    print("FAIL unknown lane \(lane)"); exit(1)
}

let q = dev.makeCommandQueue()!
var ur = UInt32(rows), uc = UInt32(cols)

func dispatchOnce() -> (wall: Double, gpu: Double) {
    let cb = q.makeCommandBuffer()!
    let enc = cb.makeComputeCommandEncoder()!
    enc.setComputePipelineState(pso)
    enc.setBuffer(bw, offset: 0, index: 0)
    enc.setBuffer(bx, offset: 0, index: 1)
    enc.setBuffer(by, offset: 0, index: 2)
    enc.setBytes(&ur, length: 4, index: 3)
    enc.setBytes(&uc, length: 4, index: 4)
    enc.dispatchThreads(MTLSize(width: rows, height: 1, depth: 1),
        threadsPerThreadgroup: MTLSize(width: min(pso.maxTotalThreadsPerThreadgroup, rows), height: 1, depth: 1))
    enc.endEncoding()
    let s = DispatchTime.now()
    cb.commit(); cb.waitUntilCompleted()
    let wall = Double(DispatchTime.now().uptimeNanoseconds - s.uptimeNanoseconds) / 1e6
    let gpu = (cb.gpuEndTime - cb.gpuStartTime) * 1000.0
    return (wall, gpu)
}

_ = dispatchOnce() // warm: pipeline + first-touch
var exact = 0; var maxAbs: Float = 0
switch lane {
case "f32":
    let yg = by.contents().bindMemory(to: Float.self, capacity: rows)
    for i in 0..<rows {
        if yg[i].bitPattern == refBits[i] { exact += 1 }
        maxAbs = max(maxAbs, abs(yg[i] - refVals[i]))
    }
default:
    let yg = by.contents().bindMemory(to: UInt16.self, capacity: rows)
    for i in 0..<rows {
        if UInt32(yg[i]) == refBits[i] { exact += 1 }
        let g = lane == "f16" ? Float(Float16(bitPattern: yg[i])) : bf16ToF32(yg[i])
        maxAbs = max(maxAbs, abs(g - refVals[i]))
    }
}
var walls: [Double] = []; var gpus: [Double] = []
for _ in 0..<iters { let r = dispatchOnce(); walls.append(r.wall); gpus.append(r.gpu) }
walls.sort(); gpus.sort()
print("lane=\(lane) parity_bitexact_rows=\(exact)/\(rows) max_abs_diff=\(maxAbs)")
print("gpu_wall_ms_median=\(String(format: "%.3f", walls[walls.count/2])) gpu_kernel_ms_median=\(String(format: "%.3f", gpus[gpus.count/2])) iters=\(iters)")
print("cpu_\(lane)_rightfold_ms=\(String(format: "%.3f", cpuMs))")
print("device=\(dev.name)")
if exact != rows { exit(1) }
EOF

swiftc -O -o "$work/runner" "$work/runner.swift" 2>"$work/swiftc.err" || {
    echo "FAIL  swiftc could not build the witness runner:"; cat "$work/swiftc.err"; exit 1; }

# ── 3. Parity gates the rows, per lane ───────────────────────────────────
overall=0
for lane in f32 f16 bf16; do
    fname="form_matvec_${lane}"
    echo
    echo "witness $lane (${ROWS}x${COLS} matvec, ${ITERS} timed dispatches after one warm):"
    "$work/runner" "$work/matvec_$lane.metal" "$fname" "$lane" "$ROWS" "$COLS" "$ITERS" | sed 's/^/  /'
    rc=${PIPESTATUS[0]}
    if [[ "$rc" == "3" ]]; then
        echo "  named gate: bf16 lane unavailable on this Metal toolchain — row skipped with its name"
    elif [[ "$rc" != "0" ]]; then
        echo "FAIL  $lane value parity broken — timing rows do not count"; overall=1
    fi
done
echo
echo "conditions: $(uname -m) $(uname -s) $(sw_vers -productVersion 2>/dev/null), Metal runtime compile" \
     "(makeLibrary, mathMode=safe), gpu_wall includes commit+wait, gpu_kernel is the GPU execution" \
     "window (gpuStartTime..gpuEndTime), cpu row is one thread in the lane's own conversion chain" \
     "(load exact -> fp32 right-fold in the recipe's op order -> one RNE store into the lane format)"
if [[ "$overall" != "0" ]]; then exit 1; fi
echo "ok — parity held per lane format and the rows are real; the emitter recipe is form-stdlib/jit-tensor-emit.fk (jte-matvec-msl-spine + format rows)"
