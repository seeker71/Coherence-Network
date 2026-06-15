#!/usr/bin/env bash
# launch_8h.sh — waits for the mounted corpus to finish extracting, then runs the
# live 8-hour sample-efficiency accumulation unattended. Self-starting so the run
# does not depend on an interactive session staying awake.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

CORPUS="$HOME/.cache/coherence-corpora/librispeech/LibriSpeech/train-clean-100"
SPEAKERS="$HOME/.cache/coherence-corpora/librispeech/LibriSpeech/SPEAKERS.TXT"
WHISPER="$HOME/whisper-models/ggml-large-v3-turbo.bin"
LOG="run-8h.log"

echo "[launch] waiting for corpus extraction at $CORPUS ..." | tee -a "$LOG"
# train-clean-100 has ~28539 flacs; wait until extraction is essentially complete
# (>= 27000) or 75 minutes pass, then proceed with whatever is present.
for i in $(seq 1 150); do
    n=$(find "$CORPUS" -name '*.flac' 2>/dev/null | wc -l | tr -d ' ')
    echo "[launch] poll $i: $n flacs extracted" | tee -a "$LOG"
    [ "${n:-0}" -ge 27000 ] && break
    sleep 30
done

n=$(find "$CORPUS" -name '*.flac' 2>/dev/null | wc -l | tr -d ' ')
echo "[launch] starting 8h run with $n corpus flacs at $(date -u +%FT%TZ)" | tee -a "$LOG"

exec .venv/bin/python run_8h_accumulation.py \
    --seed-fingerprints fingerprints-dev-clean.jsonl \
    --corpus-root "$CORPUS" \
    --corpus-data-root "$CORPUS" \
    --speakers "$SPEAKERS" \
    --kernel ../../form/form-kernel-go/bin-go \
    --nearest-shape ../../form/form-stdlib/nearest-shape.fk \
    --whisper-model "$WHISPER" \
    --receipt-script ../../scripts/real_mesh_training_emitters.sh \
    --out learning_curve.jsonl \
    --duration-hours 8 \
    --corpus-batch 120 \
    --max-train 6000 \
    --heldout-cap 800 \
    --receipt-every-min 30 >> "$LOG" 2>&1
