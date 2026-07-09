#!/usr/bin/env bash
# face-distill.sh — the person/face domain's dataset builder + capture. Grabs a still from the
# camera (energy-light: one frame per tick, not a stream), detects faces, embeds each (Vision
# detect->crop->featureprint), and stores per-face samples toward the 10k target. Faces are
# pooled unassigned, the same shape voices are — a human (or, later, a co-trained speaker turn)
# assigns the name, and the face profile sharpens from there.
#
# Frames may also arrive from the companion app: drop jpgs into $STORE/inbox and they're drained
# too (the app has camera TCC; a launchd grab may not).
#
# Run as the organ earth.hati.face-distill (every ~90s), or once by hand.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
GRAB="$HERE/camera_frame"; EMBED="$HERE/face_embed"
STORE="$HOME/.coherence-network/face-training"
INBOX="$STORE/inbox"; FRAMES="$STORE/frames"
SAMPLES="$STORE/samples.jsonl"
TARGET=10000
mkdir -p "$INBOX" "$FRAMES"; touch "$SAMPLES"

[[ -x "$EMBED" ]] || (cd "$HERE" && swiftc -O face_embed.swift -o face_embed) || exit 1
[[ -x "$GRAB" ]]  || (cd "$HERE" && swiftc -O camera_frame.swift -o camera_frame) 2>/dev/null || true

# 1. try a live grab (needs camera TCC for this process); land it in the inbox
if [[ -x "$GRAB" ]]; then
    shot="$INBOX/grab-$(date -u +%Y%m%dT%H%M%S).jpg"
    if "$GRAB" "$shot" 2>/dev/null && [[ -s "$shot" ]]; then :; else rm -f "$shot"; fi
fi

# 2. drain every frame in the inbox (live grabs + app-fed frames)
shopt -s nullglob
faces=0; frames=0
for frame in "$INBOX"/*.jpg "$INBOX"/*.jpeg "$INBOX"/*.png; do
    [[ -s "$frame" ]] || { rm -f "$frame"; continue; }
    frames=$((frames+1))
    dets="$("$EMBED" "$frame" 2>/dev/null)"
    if [[ -z "$dets" || "$dets" == "[]" ]]; then rm -f "$frame"; continue; fi
    hash="$(shasum -a 256 "$frame" | cut -c1-16)"
    kept="$FRAMES/$hash.jpg"; [[ -f "$kept" ]] || cp "$frame" "$kept"
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    added="$(python3 -c "
import json,sys
dets=json.loads(sys.argv[1]); frame=sys.argv[2]; ts=sys.argv[3]; hsh=sys.argv[4]; out=sys.argv[5]
n=0
with open(out,'a') as f:
    for i,d in enumerate(dets):
        f.write(json.dumps({'id':f'{hsh}-{i}','frame':frame,'box':d['box'],'embedding':d['embedding'],
                            'person':None,'oracle':'vision-detect+featureprint','ts':ts,
                            'distill_state':'face-pooled'})+'\n'); n+=1
print(n)
" "$dets" "$kept" "$ts" "$hash" "$SAMPLES" 2>/dev/null || echo 0)"
    faces=$((faces + ${added:-0}))
    rm -f "$frame"
done

total="$(wc -l < "$SAMPLES" 2>/dev/null | tr -d ' ' || echo 0)"
echo "[face-distill] $frames frames · +$faces faces this pass · $total/$TARGET"
