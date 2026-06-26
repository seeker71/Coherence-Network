#!/usr/bin/env bash
# fkwu_form_cli_real_gguf_logit_token_generation_receipt.sh -- prove one real
# GGUF token can be selected from real token_embd.weight Q6_K row logits in Form.
#
# Runtime path under proof:
#   form-cli -> gguf-real-logit-token-cell <manifest>
#
# The shell/Python code here is the receipt harness only. It discovers local GGUF
# offsets and writes a content-addressed manifest. The observed child runtime is
# the self-contained fkwu form-cli binary, launched with an empty PATH; it reads
# the declared tokenizer strings and token_embd.weight rows with read_file_slice,
# verifies their content hashes in Form, computes candidate logits from real Q6_K
# rows in Form, and emits decoded_token_text. This does not claim the full
# multi-layer Llama forward pass or full-vocabulary logits.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/fkwu-real-gguf-logit-token-generation-$STAMP/receipt.json"
RECEIPT="${1:-$DEFAULT_RECEIPT}"
GGUF_PATH="${2:-}"
if [[ "$RECEIPT" != /* ]]; then
    RECEIPT="$ROOT/$RECEIPT"
fi
RUN_ID="fkwu-real-gguf-logit-token-generation-$STAMP"
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

manifest_runtime="$ARTIFACT_DIR/gguf-real-logit-token.manifest"
manifest_trace="$WORK/gguf-real-logit-token-manifest.txt"
source_json="$WORK/real-logit-token-source.json"
token_hex="$WORK/real-logit-token.hex"

python3 - "$map_json" "$manifest_runtime" "$manifest_trace" "$source_json" "$token_hex" <<'PY'
from __future__ import annotations

import hashlib
import json
import re
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


def q6k_mod(a: int, n: int) -> int:
    return a - (a // n) * n


def q6k_s8(b: int) -> int:
    return b if b < 128 else b - 256


def q6k_at(block: bytes, i: int) -> float:
    ql = block[0:128]
    qh = block[128:192]
    scales = block[192:208]
    d = struct.unpack("<e", block[208:210])[0]
    h = i // 128
    wi = q6k_mod(i, 128)
    l = q6k_mod(wi, 32)
    g = wi // 32
    is_ = l // 16
    qlidx = h * 64 + l + q6k_mod(g, 2) * 32
    nib = q6k_mod(ql[qlidx], 16) if (g // 2) == 0 else ql[qlidx] // 16
    hi = q6k_mod(qh[h * 32 + l] // (4**g), 4)
    q = nib + hi * 16 - 32
    sc = q6k_s8(scales[h * 8 + is_ + 2 * g])
    return float(d) * float(sc) * float(q)


def q6k_row_dot(a: bytes, b: bytes, n: int) -> float:
    total = 0.0
    for i in range(n):
        block_off = (i // 256) * 210
        inner = i % 256
        total += q6k_at(a[block_off : block_off + 210], inner) * q6k_at(
            b[block_off : block_off + 210], inner
        )
    return total


def q6k_row_block_set_sha(row: bytes) -> str:
    block_shas = [
        hashlib.sha256(row[off : off + 210]).hexdigest()
        for off in range(0, len(row), 210)
    ]
    return hashlib.sha256(" ".join(block_shas).encode("utf-8")).hexdigest()


def find_token_embd(tensor_map: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for key in ("first_by_data_offset", "last_by_data_offset"):
        for row in tensor_map.get(key) or []:
            if isinstance(row, dict):
                rows.append(row)
    for row in rows:
        if row.get("name") == "token_embd.weight":
            return row
    raise SystemExit("token_embd.weight row not found in GGUF weight-map receipt")


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
                if text in {
                    b"Hello",
                    b"world",
                    b"token",
                    b"answer",
                    b"form",
                    b"coherence",
                    b"local",
                    b"model",
                }:
                    preferred[text] = rec
            break
        skip_value(f, value_type)

if token_count <= 0 or token_array_metadata_offset < 0:
    raise SystemExit("tokenizer.ggml.tokens array not found")
if len(tokens) < 5:
    raise SystemExit(f"too few safe tokenizer tokens found: {len(tokens)}")

prompt = None
for name in (b"Hello", b"token", b"model", b"local", b"form"):
    if name in preferred:
        prompt = preferred[name]
        break
if prompt is None:
    prompt = tokens[0]

candidate_rows: list[dict[str, Any]] = []
for name in (b"world", b"answer", b"form", b"coherence", b"local", b"model", b"token"):
    row = preferred.get(name)
    if row is not None and row["token_id"] != prompt["token_id"] and row not in candidate_rows:
        candidate_rows.append(row)
for row in tokens:
    if len(candidate_rows) >= 4:
        break
    if row["token_id"] != prompt["token_id"] and row not in candidate_rows:
        candidate_rows.append(row)
candidate_rows = candidate_rows[:4]
if not candidate_rows:
    raise SystemExit("no candidate tokens selected")

token_embd = find_token_embd(receipt["tensor_map"])
if token_embd.get("type") != "Q6_K" or int(token_embd.get("ggml_type", -1)) != 14:
    raise SystemExit("token_embd.weight is not Q6_K in this receipt")
dims = [int(x) for x in token_embd.get("dims") or []]
if len(dims) != 2:
    raise SystemExit(f"unexpected token_embd.weight dims: {dims}")
embedding_dim, vocab_rows = dims[0], dims[1]
if int(vocab_rows) != int(token_count):
    raise SystemExit(f"token count {token_count} does not match token_embd rows {vocab_rows}")
row_bytes = int(token_embd["byte_length_by_next_offset"]) // int(vocab_rows)
if row_bytes % 210 != 0:
    raise SystemExit(f"token_embd row bytes {row_bytes} is not a Q6_K block multiple")
row_values = (row_bytes // 210) * 256
if row_values < embedding_dim:
    raise SystemExit(f"token_embd row values {row_values} shorter than embedding dim {embedding_dim}")
base = int(token_embd["absolute_start"])
proof_block_count = min(row_bytes // 210, 4)
proof_row_bytes = proof_block_count * 210
proof_embedding_dim = proof_block_count * 256


def row_start(token_id: int) -> int:
    return base + row_bytes * int(token_id)


def row_bytes_for(token_id: int) -> bytes:
    with gguf_path.open("rb") as f:
        f.seek(row_start(token_id))
        return read_exact(f, row_bytes)


prompt_row = row_bytes_for(int(prompt["token_id"]))
scored_candidates: list[dict[str, Any]] = []
for row in candidate_rows:
    emb = row_bytes_for(int(row["token_id"]))
    logit = q6k_row_dot(prompt_row[:proof_row_bytes], emb[:proof_row_bytes], proof_embedding_dim)
    scored = dict(row)
    scored.update(
        {
            "embedding_row_start": row_start(int(row["token_id"])),
            "embedding_row_bytes": proof_row_bytes,
            "embedding_row_block_set_sha256": q6k_row_block_set_sha(emb[:proof_row_bytes]),
            "logit": logit,
            "logit_micro": int(round(logit * 1_000_000.0)),
        }
    )
    scored_candidates.append(scored)

selected = max(scored_candidates, key=lambda row: row["logit"])
prompt_row_sha = q6k_row_block_set_sha(prompt_row[:proof_row_bytes])
prompt_row_start = row_start(int(prompt["token_id"]))

candidate_tokens: list[str] = []
for row in scored_candidates:
    candidate_tokens.extend(
        [
            str(row["token_id"]),
            str(row["token_entry_start"]),
            str(row["token_len"]),
            str(row["token_sha256"]),
            str(row["embedding_row_start"]),
            str(row["embedding_row_block_set_sha256"]),
        ]
    )

manifest_body = (
    "gguf-real-logit-token-cell-v1 "
    f"{gguf_path_text} {file_size} {token_count} {proof_embedding_dim} {proof_row_bytes} "
    f"{prompt['token_id']} {prompt['token_entry_start']} {prompt['token_len']} "
    f"{prompt['token_sha256']} {prompt_row_start} {prompt_row_sha} {len(scored_candidates)} "
    + " ".join(candidate_tokens)
)
canonical = (
    "gguf-real-logit-token-cell-v1 "
    f"{gguf_path_text} {file_size} {token_count} {proof_embedding_dim} {proof_row_bytes} "
    f"{prompt['token_id']} {len(scored_candidates)}"
)
manifest_sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
manifest = f"gguf-real-logit-token-cell-v1 {manifest_sha} " + manifest_body.split(" ", 1)[1] + "\n"

manifest_runtime.write_text(manifest, encoding="utf-8")
manifest_trace.write_text(manifest, encoding="utf-8")
source_json.write_text(
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
            "token_embd_weight": {
                "absolute_start": base,
                "byte_length": int(token_embd["byte_length_by_next_offset"]),
                "dims": dims,
                "type": token_embd["type"],
                "row_bytes": row_bytes,
                "row_values": row_values,
                "proof_block_count": proof_block_count,
                "proof_embedding_dim": proof_embedding_dim,
                "proof_row_bytes": proof_row_bytes,
            },
            "prompt_token": {
                **prompt,
                "embedding_row_start": prompt_row_start,
                "embedding_row_bytes": proof_row_bytes,
                "embedding_row_block_set_sha256": prompt_row_sha,
            },
            "candidate_logits": scored_candidates,
            "selected_token": selected,
            "canonical_sha256_material": canonical,
            "manifest_body": manifest_body,
            "manifest_sha256": manifest_sha,
            "claim": "one real token selected by Form logits computed from observed native-safe real GGUF token_embd.weight Q6_K row blocks",
            "boundary": "candidate token-embedding prefix logits only; current fkwu receipt safely observes four Q6_K blocks (1024 dims), not the full 12-block row, full transformer hidden-state projection, or full vocabulary",
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
token_hex.write_text(selected["token_hex"] + "\n", encoding="ascii")
PY

artifact="$ARTIFACT_DIR/form-cli-real-gguf-logit-token-generation"
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
gguf-real-logit-token-cell $manifest_runtime
quit
EOF
tr -d '\r' < "$WORK/runtime.raw" > "$WORK/runtime.out"

grep -q '^real_logit_token_generation_verified=true$' "$WORK/runtime.out"
grep -q '^real_logit_generation_source=fkwu-read_file_slice-real-token-embd-q6k-row-dot$' "$WORK/runtime.out"
grep -q '^real_logit_generation_scope=candidate-token-real-gguf-token-embedding-dot$' "$WORK/runtime.out"
grep -q '^gguf_token_embedding_dim=' "$WORK/runtime.out"
grep -q '^gguf_token_embedding_row_bytes=' "$WORK/runtime.out"
grep -q '^real_logit_candidate_count=' "$WORK/runtime.out"
grep -q '^real_logit_candidate_pass_count=' "$WORK/runtime.out"
grep -q '^real_logit_argmax_token_id=' "$WORK/runtime.out"
grep -q '^real_logit_selected_logit_micro=' "$WORK/runtime.out"
grep -q '^decoded_token_text=' "$WORK/runtime.out"
grep -q '^real_logits=true$' "$WORK/runtime.out"
grep -q '^full_model_logits=false$' "$WORK/runtime.out"
grep -q '^full_vocabulary_logits=false$' "$WORK/runtime.out"
grep -q '^real_logit_token_accelerator_buffers=false$' "$WORK/runtime.out"
grep -q '^PASS fkwu-form-cli-real-gguf-logit-token-generation$' "$WORK/runtime.out"

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
    sanitize_trace_file "$manifest_trace" "$PUBLISH_TRACE_DIR/gguf-real-logit-token-manifest.txt"
    sanitize_trace_file "$source_json" "$PUBLISH_TRACE_DIR/real-logit-token-source.json"
    cp "$token_hex" "$PUBLISH_TRACE_DIR/real-logit-token.hex"
    TRACE_REPORT_DIR="$PUBLISH_TRACE_DIR"
fi

branch="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)"
commit="$(git -C "$ROOT" rev-parse HEAD)"
runtime_rel="${TRACE_REPORT_DIR#"$ROOT/"}/runtime.out"
build_rel="${TRACE_REPORT_DIR#"$ROOT/"}/build.out"
map_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-weight-map.out"
manifest_rel="${TRACE_REPORT_DIR#"$ROOT/"}/gguf-real-logit-token-manifest.txt"
source_rel="${TRACE_REPORT_DIR#"$ROOT/"}/real-logit-token-source.json"
hex_rel="${TRACE_REPORT_DIR#"$ROOT/"}/real-logit-token.hex"
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
    --arg source_json "$source_rel" \
    --arg token_hex "$hex_rel" \
    --arg artifact "$artifact_rel" \
    --arg http_or_ollama "$http_or_ollama" \
    --arg generation_sha "$(extract_value real_logit_generation_sha256)" \
    --arg expected_generation_sha "$(extract_value real_logit_generation_expected_sha256)" \
    --arg decoded_token_text "$(extract_value decoded_token_text)" \
    --argjson denied "$denied_toolchain_names_visible_on_path" \
    --argjson token_count "$(extract_value gguf_tokenizer_token_count)" \
    --argjson embedding_dim "$(extract_value gguf_token_embedding_dim)" \
    --argjson row_bytes "$(extract_value gguf_token_embedding_row_bytes)" \
    --argjson prompt_token_id "$(extract_value prompt_token_id)" \
    --argjson candidate_count "$(extract_value real_logit_candidate_count)" \
    --argjson candidate_pass_count "$(extract_value real_logit_candidate_pass_count)" \
    --argjson argmax_token_id "$(extract_value real_logit_argmax_token_id)" \
    --argjson argmax_candidate_index "$(extract_value real_logit_argmax_candidate_index)" \
    --argjson selected_logit_micro "$(extract_value real_logit_selected_logit_micro)" \
    '{
      receipt_kind: "fkwu-form-cli-real-gguf-logit-token-generation-receipt",
      trace_id: $trace_id,
      thread_branch: $branch,
      git_commit: $commit,
      verdict: "pass",
      observed: {
        real_gguf_logit_token_generation: true,
        real_logit_generation_scope: "candidate-token-real-gguf-token-embedding-dot",
        real_token_embedding_rows: true,
        real_q6k_embedding_prefix_dot_in_form: true,
        real_logits: true,
        full_model_logits: false,
        full_vocabulary_logits: false,
        accelerator_buffers: false,
        full_real_llama_gguf_generation: false,
        tokenizer_token_count: $token_count,
        embedding_dim: $embedding_dim,
        token_embedding_row_bytes: $row_bytes,
        prompt_token_id: $prompt_token_id,
        candidate_count: $candidate_count,
        candidate_pass_count: $candidate_pass_count,
        argmax_token_id: $argmax_token_id,
        argmax_candidate_index: $argmax_candidate_index,
        selected_logit_micro: $selected_logit_micro,
        decoded_token_text: $decoded_token_text,
        real_logit_generation_sha256: $generation_sha,
        real_logit_generation_expected_sha256: $expected_generation_sha
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
        real_logit_source: $source_json,
        token_hex: $token_hex
      },
      trace_sha256: $trace_sha,
      boundary: "This proves one token selected by Form logits over a native-safe 1024-dimension prefix of real GGUF token_embd.weight Q6_K candidate rows and decoded from real tokenizer bytes. It does not prove the full 3072-dimension embedding row, a full transformer hidden-state projection, full-vocabulary logits, complete accelerator tensor buffers, or full real Llama GGUF autoregressive generation."
    }' > "$RECEIPT"

printf 'receipt=%s\n' "$RECEIPT"
printf 'trace=%s\n' "$TRACE_REPORT_DIR"
printf 'real_logit_token_generation_verified=true\n'
printf 'decoded_token_text=%s\n' "$(extract_value decoded_token_text)"
printf 'argmax_token_id=%s\n' "$(extract_value real_logit_argmax_token_id)"
printf 'selected_logit_micro=%s\n' "$(extract_value real_logit_selected_logit_micro)"
printf 'full_model_logits=false\n'
printf 'full_vocabulary_logits=false\n'
printf 'http_or_ollama=%s\n' "$http_or_ollama"
printf 'denied_toolchain_names_visible_on_path=%s\n' "$denied_toolchain_names_visible_on_path"
