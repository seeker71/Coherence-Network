#!/usr/bin/env bash
# form_cli_ask_staged_model_call.sh — local model-call witness for ask-staged RAG misses.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUERY="${1:-}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_RECEIPT="$ROOT/.cache/body-test-receipts/ask-staged-model-call-$STAMP/receipt.json"
RECEIPT="${2:-$DEFAULT_RECEIPT}"

if [[ "$RECEIPT" != /* ]]; then
    RECEIPT="$ROOT/$RECEIPT"
fi

OUT_DIR="${RECEIPT%.json}.d"
MODEL_CELL_RECEIPT="$OUT_DIR/fkwu-metal-model-cell.json"
QUERY_FILE="$OUT_DIR/query.txt"
mkdir -p "$OUT_DIR" "$(dirname "$RECEIPT")"
printf '%s\n' "$QUERY" > "$QUERY_FILE"

FAIL=0
model_out="$("$ROOT/scripts/fkwu_form_cli_metal_model_cell_receipt.sh" "$MODEL_CELL_RECEIPT" 2>&1)"
model_rc=$?
printf '%s\n' "$model_out" > "$OUT_DIR/fkwu-metal-model-cell.out"
printf '%s\n' "$model_rc" > "$OUT_DIR/fkwu-metal-model-cell.rc"
if [[ "$model_rc" -ne 0 ]]; then
    FAIL=1
fi

python3 - "$ROOT" "$QUERY_FILE" "$RECEIPT" "$MODEL_CELL_RECEIPT" "$model_rc" <<'PY'
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
query_file = Path(sys.argv[2])
receipt_path = Path(sys.argv[3])
model_cell_receipt_path = Path(sys.argv[4])
model_rc = int(sys.argv[5])
query = query_file.read_text(encoding="utf-8", errors="replace").rstrip("\n")


def git_value(args: list[str], fallback: str) -> str:
    try:
        return subprocess.check_output(args, cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return fallback


model_cell = {}
if model_cell_receipt_path.exists():
    model_cell = json.loads(model_cell_receipt_path.read_text(encoding="utf-8"))

gates = model_cell.get("gates") or {}
model_pass = (
    model_rc == 0
    and model_cell.get("verdict") == "pass"
    and gates.get("form_cli_repl_verb_metal_model_cell") is True
    and gates.get("model_cell_sha256_verified_in_form") is True
    and gates.get("metal_device_observed") is True
    and gates.get("http_or_ollama_absent") is True
)

receipt = {
    "receipt_kind": "form-cli-ask-staged-model-call-receipt",
    "trace_id": f"ask-staged-model-call-{receipt_path.parent.name}",
    "git_commit": git_value(["git", "rev-parse", "--short", "HEAD"], "unknown"),
    "git_branch": git_value(["git", "rev-parse", "--abbrev-ref", "HEAD"], "unknown"),
    "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
    "verdict": "pass" if model_pass else "fail",
    "ask_staged_model_call": {
        "observed": model_pass,
        "trigger": "native ask-staged returned local RAG miss",
        "model_lane": "fkwu-metal-model-cell",
        "model_cell_receipt": str(model_cell_receipt_path),
        "model_cell_trace_id": model_cell.get("trace_id"),
        "model_cell_verdict": model_cell.get("verdict"),
        "model_cell_sha256_verified_in_form": gates.get("model_cell_sha256_verified_in_form") is True,
        "metal_device_observed": gates.get("metal_device_observed") is True,
        "http_or_ollama_absent": gates.get("http_or_ollama_absent") is True,
        "runtime_path_sanitized": gates.get("runtime_path_sanitized") is True,
        "denied_toolchain_names_visible_on_path": gates.get("denied_toolchain_names_visible_on_path"),
    },
    "prose_generation": {
        "verdict": "pending",
        "boundary": "This closes the ask-staged model-call binding to a local fkwu+Metal model-cell witness. Full tokenizer -> real GGUF buffers -> autoregressive decode -> decoded text remains a separate synthesis lane.",
    },
    "artifacts": {
        "directory": str(receipt_path.parent),
        "query_file": str(query_file),
        "model_cell_receipt": str(model_cell_receipt_path),
        "model_cell_stdout": str(model_cell_receipt_path.with_suffix(".out")),
    },
}

receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"receipt:{receipt_path}")
print(f"verdict:{receipt['verdict']}")
print(f"model-call-lane:{receipt['ask_staged_model_call']['model_lane']}")
print(f"model-call-observed:{str(model_pass).lower()}")
print("prose-generation:pending")
if not model_pass:
    sys.exit(1)
PY
py_rc=$?
if [[ "$py_rc" -ne 0 ]]; then
    FAIL=1
fi

exit "$FAIL"
