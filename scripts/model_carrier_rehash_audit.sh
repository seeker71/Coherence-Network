#!/usr/bin/env bash
# model_carrier_rehash_audit.sh — physical model carrier materialize/dematerialize re-hash witness.
#
# Floor: compile a local Swift binary that materializes a small tensor payload
# into CPU memory and a Metal buffer, dematerializes returned bytes to files, and
# gates CPU, Metal, and MLX carriers by sha256 equality against the source
# payload. MLX uses the native C API when libmlxc is present.
#
# North star: CPU, GPU, MLX, and Metal carriers are faithful only when returned
# bytes re-hash to the source chunk digest. Model truth remains the chunk cell
# and chunk-set root; accelerator buffers are projection carriers.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d "${TMPDIR:-/tmp}/mv-carrier-rehash.XXXXXX")"
trap 'rm -rf "$work"' EXIT

payload="${1:-0.25,-0.50;1.00,2.00}"
printf '%s' "$payload" > "$work/source.bin"

if [[ "$(uname -s)" != "Darwin" ]] || ! command -v swiftc >/dev/null; then
    echo "SKIP no Darwin Swift/Metal toolchain for physical carrier witness"
    exit 2
fi

cat > "$work/runner.swift" <<'SWIFT'
import Foundation
import Metal

let sourcePath = CommandLine.arguments[1]
let cpuPath = CommandLine.arguments[2]
let metalPath = CommandLine.arguments[3]

let source = try Data(contentsOf: URL(fileURLWithPath: sourcePath))
var cpuBytes = [UInt8](source)
try Data(cpuBytes).write(to: URL(fileURLWithPath: cpuPath))

guard let device = MTLCreateSystemDefaultDevice() else {
    print("SKIP no Metal device")
    exit(2)
}

let msl = """
#include <metal_stdlib>
using namespace metal;
kernel void copy_bytes(device const uchar *input [[buffer(0)]],
                       device uchar *output [[buffer(1)]],
                       constant uint &count [[buffer(2)]],
                       uint gid [[thread_position_in_grid]]) {
    if (gid < count) {
        output[gid] = input[gid];
    }
}
"""

let library = try device.makeLibrary(source: msl, options: nil)
guard let fn = library.makeFunction(name: "copy_bytes") else {
    print("FAIL Metal function missing")
    exit(1)
}
let pso = try device.makeComputePipelineState(function: fn)
let inBuffer = device.makeBuffer(bytes: cpuBytes, length: cpuBytes.count, options: [.storageModeShared])!
let outBuffer = device.makeBuffer(length: cpuBytes.count, options: [.storageModeShared])!
var count = UInt32(cpuBytes.count)
let queue = device.makeCommandQueue()!
let command = queue.makeCommandBuffer()!
let encoder = command.makeComputeCommandEncoder()!
encoder.setComputePipelineState(pso)
encoder.setBuffer(inBuffer, offset: 0, index: 0)
encoder.setBuffer(outBuffer, offset: 0, index: 1)
encoder.setBytes(&count, length: MemoryLayout<UInt32>.size, index: 2)
encoder.dispatchThreads(
    MTLSize(width: cpuBytes.count, height: 1, depth: 1),
    threadsPerThreadgroup: MTLSize(width: min(max(1, cpuBytes.count), pso.maxTotalThreadsPerThreadgroup), height: 1, depth: 1))
encoder.endEncoding()
command.commit()
command.waitUntilCompleted()

let returned = Data(bytes: outBuffer.contents(), count: cpuBytes.count)
try returned.write(to: URL(fileURLWithPath: metalPath))
print("device=\(device.name)")
print("bytes=\(cpuBytes.count)")
SWIFT

swiftc -O -o "$work/runner" "$work/runner.swift"
cat > "$work/mlx_runner.c" <<'C'
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <mlx/c/array.h>
#include <mlx/c/device.h>
#include <mlx/c/ops.h>
#include <mlx/c/stream.h>

