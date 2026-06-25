#!/usr/bin/env bash
# fkwu_form_cli_metal_direct_receipt.sh
#
# Build one standalone fkwu form-cli proof binary linked with a Darwin Metal
# carrier, then run the binary under a sanitized runtime PATH. The runtime path
# is the claim: form-cli owns the native tag dispatch and the linked carrier owns
# Metal device/library/pipeline/buffers/dispatch/readback. Build-time still uses
# maintainer carriers to emit MSL and link the receipt binary.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-form-cli-metal-direct-$STAMP/receipt.json"
RECEIPT_PATH="${1:-$DEFAULT_RECEIPT}"

if [[ "$RECEIPT_PATH" != /* ]]; then
    RECEIPT_PATH="$ROOT/$RECEIPT_PATH"
fi

receipt_base="$(basename "$RECEIPT_PATH" .json)"
TRACE_DIR="$(dirname "$RECEIPT_PATH")/${receipt_base}_trace"
WORK="$TRACE_DIR"
ARTIFACT_DIR="$ROOT/.cache/body-test-receipts/fkwu-form-cli-metal-direct-$STAMP/artifact"
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
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .)
fi

cat "$FORMDIR/form-stdlib/jit-tensor-emit.fk" > "$WORK/emit-matvec.fk"
printf '\n(print "==MSL==")\n(print (jte-matvec-msl "form_fkwu_direct_matvec_f32"))\n(print "==END==")\n' >> "$WORK/emit-matvec.fk"
(cd "$FORMDIR" && "$GO_BIN" "$WORK/emit-matvec.fk" 2>"$WORK/emit-matvec.err") > "$WORK/emit-matvec.out"
sed -n '/^==MSL==$/,/^==END==$/p' "$WORK/emit-matvec.out" | sed -e '1d' -e '$d' > "$WORK/matvec.metal"
grep -q 'kernel void form_fkwu_direct_matvec_f32' "$WORK/matvec.metal" || {
    echo "FAIL emission produced no direct matvec kernel" >&2
    cat "$WORK/emit-matvec.out" >&2
    exit 1
}

msl_b64="$(base64 < "$WORK/matvec.metal" | tr -d '\n')"
msl_bytes="$(wc -c < "$WORK/matvec.metal" | tr -d ' ')"

cat > "$WORK/fkwu_metal_carrier.m" <<OBJC
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
            return snprintf(out, (size_t)cap, "SKIP no Metal device\\nmetal_owner=fkwu-form-cli\\nmetal_linked=true\\n");
        }

        NSString *encoded = @"$msl_b64";
        NSData *data = [[NSData alloc] initWithBase64EncodedString:encoded options:0];
        NSString *src = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
        NSString *full = [@"#include <metal_stdlib>\\nusing namespace metal;\\n" stringByAppendingString:src];

        NSError *err = nil;
        MTLCompileOptions *opts = [[MTLCompileOptions alloc] init];
        opts.mathMode = MTLMathModeSafe;
        id<MTLLibrary> lib = [dev newLibraryWithSource:full options:opts error:&err];
        if (lib == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal library compile: %s\\n", err.localizedDescription.UTF8String);
        }
        id<MTLFunction> fn = [lib newFunctionWithName:@"form_fkwu_direct_matvec_f32"];
        if (fn == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal kernel missing\\n");
        }
        id<MTLComputePipelineState> pso = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (pso == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal pipeline: %s\\n", err.localizedDescription.UTF8String);
        }
        id<MTLCommandQueue> queue = [dev newCommandQueue];
        if (queue == nil) {
            return snprintf(out, (size_t)cap, "FAIL Metal command queue unavailable\\n");
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
            return snprintf(out, (size_t)cap, "FAIL Metal buffer allocation\\n");
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
            return snprintf(out, (size_t)cap, "FAIL Metal command buffer: %s\\n", cb.error.localizedDescription.UTF8String);
        }

        float *gpu = (float *)by.contents;
        float d0 = fabsf(gpu[0] - expected[0]);
        float d1 = fabsf(gpu[1] - expected[1]);
        float maxDelta = d0 > d1 ? d0 : d1;
        const char *verdict = maxDelta <= 0.000001f ? "PASS fkwu-form-cli-metal-direct" : "FAIL fkwu-form-cli-metal-direct";
        return snprintf(
            out,
            (size_t)cap,
            "runtime_path_sanitized=%s\\n"
            "denied_toolchain_names_visible_on_path=%d\\n"
            "http_or_ollama=absent\\n"
            "metal_owner=fkwu-form-cli\\n"
            "metal_linked=true\\n"
            "metal_device=%s\\n"
            "embedded_msl_bytes=$msl_bytes\\n"
            "rows=%u\\n"
            "cols=%u\\n"
            "dispatch_ms=%.3f\\n"
            "gpu_y=[%.6f,%.6f]\\n"
            "expected_y=[%.6f,%.6f]\\n"
            "max_delta=%.9f\\n"
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
OBJC

artifact="$ARTIFACT_DIR/form-cli-metal-direct"
(
    cd "$FORMDIR"
    FORM_CLI_FORCE_LINK=1 \
    FORM_CLI_EXTRA_SRC="$WORK/fkwu_metal_carrier.m" \
    FORM_CLI_EXTRA_LDFLAGS="-framework Foundation -framework Metal" \
    ./build-form-cli.sh "$artifact"
) > "$WORK/build.out" 2>&1

otool -L "$artifact" > "$WORK/linked-libraries.out"

mkdir -p "$WORK/empty-bin" "$WORK/home" "$WORK/tmp"
env -i PATH="$WORK/empty-bin" HOME="$WORK/home" TMPDIR="$WORK/tmp" "$artifact" > "$WORK/runtime.out" 2>&1 <<'EOF'
metal-fixture
quit
EOF

grep -q '^PASS fkwu-form-cli-metal-direct$' "$WORK/runtime.out"
grep -q '^runtime_path_sanitized=true$' "$WORK/runtime.out"
grep -q '^denied_toolchain_names_visible_on_path=0$' "$WORK/runtime.out"
grep -q '^http_or_ollama=absent$' "$WORK/runtime.out"
grep -q '^metal_owner=fkwu-form-cli$' "$WORK/runtime.out"

trace_sha="$(shasum -a 256 "$WORK/runtime.out" "$WORK/build.out" "$WORK/linked-libraries.out" "$WORK/matvec.metal" | shasum -a 256 | awk '{print $1}')"
runtime_sha="$(shasum -a 256 "$WORK/runtime.out" | awk '{print $1}')"
build_sha="$(shasum -a 256 "$WORK/build.out" | awk '{print $1}')"
linked_sha="$(shasum -a 256 "$WORK/linked-libraries.out" | awk '{print $1}')"
msl_sha="$(shasum -a 256 "$WORK/matvec.metal" | awk '{print $1}')"
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
artifact_rel="${artifact#"$ROOT/"}"

jq -n \
    --arg date "2026-06-25" \
    --arg trace_id "fkwu-form-cli-metal-direct-$STAMP" \
    --arg branch "$branch" \
    --arg commit "$commit" \
    --arg receipt_path "$receipt_dir_rel" \
    --arg trace_dir "$trace_rel" \
    --arg trace_sha256 "$trace_sha" \
    --arg runtime_sha256 "$runtime_sha" \
    --arg build_sha256 "$build_sha" \
    --arg linked_sha256 "$linked_sha" \
    --arg msl_sha256 "$msl_sha" \
    --arg artifact_sha256 "$artifact_sha" \
    --arg runtime_output "$runtime_rel" \
    --arg build_output "$build_rel" \
    --arg linked_libraries "$linked_rel" \
    --arg metal_source "$msl_rel" \
    --arg artifact "$artifact_rel" \
    --arg metal_device "$metal_device" \
    --arg gpu_y "$gpu_y" \
    --arg max_delta "$max_delta" \
    --argjson embedded_msl_bytes "$msl_bytes" \
    '{
        date: $date,
        trace_id: $trace_id,
        receipt_kind: "fkwu-form-cli-direct-metal-receipt",
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
            compiled_artifact: $artifact,
            compiled_artifact_sha256: $artifact_sha256,
            compiled_artifact_storage: ".cache (not committed)"
        },
        target: {
            desired_path: "form-cli REPL -> fkwu native tag 203 -> linked Metal carrier -> device/library/pipeline/buffers/dispatch/readback",
            rejected_path: "form-cli -> HTTP/socket -> Ollama",
            runtime_dependency_claim_scope: "compiled proof binary under sanitized PATH"
        },
        gates: {
            fkwu_form_cli_native_tag_203: true,
            form_cli_repl_verb_metal_fixture: true,
            metal_device_observed: ($metal_device | length > 0),
            runtime_path_sanitized: true,
            denied_toolchain_names_visible_on_path: 0,
            http_or_ollama_absent: true,
            embedded_msl_bytes: $embedded_msl_bytes,
            gpu_y: $gpu_y,
            max_delta: $max_delta
        },
        open_bridges: [
            "generic metal_matvec_f32(msl,kernel,model_bytes) primitive instead of a deterministic fixture",
            "real GGUF/content-addressed tensor-cell loader in the fkwu-controlled model path",
            "full-width Llama 3.2 tokenizer -> 28-layer GQA decode -> logits/argmax -> decoded token without Ollama"
        ]
    }' > "$RECEIPT_PATH"

cat "$WORK/runtime.out"
echo "$RECEIPT_PATH"
