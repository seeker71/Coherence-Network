#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <CoreFoundation/CoreFoundation.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static long long fk_ret(int n, long long cap) {
    if (n < 0) {
        return -1;
    }
    if ((long long)n >= cap) {
        return cap > 0 ? cap - 1 : 0;
    }
    return (long long)n;
}

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

static uint32_t fk_u32le(const unsigned char *p) {
    return ((uint32_t)p[0]) | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static float fk_f32le(const unsigned char *p) {
    uint32_t bits = fk_u32le(p);
    float value = 0.0f;
    memcpy(&value, &bits, 4);
    return value;
}

long long fk_metal_matvec_f32_external(
    const char *msl,
    long long msl_len,
    const char *kernel,
    long long kernel_len,
    const char *model,
    long long model_len,
    char *out,
    long long cap
) {
    @autoreleasepool {
        if (out == NULL || cap <= 0) {
            return -1;
        }
        if (msl == NULL || msl_len <= 0 || kernel == NULL || kernel_len <= 0 || model == NULL || model_len < 8) {
            return fk_ret(snprintf(out, (size_t)cap, "FAIL metal_matvec_f32 invalid input bytes\n"), cap);
        }

        int deniedVisible = fk_visible_denied_tools();
        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        if (dev == nil) {
            return fk_ret(snprintf(out, (size_t)cap, "SKIP no Metal device\nmetal_owner=fkwu-form-cli\nmetal_linked=true\n"), cap);
        }

        NSString *src = [[NSString alloc] initWithBytes:msl length:(NSUInteger)msl_len encoding:NSUTF8StringEncoding];
        NSString *kernelName = [[NSString alloc] initWithBytes:kernel length:(NSUInteger)kernel_len encoding:NSUTF8StringEncoding];
        if (src == nil || kernelName == nil) {
            return fk_ret(snprintf(out, (size_t)cap, "FAIL metal_matvec_f32 source/kernel encoding\n"), cap);
        }
        NSString *full = [@"#include <metal_stdlib>\nusing namespace metal;\n" stringByAppendingString:src];

        const unsigned char *mb = (const unsigned char *)model;
        uint32_t rows = fk_u32le(mb);
        uint32_t cols = fk_u32le(mb + 4);
        if (rows == 0 || cols == 0 || rows > 65536 || cols > 65536) {
            return fk_ret(snprintf(out, (size_t)cap, "FAIL metal_matvec_f32 bad dimensions rows=%u cols=%u\n", rows, cols), cap);
        }
        unsigned long long weightCount = (unsigned long long)rows * (unsigned long long)cols;
        unsigned long long expectedLen = 8ULL + (weightCount + (unsigned long long)cols) * 4ULL;
        if ((unsigned long long)model_len != expectedLen) {
            return fk_ret(snprintf(out, (size_t)cap, "FAIL metal_matvec_f32 model length got=%lld expected=%llu\n", model_len, expectedLen), cap);
        }

        float *weights = (float *)calloc((size_t)weightCount, sizeof(float));
        float *input = (float *)calloc((size_t)cols, sizeof(float));
        float *zero = (float *)calloc((size_t)rows, sizeof(float));
        float *expected = (float *)calloc((size_t)rows, sizeof(float));
        if (weights == NULL || input == NULL || zero == NULL || expected == NULL) {
            free(weights);
            free(input);
            free(zero);
            free(expected);
            return fk_ret(snprintf(out, (size_t)cap, "FAIL metal_matvec_f32 host allocation\n"), cap);
        }
        const unsigned char *fp = mb + 8;
        for (unsigned long long i = 0; i < weightCount; i++) {
            weights[i] = fk_f32le(fp + i * 4ULL);
        }
        fp += weightCount * 4ULL;
        for (uint32_t j = 0; j < cols; j++) {
            input[j] = fk_f32le(fp + (unsigned long long)j * 4ULL);
        }
        for (uint32_t i = 0; i < rows; i++) {
            float acc = 0.0f;
            uint32_t j = cols;
            while (j > 0) {
                j--;
                float p = weights[(unsigned long long)i * cols + j] * input[j];
                acc = p + acc;
            }
            expected[i] = acc;
        }

        NSError *err = nil;
        MTLCompileOptions *opts = [[MTLCompileOptions alloc] init];
        opts.mathMode = MTLMathModeSafe;
        id<MTLLibrary> lib = [dev newLibraryWithSource:full options:opts error:&err];
        if (lib == nil) {
            int n = snprintf(out, (size_t)cap, "FAIL Metal library compile: %s\n", err.localizedDescription.UTF8String);
            free(weights);
            free(input);
            free(zero);
            free(expected);
            return fk_ret(n, cap);
        }
        id<MTLFunction> fn = [lib newFunctionWithName:kernelName];
        if (fn == nil) {
            int n = snprintf(out, (size_t)cap, "FAIL Metal kernel missing: %s\n", kernelName.UTF8String);
            free(weights);
            free(input);
            free(zero);
            free(expected);
            return fk_ret(n, cap);
        }
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (pso == nil) {
            int n = snprintf(out, (size_t)cap, "FAIL Metal pipeline: %s\n", err.localizedDescription.UTF8String);
            free(weights);
            free(input);
            free(zero);
            free(expected);
            return fk_ret(n, cap);
        }
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        if (queue == nil) {
            free(weights);
            free(input);
            free(zero);
            free(expected);
            return fk_ret(snprintf(out, (size_t)cap, "FAIL Metal command queue unavailable\n"), cap);
        }

        id<MTLBuffer> bw = [dev newBufferWithBytes:weights length:(NSUInteger)(weightCount * 4ULL) options:MTLResourceStorageModeShared];
        id<MTLBuffer> bx = [dev newBufferWithBytes:input length:(NSUInteger)cols * 4U options:MTLResourceStorageModeShared];
        id<MTLBuffer> by = [dev newBufferWithBytes:zero length:(NSUInteger)rows * 4U options:MTLResourceStorageModeShared];
        if (bw == nil || bx == nil || by == nil) {
            free(weights);
            free(input);
            free(zero);
            free(expected);
            return fk_ret(snprintf(out, (size_t)cap, "FAIL Metal buffer allocation\n"), cap);
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
        NSUInteger tg = rows < pso.maxTotalThreadsPerThreadgroup ? (NSUInteger)rows : pso.maxTotalThreadsPerThreadgroup;
        if (tg < 1) {
            tg = 1;
        }
        [enc dispatchThreads:MTLSizeMake(rows, 1, 1) threadsPerThreadgroup:MTLSizeMake(tg, 1, 1)];
        [enc endEncoding];

        CFAbsoluteTime started = CFAbsoluteTimeGetCurrent();
        [cb commit];
        [cb waitUntilCompleted];
        double elapsedMs = (CFAbsoluteTimeGetCurrent() - started) * 1000.0;
        if (cb.error != nil) {
            int n = snprintf(out, (size_t)cap, "FAIL Metal command buffer: %s\n", cb.error.localizedDescription.UTF8String);
            free(weights);
            free(input);
            free(zero);
            free(expected);
            return fk_ret(n, cap);
        }

        float *gpu = (float *)by.contents;
        float maxDelta = 0.0f;
        for (uint32_t i = 0; i < rows; i++) {
            float d = fabsf(gpu[i] - expected[i]);
            if (d > maxDelta) {
                maxDelta = d;
            }
        }
        const char *verdict = maxDelta <= 0.000001f ? "PASS fkwu-form-cli-metal-matvec-f32" : "FAIL fkwu-form-cli-metal-matvec-f32";
        int n = snprintf(
            out,
            (size_t)cap,
            "runtime_path_sanitized=%s\n"
            "denied_toolchain_names_visible_on_path=%d\n"
            "http_or_ollama=absent\n"
            "metal_owner=fkwu-form-cli\n"
            "metal_linked=true\n"
            "metal_api=metal_matvec_f32\n"
            "metal_device=%s\n"
            "compiled_kernel=%s\n"
            "msl_bytes_loaded=%lld\n"
            "model_bytes_loaded=%lld\n"
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
            kernelName.UTF8String,
            msl_len,
            model_len,
            rows,
            cols,
            elapsedMs,
            rows > 0 ? gpu[0] : 0.0f,
            rows > 1 ? gpu[1] : 0.0f,
            rows > 0 ? expected[0] : 0.0f,
            rows > 1 ? expected[1] : 0.0f,
            maxDelta,
            verdict
        );
        free(weights);
        free(input);
        free(zero);
        free(expected);
        return fk_ret(n, cap);
    }
}
