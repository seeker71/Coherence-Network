#!/usr/bin/env bash
# audio-distill.sh — the audio/sound domain's dataset builder. Drains the audio inbox (windows
# the speech organ sampled), names each with the SoundAnalysis oracle (sound_classify: ~300
# everyday sounds — animals, music, rain, applause, speech), and stores a content-addressed
# clip + labelled record toward the 10k target. Same oracle-distillation shape as vision-distill.
#
# Run as the organ earth.hati.audio-distill (every ~120s), or once by hand.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ORACLE="$HERE/sound_classify"
STORE="$HOME/.coherence-network/audio-training"
INBOX="$STORE/inbox"; CLIPS="$STORE/clips"
SAMPLES="$STORE/samples.jsonl"
TARGET=10000
mkdir -p "$INBOX" "$CLIPS"

[[ -x "$ORACLE" ]] || { echo "[audio-distill] building oracle"; (cd "$HERE" && swiftc -O sound_classify.swift -o sound_classify) || exit 1; }

shopt -s nullglob
n=0
for wav in "$INBOX"/*.wav; do
    [[ -s "$wav" ]] || { rm -f "$wav"; continue; }
    labels="$("$ORACLE" "$wav" 2>/dev/null)"
    if [[ -z "$labels" || "$labels" == "[]" ]]; then rm -f "$wav"; continue; fi
    hash="$(shasum -a 256 "$wav" | cut -c1-16)"
    kept="$CLIPS/$hash.wav"
    [[ -f "$kept" ]] || cp "$wav" "$kept"
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    python3 -c "
import json,sys
rec={'id':sys.argv[1],'clip':sys.argv[2],'oracle':'soundanalysis-v1','labels':json.loads(sys.argv[3]),
     'ts':sys.argv[4],'distill_state':'teacher-labelled'}
open(sys.argv[5],'a').write(json.dumps(rec)+'\n')
" "$hash" "$kept" "$labels" "$ts" "$SAMPLES" 2>/dev/null && n=$((n+1))
    rm -f "$wav"
done

total="$(wc -l < "$SAMPLES" 2>/dev/null | tr -d ' ' || echo 0)"
echo "[audio-distill] +$n this pass · $total/$TARGET labelled"
