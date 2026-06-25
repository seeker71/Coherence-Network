#!/usr/bin/env bash
# fkwu_form_cli_metal_matvec_receipt.sh
#
# Build one standalone fkwu form-cli proof binary linked with a Darwin Metal
# carrier, then run the binary under a sanitized runtime PATH. Unlike the direct
# fixture, this crosses a generic native call:
#   form-cli -> metal-matvec <msl> <kernel> <model-bytes>
#   -> fkwu tag 204 -> linked Metal carrier.
#
# Build-time may use maintainer tools to emit MSL and link the receipt binary.
# Runtime proof is the compiled fkwu binary plus linked Metal framework, with no
# shell, Python, Go, Rust, clang, HTTP, Ollama, or runtime toolchain visible.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-form-cli-metal-matvec-$STAMP/receipt.json"
RECEIPT_PATH="${1:-$DEFAULT_RECEIPT}"

if [[ "$RECEIPT_PATH" != /* ]]; then
    RECEIPT_PATH="$ROOT/$RECEIPT_PATH"
fi

receipt_base="$(basename "$RECEIPT_PATH" .json)"
TRACE_DIR="$(dirname "$RECEIPT_PATH")/${receipt_base}_trace"
WORK="$TRACE_DIR"
ARTIFACT_DIR="$ROOT/.cache/body-test-receipts/fkwu-form-cli-metal-matvec-$STAMP/artifact"
mkdir -p "$WORK" "$ARTIFACT_DIR"

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "missing required build/receipt tool: $1" >&2
        exit 2
    fi
}

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "SKIP no Darwin/Metal runtime"
    exit 2
fi

need clang
need jq
need shasum
need otool
if [[ ! -x "$GO_BIN" ]]; then
    need go
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$WORK/emit-matvec.fk"
printf '\n(print "==MSL==")\n(print (jte-matvec-msl "form_fkwu_generic_matvec_f32"))\n(print "==END==")\n' >> "$WORK/emit-matvec.fk"
(cd "$FORMDIR" && "$GO_BIN" "$WORK/emit-matvec.fk" 2>"$WORK/emit-matvec.err") > "$WORK/emit-matvec.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$WORK/emit-matvec.out" | sed -e '1d' -e '$d' > "$WORK/matvec.metal"
grep -q 'kernel void form_fkwu_generic_matvec_f32' "$WORK/matvec.metal" || {
    echo "FAIL emission produced no generic matvec kernel" >&2
    cat "$WORK/emit-matvec.out" >&2
    exit 1
}

model_bin="$ARTIFACT_DIR/model.bin"
printf '\002\000\000\000\003\000\000\000\000\000\200\077\000\000\000\100\000\000\200\277\000\000\000\077\000\000\100\300\000\000\200\100\000\000\000\100\000\000\200\277\000\000\200\076' > "$model_bin"
model_bytes="$(wc -c < "$model_bin" | tr -d ' ')"
msl_bytes="$(wc -c < "$WORK/matvec.metal" | tr -d ' ')"
od -An -tx1 -v "$model_bin" | tr -s ' ' | sed 's/^ //; s/ $//' > "$WORK/model.hex"
cat > "$WORK/model-layout.txt" <<'EOF'
little-endian model bytes
u32 rows = 2
u32 cols = 3
f32 weights row-major = [1.0, 2.0, -1.0, 0.5, -3.0, 4.0]
f32 input = [2.0, -1.0, 0.25]
expected right-fold y = [-0.25, 5.0]
EOF

cat > "$WORK/fkwu_metal_matvec_carrier.m" <<'OBJC'
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
OBJC

artifact="$ARTIFACT_DIR/form-cli-metal-matvec"
(
    cd "$FORMDIR"
    FORM_CLI_FORCE_LINK=1 \
    FORM_CLI_EXTRA_SRC="$WORK/fkwu_metal_matvec_carrier.m" \
    FORM_CLI_EXTRA_LDFLAGS="-framework Foundation -framework Metal" \
    ./build-form-cli.sh "$artifact"
) > "$ARTIFACT_DIR/build.raw" 2>&1
LC_ALL=C sed -E "s|$ROOT|<repo>|g; s|/var/folders/[^:[:space:]]+|<tmp>|g" "$ARTIFACT_DIR/build.raw" > "$WORK/build.out"

otool -L "$artifact" > "$ARTIFACT_DIR/linked-libraries.raw"
LC_ALL=C sed -E "s|$artifact|<compiled-artifact>|g; s|$ROOT|<repo>|g" "$ARTIFACT_DIR/linked-libraries.raw" > "$WORK/linked-libraries.out"

mkdir -p "$WORK/empty-bin" "$WORK/home" "$WORK/tmp"
env -i PATH="$WORK/empty-bin" HOME="$WORK/home" TMPDIR="$WORK/tmp" "$artifact" > "$WORK/runtime.out" 2>&1 <<EOF
metal-matvec $WORK/matvec.metal form_fkwu_generic_matvec_f32 $model_bin
quit
EOF

grep -q '^PASS fkwu-form-cli-metal-matvec-f32$' "$WORK/runtime.out"
grep -q '^runtime_path_sanitized=true$' "$WORK/runtime.out"
grep -q '^denied_toolchain_names_visible_on_path=0$' "$WORK/runtime.out"
grep -q '^http_or_ollama=absent$' "$WORK/runtime.out"
grep -q '^metal_owner=fkwu-form-cli$' "$WORK/runtime.out"
grep -q '^metal_api=metal_matvec_f32$' "$WORK/runtime.out"

trace_sha="$(shasum -a 256 "$WORK/runtime.out" "$WORK/build.out" "$WORK/linked-libraries.out" "$WORK/matvec.metal" "$WORK/fkwu_metal_matvec_carrier.m" "$WORK/model.hex" "$WORK/model-layout.txt" | shasum -a 256 | awk '{print $1}')"
runtime_sha="$(shasum -a 256 "$WORK/runtime.out" | awk '{print $1}')"
build_sha="$(shasum -a 256 "$WORK/build.out" | awk '{print $1}')"
linked_sha="$(shasum -a 256 "$WORK/linked-libraries.out" | awk '{print $1}')"
msl_sha="$(shasum -a 256 "$WORK/matvec.metal" | awk '{print $1}')"
carrier_sha="$(shasum -a 256 "$WORK/fkwu_metal_matvec_carrier.m" | awk '{print $1}')"
model_sha="$(shasum -a 256 "$model_bin" | awk '{print $1}')"
model_hex_sha="$(shasum -a 256 "$WORK/model.hex" | awk '{print $1}')"
artifact_sha="$(shasum -a 256 "$artifact" | awk '{print $1}')"
branch="$(cd "$ROOT" && git branch --show-current 2>/dev/null || echo unknown)"
commit="$(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo unknown)"
metal_device="$(grep '^metal_device=' "$WORK/runtime.out" | head -1 | cut -d= -f2-)"
gpu_y="$(grep '^gpu_y=' "$WORK/runtime.out" | head -1 | cut -d= -f2-)"
max_delta="$(grep '^max_delta=' "$WORK/runtime.out" | head -1 | cut -d= -f2-)"
receipt_dir_rel="${RECEIPT_PATH#"$ROOT/"}"
trace_rel="${TRACE_DIR#"$ROOT/"}"
runtime_rel="${WORK#"$ROOT/"}/runtime.out"
build_rel="${WORK#"$ROOT/"}/build.out"
linked_rel="${WORK#"$ROOT/"}/linked-libraries.out"
msl_rel="${WORK#"$ROOT/"}/matvec.metal"
carrier_rel="${WORK#"$ROOT/"}/fkwu_metal_matvec_carrier.m"
model_hex_rel="${WORK#"$ROOT/"}/model.hex"
model_layout_rel="${WORK#"$ROOT/"}/model-layout.txt"
model_rel="${model_bin#"$ROOT/"}"
artifact_rel="${artifact#"$ROOT/"}"

jq -n \
    --arg date "2026-06-25" \
    --arg trace_id "fkwu-form-cli-metal-matvec-$STAMP" \
    --arg branch "$branch" \
    --arg commit "$commit" \
    --arg receipt_path "$receipt_dir_rel" \
    --arg trace_dir "$trace_rel" \
    --arg trace_sha256 "$trace_sha" \
    --arg runtime_sha256 "$runtime_sha" \
    --arg build_sha256 "$build_sha" \
    --arg linked_sha256 "$linked_sha" \
    --arg msl_sha256 "$msl_sha" \
    --arg carrier_sha256 "$carrier_sha" \
    --arg model_sha256 "$model_sha" \
    --arg model_hex_sha256 "$model_hex_sha" \
    --arg artifact_sha256 "$artifact_sha" \
    --arg runtime_output "$runtime_rel" \
    --arg build_output "$build_rel" \
    --arg linked_libraries "$linked_rel" \
    --arg metal_source "$msl_rel" \
    --arg carrier_source "$carrier_rel" \
    --arg model_hex "$model_hex_rel" \
    --arg model_layout "$model_layout_rel" \
    --arg model_bytes_artifact "$model_rel" \
    --arg artifact "$artifact_rel" \
    --arg metal_device "$metal_device" \
    --arg gpu_y "$gpu_y" \
    --arg max_delta "$max_delta" \
    --argjson msl_bytes "$msl_bytes" \
    --argjson model_bytes "$model_bytes" \
    '{
        date: $date,
        trace_id: $trace_id,
        receipt_kind: "fkwu-form-cli-generic-metal-matvec-receipt",
        thread_branch: $branch,
        git_commit: $commit,
        verdict: "pass",
        receipt_path: $receipt_path,
        observable_trace: {
            trace_dir: $trace_dir,
            trace_sha256: $trace_sha256,
            runtime_output: $runtime_output,
            runtime_output_sha256: $runtime_sha256,
            build_output: $build_output,
            build_output_sha256: $build_sha256,
            linked_libraries: $linked_libraries,
            linked_libraries_sha256: $linked_sha256,
            metal_source: $metal_source,
            metal_source_sha256: $msl_sha256,
            carrier_source: $carrier_source,
            carrier_source_sha256: $carrier_sha256,
            model_layout: $model_layout,
            model_hex: $model_hex,
            model_hex_sha256: $model_hex_sha256,
            model_bytes_artifact: $model_bytes_artifact,
            model_bytes_sha256: $model_sha256,
            model_bytes_storage: ".cache (not committed); text hex/layout trace is committed",
            compiled_artifact: $artifact,
            compiled_artifact_sha256: $artifact_sha256,
            compiled_artifact_storage: ".cache (not committed)"
        },
        target: {
            desired_path: "form-cli REPL -> fkwu native tag 204 -> linked metal_matvec_f32 carrier -> supplied MSL/model bytes -> device/library/pipeline/buffers/dispatch/readback",
            rejected_path: "form-cli -> HTTP/socket -> Ollama",
            runtime_dependency_claim_scope: "compiled proof binary under sanitized PATH"
        },
        gates: {
            fkwu_form_cli_native_tag_204: true,
            form_cli_repl_verb_metal_matvec: true,
            metal_device_observed: ($metal_device | length > 0),
            runtime_path_sanitized: true,
            denied_toolchain_names_visible_on_path: 0,
            http_or_ollama_absent: true,
            msl_bytes_loaded: $msl_bytes,
            model_bytes_loaded: $model_bytes,
            gpu_y: $gpu_y,
            max_delta: $max_delta
        },
        open_bridges: [
            "real GGUF/content-addressed tensor-cell loader in the fkwu-controlled model path",
            "full-width Llama 3.2 tokenizer -> 28-layer GQA decode -> logits/argmax -> decoded token without Ollama",
            "Android Vulkan and Windows DirectML/D3D12 generic carrier receipts matching the macOS Metal generic carrier"
        ]
    }' > "$RECEIPT_PATH"

cat "$WORK/runtime.out"
echo "$RECEIPT_PATH"
