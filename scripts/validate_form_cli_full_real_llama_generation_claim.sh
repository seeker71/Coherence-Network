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
mkdir -p "$TRACE_DIR/isolated-home" "$TRACE_DIR/tmp"

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
    env HOME="$TRACE_DIR/isolated-home" TMPDIR="$TRACE_DIR/tmp" \
    "$ROOT/bin/form-cli" ask "full real Llama GGUF token generation claim gate isolated model call $STAMP"

run_capture model_status \
    "$ROOT/bin/form-cli" model-status

run_capture final_observations \
    "$ROOT/bin/form-cli" final-observations

run_capture real_gguf_weight_map \
    python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$TRACE_DIR/real-gguf-weight-map.json"

run_capture real_gguf_fullwidth_logits \
    "$ROOT/scripts/fkwu_form_cli_gguf_fullwidth_logits_receipt.sh" "$TRACE_DIR/fullwidth-logits.json"

run_capture sampler_min_p_band \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/transformer-numerics.fk form-stdlib/transformer-block.fk form-stdlib/transformer-generate.fk form-stdlib/sampling.fk form-stdlib/tests/sampling-band.fk"

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
final_observations = read_text("final_observations")
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
    and "observed:tokenizer-carrier,full-gguf-weight-map,named-real-gguf-tensor-math,full-gguf-named-tensor-slice-math,full-gguf-required-tensor-set-materialization,real-gguf-tokenizer-token-decode,semantic-token-generation,full-width-model-logit-generation,sampler-min-p-four-way,metal-weight-bytes-runtime,autoregressive-loop,ask-staged-model-call,decoded-prose-answer-binding" in status
    and "missing:full-real-llama-gguf-token-generation" in status
)
status_names_semantic_token_generation = (
    read_rc("model_status") == 0
    and "real-gguf-tokenizer-token-decode,semantic-token-generation" in status
)
ask_names_full_real_gap = "full-real-llama-gguf-generation:pending" in ask
final_observations_wide_lane = (
    read_rc("final_observations") == 0
    and "model-lane-convergence:one-wide-move" in final_observations
    and "pending:full-real-llama-gguf-token-generation" in final_observations
)
real_gguf_map_observed = read_rc("real_gguf_weight_map") == 0 and gguf_map.get("verdict") == "pass"
fullwidth_path = trace_dir / "fullwidth-logits.json"
fullwidth_json = {}
if fullwidth_path.exists():
    try:
        fullwidth_json = json.loads(fullwidth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        fullwidth_json = {}
fullwidth_observed = fullwidth_json.get("observed") or {}
real_gguf_fullwidth_logits_observed = (
    read_rc("real_gguf_fullwidth_logits") == 0
    and fullwidth_json.get("verdict") == "PASS fkwu-form-cli-gguf-fullwidth-logits"
    and fullwidth_observed.get("full_width_model_logit_generation_verified") is True
    and fullwidth_observed.get("full_width_logits_generated_in_form") is True
    and fullwidth_observed.get("full_vocabulary_logits") is True
)
sampler_min_p_observed = read_rc("sampler_min_p_band") == 0

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
        "model_status_names_semantic_token_generation": status_names_semantic_token_generation,
        "model_status_names_fullwidth_logit_generation": "full-width-model-logit-generation" in status,
        "model_status_names_sampler_min_p": "sampler-min-p-four-way" in status,
        "final_observations_wide_lane": final_observations_wide_lane,
        "sampler_min_p_four_way_observed": sampler_min_p_observed,
        "ask_trace_names_full_real_generation_gap": ask_names_full_real_gap,
        "real_gguf_weight_map_observed": real_gguf_map_observed,
        "real_gguf_fullwidth_logits_observed": real_gguf_fullwidth_logits_observed,
        "real_gguf_fullwidth_logit_count": fullwidth_observed.get("full_width_logit_count"),
        "real_gguf_fullwidth_argmax_token_id": fullwidth_observed.get("full_width_argmax_token_id"),
        "real_gguf_fullwidth_decoded_token_text": fullwidth_observed.get("decoded_token_text"),
        "real_gguf_tensor_count": ((gguf_map.get("tensor_map") or {}).get("count_observed")),
        "real_gguf_architecture": ((gguf_map.get("metadata") or {}).get("architecture")),
    },
    "blocked_requirements": [] if claim_allowed else [
        "complete one wide native path: tensor payload staging -> dequant and accelerator buffer placement -> full multi-layer GQA hidden-state loop -> full-vocabulary hidden-state logits -> real token ID decode -> form-cli ask answer binding",
    ],
    "artifacts": {
        "trace_dir": rel(trace_dir),
        "ask_full_real_claim": rel(trace_dir / "ask_full_real_claim.out"),
        "model_status": rel(trace_dir / "model_status.out"),
        "final_observations": rel(trace_dir / "final_observations.out"),
        "real_gguf_weight_map": rel(gguf_map_path),
        "real_gguf_fullwidth_logits": rel(fullwidth_path),
        "sampler_min_p_band": rel(trace_dir / "sampler_min_p_band.out"),
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
