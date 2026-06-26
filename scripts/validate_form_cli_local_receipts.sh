#!/usr/bin/env bash
# validate_form_cli_local_receipts.sh — local receipts for the form-cli ask lane.
#
# This proves the honest floor:
#   - `form-cli ask` is served by the native fkwu grounded-RAG lane.
#   - the fkwu+Metal GGUF prose lane is present only as proven pieces, not as a
#     wired end-to-end generator.
#   - the Metal witnesses and Form proof bands that back those pieces still pass.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUERY="${1:-substrate}"
FAIL=0

ok() { printf "  ✓  %s\n" "$1"; }
gap() { printf "  ✗  %s\n" "$1"; FAIL=1; }
note() { printf "     %s\n" "$1"; }

run_receipt() {
    label="$1"; shift
    out="$("$@" 2>&1)"
    rc=$?
    if [[ "$rc" -eq 0 ]]; then
        ok "$label"
        printf '%s\n' "$out" | sed -n '1,6p' | sed 's/^/     /'
    else
        gap "$label"
        printf '%s\n' "$out" | sed -n '1,20p' | sed 's/^/     /'
    fi
}

echo "── form-cli local receipts ──"

ask_out="$("$ROOT/bin/form-cli" ask "$QUERY" 2>&1)"
if printf '%s' "$ask_out" | grep -q '^grounded:' &&
   printf '%s' "$ask_out" | grep -q '^local-lane:fkwu-rag-grounded' &&
   printf '%s' "$ask_out" | grep -q '^synthesis-lane:pending-fkwu-metal-llm'; then
    ok "native fkwu ask grounded locally for query: $QUERY"
    printf '%s\n' "$ask_out" | sed 's/^/     /'
else
    gap "native fkwu ask did not produce the expected grounded local receipt"
    printf '%s\n' "$ask_out" | sed 's/^/     /'
fi

synth_out="$("$ROOT/bin/form-cli" synthesis-status 2>&1)"
if printf '%s' "$synth_out" | grep -q '^synthesis-lane:pending-fkwu-metal-llm' &&
   printf '%s' "$synth_out" | grep -q '^available:gguf-locate,gguf-model-cell,weight-load,block-join,metal-matvec,metal-model-cell,metal-decode-step' &&
   { printf '%s' "$synth_out" | grep -q '^missing:tokenizer-carrier,full-gguf-weight-map-to-metal,autoregressive-loop-binding,ask-staged-model-call' ||
     { printf '%s' "$synth_out" | grep -q '^missing:tokenizer-carrier,full-gguf-weight-map-to-metal,autoregressive-loop-binding' &&
       printf '%s' "$synth_out" | grep -q '^available-observed:ask-staged-model-call-witness'; }; }; then
    ok "synthesis lane receipt names available pieces and missing composition"
    printf '%s\n' "$synth_out" | sed 's/^/     /'
else
    gap "synthesis lane receipt is missing or ambiguous"
    printf '%s\n' "$synth_out" | sed 's/^/     /'
fi

run_receipt "form-cli native dispatch band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/text-tokenize.fk form-stdlib/rag-embed.fk form-stdlib/rag-index-codec.fk form-stdlib/rag-retrieve.fk form-stdlib/rag-ask.fk form-stdlib/form-cli-ask.fk form-stdlib/line-grammar.fk form-stdlib/voice-traits.fk form-stdlib/nearest-shape.fk form-stdlib/co-learning.fk form-stdlib/co-learning-stream.fk form-stdlib/mesh-dispatch.fk form-stdlib/surprise-salience.fk form-stdlib/host-sense-organ.fk form-stdlib/speech-organ.fk form-stdlib/native-host-instance.fk form-stdlib/resource-port.fk form-stdlib/bml-native-interface-package-import.fk form-stdlib/hati-os-targets.fk form-stdlib/form-native-resource-interfaces.fk form-stdlib/form-fs.fk form-stdlib/storage-port.fk form-stdlib/host-kernel-carrier.fk form-stdlib/fnri-standin.fk form-stdlib/fnri-receipt.fk form-stdlib/form-cli.fk form-stdlib/tests/form-cli-band.fk"
run_receipt "GGUF weight-load/block-join band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/core.fk form-stdlib/format-arith.fk form-stdlib/f16-decode.fk form-stdlib/gguf-read.fk form-stdlib/q6k-dequant.fk form-stdlib/weight-load.fk form-stdlib/transformer-block.fk form-stdlib/llama-block.fk form-stdlib/block-join.fk form-stdlib/tests/block-join-band.fk"
run_receipt "cached generation semantics band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/trig.fk form-stdlib/transformer-numerics.fk form-stdlib/transformer-block.fk form-stdlib/transformer-mh.fk form-stdlib/transformer-decoder.fk form-stdlib/transformer-generate.fk form-stdlib/transformer-generate-cached.fk form-stdlib/tests/transformer-generate-cached-band.fk"
run_receipt "Metal emitter band" \
    bash -lc "cd '$ROOT/form' && ./validate.sh form-stdlib/jit-tensor-emit.fk form-stdlib/tests/metal-emit-band.fk"
run_receipt "form-cli model-lane gap receipt" \
    "$ROOT/scripts/validate_form_cli_model_lane_gap_receipts.sh" "$ROOT/.cache/body-test-receipts/current-model-lane-gap-receipt.json"
run_receipt "fkwu form-cli GGUF model-cell receipt" \
    "$ROOT/scripts/fkwu_form_cli_gguf_model_cell_receipt.sh" "$ROOT/.cache/body-test-receipts/current-gguf-model-cell-receipt.json"

if [[ "$(uname -s)" == "Darwin" ]] && command -v swiftc >/dev/null 2>&1; then
    run_receipt "Metal matvec witness" "$ROOT/scripts/metal_matvec_audit.sh" 16 16 1
    run_receipt "Metal llama decode-step witness" "$ROOT/scripts/metal_llama_block_decode_audit.sh"
    run_receipt "fkwu form-cli Metal model-cell receipt" \
        "$ROOT/scripts/fkwu_form_cli_metal_model_cell_receipt.sh" "$ROOT/.cache/body-test-receipts/current-model-cell-receipt.json"
else
    note "Metal witnesses skipped: Darwin + swiftc unavailable on this host"
fi

echo "── verdict ──"
if [[ "$FAIL" -eq 0 ]]; then
    echo "  PASS: local grounded ask and pending synthesis receipts are honest."
    echo "  The full fkwu+Metal GGUF prose generator is still not claimed."
else
    echo "  FAIL: one or more local receipts did not hold."
fi
exit "$FAIL"
