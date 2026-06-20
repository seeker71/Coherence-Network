#!/usr/bin/env bash
# build_form_llama.sh — train + fuse + serve the Form-knowledge local oracle.
#
# Produces an ollama model `form-llama` that the form-cli ask verb can call over
# the existing /api/generate wire (http://localhost:11434), genuinely fluent in
# the Coherence Network's Form language and substrate.
#
# Pipeline (all local, Apple Silicon / mlx-lm + ollama):
#   1. LoRA fine-tune the base on the Form-knowledge corpus  (mlx_lm.lora)
#   2. fuse the adapter into the base, DEQUANTIZED to safetensors  (mlx_lm.fuse)
#   3. import into ollama via the experimental safetensors path, re-quantized
#      to q4_K_M, WITH a correct Llama-3 chat template (the import sets a
#      degenerate `{{ .Prompt }}` template that emits EOS immediately — this
#      script overrides it; that override is the one non-obvious step).
#
# BLOCKER ROUTED AROUND: mlx_lm.fuse --export-gguf cannot convert quantized
# models ("Conversion of quantized models is not yet supported") and even with
# --dequantize its save_gguf path fails ("can only serialize row-major arrays").
# So we DO NOT go through GGUF; we use ollama's `--experimental` safetensors
# import on the dequantized fused model instead. No llama.cpp needed.
#
# Usage: bash scripts/build_form_llama.sh [iters]
set -euo pipefail

VENV="$HOME/.coherence-network/offline-train-venv/bin/python"
BASE="mlx-community/Llama-3.2-3B-Instruct-4bit"
CORPUS="$HOME/.coherence-network/form-knowledge-corpus/full"
RUNS="$HOME/.coherence-network/form-train-runs"
ADAPTER="$RUNS/full-adapter"
FUSED_DQ="$RUNS/full-fused-dq"
MODEL_NAME="form-llama"
ITERS="${1:-800}"

mkdir -p "$ADAPTER" "$FUSED_DQ"

echo "==> 1/3 LoRA fine-tune ($ITERS iters) on $CORPUS"
"$VENV" -m mlx_lm.lora \
  --model "$BASE" --train --data "$CORPUS" \
  --fine-tune-type lora --num-layers 16 --batch-size 4 \
  --iters "$ITERS" --learning-rate 1e-4 \
  --steps-per-report 50 --steps-per-eval 200 --val-batches 10 \
  --max-seq-length 1024 --adapter-path "$ADAPTER" --save-every 400

echo "==> 2/3 fuse adapter into base (dequantized safetensors)"
rm -rf "$FUSED_DQ"; mkdir -p "$FUSED_DQ"
"$VENV" -m mlx_lm.fuse \
  --model "$BASE" --adapter-path "$ADAPTER" \
  --save-path "$FUSED_DQ" --dequantize

echo "==> 3/3 import into ollama as $MODEL_NAME (q4_K_M) with correct chat template"
MODELFILE="$RUNS/Modelfile.$MODEL_NAME"
cat > "$MODELFILE" <<EOF
FROM $FUSED_DQ
TEMPLATE """{{- range \$i, \$_ := .Messages }}
{{- \$last := eq (len (slice \$.Messages \$i)) 1 }}
{{- if eq .Role "system" }}<|start_header_id|>system<|end_header_id|>

{{ .Content }}<|eot_id|>
{{- else if eq .Role "user" }}<|start_header_id|>user<|end_header_id|>

{{ .Content }}<|eot_id|>{{ if \$last }}<|start_header_id|>assistant<|end_header_id|>

{{ end }}
{{- else if eq .Role "assistant" }}<|start_header_id|>assistant<|end_header_id|>

{{ .Content }}{{ if not \$last }}<|eot_id|>{{ end }}
{{- end }}
{{- end }}"""
PARAMETER stop "<|start_header_id|>"
PARAMETER stop "<|end_header_id|>"
PARAMETER stop "<|eot_id|>"
EOF

# import the raw safetensors first (quantizes), then re-create with the template.
ollama create "$MODEL_NAME-raw" --experimental -q q4_K_M -f - <<EOF
FROM $FUSED_DQ
EOF

# rebuild on the quantized layers with the correct template (cheap; reuses layers)
TMPL_MODELFILE="$RUNS/Modelfile.$MODEL_NAME.final"
{
  echo "FROM $MODEL_NAME-raw:latest"
  sed -n '/^TEMPLATE/,$p' "$MODELFILE"
} > "$TMPL_MODELFILE"
ollama create "$MODEL_NAME" -f "$TMPL_MODELFILE"

echo "==> done. test:"
echo "  curl -s http://localhost:11434/api/generate -d '{\"model\":\"$MODEL_NAME\",\"prompt\":\"What do ice, water, and gas mean for a cell?\",\"stream\":false}'"
