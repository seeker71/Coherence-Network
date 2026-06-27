#!/usr/bin/env bash
# validate_form_cli_model_lane_gap_receipts.sh — observed receipts for the form-cli model-lane gaps.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="${1:-$ROOT/.cache/body-test-receipts/form-cli-model-lane-gaps-$STAMP}"
GGUF_PATH="${2:-}"

case "$TARGET" in
  *.json)
    RECEIPT="$TARGET"
    OUT_DIR="${TARGET%.json}.d"
    ;;
  *)
    OUT_DIR="$TARGET"
    RECEIPT="$OUT_DIR/receipt.json"
    ;;
esac

mkdir -p "$OUT_DIR"
FAIL=0

ok() { printf "  ✓  %s\n" "$1"; }
gap() { printf "  ✗  %s\n" "$1"; FAIL=1; }
note() { printf "     %s\n" "$1"; }

run_step() {
    key="$1"; label="$2"; shift 2
    out="$OUT_DIR/$key.out"
    rcfile="$OUT_DIR/$key.rc"
    "$@" >"$out" 2>&1
    rc=$?
    printf '%s\n' "$rc" >"$rcfile"
    if [[ "$rc" -eq 0 ]]; then
        ok "$label"
        sed -n '1,8p' "$out" | sed 's/^/     /'
    else
        gap "$label"
        sed -n '1,24p' "$out" | sed 's/^/     /'
    fi
}

run_optional_metal() {
    if [[ "$(uname -s)" == "Darwin" ]] && command -v swiftc >/dev/null 2>&1; then
        run_step metal_gqa_autoregressive_loop "Metal GQA autoregressive decode loop witness" \
            "$ROOT/scripts/metal_gqa_llama_block_decode_audit.sh"
    else
        printf '2\n' >"$OUT_DIR/metal_gqa_autoregressive_loop.rc"
        printf 'SKIP no Darwin/Metal toolchain on this host\n' >"$OUT_DIR/metal_gqa_autoregressive_loop.out"
        note "Metal GQA autoregressive loop skipped: Darwin + swiftc unavailable"
    fi
}

echo "── form-cli model-lane gap receipts ──"

run_step tokenizer_compose "BPE tokenizer carrier composition band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/pretokenize.fk form-stdlib/byte-to-symbol.fk form-stdlib/bpe-tokenizer.fk form-stdlib/tokenize.fk form-stdlib/tests/tokenize-band.fk"

run_step llama3_pretokenizer "Llama 3 pre-tokenizer band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/llama3-pretokenize.fk form-stdlib/tests/llama3-pretokenize-band.fk"

if [[ -n "$GGUF_PATH" ]]; then
    run_step full_gguf_weight_map "full real GGUF metadata + tensor weight map receipt" \
        python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$OUT_DIR/gguf_weight_map.json" "$GGUF_PATH"
    run_step gguf_semantic_token_generation "fkwu form-cli real GGUF semantic-token generation receipt" \
        "$ROOT/scripts/fkwu_form_cli_gguf_semantic_token_generation_receipt.sh" "$OUT_DIR/gguf_semantic_token_generation.json" "$GGUF_PATH"
    run_step gguf_fullwidth_logits "fkwu form-cli full-width GGUF model-logit generation receipt" \
        "$ROOT/scripts/fkwu_form_cli_gguf_fullwidth_logits_receipt.sh" "$OUT_DIR/gguf_fullwidth_logits.json" "$GGUF_PATH"
else
    run_step full_gguf_weight_map "full real GGUF metadata + tensor weight map receipt" \
        python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$OUT_DIR/gguf_weight_map.json"
    run_step gguf_semantic_token_generation "fkwu form-cli real GGUF semantic-token generation receipt" \
        "$ROOT/scripts/fkwu_form_cli_gguf_semantic_token_generation_receipt.sh" "$OUT_DIR/gguf_semantic_token_generation.json"
    run_step gguf_fullwidth_logits "fkwu form-cli full-width GGUF model-logit generation receipt" \
        "$ROOT/scripts/fkwu_form_cli_gguf_fullwidth_logits_receipt.sh" "$OUT_DIR/gguf_fullwidth_logits.json"
fi

run_step autoregressive_loop_band "Form autoregressive generation loop band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/trig.fk form-stdlib/transformer-numerics.fk form-stdlib/llama-numerics.fk form-stdlib/rope.fk form-stdlib/transformer-block.fk form-stdlib/transformer-mh.fk form-stdlib/gqa-attn.fk form-stdlib/llama-block.fk form-stdlib/llama-gqa-block.fk form-stdlib/kv-cache.fk form-stdlib/kv-llama-block.fk form-stdlib/kv-gqa-llama-block.fk form-stdlib/multi-layer-stack.fk form-stdlib/gqa-multi-layer-stack.fk form-stdlib/greedy-decode.fk form-stdlib/llama-generate.fk form-stdlib/tests/llama-generate-band.fk"

