#!/usr/bin/env bash
# fkwu_form_cli_full_gguf_tensor_slice_math_receipt.sh -- prove a named tensor
# byte window from a real full GGUF file enters fkwu/Form Q6_K math.
#
# Runtime path under proof:
#   form-cli -> gguf-tensor-slice-math <manifest>
#
# The shell/Python code here is the receipt harness only. The observed child
# runtime is the self-contained fkwu form-cli binary, launched with an empty PATH;
# it reads the real GGUF slice through read_file_slice, hashes it in Form, and
# runs the Q6_K dequant/dot recipe in Form.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-full-gguf-tensor-slice-math-$STAMP/receipt.json"
RECEIPT="${1:-$DEFAULT_RECEIPT}"
GGUF_PATH="${2:-}"
if [[ "$RECEIPT" != /* ]]; then
    RECEIPT="$ROOT/$RECEIPT"
fi
RUN_ID="fkwu-full-gguf-tensor-slice-math-$STAMP"
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

hash_files_digest() {
    if command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$@" | shasum -a 256 | awk '{print $1}'
    else
        sha256sum "$@" | sha256sum | awk '{print $1}'
    fi
}

need_hash_tool
command -v python3 >/dev/null 2>&1 || { echo "missing receipt harness tool: python3" >&2; exit 2; }

map_json="$WORK/gguf-weight-map.json"
if [[ -n "$GGUF_PATH" ]]; then
    python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$map_json" "$GGUF_PATH" > "$WORK/gguf-weight-map.out"
else
    python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$map_json" > "$WORK/gguf-weight-map.out"
fi

manifest_runtime="$ARTIFACT_DIR/gguf-tensor-slice.manifest"
manifest_trace="$WORK/gguf-tensor-slice-manifest.txt"
slice_source="$WORK/tensor-slice-source.json"
slice_hex="$WORK/tensor-slice.hex"

python3 - "$map_json" "$manifest_runtime" "$manifest_trace" "$slice_source" "$slice_hex" <<'PY'
import hashlib
import json
import struct
import sys
from pathlib import Path

map_path = Path(sys.argv[1])
manifest_runtime = Path(sys.argv[2])
manifest_trace = Path(sys.argv[3])
slice_source = Path(sys.argv[4])
slice_hex = Path(sys.argv[5])

receipt = json.loads(map_path.read_text(encoding="utf-8"))
if receipt.get("verdict") != "pass":
    raise SystemExit("GGUF weight-map receipt did not pass")

tensor = ((receipt.get("tensor_map") or {}).get("focus_tensors") or {}).get("token_embd.weight")
if not tensor:
    raise SystemExit("token_embd.weight not present in GGUF focus_tensors")
if int(tensor.get("ggml_type", 0)) != 14 and str(tensor.get("type")) != "Q6_K":
    raise SystemExit(f"token_embd.weight is not Q6_K: {tensor.get('type')}")

gguf_path = Path(receipt["path"])
absolute_start = int(tensor["absolute_start"])
slice_len = 210
with gguf_path.open("rb") as f:
    f.seek(absolute_start)
    payload = f.read(slice_len)
if len(payload) != slice_len:
    raise SystemExit(f"short tensor slice: {len(payload)} != {slice_len}")

def s8(byte: int) -> int:
    return byte if byte < 128 else byte - 256

def q6k_at(data: bytes, i: int) -> float:
    ql = data[:128]
    qh = data[128:192]
    scales = data[192:208]
    d = float(struct.unpack("<e", data[208:210])[0])
    h = i // 128
    wi = i % 128
    l = wi % 32
    g = wi // 32
    is_ = l // 16
    qlidx = h * 64 + l + (g % 2) * 32
    nib = ql[qlidx] % 16 if g // 2 == 0 else ql[qlidx] // 16
    hi = (qh[h * 32 + l] // (4 ** g)) % 4
    quant = nib + hi * 16 - 32
    scale = s8(scales[h * 8 + is_ + 2 * g])
    return d * scale * quant

def micro(value: float) -> int:
    return round(value * 1_000_000.0)

q0 = micro(q6k_at(payload, 0))
q31 = micro(q6k_at(payload, 31))
q255 = micro(q6k_at(payload, 255))
dot1 = q0
dot4 = micro(
    q6k_at(payload, 0) * 1.0
    + q6k_at(payload, 1) * -0.5
    + q6k_at(payload, 2) * 0.5
    + q6k_at(payload, 3) * 2.0
)
slice_sha = hashlib.sha256(payload).hexdigest()
file_size = int(receipt["size_bytes"])
dim0 = int((tensor.get("dims") or [0])[0])
line = (
    f"gguf-tensor-slice-math-v1 {slice_sha} {gguf_path} token_embd.weight "
    f"{int(tensor['index'])} 14 {dim0} {absolute_start} {slice_len} {file_size} "
    f"{q0} {q31} {q255} {dot1} {dot4}\n"
)
manifest_runtime.write_text(line, encoding="utf-8")
manifest_trace.write_text(line, encoding="utf-8")
slice_source.write_text(
    json.dumps(
        {
            "gguf_path": str(gguf_path),
            "gguf_size_bytes": file_size,
            "tensor": tensor,
            "slice_len": slice_len,
            "slice_sha256": slice_sha,
            "expected_q6k_micro": {
                "sample0": q0,
                "sample31": q31,
                "sample255": q255,
                "dot1": dot1,
                "dot4": dot4,
            },
            "claim": "token_embd.weight first Q6_K superblock from full real GGUF",
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
slice_hex.write_text(" ".join(f"{b:02x}" for b in payload) + "\n", encoding="ascii")
PY

artifact="$ARTIFACT_DIR/form-cli-full-gguf-tensor-slice-math"
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
gguf-tensor-slice-math $manifest_runtime
quit
EOF
tr -d '\r' < "$WORK/runtime.raw" > "$WORK/runtime.out"

grep -q '^gguf_tensor_slice_verified=true$' "$WORK/runtime.out"
grep -q '^gguf_tensor_slice_source=content-addressed-full-gguf-slice-manifest$' "$WORK/runtime.out"
grep -q '^gguf_tensor_math_source=fkwu-read_file_slice-to-form-q6k-math$' "$WORK/runtime.out"
grep -q '^gguf_tensor_name=token_embd.weight$' "$WORK/runtime.out"
grep -q '^gguf_tensor_type=14$' "$WORK/runtime.out"
grep -q '^gguf_tensor_slice_len=210$' "$WORK/runtime.out"
grep -q '^gguf_tensor_slice_read_len=210$' "$WORK/runtime.out"
grep -q '^q6k_expected_sample0_micro=' "$WORK/runtime.out"
grep -q '^q6k_expected_sample31_micro=' "$WORK/runtime.out"
grep -q '^q6k_expected_sample255_micro=' "$WORK/runtime.out"
grep -q '^q6k_expected_dot1_micro=' "$WORK/runtime.out"
grep -q '^q6k_expected_dot4_micro=' "$WORK/runtime.out"
grep -q '^q6k_full_load_len=256$' "$WORK/runtime.out"
grep -q '^PASS fkwu-form-cli-full-gguf-tensor-slice-math$' "$WORK/runtime.out"

http_or_ollama="absent"
if grep -Eiq '(^|[[:space:]=])(https?://|ollama)([[:space:]]|$)' "$WORK/runtime.out"; then
    http_or_ollama="present"
fi

denied_toolchain_names_visible_on_path=0
denied_toolchain_names_visible=""
for name in go rustc cargo python python3 clang cc gcc sh bash curl ollama; do
    if [[ -x "$empty_path/$name" ]]; then
        denied_toolchain_names_visible_on_path=$((denied_toolchain_names_visible_on_path + 1))
        denied_toolchain_names_visible="${denied_toolchain_names_visible}${denied_toolchain_names_visible:+,}${name}"
    fi
done
{
    printf 'runtime_path_sanitized=true\n'
    printf 'http_or_ollama=%s\n' "$http_or_ollama"
    printf 'denied_toolchain_names_visible_on_path=%s\n' "$denied_toolchain_names_visible_on_path"
    printf 'denied_toolchain_names_visible=%s\n' "${denied_toolchain_names_visible:-none}"
} >> "$WORK/runtime.out"

extract_value() {
    local key="$1"
    awk -F= -v key="$key" '$1 == key { print $2; exit }' "$WORK/runtime.out"
}

trace_sha="$(hash_files_digest "$WORK/runtime.out" "$WORK/build.out" "$WORK/gguf-weight-map.out" "$manifest_trace" "$slice_source" "$slice_hex")"

sanitize_trace_file() {
    local src="$1"
    local dst="$2"
    LC_ALL=C sed -E \
        -e "s|$ROOT|<repo>|g" \
        -e "s|$HOME|<home>|g" \
        -e 's|<home>/.ollama/models/blobs/sha256-[0-9a-fA-F]+|<local-gguf-blob>|g' \
        -e 's|<home>/mentor-install/.models/[^"[:space:]]+|<local-gguf-file>|g' \
        -e 's|/private/var/folders/[^[:space:]:]+|<tmp>|g' \
        -e 's|/var/folders/[^[:space:]:]+|<tmp>|g' \
        -e 's/^ +\t/\t/' \
        -e 's/[[:blank:]]+$//' \
        "$src" > "$dst"
}

TRACE_REPORT_DIR="$WORK"
if [[ -n "$PUBLISH_TRACE_DIR" ]]; then
    mkdir -p "$PUBLISH_TRACE_DIR"
    sanitize_trace_file "$WORK/runtime.out" "$PUBLISH_TRACE_DIR/runtime.out"
    sanitize_trace_file "$WORK/build.out" "$PUBLISH_TRACE_DIR/build.out"
    sanitize_trace_file "$WORK/gguf-weight-map.out" "$PUBLISH_TRACE_DIR/gguf-weight-map.out"
    sanitize_trace_file "$manifest_trace" "$PUBLISH_TRACE_DIR/gguf-tensor-slice-manifest.txt"
    sanitize_trace_file "$slice_source" "$PUBLISH_TRACE_DIR/tensor-slice-source.json"
    cp "$slice_hex" "$PUBLISH_TRACE_DIR/tensor-slice.hex"
    TRACE_REPORT_DIR="$PUBLISH_TRACE_DIR"
fi

branch="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
commit="$(git -C "$ROOT" rev-parse HEAD)"
runtime_rel="${TRACE_REPORT_DIR#"$ROOT/"}/runtime.out"
build_rel="${TRACE_REPORT_DIR#"$ROOT/"}/build.out"
map_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-weight-map.out"
manifest_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-tensor-slice-manifest.txt"
source_rel="${TRACE_REPORT_DIR#"$ROOT/"}/tensor-slice-source.json"
hex_rel="${TRACE_REPORT_DIR#"$ROOT/"}/tensor-slice.hex"
artifact_rel="${artifact#"$ROOT/"}"

jq -n \
    --arg trace_id "$RUN_ID" \
    --arg branch "$branch" \
    --arg commit "$commit" \
    --arg trace_sha "$trace_sha" \
    --arg runtime_out "$runtime_rel" \
    --arg build_out "$build_rel" \
    --arg map_out "$map_rel" \
    --arg manifest "$manifest_rel" \
    --arg slice_source "$source_rel" \
    --arg slice_hex "$hex_rel" \
    --arg artifact "$artifact_rel" \
    --arg http_or_ollama "$http_or_ollama" \
    --arg slice_sha "$(extract_value gguf_tensor_slice_sha256)" \
    --arg expected_slice_sha "$(extract_value gguf_tensor_slice_expected_sha256)" \
    --arg tensor_name "$(extract_value gguf_tensor_name)" \
    --argjson denied "$denied_toolchain_names_visible_on_path" \
    --argjson tensor_index "$(extract_value gguf_tensor_index)" \
    --argjson tensor_type "$(extract_value gguf_tensor_type)" \
    --argjson tensor_dim0 "$(extract_value gguf_tensor_dim0)" \
    --argjson tensor_absolute_start "$(extract_value gguf_tensor_absolute_start)" \
    --argjson slice_len "$(extract_value gguf_tensor_slice_len)" \
    --argjson slice_read_len "$(extract_value gguf_tensor_slice_read_len)" \
    --argjson file_size_expected "$(extract_value gguf_file_size_expected)" \
    --argjson file_size_observed "$(extract_value gguf_file_size_observed)" \
    --argjson q0 "$(extract_value q6k_sample0_micro)" \
    --argjson q31 "$(extract_value q6k_sample31_micro)" \
    --argjson q255 "$(extract_value q6k_sample255_micro)" \
    --argjson dot1 "$(extract_value q6k_dot1_micro)" \
    --argjson dot4 "$(extract_value q6k_dot4_micro)" \
    --argjson exp_q0 "$(extract_value q6k_expected_sample0_micro)" \
    --argjson exp_q31 "$(extract_value q6k_expected_sample31_micro)" \
    --argjson exp_q255 "$(extract_value q6k_expected_sample255_micro)" \
    --argjson exp_dot1 "$(extract_value q6k_expected_dot1_micro)" \
    --argjson exp_dot4 "$(extract_value q6k_expected_dot4_micro)" \
    --argjson full_len "$(extract_value q6k_full_load_len)" \
    '{
      trace_id: $trace_id,
      receipt_kind: "fkwu-form-cli-full-gguf-tensor-slice-math-receipt",
      thread_branch: $branch,
      git_commit: $commit,
      runtime: {
        owner: "fkwu-form-cli",
        verb: "gguf-tensor-slice-math",
        path_sanitized: true,
        denied_toolchain_names_visible_on_path: $denied,
        http_or_ollama: $http_or_ollama
      },
      artifacts: {
        compiled_artifact: $artifact,
        runtime_out: $runtime_out,
        build_out: $build_out,
        gguf_weight_map_out: $map_out,
        manifest_trace: $manifest,
        tensor_slice_source: $slice_source,
        tensor_slice_hex: $slice_hex
      },
      observed: {
        full_real_gguf_file_observed: true,
        tensor_name: $tensor_name,
        tensor_index: $tensor_index,
        tensor_type: $tensor_type,
        tensor_dim0: $tensor_dim0,
        tensor_absolute_start: $tensor_absolute_start,
        tensor_slice_len: $slice_len,
        tensor_slice_read_len: $slice_read_len,
        gguf_file_size_expected: $file_size_expected,
        gguf_file_size_observed: $file_size_observed,
        tensor_slice_sha256: $slice_sha,
        tensor_slice_expected_sha256: $expected_slice_sha,
        q6k_sample0_micro: $q0,
        q6k_sample31_micro: $q31,
        q6k_sample255_micro: $q255,
        q6k_dot1_micro: $dot1,
        q6k_dot4_micro: $dot4,
        q6k_expected_sample0_micro: $exp_q0,
        q6k_expected_sample31_micro: $exp_q31,
        q6k_expected_sample255_micro: $exp_q255,
        q6k_expected_dot1_micro: $exp_dot1,
        q6k_expected_dot4_micro: $exp_dot4,
        q6k_full_load_len: $full_len,
        verdict: "PASS fkwu-form-cli-full-gguf-tensor-slice-math"
      },
      path_claim: {
        proven_now: "a named tensor row from the full real GGUF map feeds a content-addressed byte window into fkwu form-cli; form-cli reads the slice with read_file_slice and runs Q6_K Form dequant/dot math",
        not_claimed: [
          "the whole real Llama tensor set is loaded into accelerator buffers",
          "full real Llama autoregressive token generation",
          "logit projection over the real vocabulary",
          "decoded tokens from the real tokenizer arrays",
          "Android Vulkan or Windows DirectML/D3D12 execution"
        ]
      },
      trace_sha256: $trace_sha
    }' > "$RECEIPT"

printf 'receipt=%s\n' "$RECEIPT"
printf 'trace_id=%s\n' "$RUN_ID"
printf 'gguf_tensor_slice_sha256=%s\n' "$(extract_value gguf_tensor_slice_sha256)"
sed -n '1,22p' "$WORK/runtime.out"
