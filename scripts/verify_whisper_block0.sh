#!/usr/bin/env bash
# scripts/verify_whisper_block0.sh — coordinate M6 validation check end-to-end.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Step 1: Generate Whisper-tiny block 0 reference activations ==="
"$ROOT/api/.venv/bin/python" "$ROOT/scripts/whisper_block0_carrier.py"

echo ""
echo "=== Step 2: Validate value parity across sibling kernels ==="
(cd "$ROOT/form" && ./validate.sh form-stdlib/core.fk form-stdlib/trig.fk form-stdlib/json.fk form-stdlib/transformer-numerics.fk form-stdlib/tensor-quant.fk form-stdlib/transformer-block.fk form-stdlib/tests/whisper-block0-band.fk)

echo ""
echo "=== Step 3: Validate in binary mode (compiled artifact) ==="
(cd "$ROOT/form" && ./validate.sh --binary form-stdlib/core.fk form-stdlib/trig.fk form-stdlib/json.fk form-stdlib/transformer-numerics.fk form-stdlib/tensor-quant.fk form-stdlib/transformer-block.fk form-stdlib/tests/whisper-block0-band.fk)

echo ""
echo "OK — Whisper-tiny block 0 validation successful!"
