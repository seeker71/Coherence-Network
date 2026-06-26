#!/usr/bin/env bash
# fkwu_form_cli_gguf_semantic_token_generation_receipt.sh -- prove one real
# GGUF tokenizer string can be selected by Form argmax and decoded by fkwu.
#
# Runtime path under proof:
#   form-cli -> gguf-semantic-token-cell <manifest>
#
# The shell/Python code here is the receipt harness only. The observed child
# runtime is the self-contained fkwu form-cli binary, launched with an empty PATH;
# it reads the declared tokenizer string entry with read_file_slice, verifies the
# token bytes in Form, performs greedy argmax over the manifest logits in Form,
# and emits decoded_token_text. This does not claim full model logits or full
# real Llama token generation.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-gguf-semantic-token-generation-$STAMP/receipt.json"
RECEIPT="${1:-$DEFAULT_RECEIPT}"
GGUF_PATH="${2:-}"
if [[ "$RECEIPT" != /* ]]; then
    RECEIPT="$ROOT/$RECEIPT"
fi
RUN_ID="fkwu-gguf-semantic-token-generation-$STAMP"
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

manifest_runtime="$ARTIFACT_DIR/gguf-semantic-token.manifest"
manifest_trace="$WORK/gguf-semantic-token-manifest.txt"
semantic_source="$WORK/semantic-token-source.json"
token_hex="$WORK/semantic-token.hex"

python3 - "$map_json" "$manifest_runtime" "$manifest_trace" "$semantic_source" "$token_hex" <<'PY'
from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path
from typing import BinaryIO, Any

map_path = Path(sys.argv[1])
manifest_runtime = Path(sys.argv[2])
manifest_trace = Path(sys.argv[3])
semantic_source = Path(sys.argv[4])
token_hex = Path(sys.argv[5])

receipt = json.loads(map_path.read_text(encoding="utf-8"))
if receipt.get("verdict") != "pass":
    raise SystemExit("GGUF weight-map receipt did not pass")

gguf_path = Path(receipt["path"])
gguf_path_text = str(gguf_path)
if " " in gguf_path_text:
    raise SystemExit("GGUF path contains spaces; current Form manifest carrier is space-tokenized")
file_size = int(receipt["size_bytes"])


def read_exact(f: BinaryIO, n: int) -> bytes:
    data = f.read(n)
    if len(data) != n:
        raise EOFError(f"short read at {f.tell()} expected {n}, got {len(data)}")
    return data


def read_u32(f: BinaryIO) -> int:
    return int.from_bytes(read_exact(f, 4), "little", signed=False)


def read_u64(f: BinaryIO) -> int:
    return int.from_bytes(read_exact(f, 8), "little", signed=False)


def read_string(f: BinaryIO) -> str:
    length = read_u64(f)
    return read_exact(f, length).decode("utf-8", "replace")


def skip_scalar(f: BinaryIO, value_type: int) -> None:
    fixed = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
    if value_type == 8:
        _ = read_string(f)
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
            _ = read_string(f)
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


def safe_token(data: bytes) -> bool:
    if not (2 <= len(data) <= 16):
        return False
    if data.startswith(b"<") or data.startswith(b"["):
        return False
    if any(b < 33 or b > 126 for b in data):
        return False
    return re.fullmatch(rb"[A-Za-z][A-Za-z0-9_\-]*", data) is not None


def token_record(index: int, entry_start: int, data: bytes) -> dict[str, Any]:
    return {
        "token_id": index,
        "token_array_index": index,
        "token_entry_start": entry_start,
        "token_text_start": entry_start + 8,
        "token_len": len(data),
        "token_sha256": hashlib.sha256(data).hexdigest(),
        "token_text": data.decode("ascii"),
        "token_hex": data.hex(),
    }


with gguf_path.open("rb") as f:
    magic = read_u32(f)
    version = read_u32(f)
    tensor_count = read_u64(f)
    kv_count = read_u64(f)
    if magic != 0x46554747:
        raise SystemExit("not a GGUF file")

    tokens: list[dict[str, Any]] = []
    preferred: dict[bytes, dict[str, Any]] = {}
    token_count = 0
    token_array_metadata_offset = -1
    for _ in range(kv_count):
        key = read_string(f)
        value_type = read_u32(f)
        if key == "tokenizer.ggml.tokens":
            token_array_metadata_offset = f.tell()
            if value_type != 9:
                raise SystemExit("tokenizer.ggml.tokens is not a GGUF array")
            element_type = read_u32(f)
            token_count = read_u64(f)
            if element_type != 8:
                raise SystemExit("tokenizer.ggml.tokens is not an array of strings")
            for index in range(token_count):
                entry_start = f.tell()
                length = read_u64(f)
                text = read_exact(f, length)
                if not safe_token(text):
                    continue
                rec = token_record(index, entry_start, text)
                tokens.append(rec)
                if text in {b"Hello", b"world", b"token", b"answer", b"form", b"coherence"}:
                    preferred[text] = rec
            break
        skip_value(f, value_type)

if token_count <= 0 or token_array_metadata_offset < 0:
    raise SystemExit("tokenizer.ggml.tokens array not found")
if len(tokens) < 4:
    raise SystemExit(f"too few safe tokenizer tokens found: {len(tokens)}")

selected = None
for name in (b"Hello", b"world", b"token", b"answer", b"form", b"coherence"):
    if name in preferred:
        selected = preferred[name]
        break
if selected is None:
    selected = tokens[0]

others = [row for row in tokens if row["token_id"] != selected["token_id"]][:3]
candidates = [
    {"token_id": int(others[0]["token_id"]), "token_text": others[0]["token_text"], "logit_micro": -8000},
    {"token_id": int(selected["token_id"]), "token_text": selected["token_text"], "logit_micro": 42000},
    {"token_id": int(others[1]["token_id"]), "token_text": others[1]["token_text"], "logit_micro": 21000},
    {"token_id": int(others[2]["token_id"]), "token_text": others[2]["token_text"], "logit_micro": -3000},
]

candidate_tokens: list[str] = []
for row in candidates:
    candidate_tokens.extend([str(row["token_id"]), str(row["logit_micro"])])

canonical = (
    "gguf-semantic-token-cell-v1 "
    f"{gguf_path_text} {file_size} {token_count} {selected['token_id']} "
    f"{selected['token_array_index']} {selected['token_entry_start']} "
    f"{selected['token_len']} {selected['token_sha256']} {len(candidates)} "
    + " ".join(candidate_tokens)
)
manifest_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
manifest = f"gguf-semantic-token-cell-v1 {manifest_sha} " + canonical.split(" ", 1)[1] + "\n"

manifest_runtime.write_text(manifest, encoding="utf-8")
manifest_trace.write_text(manifest, encoding="utf-8")
semantic_source.write_text(
    json.dumps(
        {
            "gguf_path": gguf_path_text,
            "gguf_size_bytes": file_size,
            "gguf_header": {
                "version": version,
                "tensor_count": tensor_count,
                "metadata_kv_count": kv_count,
            },
            "tokenizer_array": {
                "key": "tokenizer.ggml.tokens",
                "metadata_value_offset": token_array_metadata_offset,
                "count": token_count,
            },
            "selected_token": selected,
            "candidate_logits": candidates,
            "canonical_sha256_material": canonical,
            "manifest_sha256": manifest_sha,
            "claim": "one real GGUF tokenizer string row selected by Form greedy argmax and decoded by fkwu",
            "boundary": "candidate logits are receipt logits, not full model logits over the full vocabulary",
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
token_hex.write_text(selected["token_hex"] + "\n", encoding="ascii")
PY

artifact="$ARTIFACT_DIR/form-cli-gguf-semantic-token-generation"
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
gguf-semantic-token-cell $manifest_runtime
quit
EOF
tr -d '\r' < "$WORK/runtime.raw" > "$WORK/runtime.out"

grep -q '^semantic_token_generation_verified=true$' "$WORK/runtime.out"
grep -q '^semantic_generation_source=fkwu-read_file_slice-real-gguf-tokenizer-string-to-greedy-token$' "$WORK/runtime.out"
grep -q '^semantic_generation_scope=single-token-real-gguf-tokenizer-decode$' "$WORK/runtime.out"
grep -q '^semantic_selected_token_id=' "$WORK/runtime.out"
grep -q '^semantic_token_array_index=' "$WORK/runtime.out"
grep -q '^semantic_token_declared_len=' "$WORK/runtime.out"
grep -q '^semantic_token_read_len=' "$WORK/runtime.out"
grep -q '^semantic_argmax_token_id=' "$WORK/runtime.out"
grep -q '^decoded_token_text=' "$WORK/runtime.out"
grep -q '^full_model_logits=false$' "$WORK/runtime.out"
grep -q '^full_vocabulary_logits=false$' "$WORK/runtime.out"
grep -q '^semantic_token_accelerator_buffers=false$' "$WORK/runtime.out"
grep -q '^PASS fkwu-form-cli-gguf-semantic-token-generation$' "$WORK/runtime.out"

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

trace_sha="$(hash_files_digest "$WORK/runtime.out" "$WORK/build.out" "$WORK/gguf-weight-map.out" "$manifest_trace" "$semantic_source" "$token_hex")"

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
    sanitize_trace_file "$manifest_trace" "$PUBLISH_TRACE_DIR/gguf-semantic-token-manifest.txt"
    sanitize_trace_file "$semantic_source" "$PUBLISH_TRACE_DIR/semantic-token-source.json"
    cp "$token_hex" "$PUBLISH_TRACE_DIR/semantic-token.hex"
    TRACE_REPORT_DIR="$PUBLISH_TRACE_DIR"
fi

branch="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
commit="$(git -C "$ROOT" rev-parse HEAD)"
runtime_rel="${TRACE_REPORT_DIR#"$ROOT/"}/runtime.out"
build_rel="${TRACE_REPORT_DIR#"$ROOT/"}/build.out"
map_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-weight-map.out"
manifest_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-semantic-token-manifest.txt"
source_rel="${TRACE_REPORT_DIR#"$ROOT/"}/semantic-token-source.json"
hex_rel="${TRACE_REPORT_DIR#"$ROOT/"}/semantic-token.hex"
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
    --arg semantic_source "$source_rel" \
    --arg token_hex "$hex_rel" \
    --arg artifact "$artifact_rel" \
    --arg http_or_ollama "$http_or_ollama" \
    --arg semantic_sha "$(extract_value semantic_generation_sha256)" \
    --arg expected_semantic_sha "$(extract_value semantic_generation_expected_sha256)" \
    --arg token_sha "$(extract_value semantic_token_text_sha256)" \
    --arg expected_token_sha "$(extract_value semantic_token_text_expected_sha256)" \
    --arg decoded_token_text "$(extract_value decoded_token_text)" \
    --argjson denied "$denied_toolchain_names_visible_on_path" \
    --argjson selected_token_id "$(extract_value semantic_selected_token_id)" \
    --argjson token_array_index "$(extract_value semantic_token_array_index)" \
    --argjson token_count "$(extract_value gguf_tokenizer_token_count)" \
    --argjson token_entry_start "$(extract_value semantic_token_entry_start)" \
    --argjson token_text_start "$(extract_value semantic_token_text_start)" \
    --argjson token_text_len "$(extract_value semantic_token_text_len)" \
    --argjson candidate_count "$(extract_value semantic_candidate_count)" \
    --argjson argmax_token_id "$(extract_value semantic_argmax_token_id)" \
    --argjson selected_logit_micro "$(extract_value semantic_selected_logit_micro)" \
    '{
      receipt_kind: "fkwu-form-cli-gguf-semantic-token-generation-receipt",
      trace_id: $trace_id,
      thread_branch: $branch,
      git_commit: $commit,
      verdict: "pass",
      observed: {
        semantic_token_generation: true,
        semantic_generation_scope: "single-token-real-gguf-tokenizer-decode",
        real_gguf_tokenizer_string_row: true,
        greedy_argmax_in_form: true,
        full_model_logits: false,
        full_vocabulary_logits: false,
        accelerator_buffers: false,
        full_real_llama_gguf_generation: false,
        selected_token_id: $selected_token_id,
        token_array_index: $token_array_index,
        tokenizer_token_count: $token_count,
        token_entry_start: $token_entry_start,
        token_text_start: $token_text_start,
        token_text_len: $token_text_len,
        candidate_count: $candidate_count,
        argmax_token_id: $argmax_token_id,
        selected_logit_micro: $selected_logit_micro,
        decoded_token_text: $decoded_token_text,
        semantic_generation_sha256: $semantic_sha,
        semantic_generation_expected_sha256: $expected_semantic_sha,
        token_text_sha256: $token_sha,
        token_text_expected_sha256: $expected_token_sha
      },
      runtime_dependency_claim: {
        scope: "child fkwu form-cli runtime, not this shell harness",
        runtime_path_sanitized: true,
        http_or_ollama: $http_or_ollama,
        denied_go_rust_python_shell_clang_visible_on_path: $denied
      },
      artifacts: {
        compiled_artifact: $artifact,
        runtime_out: $runtime_out,
        build_out: $build_out,
        gguf_weight_map_out: $map_out,
        manifest_trace: $manifest,
        semantic_source: $semantic_source,
        token_hex: $token_hex
      },
      trace_sha256: $trace_sha,
      boundary: "This proves one semantic token decoded from real GGUF tokenizer bytes after Form argmax over receipt logits. It does not prove full model logits, full-vocabulary projection, complete tensor buffers, or full real Llama GGUF token generation."
    }' > "$RECEIPT"

printf 'receipt=%s\n' "$RECEIPT"
printf 'trace=%s\n' "$TRACE_REPORT_DIR"
printf 'semantic_token_generation_verified=true\n'
printf 'decoded_token_text=%s\n' "$(extract_value decoded_token_text)"
printf 'selected_token_id=%s\n' "$(extract_value semantic_selected_token_id)"
printf 'full_model_logits=false\n'
printf 'full_vocabulary_logits=false\n'
printf 'http_or_ollama=%s\n' "$http_or_ollama"
printf 'denied_toolchain_names_visible_on_path=%s\n' "$denied_toolchain_names_visible_on_path"
