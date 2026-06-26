#!/usr/bin/env bash
# validate_form_cli_full_real_llama_generation_claim.sh
#
# Claim gate for the strict full-real Llama GGUF generation path.
# This receipt is intentionally stricter than the grounded decoded-answer lane:
# it only allows the full claim when form-cli produces text through one native
# path from real prompt text -> real GGUF tokenizer/tensor bytes -> accelerator
# buffers -> full autoregressive token IDs -> decoded text.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/full-real-llama-generation-claim-$STAMP/receipt.json"
RECEIPT_PATH="${1:-$DEFAULT_RECEIPT}"

if [[ "$RECEIPT_PATH" != /* ]]; then
    RECEIPT_PATH="$ROOT/$RECEIPT_PATH"
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "missing required receipt harness tool: python3" >&2
    exit 2
fi

TRACE_DIR="${RECEIPT_PATH%.json}_trace"
rm -rf "$TRACE_DIR"
mkdir -p "$TRACE_DIR" "$(dirname "$RECEIPT_PATH")"

sanitize_trace_file() {
    local src="$1"
    local tmp="$src.sanitized"
    LC_ALL=C sed -E \
        -e "s|$ROOT|<repo>|g" \
        -e "s|$HOME|<home>|g" \
        -e 's|[A-Za-z]:\\[^"[:space:]]*Coherence-Network\\Coherence-Network|<repo>|g' \
        -e 's|[A-Za-z]:\\Users\\[^"[:space:]]+|<home>|g' \
        -e 's|<home>/.ollama/models/blobs/sha256-[0-9a-fA-F]+|<local-gguf-blob>|g' \
        -e 's|<home>/mentor-install/.models/[^"[:space:]]+|<local-gguf-file>|g' \
        -e 's|/private/var/folders/[^[:space:]:]+|<tmp>|g' \
        -e 's|/var/folders/[^[:space:]:]+|<tmp>|g' \
        "$src" > "$tmp"
    mv "$tmp" "$src"
}

sanitize_trace_tree() {
    local file
    while IFS= read -r -d '' file; do
        sanitize_trace_file "$file"
    done < <(find "$TRACE_DIR" -type f -print0)
}

run_capture() {
    local key="$1"
    shift
    local out="$TRACE_DIR/$key.out"
    local rcfile="$TRACE_DIR/$key.rc"
    "$@" >"$out" 2>&1
    local rc=$?
    printf '%s\n' "$rc" >"$rcfile"
}

run_capture ask_full_real_claim \
    "$ROOT/bin/form-cli" ask "full real Llama GGUF token generation claim gate $STAMP"

run_capture model_status \
    "$ROOT/bin/form-cli" model-status

run_capture real_gguf_weight_map \
    python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$TRACE_DIR/real-gguf-weight-map.json"

sanitize_trace_tree

python3 - "$ROOT" "$TRACE_DIR" "$RECEIPT_PATH" <<'PY'
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
trace_dir = Path(sys.argv[2])
receipt_path = Path(sys.argv[3])


def read_text(name: str) -> str:
    path = trace_dir / f"{name}.out"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_rc(name: str) -> int:
    path = trace_dir / f"{name}.rc"
    if not path.exists():
        return 127
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return 127


def git_value(args: list[str], fallback: str) -> str:
    try:
        return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return fallback


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


ask = read_text("ask_full_real_claim")
status = read_text("model_status")
gguf_map_path = trace_dir / "real-gguf-weight-map.json"
gguf_map = {}
if gguf_map_path.exists():
    try:
        gguf_map = json.loads(gguf_map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        gguf_map = {}

observed_grounded_answer = (
    read_rc("ask_full_real_claim") == 0
    and "model-call-observed:true" in ask
    and "prose-generation:decoded-grounded-answer" in ask
)
status_names_full_real_gap = (
    read_rc("model_status") == 0
    and "observed:tokenizer-carrier,full-gguf-weight-map,metal-weight-bytes-runtime,autoregressive-loop,ask-staged-model-call,decoded-prose-answer-binding" in status
    and "missing:full-real-llama-gguf-token-generation" in status
)
ask_names_full_real_gap = "full-real-llama-gguf-generation:pending" in ask
real_gguf_map_observed = read_rc("real_gguf_weight_map") == 0 and gguf_map.get("verdict") == "pass"

claim_allowed = (
    observed_grounded_answer
    and not status_names_full_real_gap
    and "full-real-llama-gguf-generation:pass" in ask
)

# A blocked claim is a successful gate result on every device row. Device rows
# may differ in which local answer/status witnesses are present, but none may
# promote the full-real generation claim unless the strict positive evidence is
# present.
hard_failures: list[str] = []
if claim_allowed and not observed_grounded_answer:
    hard_failures.append("claim_allowed_without_grounded_decoded_answer")
if claim_allowed and not real_gguf_map_observed:
    hard_failures.append("claim_allowed_without_real_gguf_weight_map")

verdict = "pass_full_real_llama_generation_claimed" if claim_allowed else "blocked_full_real_llama_generation_pending"
if hard_failures:
    verdict = "fail_claim_gate_ambiguous"

receipt = {
    "receipt_kind": "form-cli-full-real-llama-generation-claim-receipt",
    "trace_id": f"full-real-llama-generation-claim-{receipt_path.parent.name}",
    "git_commit": git_value(["git", "rev-parse", "--short", "HEAD"], "unknown"),
    "git_branch": git_value(["git", "rev-parse", "--abbrev-ref", "HEAD"], "unknown"),
    "verdict": verdict,
    "claim_allowed": claim_allowed,
    "hard_failures": hard_failures,
    "observed_components": {
        "ask_staged_model_call_and_grounded_decoded_answer": observed_grounded_answer,
        "model_status_names_full_real_generation_gap": status_names_full_real_gap,
        "ask_trace_names_full_real_generation_gap": ask_names_full_real_gap,
        "real_gguf_weight_map_observed": real_gguf_map_observed,
        "real_gguf_tensor_count": ((gguf_map.get("tensor_map") or {}).get("count_observed")),
        "real_gguf_architecture": ((gguf_map.get("metadata") or {}).get("architecture")),
    },
    "blocked_requirements": [] if claim_allowed else [
        "materialize named real GGUF tensors into the fkwu-controlled model-cell path, not only a metadata map",
        "dequant and place the full-width Llama tensor set into Metal/accelerator buffers",
        "run the full multi-layer GQA autoregressive loop over those real tensors",
        "project logits over the real vocabulary, select token IDs, and decode through the real tokenizer arrays",
        "bind that decoded text as the form-cli ask answer without HTTP, Ollama, MLX serving, or a proxy oracle",
    ],
    "artifacts": {
        "trace_dir": rel(trace_dir),
        "ask_full_real_claim": rel(trace_dir / "ask_full_real_claim.out"),
        "model_status": rel(trace_dir / "model_status.out"),
        "real_gguf_weight_map": rel(gguf_map_path),
    },
}

receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"receipt:{rel(receipt_path)}")
print(f"verdict:{verdict}")
print(f"claim-allowed:{str(claim_allowed).lower()}")
print(f"grounded-decoded-answer:{str(observed_grounded_answer).lower()}")
print(f"full-real-llama-gguf-generation:{'pass' if claim_allowed else 'pending'}")
if not claim_allowed:
    print("blocked-requirements:" + str(len(receipt["blocked_requirements"])))

if hard_failures:
    sys.exit(1)
PY