int main(int argc, char** argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: mlx_runner <source> <out>\n");
        return 64;
    }
    FILE* in = fopen(argv[1], "rb");
    if (!in) {
        perror("fopen source");
        return 1;
    }
    fseek(in, 0, SEEK_END);
    long n = ftell(in);
    fseek(in, 0, SEEK_SET);
    if (n <= 0) {
        fprintf(stderr, "empty source\n");
        fclose(in);
        return 1;
    }
    uint8_t* data = (uint8_t*)malloc((size_t)n);
    if (!data) {
        fclose(in);
        return 1;
    }
    if (fread(data, 1, (size_t)n, in) != (size_t)n) {
        perror("fread");
        free(data);
        fclose(in);
        return 1;
    }
    fclose(in);

    mlx_device gpu = mlx_device_new_type(MLX_GPU, 0);
    bool available = false;
    if (mlx_device_is_available(&available, gpu) != 0 || !available) {
        fprintf(stderr, "mlx gpu unavailable\n");
        free(data);
        mlx_device_free(gpu);
        return 2;
    }
    mlx_stream stream = mlx_stream_new_device(gpu);
    int shape[1] = {(int)n};
    mlx_array arr = mlx_array_new_data(data, shape, 1, MLX_UINT8);
    mlx_array copied = mlx_array_new();
    if (mlx_copy(&copied, arr, stream) != 0) {
        fprintf(stderr, "mlx_copy failed\n");
        return 3;
    }
    if (mlx_array_eval(copied) != 0 || mlx_synchronize(stream) != 0) {
        fprintf(stderr, "mlx eval/sync failed\n");
        return 4;
    }
    const uint8_t* returned = mlx_array_data_uint8(copied);
    if (!returned) {
        fprintf(stderr, "mlx returned null data\n");
        return 5;
    }
    FILE* out = fopen(argv[2], "wb");
    if (!out) {
        perror("fopen out");
        return 1;
    }
    fwrite(returned, 1, (size_t)n, out);
    fclose(out);
    printf("mlx_bytes=%ld\n", n);
    printf("mlx_device=gpu:0\n");
    mlx_array_free(arr);
    mlx_array_free(copied);
    mlx_stream_free(stream);
    mlx_device_free(gpu);
    free(data);
    return 0;
}
C

"$work/runner" "$work/source.bin" "$work/cpu.bin" "$work/metal.bin" > "$work/runner.out"

mlx_state="not-run"
if [[ -f /opt/homebrew/include/mlx/c/array.h && -f /opt/homebrew/lib/libmlxc.dylib ]]; then
    clang -I/opt/homebrew/include -L/opt/homebrew/lib -lmlxc -Wl,-rpath,/opt/homebrew/lib \
        -o "$work/mlx_runner" "$work/mlx_runner.c"
    "$work/mlx_runner" "$work/source.bin" "$work/mlx.bin" > "$work/mlx.out"
    mlx_state="ran"
else
    mlx_state="blocked-no-native-mlx-library-or-header"
fi

sha_file() {
    shasum -a 256 "$1" | awk '{print $1}'
}

source_sha="$(sha_file "$work/source.bin")"
cpu_sha="$(sha_file "$work/cpu.bin")"
metal_sha="$(sha_file "$work/metal.bin")"
mlx_sha=""
if [[ "$mlx_state" == "ran" ]]; then
    mlx_sha="$(sha_file "$work/mlx.bin")"
fi
bytes="$(wc -c < "$work/source.bin" | tr -d ' ')"
device="$(sed -n 's/^device=//p' "$work/runner.out" | head -n 1)"

if [[ "$source_sha" != "$cpu_sha" ]]; then
    echo "FAIL cpu:buffer source_sha=$source_sha returned_sha=$cpu_sha bytes=$bytes"
    exit 1
fi
if [[ "$source_sha" != "$metal_sha" ]]; then
    echo "FAIL metal:buffer source_sha=$source_sha returned_sha=$metal_sha bytes=$bytes device=$device"
    exit 1
fi
if [[ "$mlx_state" == "ran" && "$source_sha" != "$mlx_sha" ]]; then
    echo "FAIL mlx:array source_sha=$source_sha returned_sha=$mlx_sha bytes=$bytes"
    exit 1
fi

echo "PASS cpu:buffer physical-rehash-ok bytes=$bytes sha256=$cpu_sha"
echo "PASS gpu:buffer physical-rehash-ok bytes=$bytes sha256=$metal_sha device=$device carrier=metal"
echo "PASS metal:buffer physical-rehash-ok bytes=$bytes sha256=$metal_sha device=$device"
if [[ "$mlx_state" == "ran" ]]; then
    echo "PASS mlx:array physical-rehash-ok bytes=$bytes sha256=$mlx_sha device=gpu:0 lib=/opt/homebrew/lib/libmlxc.dylib"
else
    echo "GAP mlx:array native-carrier=$mlx_state next=install-libmlxc-and-run-materialize-dematerialize"
fi
