#!/usr/bin/env bash
# fkwu_form_cli_gguf_model_cell_receipt.sh -- prove form-cli can verify a
# content-addressed GGUF cell and parse tensor metadata inside fkwu.
#
# Runtime path under proof:
#   form-cli -> gguf-model-cell <manifest>
# The shell creates the deterministic fixture and receipt; the observed runtime
# is the self-contained fkwu form-cli binary with an empty PATH.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-form-cli-gguf-model-cell-$STAMP/receipt.json"
RECEIPT="${1:-$DEFAULT_RECEIPT}"
if [[ "$RECEIPT" != /* ]]; then
    RECEIPT="$ROOT/$RECEIPT"
fi
RUN_ID="fkwu-form-cli-gguf-model-cell-$STAMP"
ARTIFACT_DIR="$ROOT/.cache/body-test-receipts/$RUN_ID/artifact"
WORK="$ROOT/.cache/body-test-receipts/$RUN_ID/trace"
PUBLISH_TRACE_DIR="${PUBLISH_TRACE_DIR:-}"

if [[ -z "$PUBLISH_TRACE_DIR" && "$RECEIPT" == "$ROOT/docs/system_audit/"* ]]; then
    PUBLISH_TRACE_DIR="${RECEIPT%.json}_trace"
fi

mkdir -p "$ARTIFACT_DIR" "$WORK" "$(dirname "$RECEIPT")"

need_hash_tool() {
    if command -v shasum >/dev/null 2>&1 || command -v sha256sum >/dev/null 2>&1; then
        return 0
    fi
    echo "missing required receipt harness tool: shasum or sha256sum" >&2
    exit 2
}

hash_file() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        sha256sum "$1" | awk '{print $1}'
    fi
}

hash_files_digest() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$@" | shasum -a 256 | awk '{print $1}'
    else
        sha256sum "$@" | sha256sum | awk '{print $1}'
    fi
}

need_hash_tool

write_bytes() {
    local out="$1"
    local b oct
    shift
    : > "$out"
    for b in "$@"; do
        oct="$(printf '%03o' "$b")"
        printf "\\$oct" >> "$out"
    done
}

gguf_bin="$ARTIFACT_DIR/mini.gguf"
write_bytes "$gguf_bin" \
    71 71 85 70  3 0 0 0  1 0 0 0 0 0 0 0  2 0 0 0 0 0 0 0 \
    1 0 0 0 0 0 0 0  97  4 0 0 0  42 0 0 0 \
    1 0 0 0 0 0 0 0  98  9 0 0 0  4 0 0 0  2 0 0 0 0 0 0 0  7 0 0 0  8 0 0 0 \
    1 0 0 0 0 0 0 0  119  1 0 0 0  0 1 0 0 0 0 0 0  12 0 0 0  0 0 0 0 0 0 0 0

gguf_sha="$(hash_file "$gguf_bin")"
manifest_runtime="$ARTIFACT_DIR/gguf-cell.manifest"
printf 'gguf-cell-v1 %s %s 0\n' "$gguf_sha" "$gguf_bin" > "$manifest_runtime"
printf 'gguf-cell-v1 %s <mini-gguf-artifact> 0\n' "$gguf_sha" > "$WORK/gguf-cell-manifest.txt"

cat > "$WORK/model-layout.txt" <<'LAYOUT'
GGUF fixture: header(0..24) + KV scalar "a" + KV array "b" + tensor-info "w".
Expected:
  magic=GGUF
  version=3
  tensor_count=1
  kv_count=2
  tensor_info_offset=74
  tensor_index=0
  tensor_ndims=1
  tensor_dim0=256
  tensor_type=12
  tensor_data_offset=0
LAYOUT
od -An -tx1 -v "$gguf_bin" > "$WORK/mini-gguf.hex"

artifact="$ARTIFACT_DIR/form-cli-gguf-model-cell"
(
    cd "$ROOT/form"
    FORM_STANDARD_LANE=1 ./build-form-cli.sh "$artifact"
) > "$WORK/build.out" 2>&1
chmod +x "$artifact"

empty_path="$ARTIFACT_DIR/empty-path"
runtime_home="$ARTIFACT_DIR/home"
runtime_tmp="$ARTIFACT_DIR/tmp"
mkdir -p "$empty_path" "$runtime_home" "$runtime_tmp"

env -i PATH="$empty_path" HOME="$runtime_home" TMPDIR="$runtime_tmp" "$artifact" > "$WORK/runtime.raw" 2>&1 <<EOF
gguf-model-cell $manifest_runtime
quit
EOF
tr -d '\r' < "$WORK/runtime.raw" > "$WORK/runtime.out"

grep -q '^gguf_cell_verified=true$' "$WORK/runtime.out"
grep -q '^gguf_magic_ok=1$' "$WORK/runtime.out"
grep -q '^gguf_version=3$' "$WORK/runtime.out"
grep -q '^gguf_tensor_count=1$' "$WORK/runtime.out"
grep -q '^gguf_kv_count=2$' "$WORK/runtime.out"
grep -q '^gguf_tensor_info_offset=74$' "$WORK/runtime.out"
grep -q '^gguf_tensor_ndims=1$' "$WORK/runtime.out"
grep -q '^gguf_tensor_dim0=256$' "$WORK/runtime.out"
grep -q '^gguf_tensor_type=12$' "$WORK/runtime.out"
grep -q '^gguf_tensor_data_offset=0$' "$WORK/runtime.out"
grep -q '^PASS fkwu-form-cli-gguf-model-cell$' "$WORK/runtime.out"

http_or_ollama="absent"
if grep -Eiq 'http|ollama' "$WORK/runtime.out"; then
    http_or_ollama="present"
fi

denied_toolchain_names_visible_on_path=0
for name in go rustc cargo python python3 clang cc gcc sh bash curl ollama; do
    if PATH="$empty_path" command -v "$name" >/dev/null 2>&1; then
        denied_toolchain_names_visible_on_path=$((denied_toolchain_names_visible_on_path + 1))
    fi
done

extract_value() {
    local key="$1"
    awk -F= -v key="$key" '$1 == key { print $2; exit }' "$WORK/runtime.out"
}

trace_sha="$(hash_files_digest "$WORK/runtime.out" "$WORK/build.out" "$WORK/model-layout.txt" "$WORK/mini-gguf.hex" "$WORK/gguf-cell-manifest.txt")"

sanitize_trace_file() {
    local src="$1"
    local dst="$2"
    LC_ALL=C sed -E \
        -e "s|$ROOT|<repo>|g" \
        -e "s|$HOME|<home>|g" \
        -e 's|/private/var/folders/[^[:space:]:]+|<tmp>|g' \
        -e 's|/var/folders/[^[:space:]:]+|<tmp>|g' \
        "$src" > "$dst"
}

TRACE_REPORT_DIR="$WORK"
if [[ -n "$PUBLISH_TRACE_DIR" ]]; then
    mkdir -p "$PUBLISH_TRACE_DIR"
    sanitize_trace_file "$WORK/runtime.out" "$PUBLISH_TRACE_DIR/runtime.out"
    sanitize_trace_file "$WORK/build.out" "$PUBLISH_TRACE_DIR/build.out"
    cp "$WORK/model-layout.txt" "$PUBLISH_TRACE_DIR/model-layout.txt"
    cp "$WORK/mini-gguf.hex" "$PUBLISH_TRACE_DIR/mini-gguf.hex"
    cp "$WORK/gguf-cell-manifest.txt" "$PUBLISH_TRACE_DIR/gguf-cell-manifest.txt"
    TRACE_REPORT_DIR="$PUBLISH_TRACE_DIR"
fi

branch="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
commit="$(git -C "$ROOT" rev-parse HEAD)"
runtime_rel="${TRACE_REPORT_DIR#"$ROOT/"}/runtime.out"
build_rel="${TRACE_REPORT_DIR#"$ROOT/"}/build.out"
layout_rel="${TRACE_REPORT_DIR#"$ROOT/"}/model-layout.txt"
hex_rel="${TRACE_REPORT_DIR#"$ROOT/"}/mini-gguf.hex"
manifest_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-cell-manifest.txt"
artifact_rel="${artifact#"$ROOT/"}"
gguf_rel="${gguf_bin#"$ROOT/"}"

jq -n \
    --arg trace_id "$RUN_ID" \
    --arg branch "$branch" \
    --arg commit "$commit" \
    --arg gguf_sha "$gguf_sha" \
    --arg trace_sha "$trace_sha" \
    --arg runtime_out "$runtime_rel" \
    --arg build_out "$build_rel" \
    --arg layout "$layout_rel" \
    --arg hex "$hex_rel" \
    --arg manifest "$manifest_rel" \
    --arg artifact "$artifact_rel" \
    --arg gguf "$gguf_rel" \
    --arg http_or_ollama "$http_or_ollama" \
    --argjson denied "$denied_toolchain_names_visible_on_path" \
    --argjson magic_ok "$(extract_value gguf_magic_ok)" \
    --argjson version "$(extract_value gguf_version)" \
    --argjson tensor_count "$(extract_value gguf_tensor_count)" \
    --argjson kv_count "$(extract_value gguf_kv_count)" \
    --argjson tensor_index "$(extract_value gguf_tensor_index)" \
    --argjson tensor_info_offset "$(extract_value gguf_tensor_info_offset)" \
    --argjson tensor_ndims "$(extract_value gguf_tensor_ndims)" \
    --argjson tensor_dim0 "$(extract_value gguf_tensor_dim0)" \
    --argjson tensor_type "$(extract_value gguf_tensor_type)" \
    --argjson tensor_data_offset "$(extract_value gguf_tensor_data_offset)" \
    '{
      trace_id: $trace_id,
      receipt_kind: "fkwu-form-cli-gguf-model-cell-receipt",
      thread_branch: $branch,
      git_commit: $commit,
      runtime: {
        owner: "fkwu-form-cli",
        verb: "gguf-model-cell",
        path_sanitized: true,
        denied_toolchain_names_visible_on_path: $denied,
        http_or_ollama: $http_or_ollama
      },
      artifacts: {
        compiled_artifact: $artifact,
        gguf_artifact: $gguf,
        manifest_trace: $manifest,
        runtime_out: $runtime_out,
        build_out: $build_out,
        model_layout: $layout,
        mini_gguf_hex: $hex
      },
      observed: {
        gguf_cell_verified: true,
        gguf_cell_source: "content-addressed-manifest",
        gguf_cell_format: "gguf-v3-tensor-info",
        gguf_cell_sha256: $gguf_sha,
        gguf_magic_ok: $magic_ok,
        gguf_version: $version,
        gguf_tensor_count: $tensor_count,
        gguf_kv_count: $kv_count,
        gguf_tensor_index: $tensor_index,
        gguf_tensor_info_offset: $tensor_info_offset,
        gguf_tensor_ndims: $tensor_ndims,
        gguf_tensor_dim0: $tensor_dim0,
        gguf_tensor_type: $tensor_type,
        gguf_tensor_data_offset: $tensor_data_offset,
        verdict: "PASS fkwu-form-cli-gguf-model-cell"
      },
      path_claim: {
        desired_path: "form-cli REPL -> fkwu Form SHA-256 GGUF manifest gate -> GGUF tensor metadata parse mirroring gguf-read.fk",
        proven_now: "content-addressed GGUF bytes are verified in Form and their first tensor-info record is parsed inside the fkwu form-cli app",
        not_claimed: [
          "full real Llama GGUF metadata walk through variable-width tokenizer arrays",
          "full GGUF weight map materialized into Metal buffers",
          "tokenizer plus full-width autoregressive decode",
          "Android Vulkan or Windows DirectML/D3D12 execution"
        ]
      },
      trace_sha256: $trace_sha
    }' > "$RECEIPT"

printf 'receipt=%s\n' "$RECEIPT"
printf 'trace_id=%s\n' "$RUN_ID"
printf 'gguf_cell_sha256=%s\n' "$gguf_sha"
sed -n '1,14p' "$WORK/runtime.out"
