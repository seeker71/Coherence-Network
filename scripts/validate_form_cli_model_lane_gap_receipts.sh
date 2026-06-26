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

run_step model_status "native model status still names the composition boundary" \
    "$ROOT/bin/form-cli" model-status

run_step tokenizer_compose "BPE tokenizer carrier composition band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/pretokenize.fk form-stdlib/byte-to-symbol.fk form-stdlib/bpe-tokenizer.fk form-stdlib/tokenize.fk form-stdlib/tests/tokenize-band.fk"

run_step llama3_pretokenizer "Llama 3 pre-tokenizer band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/llama3-pretokenize.fk form-stdlib/tests/llama3-pretokenize-band.fk"

if [[ -n "$GGUF_PATH" ]]; then
    run_step full_gguf_weight_map "full real GGUF metadata + tensor weight map receipt" \
        python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$OUT_DIR/gguf_weight_map.json" "$GGUF_PATH"
else
    run_step full_gguf_weight_map "full real GGUF metadata + tensor weight map receipt" \
        python3 "$ROOT/scripts/gguf_weight_map_receipt.py" --json "$OUT_DIR/gguf_weight_map.json"
fi

run_step autoregressive_loop_band "Form autoregressive generation loop band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/trig.fk form-stdlib/transformer-numerics.fk form-stdlib/llama-numerics.fk form-stdlib/rope.fk form-stdlib/transformer-block.fk form-stdlib/transformer-mh.fk form-stdlib/gqa-attn.fk form-stdlib/llama-block.fk form-stdlib/llama-gqa-block.fk form-stdlib/kv-cache.fk form-stdlib/kv-llama-block.fk form-stdlib/kv-gqa-llama-block.fk form-stdlib/multi-layer-stack.fk form-stdlib/gqa-multi-layer-stack.fk form-stdlib/greedy-decode.fk form-stdlib/llama-generate.fk form-stdlib/tests/llama-generate-band.fk"

run_optional_metal

probe="ask staged model call probe $STAMP"
run_step ask_staged_probe "ask-staged miss invokes the local fkwu+Metal model-call witness" \
    "$ROOT/bin/form-cli" ask "$probe"

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
autoregressive_band_ok = rc("autoregressive_loop_band") == 0
metal_rc = rc("metal_gqa_autoregressive_loop")
metal_observed = metal_rc == 0
metal_skipped = metal_rc == 2
ask_out = text("ask_staged_probe")
model_status = text("model_status")
status_closes_old_missing = (
    "observed:tokenizer-carrier,full-gguf-weight-map,metal-weight-bytes-runtime,autoregressive-loop,ask-staged-model-call" in model_status
    and "missing:decoded-prose-answer-binding" in model_status
)
ask_staged_model_call_observed = (
    "[ask: local fkwu RAG index has no grounded hit]" in ask_out
    and "model-call-lane:fkwu-metal-model-cell" in ask_out
    and "model-call-observed:true" in ask_out
    and "synthesis-lane:ask-staged-model-call-observed" in ask_out
    and "prose-generation:pending" in ask_out
)

hard_failures = []
for name, ok in [
    ("tokenizer_compose", tokenizer_compose_ok),
    ("llama3_pretokenizer", llama3_pretokenizer_ok),
    ("full_gguf_weight_map", full_gguf_ok),
    ("autoregressive_loop_band", autoregressive_band_ok),
]:
    if not ok:
        hard_failures.append(name)
if metal_rc not in (0, 2):
    hard_failures.append("metal_gqa_autoregressive_loop")
if not ask_staged_model_call_observed:
    hard_failures.append("ask_staged_model_call_contract")
if not status_closes_old_missing:
    hard_failures.append("model_status_closure_contract")

receipt = {
    "receipt_kind": "form-cli-model-lane-gap-receipt",
    "trace_id": f"form-cli-model-lane-gaps-{receipt_path.parent.name}",
    "git_commit": git_value(["git", "rev-parse", "--short", "HEAD"], "unknown"),
    "git_branch": git_value(["git", "rev-parse", "--abbrev-ref", "HEAD"], "unknown"),
    "verdict": "observed-components-decoded-prose-binding-pending" if not hard_failures else "fail",
    "hard_failures": hard_failures,
    "gap_rows": {
        "tokenizer_carrier": {
            "verdict": "observed-not-ask-text-bound",
            "tokenizer_compose_four_way": tokenizer_compose_ok,
            "llama3_pretokenizer_four_way": llama3_pretokenizer_ok,
            "full_llama3_vocab_merge_table_observed": bool(((gguf_json.get("metadata") or {}).get("tokenizer_array_counts") or {}).get("tokenizer.ggml.tokens")),
            "ask_text_binding": False,
            "boundary": "Tokenizer algorithms and real GGUF tokenizer arrays are observed; decoded text is not yet returned as the ask-staged answer.",
        },
        "full_gguf_weight_map": {
            "verdict": "pass" if full_gguf_ok else "fail",
            "observed": full_gguf_ok,
            "gguf_receipt": str(gguf_path),
            "architecture": (gguf_json.get("metadata") or {}).get("architecture"),
            "tensor_count": ((gguf_json.get("tensor_map") or {}).get("count_observed")),
            "tokenizer_arrays": ((gguf_json.get("metadata") or {}).get("tokenizer_array_counts")),
        },
        "autoregressive_loop_binding": {
            "verdict": "observed-not-text-bound" if autoregressive_band_ok and (metal_observed or metal_skipped) else "fail",
            "form_autoregressive_loop_four_way": autoregressive_band_ok,
            "metal_gqa_decode_loop_observed": metal_observed,
            "metal_gqa_decode_loop_skipped": metal_skipped,
            "decoded_text_binding": False,
            "boundary": "The loop and Metal GQA decode witness are local proof surfaces; ask-staged calls a local model-cell witness but still does not return decoded local prose.",
        },
        "ask_staged_model_call": {
            "verdict": "pass" if ask_staged_model_call_observed else "fail",
            "observed_model_call": ask_staged_model_call_observed,
            "observed_local_rag_miss_trigger": "[ask: local fkwu RAG index has no grounded hit]" in ask_out,
            "model_lane": "fkwu-metal-model-cell",
            "prose_generation": "pending-decoded-prose-answer-binding",
            "boundary": "ask-staged invokes a local fkwu+Metal model-cell witness after a RAG miss; it still does not claim decoded local prose.",
        },
        "decoded_prose_answer_binding": {
            "verdict": "pending",
            "observed_components": status_closes_old_missing,
            "boundary": "This is now the only model-status missing row: turning the observed tokenizer, real GGUF map, Metal weight/runtime, autoregressive loop, and ask-staged model-call witness into one decoded local answer.",
        },
    },
    "artifacts": {
        "directory": str(out_dir),
        "model_status": str(out_dir / "model_status.out"),
        "ask_staged_probe": str(out_dir / "ask_staged_probe.out"),
        "gguf_weight_map": str(gguf_path),
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
    echo "  PASS: stale missing rows closed as observed components; decoded prose answer binding remains the honest blocker."
else
    echo "  FAIL: one or more model-lane gap receipts did not hold."
fi
exit "$FAIL"
