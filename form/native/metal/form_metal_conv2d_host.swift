// form_metal_conv2d_host.swift — proves conv2d.metal BIT-EXACT vs cv2d-conv (form-stdlib/conv2d.fk)
// on the real Apple GPU. The CPU oracle is the SAME nested right-fold as form_cuda_ptx_conv2d_host.c:
// ky down (cv2d-window-dot), kx down (cv-window-dot), ic down (tb-dot), nested accumulators td/wd/acc,
// + bias; an out-of-bounds patch pixel contributes 0 (zero-pad). Same deterministic seeds as the CUDA
// host so the two GPU lanes (PTX, Metal) are proven against the identical numbers.
//
// No third-party deps — Metal.framework only (the driver-organ idiom, host-kernel.form host-resource-access).
// The MSL is loaded from conv2d.metal as source and compiled mathMode=.safe (IEEE, no fast-math) so the
// recipe's two-rounding mul/add fold is never contracted into an FMA — uint32-identical to the C oracle.
//
// Build: swiftc -O -o form_metal_conv2d_host form_metal_conv2d_host.swift
// Run:   ./form_metal_conv2d_host conv2d.metal [IC OC H W kh kw pad stride]   (defaults 2 3 5 5 3 3 1 1)
import Metal
import Foundation

struct ConvDims { var ic, h, wd, oc, kh, kw, pad, stride: UInt32 }

let args = CommandLine.arguments
let mslPath = args.count > 1 ? args[1] : "conv2d.metal"
func argi(_ i: Int, _ dflt: Int) -> Int { args.count > i ? (Int(args[i]) ?? dflt) : dflt }
let IC = argi(2, 2), OC = argi(3, 3), Hh = argi(4, 5), Wd = argi(5, 5)
let kh = argi(6, 3), kw = argi(7, 3), pad = argi(8, 1), stride = argi(9, 1)

let outH = (Hh + 2*pad - kh)/stride + 1, outW = (Wd + 2*pad - kw)/stride + 1
if outH <= 0 || outW <= 0 { print("FAIL bad dims"); exit(1) }

// deterministic seeds — identical to form_cuda_ptx_conv2d_host.c (val(n) = n/256, all exactly f32)
func val(_ n: Int) -> Float { Float(n) / 256.0 }
let nW = OC*kh*kw*IC, nIn = Hh*Wd*IC, nOut = outH*outW*OC
var W = [Float](repeating: 0, count: nW)
var b = [Float](repeating: 0, count: OC)
var inp = [Float](repeating: 0, count: nIn)
for i in 0..<nW  { W[i]   = val((i*37 + 11) % 256 - 128) }
for i in 0..<OC  { b[i]   = val((i*53 + 7)  % 256 - 128) }
for i in 0..<nIn { inp[i] = val((i*29 + 5)  % 256 - 128) }

// CPU oracle = cv2d-conv exact nested fold (mirrors the C oracle line-for-line)
var ref = [Float](repeating: 0, count: nOut)
for oc in 0..<OC { for oy in 0..<outH { for ox in 0..<outW {
    var acc: Float = 0.0
    var ky = kh
    while ky > 0 { ky -= 1; let iy = oy*stride + ky - pad
        var wd: Float = 0.0
        var kx = kw
        while kx > 0 { kx -= 1; let ix = ox*stride + kx - pad
            var td: Float = 0.0
            if iy >= 0 && iy < Hh && ix >= 0 && ix < Wd {
                var ic = IC
                while ic > 0 { ic -= 1
                    let p = W[(((oc*kh+ky)*kw+kx)*IC)+ic] * inp[(((iy*Wd+ix)*IC))+ic]
                    td = p + td
                }
            }
            wd = td + wd
        }
        acc = wd + acc
    }
    ref[(((oy*outW+ox)*OC))+oc] = acc + b[oc]
}}}

// ── Metal carrier: compile the MSL source, dispatch one thread per output element ──
guard let dev = MTLCreateSystemDefaultDevice() else { print("SKIP no Metal device"); exit(2) }
let src: String
do { src = try String(contentsOfFile: mslPath, encoding: .utf8) }
catch { print("FAIL open \(mslPath): \(error.localizedDescription)"); exit(1) }
let opts = MTLCompileOptions()
opts.mathMode = .safe   // IEEE-conformant: no fast-math reassociation/contraction (no FMA fusion)
let lib: MTLLibrary
do { lib = try dev.makeLibrary(source: src, options: opts) }
catch { print("FAIL MSL compile: \(error.localizedDescription)"); exit(1) }
guard let fn = lib.makeFunction(name: "form_conv2d_f32") else { print("FAIL function form_conv2d_f32 absent"); exit(1) }
let pso = try dev.makeComputePipelineState(function: fn)

let bW   = dev.makeBuffer(bytes: W,   length: nW*4)!
let bB   = dev.makeBuffer(bytes: b,   length: OC*4)!
let bIn  = dev.makeBuffer(bytes: inp, length: nIn*4)!
let bOut = dev.makeBuffer(length: nOut*4)!
var dims = ConvDims(ic: UInt32(IC), h: UInt32(Hh), wd: UInt32(Wd), oc: UInt32(OC),
                    kh: UInt32(kh), kw: UInt32(kw), pad: UInt32(pad), stride: UInt32(stride))

let q = dev.makeCommandQueue()!
let cb = q.makeCommandBuffer()!
let enc = cb.makeComputeCommandEncoder()!
enc.setComputePipelineState(pso)
enc.setBuffer(bW,  offset: 0, index: 0)
enc.setBuffer(bB,  offset: 0, index: 1)
enc.setBuffer(bIn, offset: 0, index: 2)
enc.setBuffer(bOut, offset: 0, index: 3)
enc.setBytes(&dims, length: MemoryLayout<ConvDims>.stride, index: 4)
let total = nOut
enc.dispatchThreads(MTLSize(width: total, height: 1, depth: 1),
    threadsPerThreadgroup: MTLSize(width: min(pso.maxTotalThreadsPerThreadgroup, total), height: 1, depth: 1))
enc.endEncoding()
cb.commit(); cb.waitUntilCompleted()
if let e = cb.error { print("FAIL GPU dispatch: \(e.localizedDescription)"); exit(1) }

// ── bit-exact gate: uint32-identical to the CPU oracle, no tolerance ──
let yg = bOut.contents().bindMemory(to: Float.self, capacity: nOut)
var exact = 0
var maxAbs: Float = 0
for i in 0..<nOut {
    if yg[i].bitPattern == ref[i].bitPattern { exact += 1 }
    maxAbs = max(maxAbs, abs(yg[i] - ref[i]))
}
print("device=\(dev.name)")
print("kernel=form_conv2d_f32  IC=\(IC) OC=\(OC) in=\(Hh)x\(Wd) k=\(kh)x\(kw) pad=\(pad) stride=\(stride) -> out=\(outH)x\(outW)x\(OC)")
print("parity_bitexact=\(exact)/\(nOut) max_abs_diff=\(maxAbs)")
if exact != nOut { print("FAIL not bit-exact"); exit(1) }
print("ok — conv2d ran on the Apple GPU, bit-exact (uint32) to cv2d-conv (diffusion stem on Metal)")
