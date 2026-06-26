#!/usr/bin/env bash
# fkwu_form_cli_gguf_fullwidth_logits_receipt.sh -- prove fkwu/Form can
# generate a full-width GGUF token-logit projection row and decode its argmax.
#
# Runtime path under proof:
#   form-cli -> gguf-fullwidth-logits-cell <manifest>
#
# The shell/Python code here is the receipt harness only. The observed child
# runtime is the self-contained fkwu form-cli binary, launched with an empty
# PATH; it walks every tokenizer row in token_embd.weight through read_file_slice,
# computes the Q6_K dot4 projection in Form, performs full-vocabulary argmax,
# and decodes the winning real GGUF tokenizer string. This closes the
# candidate-only semantic-token gap while keeping full hidden-state Llama
# generation explicitly pending.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-gguf-fullwidth-logits-$STAMP/receipt.json"
RECEIPT="${1:-$DEFAULT_RECEIPT}"
GGUF_PATH="${2:-}"
if [[ "$RECEIPT" != /* ]]; then
    RECEIPT="$ROOT/$RECEIPT"
fi
RUN_ID="fkwu-gguf-fullwidth-logits-$STAMP"
ARTIFACT_DIR="$ROOT/.cache/body-test-receipts/$RUN_ID/artifact"
WORK="$ROOT/.cache/body-test-receipts/$RUN_ID/trace"
PUBLISH_TRACE_DIR="${PUBLISH_TRACE_DIR:-}"

if [[ -z "$PUBLISH_TRACE_DIR" && "$RECEIPT" == "$ROOT/docs/system_audit/"* ]]; then
    PUBLISH_TRACE_DIR="${RECEIPT%.json}_trace"
fi

mkdir -p "$ARTIFACT_DIR" "$WORK" "$(dirname "$RECEIPT")"
command -v python3 >/dev/null 2>&1 || { echo "missing receipt harness tool: python3" >&2; exit 2; }

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

map_json="$WORK/gguf-weight-map.json"
if [[ -n "$GGUF_PATH" ]]; then
    python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$map_json" "$GGUF_PATH" > "$WORK/gguf-weight-map.out"
else
    python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$map_json" > "$WORK/gguf-weight-map.out"
fi

manifest_runtime="$ARTIFACT_DIR/gguf-fullwidth-logits.manifest"
manifest_trace="$WORK/gguf-fullwidth-logits-manifest.txt"
source_json="$WORK/fullwidth-logits-source.json"
token_hex="$WORK/fullwidth-token.hex"

python3 - "$map_json" "$manifest_runtime" "$manifest_trace" "$source_json" "$token_hex" <<'PY'
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path
from typing import Any, BinaryIO

map_path = Path(sys.argv[1])
manifest_runtime = Path(sys.argv[2])
manifest_trace = Path(sys.argv[3])
source_json = Path(sys.argv[4])
token_hex = Path(sys.argv[5])

receipt = json.loads(map_path.read_text(encoding="utf-8"))
if receipt.get("verdict") != "pass":
    raise SystemExit("GGUF weight-map receipt did not pass")

gguf_path = Path(receipt["path"])
gguf_path_text = str(gguf_path)
if " " in gguf_path_text:
    raise SystemExit("GGUF path contains spaces; current Form manifest carrier is space-tokenized")
file_size = int(receipt["size_bytes"])

focus = receipt["tensor_map"]["focus_tensors"]
tensor = focus.get("token_embd.weight")
if tensor is None:
    raise SystemExit("token_embd.weight not present in GGUF focus tensor map")
if tensor.get("type") != "Q6_K" or int(tensor.get("ggml_type")) != 14:
    raise SystemExit(f"token_embd.weight is not Q6_K: {tensor}")
dims = [int(x) for x in tensor["dims"]]
if len(dims) < 2:
    raise SystemExit(f"token_embd.weight dims are not two-dimensional: {dims}")
dim0, token_count = dims[0], dims[1]
byte_length = int(tensor["byte_length_by_next_offset"])
if byte_length % token_count != 0:
    raise SystemExit("token_embd.weight byte length does not divide by tokenizer count")
row_stride = byte_length // token_count
block_len = 210
if dim0 % 256 != 0 or row_stride < block_len:
    raise SystemExit(f"unexpected Q6_K token_embd layout dim0={dim0} row_stride={row_stride}")
tensor_start = int(tensor["absolute_start"])
tensor_index = int(tensor["index"])
tensor_type = int(tensor["ggml_type"])


def read_exact(f: BinaryIO, n: int) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise EOFError(f"short read at {f.tell()} expected {n}, got {len(data)}")
    return data


def read_u32(f: BinaryIO) -> int:
    return int.from_bytes(read_exact(f, 4), "little", signed=False)


def read_u64(f: BinaryIO) -> int:
    return int.from_bytes(read_exact(f, 8), "little", signed=False)


def read_string_bytes(f: BinaryIO) -> bytes:
    length = read_u64(f)
    return read_exact(f, length)


def skip_scalar(f: BinaryIO, value_type: int) -> None:
    fixed = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
    if value_type == 8:
        _ = read_string_bytes(f)
        return
    if value_type in fixed:
        f.seek(fixed[value_type], 1)
        return
    raise ValueError(f"unsupported scalar metadata type {value_type}")


def skip_array(f: BinaryIO, element_type: int, count: int) -> None:
    fixed = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
    if element_type in fixed:
        f.seek(fixed[element_type] * count, 1)
        return
    if element_type == 8:
        for _ in range(count):
            _ = read_string_bytes(f)
        return
    if element_type == 9:
        for _ in range(count):
            nested_type = read_u32(f)
            nested_count = read_u64(f)
            skip_array(f, nested_type, nested_count)
        return
    raise ValueError(f"unsupported array element type {element_type}")


def skip_value(f: BinaryIO, value_type: int) -> None:
    if value_type == 9:
        element_type = read_u32(f)
        count = read_u64(f)
        skip_array(f, element_type, count)
    else:
        skip_scalar(f, value_type)


def s8(value: int) -> int:
    return value if value < 128 else value - 256


def q6k_mod(a: int, n: int) -> int:
    return a - (a // n) * n


def q6k_h(i: int) -> int:
    return i // 128


def q6k_wi(i: int) -> int:
    return q6k_mod(i, 128)


def q6k_l(i: int) -> int:
    return q6k_mod(q6k_wi(i), 32)


def q6k_g(i: int) -> int:
    return q6k_wi(i) // 32


def q6k_is(i: int) -> int:
    return q6k_l(i) // 16


def q6k_qlidx(i: int) -> int:
    return q6k_h(i) * 64 + q6k_l(i) + q6k_mod(q6k_g(i), 2) * 32


def q6k_nib(i: int, ql: bytes) -> int:
    return q6k_mod(ql[q6k_qlidx(i)], 16) if q6k_g(i) // 2 == 0 else ql[q6k_qlidx(i)] // 16


def q6k_hi(i: int, qh: bytes) -> int:
    return q6k_mod(qh[q6k_h(i) * 32 + q6k_l(i)] // (4 ** q6k_g(i)), 4)


def q6k_q(i: int, ql: bytes, qh: bytes) -> int:
    return q6k_nib(i, ql) + q6k_hi(i, qh) * 16 - 32


def q6k_scale(i: int, scales: bytes) -> int:
    return s8(scales[q6k_h(i) * 8 + q6k_is(i) + 2 * q6k_g(i)])


def q6k_at(block: bytes, i: int) -> float:
    ql = block[:128]
    qh = block[128:192]
    scales = block[192:208]
    d = struct.unpack("<e", block[208:210])[0]
    return d * q6k_scale(i, scales) * q6k_q(i, ql, qh)


def dot4_micro(block: bytes) -> int:
    value = (
        q6k_at(block, 0) * 1.0
        + q6k_at(block, 1) * -0.5
        + q6k_at(block, 2) * 0.5
        + q6k_at(block, 3) * 2.0
    )
    return int(round(value * 1_000_000))


def token_record(index: int, entry_start: int, data: bytes) -> dict[str, Any]:
    return {
        "token_id": index,
        "token_array_index": index,
        "token_entry_start": entry_start,
        "token_text_start": entry_start + 8,
        "token_len": len(data),
        "token_sha256": hashlib.sha256(data).hexdigest(),
        "token_text": data.decode("utf-8", "replace"),
        "token_hex": data.hex(),
    }


best_id = 0
best_logit = -(2**63)
samples: list[dict[str, int]] = []
with gguf_path.open("rb") as f:
    for token_id in range(token_count):
        f.seek(tensor_start + token_id * row_stride)
        block = read_exact(f, block_len)
        logit = dot4_micro(block)
        if token_id < 8:
            samples.append({"token_id": token_id, "logit_micro": logit})
        if logit > best_logit:
            best_id = token_id
            best_logit = logit

with gguf_path.open("rb") as f:
    magic = read_u32(f)
    version = read_u32(f)
    tensor_count_header = read_u64(f)
    kv_count = read_u64(f)
    if magic != 0x46554747:
        raise SystemExit("not a GGUF file")

    selected = None
    tokenizer_array_metadata_offset = -1
    tokenizer_count = 0
    for _ in range(kv_count):
        key = read_string_bytes(f).decode("utf-8", "replace")
        value_type = read_u32(f)
        if key == "tokenizer.ggml.tokens":
            tokenizer_array_metadata_offset = f.tell()
            if value_type != 9:
                raise SystemExit("tokenizer.ggml.tokens is not a GGUF array")
            element_type = read_u32(f)
            tokenizer_count = read_u64(f)
            if element_type != 8:
                raise SystemExit("tokenizer.ggml.tokens is not an array of strings")
            if tokenizer_count != token_count:
                raise SystemExit(f"tokenizer count {tokenizer_count} != tensor width {token_count}")
            for index in range(tokenizer_count):
                entry_start = f.tell()
                length = read_u64(f)
                text = read_exact(f, length)
                if index == best_id:
                    selected = token_record(index, entry_start, text)
                    break
            break
        skip_value(f, value_type)

if selected is None or tokenizer_array_metadata_offset < 0:
    raise SystemExit("selected tokenizer row was not found")

projection_name = "token_embd_q6k_dot4_fullwidth"
canonical = (
    "gguf-fullwidth-logits-cell-v1 "
    f"{gguf_path_text} {file_size} {token_count} {best_id} {best_logit} "
    f"{selected['token_array_index']} {selected['token_entry_start']} "
    f"{selected['token_len']} {selected['token_sha256']} "
    f"token_embd.weight {tensor_index} {tensor_type} {tensor_start} {row_stride} {block_len} "
    f"{projection_name}"
)
manifest_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
manifest = f"gguf-fullwidth-logits-cell-v1 {manifest_sha} " + canonical.split(" ", 1)[1] + "\n"

manifest_runtime.write_text(manifest, encoding="utf-8")
manifest_trace.write_text(manifest, encoding="utf-8")
source_json.write_text(
    json.dumps(
        {
            "gguf_path": gguf_path_text,
            "gguf_size_bytes": file_size,
            "gguf_header": {
                "version": version,
                "tensor_count": tensor_count_header,
                "metadata_kv_count": kv_count,
            },
            "tokenizer_array": {
                "key": "tokenizer.ggml.tokens",
                "metadata_value_offset": tokenizer_array_metadata_offset,
                "count": tokenizer_count,
            },
            "source_tensor": {
                "name": "token_embd.weight",
                "index": tensor_index,
                "ggml_type": tensor_type,
                "type": tensor["type"],
                "dims": dims,
                "absolute_start": tensor_start,
                "row_stride_bytes": row_stride,
                "q6k_block_len": block_len,
                "byte_length_by_next_offset": byte_length,
            },
            "projection": {
                "name": projection_name,
                "formula": "round(1*w0 + -0.5*w1 + 0.5*w2 + 2*w3) * 1e6",
                "vocab_width": token_count,
                "argmax_token_id": best_id,
                "argmax_logit_micro": best_logit,
                "samples": samples,
            },
            "selected_token": selected,
            "canonical_sha256_material": canonical,
            "manifest_sha256": manifest_sha,
            "claim": "fkwu/Form walks every token_embd.weight row in the real GGUF and computes a full-width projection argmax",
            "boundary": "full-width token-embedding projection logits are observed; full hidden-state 28-layer Llama generation remains pending",
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
token_hex.write_text(selected["token_hex"] + "\n", encoding="ascii")
PY

artifact="$ARTIFACT_DIR/form-cli-gguf-fullwidth-logits"
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
gguf-fullwidth-logits-cell $manifest_runtime
quit
EOF
tr -d '\r' < "$WORK/runtime.raw" > "$WORK/runtime.out"

grep -q '^full_width_model_logit_generation_verified=true$' "$WORK/runtime.out"
grep -q '^full_width_logit_generation_source=fkwu-read_file_slice-real-gguf-token-embedding-q6k-dot4$' "$WORK/runtime.out"
grep -q '^full_width_logit_generation_scope=full-vocabulary-real-gguf-token-embedding-projection$' "$WORK/runtime.out"
grep -q '^full_width_logit_count=128256$' "$WORK/runtime.out"
grep -q '^full_width_argmax_token_id=' "$WORK/runtime.out"
grep -q '^full_width_selected_token_id=' "$WORK/runtime.out"
grep -q '^full_width_selected_logit_micro=' "$WORK/runtime.out"
grep -q '^decoded_token_text=' "$WORK/runtime.out"
grep -q '^full_width_logits_generated_in_form=true$' "$WORK/runtime.out"
grep -q '^full_width_model_logits=true$' "$WORK/runtime.out"
grep -q '^full_vocabulary_logits=true$' "$WORK/runtime.out"
grep -q '^full_model_logits=false$' "$WORK/runtime.out"
grep -q '^full_llama_hidden_state_logits=false$' "$WORK/runtime.out"
grep -q '^full_width_logit_accelerator_buffers=false$' "$WORK/runtime.out"
grep -q '^PASS fkwu-form-cli-gguf-fullwidth-logits$' "$WORK/runtime.out"

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

trace_sha="$(hash_files_digest "$WORK/runtime.out" "$WORK/build.out" "$WORK/gguf-weight-map.out" "$manifest_trace" "$source_json" "$token_hex")"

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
    sanitize_trace_file "$manifest_trace" "$PUBLISH_TRACE_DIR/gguf-fullwidth-logits-manifest.txt"
    sanitize_trace_file "$source_json" "$PUBLISH_TRACE_DIR/fullwidth-logits-source.json"
    cp "$token_hex" "$PUBLISH_TRACE_DIR/fullwidth-token.hex"
    TRACE_REPORT_DIR="$PUBLISH_TRACE_DIR"
fi

branch="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
commit="$(git -C "$ROOT" rev-parse HEAD)"
runtime_rel="${TRACE_REPORT_DIR#"$ROOT/"}/runtime.out"
build_rel="${TRACE_REPORT_DIR#"$ROOT/"}/build.out"
map_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-weight-map.out"
manifest_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-fullwidth-logits-manifest.txt"
source_rel="${TRACE_REPORT_DIR#"$ROOT/"}/fullwidth-logits-source.json"
hex_rel="${TRACE_REPORT_DIR#"$ROOT/"}/fullwidth-token.hex"
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
    --arg source "$source_rel" \
    --arg token_hex "$hex_rel" \
    --arg artifact "$artifact_rel" \
    --arg http_or_ollama "$http_or_ollama" \
    --arg sha "$(extract_value full_width_logit_generation_sha256)" \
    --arg expected_sha "$(extract_value full_width_logit_generation_expected_sha256)" \
    --arg token_sha "$(extract_value full_width_token_text_sha256)" \
    --arg expected_token_sha "$(extract_value full_width_token_text_expected_sha256)" \
    --arg decoded_token "$(extract_value decoded_token_text)" \
    --arg count "$(extract_value full_width_logit_count)" \
    --arg argmax_id "$(extract_value full_width_argmax_token_id)" \
    --arg selected_id "$(extract_value full_width_selected_token_id)" \
    --arg selected_logit "$(extract_value full_width_selected_logit_micro)" \
    --arg expected_selected_logit "$(extract_value full_width_expected_selected_logit_micro)" \
    --arg tensor_name "$(extract_value full_width_logit_tensor_name)" \
    --arg tensor_index "$(extract_value full_width_logit_tensor_index)" \
    --arg tensor_type "$(extract_value full_width_logit_tensor_type)" \
    --arg tensor_start "$(extract_value full_width_logit_tensor_start)" \
    --arg row_stride "$(extract_value full_width_logit_row_stride)" \
    --arg block_len "$(extract_value full_width_logit_block_len)" \
    --arg runtime_path_sanitized "$(extract_value runtime_path_sanitized)" \
    --arg denied_visible "$(extract_value denied_toolchain_names_visible_on_path)" \
    '{
      receipt_kind: "fkwu-form-cli-gguf-fullwidth-logits-receipt",
      trace_id: $trace_id,
      branch: $branch,
      commit: $commit,
      trace_sha256: $trace_sha,
      runtime: {
        verb: "gguf-fullwidth-logits-cell",
        artifact: $artifact,
        runtime_path_sanitized: ($runtime_path_sanitized == "true"),
        http_or_ollama: $http_or_ollama,
        denied_toolchain_names_visible_on_path: ($denied_visible | tonumber)
      },
      observed: {
        full_width_model_logit_generation_verified: true,
        full_width_logits_generated_in_form: true,
        full_width_model_logits: true,
        full_vocabulary_logits: true,
        full_model_logits: false,
        full_llama_hidden_state_logits: false,
        full_width_logit_accelerator_buffers: false,
        full_width_logit_count: ($count | tonumber),
        full_width_argmax_token_id: ($argmax_id | tonumber),
        full_width_selected_token_id: ($selected_id | tonumber),
        full_width_selected_logit_micro: ($selected_logit | tonumber),
        full_width_expected_selected_logit_micro: ($expected_selected_logit | tonumber),
        decoded_token_text: $decoded_token,
        full_width_logit_generation_sha256: $sha,
        full_width_logit_generation_expected_sha256: $expected_sha,
        full_width_token_text_sha256: $token_sha,
        full_width_token_text_expected_sha256: $expected_token_sha
      },
      source_tensor: {
        name: $tensor_name,
        index: ($tensor_index | tonumber),
        ggml_type: ($tensor_type | tonumber),
        absolute_start: ($tensor_start | tonumber),
        row_stride_bytes: ($row_stride | tonumber),
        q6k_block_len: ($block_len | tonumber)
      },
      traces: {
        runtime_out: $runtime_out,
        build_out: $build_out,
        gguf_weight_map_out: $map_out,
        manifest: $manifest,
        source: $source,
        token_hex: $token_hex
      },
      claim_boundary: {
        closed: "full-width token-embedding projection argmax generated inside fkwu/Form over the complete GGUF vocabulary",
        still_pending: "full hidden-state 28-layer Llama decode logits and Metal accelerator-buffer placement"
      },
      verdict: "PASS fkwu-form-cli-gguf-fullwidth-logits"
    }' > "$RECEIPT"

printf 'receipt: %s\n' "$RECEIPT"
printf 'trace: %s\n' "$TRACE_REPORT_DIR"
printf 'full_width_logit_count=%s\n' "$(extract_value full_width_logit_count)"
printf 'full_width_argmax_token_id=%s\n' "$(extract_value full_width_argmax_token_id)"
printf 'full_width_selected_logit_micro=%s\n' "$(extract_value full_width_selected_logit_micro)"
printf 'decoded_token_text=%s\n' "$(extract_value decoded_token_text)"
printf 'verdict: PASS fkwu-form-cli-gguf-fullwidth-logits\n'
