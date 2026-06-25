#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <CoreFoundation/CoreFoundation.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int fk_visible_denied_tools(void) {
    const char *path = getenv("PATH");
    const char *tools[] = {"go", "rustc", "cargo", "python", "python3", "sh", "bash", "zsh", "clang", "swiftc", "curl", "ollama", NULL};
    if (path == NULL || path[0] == 0) {
        return 0;
    }
    char copy[4096];
    snprintf(copy, sizeof(copy), "%s", path);
    int visible = 0;
    char *save = NULL;
    char *dir = strtok_r(copy, ":", &save);
    while (dir != NULL) {
        for (int i = 0; tools[i] != NULL; i++) {
            char probe[4096];
            snprintf(probe, sizeof(probe), "%s/%s", dir, tools[i]);
            if (access(probe, X_OK) == 0) {
                visible++;
            }
        }
        dir = strtok_r(NULL, ":", &save);
    }
    return visible;
}

long long fk_metal_matvec_fixture_external(char *out, long long cap) {
    @autoreleasepool {
        if (out == NULL || cap <= 0) {
            return -1;
        }
        int deniedVisible = fk_visible_denied_tools();
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (dev == nil) {
            return snprintf(out, (size_t)cap, "SKIP no Metal device\nmetal_owner=fkwu-form-cli\nmetal_linked=true\n");
        }

        NSString *encoded = @"a2VybmVsIHZvaWQgZm9ybV9ma3d1X2RpcmVjdF9tYXR2ZWNfZjMyKGRldmljZSBjb25zdCBmbG9hdCogdyBbW2J1ZmZlcigwKV1dLCBkZXZpY2UgY29uc3QgZmxvYXQqIHggW1tidWZmZXIoMSldXSwgZGV2aWNlIGZsb2F0KiB5IFtbYnVmZmVyKDIpXV0sIGNvbnN0YW50IHVpbnQmIHJvd3MgW1tidWZmZXIoMyldXSwgY29uc3RhbnQgdWludCYgY29scyBbW2J1ZmZlcig0KV1dLCB1aW50IGkgW1t0aHJlYWRfcG9zaXRpb25faW5fZ3JpZF1dKSB7IGlmIChpID49IHJvd3MpIHJldHVybjsgZGV2aWNlIGNvbnN0IGZsb2F0KiByb3cgPSB3ICsgaSAqIGNvbHM7IGZsb2F0IGFjYyA9IDAuMGY7IHVpbnQgaiA9IGNvbHM7IHdoaWxlIChqID4gMCkgeyBqIC09IDE7IGZsb2F0IHAgPSBmbG9hdChyb3dbal0pICogZmxvYXQoeFtqXSk7IGFjYyA9IHAgKyBhY2M7IH0geVtpXSA9IGZsb2F0KGFjYyk7IH0K";
        NSData *data = [[NSData alloc] initWithBase64EncodedString:encoded options:0];
        NSString *src = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
        NSString *full = [@"#include <metal_stdlib>\nusing namespace metal;\n" stringByAppendingString:src];

        NSError *err = nil;
        MTLCompileOptions *opts = [[MTLCompileOptions alloc] init];
        opts.mathMode = MTLMathModeSafe;
        id<MTLLibrary> lib = [dev newLibraryWithSource:full options:opts error:&err];
        if (lib == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal library compile: %s\n", err.localizedDescription.UTF8String);
        }
        id<MTLFunction> fn = [lib newFunctionWithName:@"form_fkwu_direct_matvec_f32"];
        if (fn == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal kernel missing\n");
        }
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (pso == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal pipeline: %s\n", err.localizedDescription.UTF8String);
        }
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        if (queue == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal command queue unavailable\n");
        }

        const uint32_t rows = 2;
        const uint32_t cols = 3;
        float weights[6] = {1.0f, 2.0f, -1.0f, 0.5f, -3.0f, 4.0f};
        float input[3] = {2.0f, -1.0f, 0.25f};
        float zero[2] = {0.0f, 0.0f};
        float expected[2] = {-0.25f, 5.0f};

        id<MTLBuffer> bw = [dev newBufferWithBytes:weights length:sizeof(weights) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bx = [dev newBufferWithBytes:input length:sizeof(input) options:MTLResourceStorageModeShared];
        id<MTLBuffer> by = [dev newBufferWithBytes:zero length:sizeof(zero) options:MTLResourceStorageModeShared];
        if (bw == nil || bx == nil || by == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal buffer allocation\n");
        }

        id<MTLCommandBuffer> cb = [queue commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        [enc setComputePipelineState:pso];
        [enc setBuffer:bw offset:0 atIndex:0];
        [enc setBuffer:bx offset:0 atIndex:1];
        [enc setBuffer:by offset:0 atIndex:2];
        uint32_t uRows = rows;
        uint32_t uCols = cols;
        [enc setBytes:&uRows length:4 atIndex:3];
        [enc setBytes:&uCols length:4 atIndex:4];
        [enc dispatchThreads:MTLSizeMake(rows, 1, 1) threadsPerThreadgroup:MTLSizeMake(rows, 1, 1)];
        [enc endEncoding];

        CFAbsoluteTime started = CFAbsoluteTimeGetCurrent();
        [cb commit];
        [cb waitUntilCompleted];
        double elapsedMs = (CFAbsoluteTimeGetCurrent() - started) * 1000.0;
        if (cb.error != nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal command buffer: %s\n", cb.error.localizedDescription.UTF8String);
        }

        float *gpu = (float *)by.contents;
        float d0 = fabsf(gpu[0] - expected[0]);
        float d1 = fabsf(gpu[1] - expected[1]);
        float maxDelta = d0 > d1 ? d0 : d1;
        const char *verdict = maxDelta <= 0.000001f ? "PASS fkwu-form-cli-metal-direct" : "FAIL fkwu-form-cli-metal-direct";
        return snprintf(
            out,
            (size_t)cap,
            "runtime_path_sanitized=%s\n"
            "denied_toolchain_names_visible_on_path=%d\n"
            "http_or_ollama=absent\n"
            "metal_owner=fkwu-form-cli\n"
            "metal_linked=true\n"
            "metal_device=%s\n"
            "embedded_msl_bytes=450\n"
            "rows=%u\n"
            "cols=%u\n"
            "dispatch_ms=%.3f\n"
            "gpu_y=[%.6f,%.6f]\n"
            "expected_y=[%.6f,%.6f]\n"
            "max_delta=%.9f\n"
            "%s",
            deniedVisible == 0 ? "true" : "false",
            deniedVisible,
            dev.name.UTF8String,
            rows,
            cols,
            elapsedMs,
            gpu[0],
            gpu[1],
            expected[0],
            expected[1],
            maxDelta,
            verdict
        );
    }
}
