#!/usr/bin/env bash
# fkwu_form_cli_metal_model_cell_receipt.sh
#
# Build one standalone fkwu form-cli proof binary linked with the Darwin Metal
# matvec carrier, then run the binary under a sanitized runtime PATH through:
#   form-cli -> metal-model-cell <manifest>
#   -> Form SHA-256 content-address check
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
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-form-cli-metal-model-cell-$STAMP/receipt.json"
RECEIPT_PATH="${1:-$DEFAULT_RECEIPT}"

if [[ "$RECEIPT_PATH" != /* ]]; then
    RECEIPT_PATH="$ROOT/$RECEIPT_PATH"
fi

receipt_base="$(basename "$RECEIPT_PATH" .json)"
TRACE_DIR="$(dirname "$RECEIPT_PATH")/${receipt_base}_trace"
WORK="$TRACE_DIR"
ARTIFACT_DIR="$ROOT/.cache/body-test-receipts/fkwu-form-cli-metal-model-cell-$STAMP/artifact"
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

need awk
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
model_sha="$(shasum -a 256 "$model_bin" | awk '{print $1}')"
od -An -tx1 -v "$model_bin" | tr -s ' ' | sed -E 's/^ //; s/ $//; /^[[:blank:]]*$/d' > "$WORK/model.hex"
cat > "$WORK/model-layout.txt" <<'EOF'
little-endian model bytes
u32 rows = 2
u32 cols = 3
f32 weights row-major = [1.0, 2.0, -1.0, 0.5, -3.0, 4.0]
f32 input = [2.0, -1.0, 0.25]
expected right-fold y = [-0.25, 5.0]
EOF

manifest_runtime="$ARTIFACT_DIR/model-cell.manifest"
printf 'model-cell-v1 %s %s %s form_fkwu_generic_matvec_f32' "$model_sha" "$model_bin" "$WORK/matvec.metal" > "$manifest_runtime"
printf 'model-cell-v1 %s <model-bytes-artifact> <metal-source> form_fkwu_generic_matvec_f32\n' "$model_sha" > "$WORK/model-cell-manifest.txt"

awk '
    emit && $0 == "OBJC" { exit }
    emit { print }
    $0 == "#import <Foundation/Foundation.h>" { emit = 1; print }
' "$ROOT/scripts/fkwu_form_cli_metal_matvec_receipt.sh" > "$WORK/fkwu_metal_matvec_carrier.m"
grep -q 'fk_metal_matvec_f32_external' "$WORK/fkwu_metal_matvec_carrier.m" || {
    echo "FAIL could not extract Metal matvec carrier source" >&2
    exit 1
}

artifact="$ARTIFACT_DIR/form-cli-metal-model-cell"
(
    cd "$FORMDIR"
    FORM_CLI_FORCE_LINK=1 \
    FORM_CLI_EXTRA_SRC="$WORK/fkwu_metal_matvec_carrier.m" \
    FORM_CLI_EXTRA_LDFLAGS="-framework Foundation -framework Metal" \
    ./build-form-cli.sh "$artifact"
) > "$ARTIFACT_DIR/build.raw" 2>&1
LC_ALL=C sed -E "s|$ROOT|<repo>|g; s|/var/folders/[^:[:space:]]+|<tmp>|g; s/[[:blank:]]+$//" "$ARTIFACT_DIR/build.raw" > "$WORK/build.out"

otool -L "$artifact" > "$ARTIFACT_DIR/linked-libraries.raw"
LC_ALL=C sed -E "s|$artifact|<compiled-artifact>|g; s|$ROOT|<repo>|g; s/^ +\t/\t/; s/[[:blank:]]+$//" "$ARTIFACT_DIR/linked-libraries.raw" > "$WORK/linked-libraries.out"

mkdir -p "$WORK/empty-bin" "$WORK/home" "$WORK/tmp"
env -i PATH="$WORK/empty-bin" HOME="$WORK/home" TMPDIR="$WORK/tmp" "$artifact" > "$WORK/runtime.out" 2>&1 <<EOF
metal-model-cell $manifest_runtime
quit
EOF

grep -q '^model_cell_verified=true$' "$WORK/runtime.out"
grep -q "^model_cell_sha256=$model_sha$" "$WORK/runtime.out"
grep -q '^PASS fkwu-form-cli-metal-matvec-f32$' "$WORK/runtime.out"
grep -q '^runtime_path_sanitized=true$' "$WORK/runtime.out"
grep -q '^denied_toolchain_names_visible_on_path=0$' "$WORK/runtime.out"
grep -q '^http_or_ollama=absent$' "$WORK/runtime.out"
grep -q '^metal_owner=fkwu-form-cli$' "$WORK/runtime.out"
grep -q '^metal_api=metal_matvec_f32$' "$WORK/runtime.out"

trace_sha="$(shasum -a 256 "$WORK/runtime.out" "$WORK/build.out" "$WORK/linked-libraries.out" "$WORK/matvec.metal" "$WORK/fkwu_metal_matvec_carrier.m" "$WORK/model.hex" "$WORK/model-layout.txt" "$WORK/model-cell-manifest.txt" | shasum -a 256 | awk '{print $1}')"
runtime_sha="$(shasum -a 256 "$WORK/runtime.out" | awk '{print $1}')"
build_sha="$(shasum -a 256 "$WORK/build.out" | awk '{print $1}')"
linked_sha="$(shasum -a 256 "$WORK/linked-libraries.out" | awk '{print $1}')"
msl_sha="$(shasum -a 256 "$WORK/matvec.metal" | awk '{print $1}')"
carrier_sha="$(shasum -a 256 "$WORK/fkwu_metal_matvec_carrier.m" | awk '{print $1}')"
model_hex_sha="$(shasum -a 256 "$WORK/model.hex" | awk '{print $1}')"
manifest_sha="$(shasum -a 256 "$WORK/model-cell-manifest.txt" | awk '{print $1}')"
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
manifest_trace_rel="${WORK#"$ROOT/"}/model-cell-manifest.txt"
model_rel="${model_bin#"$ROOT/"}"
manifest_runtime_rel="${manifest_runtime#"$ROOT/"}"
artifact_rel="${artifact#"$ROOT/"}"

jq -n \
    --arg date "2026-06-25" \
    --arg trace_id "fkwu-form-cli-metal-model-cell-$STAMP" \
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
    --arg manifest_sha256 "$manifest_sha" \
    --arg artifact_sha256 "$artifact_sha" \
    --arg runtime_output "$runtime_rel" \
    --arg build_output "$build_rel" \
    --arg linked_libraries "$linked_rel" \
    --arg metal_source "$msl_rel" \
    --arg carrier_source "$carrier_rel" \
    --arg model_hex "$model_hex_rel" \
    --arg model_layout "$model_layout_rel" \
    --arg model_cell_manifest "$manifest_trace_rel" \
    --arg model_bytes_artifact "$model_rel" \
    --arg runtime_manifest_artifact "$manifest_runtime_rel" \
    --arg artifact "$artifact_rel" \
    --arg metal_device "$metal_device" \
    --arg gpu_y "$gpu_y" \
    --arg max_delta "$max_delta" \
    --argjson msl_bytes "$msl_bytes" \
    --argjson model_bytes "$model_bytes" \
    '{
        date: $date,
        trace_id: $trace_id,
        receipt_kind: "fkwu-form-cli-metal-model-cell-receipt",
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
            model_cell_manifest: $model_cell_manifest,
            model_cell_manifest_sha256: $manifest_sha256,
            runtime_manifest_artifact: $runtime_manifest_artifact,
            runtime_manifest_storage: ".cache (not committed); sanitized manifest trace is committed",
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
            desired_path: "form-cli REPL -> fkwu Form SHA-256 model-cell manifest gate -> fkwu native tag 204 -> linked metal_matvec_f32 carrier -> supplied MSL/model bytes -> device/library/pipeline/buffers/dispatch/readback",
            rejected_path: "form-cli -> HTTP/socket -> Ollama",
            runtime_dependency_claim_scope: "compiled proof binary under sanitized PATH"
        },
        gates: {
            fkwu_form_cli_native_tag_204: true,
            form_cli_repl_verb_metal_model_cell: true,
            model_cell_sha256_verified_in_form: true,
            model_cell_sha256: $model_sha256,
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
            "complete full GGUF tensor payload staging into this content-addressed model-cell path; required tensor-set byte windows are witnessed separately",
            "full-width Llama 3.2 tokenizer -> 28-layer GQA decode -> logits/argmax -> decoded token without Ollama",
            "Android Vulkan and Windows DirectML/D3D12 generic carrier receipts matching the macOS Metal generic carrier"
        ]
    }' > "$RECEIPT_PATH"

cat "$WORK/runtime.out"
echo "$RECEIPT_PATH"
