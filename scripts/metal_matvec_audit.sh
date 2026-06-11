#!/usr/bin/env bash
# metal_matvec_audit.sh — GPU witness for the Form MSL matvec emitter (jte-matvec-msl in
# form/form-stdlib/jit-tensor-emit.fk): the kernel's mouth prints the Form-emitted MSL, the
# host Metal runtime compiles it (mathMode safe — IEEE, no fast-math), one thread per output
# row dispatches over deterministic input cells, and VALUE PARITY against a CPU fp32
# right-fold in the recipe's exact op order (j counts DOWN, mul-then-add as two roundings)
# gates the timing rows — a row only counts when every output row is bit-exact.
#
# Carriers: form-kernel-go (the mouth; the band proves the text byte-identical three-way),
# swiftc + Metal.framework (the driver-organ idiom — allowed host carriers per
# host-kernel.form host-resource-access); the emitter intelligence lives in the body.
# fp32 is the lane MSL declares (no f64 in device code); both sides are held to it.
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

# ── 1. Form emits the MSL; the kernel is only the mouth ──────────────────
cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$work/driver.fk"
cat >> "$work/driver.fk" <<'EOF'
(print "==MSL==")
(print (jte-matvec-msl "form_matvec_f32"))
(print "==END==")
EOF
(cd "$FORMDIR" && "$GO_BIN" "$work/driver.fk" 2>/dev/null) > "$work/emit.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' > "$work/matvec.metal"
if ! grep -q 'kernel void form_matvec_f32' "$work/matvec.metal"; then
    echo "FAIL  emission did not produce the MSL kernel — see $work/emit.out"; exit 1
fi
echo "emitted MSL: $(wc -c < "$work/matvec.metal" | tr -d ' ') bytes, every byte authored by the Form recipe"

# ── 2. The witness runner — dumb carrier: buffers, dispatch, compare, time ──
cat > "$work/runner.swift" <<'EOF'
// metal matvec witness — runtime-compile Form-emitted MSL, parity-gate, time. Carrier only.
import Metal
import Foundation

let args = CommandLine.arguments
let mslPath = args[1], fname = args[2]
let rows = Int(args[3])!, cols = Int(args[4])!, iters = Int(args[5])!

let src = try String(contentsOfFile: mslPath, encoding: .utf8)
guard let dev = MTLCreateSystemDefaultDevice() else { print("SKIP no Metal device"); exit(2) }
let opts = MTLCompileOptions()
opts.mathMode = .safe   // IEEE-conformant: no fast-math reassociation/contraction
let lib = try dev.makeLibrary(source: src, options: opts)
guard let fn = lib.makeFunction(name: fname) else { print("FAIL function \(fname) absent"); exit(1) }
let pso = try dev.makeComputePipelineState(function: fn)

// deterministic input cells — integer-derived over 256 (exactly representable)
var w = [Float](repeating: 0, count: rows * cols)
var x = [Float](repeating: 0, count: cols)
for i in 0..<rows { for j in 0..<cols {
    w[i*cols + j] = Float((i*31 + j*17) % 1000 - 500) / 256.0
}}
for j in 0..<cols { x[j] = Float((j*13) % 1000 - 500) / 256.0 }

// CPU reference — the recipe's exact right-fold (j DOWN), fp32, mul then add (two roundings)
var yref = [Float](repeating: 0, count: rows)
let t0 = DispatchTime.now()
for i in 0..<rows {
    var acc: Float = 0.0
    var j = cols
    while j > 0 { j -= 1; let p = w[i*cols + j] * x[j]; acc = p + acc }
    yref[i] = acc
}
let cpuMs = Double(DispatchTime.now().uptimeNanoseconds - t0.uptimeNanoseconds) / 1e6

let q = dev.makeCommandQueue()!
let bw = dev.makeBuffer(bytes: w, length: w.count*4)!
let bx = dev.makeBuffer(bytes: x, length: x.count*4)!
let by = dev.makeBuffer(length: rows*4)!
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
let ygpu = by.contents().bindMemory(to: Float.self, capacity: rows)
var exact = 0; var maxAbs: Float = 0
for i in 0..<rows {
    if ygpu[i].bitPattern == yref[i].bitPattern { exact += 1 }
    maxAbs = max(maxAbs, abs(ygpu[i] - yref[i]))
}
var walls: [Double] = []; var gpus: [Double] = []
for _ in 0..<iters { let r = dispatchOnce(); walls.append(r.wall); gpus.append(r.gpu) }
walls.sort(); gpus.sort()
print("parity_bitexact_rows=\(exact)/\(rows) max_abs_diff=\(maxAbs)")
print("gpu_wall_ms_median=\(String(format: "%.3f", walls[walls.count/2])) gpu_kernel_ms_median=\(String(format: "%.3f", gpus[gpus.count/2])) iters=\(iters)")
print("cpu_fp32_rightfold_ms=\(String(format: "%.3f", cpuMs))")
print("device=\(dev.name)")
if exact != rows { exit(1) }
EOF

swiftc -O -o "$work/runner" "$work/runner.swift" 2>"$work/swiftc.err" || {
    echo "FAIL  swiftc could not build the witness runner:"; cat "$work/swiftc.err"; exit 1; }

# ── 3. Parity gates the rows ─────────────────────────────────────────────
echo "witness (${ROWS}x${COLS} fp32 matvec, ${ITERS} timed dispatches after one warm):"
if ! "$work/runner" "$work/matvec.metal" form_matvec_f32 "$ROWS" "$COLS" "$ITERS" | sed 's/^/  /'; then
    echo "FAIL  value parity broken — timing rows do not count"; exit 1
fi
echo
echo "conditions: $(uname -m) $(uname -s) $(sw_vers -productVersion 2>/dev/null), Metal runtime compile" \
     "(makeLibrary, mathMode=safe), gpu_wall includes commit+wait, gpu_kernel is the GPU execution" \
     "window (gpuStartTime..gpuEndTime), cpu row is one thread in the recipe's own fold order"
echo "ok — parity held and the rows are real; the emitter recipe is form-stdlib/jit-tensor-emit.fk (jte-matvec-msl)"
