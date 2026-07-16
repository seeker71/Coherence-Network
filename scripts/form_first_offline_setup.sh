#!/usr/bin/env bash
# form_first_offline_setup.sh — bring the complete grounded body home.
#
# This is the cold-start carrier for the Form-first lane. Readiness is no longer
# inferred from the presence of one arbitrary cell. The substrate bootstrap
# reconciles every answer source to an exact source/answer-hash ARTIFACT CTOR,
# then asks the native carrier to materialize semantic-v2 vectors. Any
# incomplete stage fails loudly.
set -euo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/api/.venv/bin/python" ]]; then
  PYTHON=("$ROOT/api/.venv/bin/python")
elif [[ -x "$ROOT/api/.venv/Scripts/python.exe" ]]; then
  PYTHON=("$ROOT/api/.venv/Scripts/python.exe")
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=(python3)
elif command -v py >/dev/null 2>&1 && py -3 --version >/dev/null 2>&1; then
  PYTHON=(py -3)
elif command -v python >/dev/null 2>&1 && python --version 2>&1 | grep -q '^Python 3'; then
  PYTHON=(python)
else
  echo "Form-first setup failed: Python 3 carrier unavailable" >&2
  exit 2
fi

echo "⟐ bringing the complete Form-first body home…"
"${PYTHON[@]}" scripts/coh_substrate.py bootstrap

echo "⟐ materializing the NodeID-backed sovereign RAG index…"
bash scripts/ensure_form_cli_native.sh >/dev/null
"${PYTHON[@]}" scripts/form_cli_rag.py heal

"${PYTHON[@]}" scripts/form_cli_rag.py validate-index
echo "⟐ ready — exact ARTIFACT bindings and native semantic-v2 index are current."
