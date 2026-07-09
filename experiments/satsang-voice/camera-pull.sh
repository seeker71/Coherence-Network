#!/usr/bin/env bash
# camera-pull.sh — bring the phone's eye into the same training pipeline as the Mac's. Mirrors
# satsang-mesh-sync: over the LAN it shares with the phone, pull every camera frame the phone's
# CameraEye captured, drop each into BOTH the face and vision inboxes (so face-distill and
# vision-distill label them), then remove them from the phone. Two devices, multiple angles, one
# training set. Raw frames are content-addressed on the Mac; the phone keeps none once pulled.
#
# Run as the organ earth.hati.camera-pull (every ~60s), or once by hand.
set -uo pipefail
ADB="${ADB:-/opt/homebrew/bin/adb}"
SERIAL="${SEMA_PHONE:-192.168.0.8:5555}"
REMOTE="/sdcard/Android/data/com.coherence.sema/files/camera"
CN="$HOME/.coherence-network"
FACE="$CN/face-training/inbox"; VISION="$CN/vision-training/inbox"
STAGE="$CN/camera-pull/stage"
mkdir -p "$FACE" "$VISION" "$STAGE"

"$ADB" connect "$SERIAL" >/dev/null 2>&1 || true
"$ADB" -s "$SERIAL" shell true >/dev/null 2>&1 || { echo "[camera-pull] phone not on this LAN — nothing to pull"; exit 0; }

# list frames on the phone (macOS bash 3.2 — no mapfile; stream through a while-read loop)
listing="$("$ADB" -s "$SERIAL" shell "ls $REMOTE/*.jpg 2>/dev/null" | tr -d '\r')"
[[ -z "$listing" ]] && { echo "[camera-pull] no frames on phone"; exit 0; }

n=0
while IFS= read -r remote; do
    [[ -n "$remote" ]] || continue
    base="$(basename "$remote")"
    local_stage="$STAGE/$base"
    if "$ADB" -s "$SERIAL" pull "$remote" "$local_stage" >/dev/null 2>&1 && [[ -s "$local_stage" ]]; then
        # phone frames are named front-/back- ; tag provenance so the store shows the angle
        cp "$local_stage" "$FACE/phone-$base"
        cp "$local_stage" "$VISION/phone-$base"
        "$ADB" -s "$SERIAL" shell "rm -f '$remote'" >/dev/null 2>&1
        rm -f "$local_stage"
        n=$((n+1))
    fi
done <<< "$listing"
echo "[camera-pull] pulled $n phone frames into face+vision inboxes"