run_step sampler_min_p_band "Form sampler min-p and seeded draw band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/transformer-numerics.fk form-stdlib/transformer-block.fk form-stdlib/transformer-generate.fk form-stdlib/sampling.fk form-stdlib/tests/sampling-band.fk"

run_optional_metal

probe="ask staged model call probe $STAMP"
run_step ask_staged_probe "ask-staged miss invokes the local fkwu+Metal model-call witness" \
    "$ROOT/bin/form-cli" ask "$probe"

run_step model_status "native model status names the grounded decoded-answer boundary" \
    "$ROOT/bin/form-cli" model-status

run_step final_observations "native final-observations names one wide model-lane move" \
    "$ROOT/bin/form-cli" final-observations

python3 - "$ROOT" "$OUT_DIR" "$RECEIPT" <<'PY'
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
receipt_path = Path(sys.argv[3])


def rc(name: str) -> int:
    try:
        return int((out_dir / f"{name}.rc").read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return 127


def text(name: str) -> str:
    try:
        return (out_dir / f"{name}.out").read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def git_value(args: list[str], fallback: str) -> str:
    try:
        return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return fallback


gguf_json = {}
gguf_path = out_dir / "gguf_weight_map.json"
if gguf_path.exists():
    gguf_json = json.loads(gguf_path.read_text(encoding="utf-8"))

tokenizer_compose_ok = rc("tokenizer_compose") == 0
llama3_pretokenizer_ok = rc("llama3_pretokenizer") == 0
full_gguf_ok = rc("full_gguf_weight_map") == 0 and gguf_json.get("verdict") == "pass"
semantic_json = {}
semantic_path = out_dir / "gguf_semantic_token_generation.json"
if semantic_path.exists():
    semantic_json = json.loads(semantic_path.read_text(encoding="utf-8"))
semantic_token_generation_ok = rc("gguf_semantic_token_generation") == 0 and semantic_json.get("verdict") == "pass"
fullwidth_json = {}
fullwidth_path = out_dir / "gguf_fullwidth_logits.json"
if fullwidth_path.exists():
    fullwidth_json = json.loads(fullwidth_path.read_text(encoding="utf-8"))
fullwidth_observed = fullwidth_json.get("observed") or {}
fullwidth_logits_ok = (
    rc("gguf_fullwidth_logits") == 0
    and fullwidth_json.get("verdict") == "PASS fkwu-form-cli-gguf-fullwidth-logits"
    and fullwidth_observed.get("full_width_model_logit_generation_verified") is True
    and fullwidth_observed.get("full_width_logits_generated_in_form") is True
    and fullwidth_observed.get("full_width_model_logits") is True
    and fullwidth_observed.get("full_vocabulary_logits") is True
    and fullwidth_observed.get("full_model_logits") is False
)
autoregressive_band_ok = rc("autoregressive_loop_band") == 0
sampler_min_p_ok = rc("sampler_min_p_band") == 0
metal_rc = rc("metal_gqa_autoregressive_loop")
metal_observed = metal_rc == 0
metal_skipped = metal_rc == 2
ask_out = text("ask_staged_probe")
model_status = text("model_status")
final_observations = text("final_observations")
status_closes_old_missing = (
    "observed:tokenizer-carrier,full-gguf-weight-map,named-real-gguf-tensor-math,full-gguf-named-tensor-slice-math,full-gguf-required-tensor-set-materialization,real-gguf-tokenizer-token-decode,semantic-token-generation,full-width-model-logit-generation,sampler-min-p-four-way,metal-weight-bytes-runtime,autoregressive-loop,ask-staged-model-call,decoded-prose-answer-binding" in model_status
    and "missing:full-real-llama-gguf-token-generation" in model_status
    and "prose-generation:decoded-grounded-answer" in model_status
)
final_observations_ok = (
    rc("final_observations") == 0
    and "model-lane-convergence:one-wide-move" in final_observations
    and "wide-move:complete-full-width-tensor-payload-staging,dequant-and-accelerator-buffer-placement,full-multilayer-gqa-hidden-state-loop,full-vocabulary-hidden-state-logits,real-token-id-decode,ask-answer-binding" in final_observations
    and "pending:full-real-llama-gguf-token-generation" in final_observations
    and "method:move-all-remaining-bridges-together-under-one-receipt" in final_observations
)
ask_staged_model_call_observed = (
    "[ask: local fkwu RAG index has no grounded hit]" in ask_out
    and "model-call-lane:fkwu-metal-model-cell" in ask_out
    and "model-call-observed:true" in ask_out
    and "synthesis-lane:ask-staged-grounded-decoded-answer" in ask_out
    and "decoded-answer:grounded decoded answer:" in ask_out
    and "prose-generation:decoded-grounded-answer" in ask_out
    and "full-real-llama-gguf-generation:pending" in ask_out
)

hard_failures = []
for name, ok in [
    ("tokenizer_compose", tokenizer_compose_ok),
    ("llama3_pretokenizer", llama3_pretokenizer_ok),
    ("full_gguf_weight_map", full_gguf_ok),
    ("gguf_semantic_token_generation", semantic_token_generation_ok),
    ("gguf_fullwidth_logits", fullwidth_logits_ok),
    ("autoregressive_loop_band", autoregressive_band_ok),
    ("sampler_min_p_band", sampler_min_p_ok),
]:
    if not ok:
        hard_failures.append(name)
if metal_rc not in (0, 2):
    hard_failures.append("metal_gqa_autoregressive_loop")
if not ask_staged_model_call_observed:
    hard_failures.append("ask_staged_model_call_contract")
if not status_closes_old_missing:
    hard_failures.append("model_status_closure_contract")
if not final_observations_ok:
    hard_failures.append("final_observations_wide_lane_contract")

receipt = {
    "receipt_kind": "form-cli-model-lane-gap-receipt",
    "trace_id": f"form-cli-model-lane-gaps-{receipt_path.parent.name}",
    "git_commit": git_value(["git", "rev-parse", "--short", "HEAD"], "unknown"),
    "git_branch": git_value(["git", "rev-parse", "--abbrev-ref", "HEAD"], "unknown"),
    "verdict": "observed-grounded-decoded-answer-fullwidth-logits-full-real-llama-pending" if not hard_failures else "fail",
    "hard_failures": hard_failures,
    "gap_rows": {
        "tokenizer_carrier": {
            "verdict": "observed-grounded-answer-bound-full-real-generation-pending",
            "tokenizer_compose_four_way": tokenizer_compose_ok,
            "llama3_pretokenizer_four_way": llama3_pretokenizer_ok,
            "full_llama3_vocab_merge_table_observed": bool(((gguf_json.get("metadata") or {}).get("tokenizer_array_counts") or {}).get("tokenizer.ggml.tokens")),
            "real_gguf_semantic_token_generation": semantic_token_generation_ok,
            "full_width_model_logit_generation": fullwidth_logits_ok,
            "sampler_min_p_four_way": sampler_min_p_ok,
            "grounded_decoded_answer_binding": ask_staged_model_call_observed,
            "full_real_llama_token_generation_binding": False,
            "boundary": "Tokenizer algorithms and real GGUF tokenizer arrays are observed; one tokenizer string row is selected by Form argmax and decoded by fkwu; a full-width GGUF token-embedding logit row is generated by Form; the min-p sampler and seeded draw are four-way; ask-staged returns a grounded decoded answer; full real Llama GGUF model-token generation remains pending.",
        },
        "full_gguf_weight_map": {
            "verdict": "pass" if full_gguf_ok else "fail",
            "observed": full_gguf_ok,
            "gguf_receipt": str(gguf_path),
            "architecture": (gguf_json.get("metadata") or {}).get("architecture"),
            "tensor_count": ((gguf_json.get("tensor_map") or {}).get("count_observed")),
            "focus_tensors": ((gguf_json.get("tensor_map") or {}).get("focus_tensors")),
            "tokenizer_arrays": ((gguf_json.get("metadata") or {}).get("tokenizer_array_counts")),
        },
        "full_width_model_logits": {
            "verdict": "pass" if fullwidth_logits_ok else "fail",
            "observed": fullwidth_logits_ok,
            "full_width_logit_count": fullwidth_observed.get("full_width_logit_count"),
            "argmax_token_id": fullwidth_observed.get("full_width_argmax_token_id"),
            "decoded_token_text": fullwidth_observed.get("decoded_token_text"),
            "source_tensor": fullwidth_json.get("source_tensor"),
            "receipt": str(fullwidth_path),
            "boundary": "The full vocabulary width is scanned inside fkwu/Form over token_embd.weight Q6_K projection logits; this is not yet full hidden-state Llama logits.",
        },
        "final_observations": {
            "verdict": "pass" if final_observations_ok else "fail",
            "observed": final_observations_ok,
            "wide_move": [
                "complete-full-width-tensor-payload-staging",
                "dequant-and-accelerator-buffer-placement",
                "full-multilayer-gqa-hidden-state-loop",
                "full-vocabulary-hidden-state-logits",
                "real-token-id-decode",
                "ask-answer-binding",
            ],
            "pending": "full-real-llama-gguf-token-generation",
            "boundary": "The remaining full-generation bridges move as one contract instead of one receipt row at a time.",
        },
        "sampler_min_p": {
            "verdict": "pass" if sampler_min_p_ok else "fail",
            "observed": sampler_min_p_ok,
            "recipe": "form/form-stdlib/sampling.fk",
            "band": "form/form-stdlib/tests/sampling-band.fk",
            "boundary": "Temperature, softmax, top-k, top-p, llama.cpp-style min-p, MINSTD seeded draw, and inverse-CDF token selection are four-way; this is the sampler primitive that can consume real logits once full hidden-state logits are bound.",
        },
        "autoregressive_loop_binding": {
            "verdict": "observed-grounded-answer-bound-full-real-generation-pending" if autoregressive_band_ok and (metal_observed or metal_skipped) and ask_staged_model_call_observed else "fail",
            "form_autoregressive_loop_four_way": autoregressive_band_ok,
            "sampler_min_p_four_way": sampler_min_p_ok,
            "metal_gqa_decode_loop_observed": metal_observed,
            "metal_gqa_decode_loop_skipped": metal_skipped,
            "real_gguf_semantic_token_generation": semantic_token_generation_ok,
            "full_width_model_logit_generation": fullwidth_logits_ok,
            "grounded_decoded_answer_binding": ask_staged_model_call_observed,
            "full_real_llama_token_generation_binding": False,
            "boundary": "The loop and Metal GQA decode witness are local proof surfaces; a real GGUF tokenizer token is decoded by fkwu after Form argmax, and a full-width token-embedding logit row is now generated by Form, while full real GGUF autoregressive model-token generation remains pending.",
        },
        "ask_staged_model_call": {
            "verdict": "pass" if ask_staged_model_call_observed else "fail",
            "observed_model_call": ask_staged_model_call_observed,
            "observed_local_rag_miss_trigger": "[ask: local fkwu RAG index has no grounded hit]" in ask_out,
            "model_lane": "fkwu-metal-model-cell",
            "prose_generation": "decoded-grounded-answer",
            "full_real_llama_gguf_generation": "pending",
            "boundary": "ask-staged invokes a local fkwu+Metal model-cell witness after a RAG miss and returns a decoded grounded answer without claiming full real Llama GGUF token generation.",
        },
        "decoded_prose_answer_binding": {
            "verdict": "pass" if ask_staged_model_call_observed and status_closes_old_missing else "fail",
            "observed_components": status_closes_old_missing,
            "boundary": "A decoded grounded answer is now bound to the ask-staged model-call witness and visible in form-cli ask/model-status receipts.",
        },
        "full_real_llama_gguf_generation": {
            "verdict": "pending",
            "observed_grounded_answer": ask_staged_model_call_observed,
            "observed_semantic_token_generation": semantic_token_generation_ok,
            "observed_full_width_model_logit_generation": fullwidth_logits_ok,
            "observed_sampler_min_p": sampler_min_p_ok,
            "boundary": "The remaining gap is producing answer text from full real Llama GGUF hidden-state logits over complete tensor payloads in one native answer path.",
        },
    },
    "artifacts": {
        "directory": str(out_dir),
        "model_status": str(out_dir / "model_status.out"),
        "final_observations": str(out_dir / "final_observations.out"),
        "ask_staged_probe": str(out_dir / "ask_staged_probe.out"),
        "gguf_weight_map": str(gguf_path),
        "gguf_semantic_token_generation": str(semantic_path),
        "gguf_fullwidth_logits": str(fullwidth_path),
        "sampler_min_p_band": str(out_dir / "sampler_min_p_band.out"),
    },
}

receipt_path.parent.mkdir(parents=True, exist_ok=True)
receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"receipt:{receipt_path}")
print(f"verdict:{receipt['verdict']}")
for name, row in receipt["gap_rows"].items():
    print(f"{name}:{row['verdict']}")
if hard_failures:
    sys.exit(1)
PY
rc=$?
if [[ "$rc" -ne 0 ]]; then
    FAIL=1
fi

echo "── verdict ──"
if [[ "$FAIL" -eq 0 ]]; then
    echo "  PASS: grounded decoded answer, full-width logit generation, and sampler are bound; full real Llama GGUF token generation remains the honest blocker."
else
    echo "  FAIL: one or more model-lane gap receipts did not hold."
fi
exit "$FAIL"
