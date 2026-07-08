#!/usr/bin/env bash
# satsang-transcribe.sh — pull the latest satsang recording off the phone and transcribe it
# with the Mac's whisper (ggml-large-v3-turbo). The phone records the audio (the source of
# truth); this turns it into text + timestamped subtitles, all on the Mac, nothing cloud.
#
#   ./satsang-transcribe.sh                 # newest recording on the phone
#   ./satsang-transcribe.sh <file.m4a>      # a specific already-pulled file
#
# Output lands beside the audio: <name>.txt and <name>.srt.
set -euo pipefail

ADB="${ADB:-/opt/homebrew/bin/adb}"
SERIAL="${SEMA_PHONE:-192.168.0.8:5555}"
MODEL="${WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"
REMOTE_DIR="/sdcard/Android/data/com.coherence.sema/files/satsang"
OUT_DIR="${SATSANG_DIR:-$HOME/Documents/Coherence-private/satsang}"
mkdir -p "$OUT_DIR"

[[ -f "$MODEL" ]] || { echo "whisper model not found: $MODEL"; exit 2; }
command -v whisper-cli >/dev/null || { echo "whisper-cli not on PATH (brew install whisper-cpp)"; exit 2; }
command -v ffmpeg >/dev/null || { echo "ffmpeg not on PATH (brew install ffmpeg)"; exit 2; }

if [[ $# -ge 1 && -f "$1" ]]; then
    AUDIO="$1"
else
    # newest recording on the phone
    "$ADB" connect "$SERIAL" >/dev/null 2>&1 || true
    latest="$("$ADB" -s "$SERIAL" shell "ls -t $REMOTE_DIR/*.m4a 2>/dev/null | head -1" | tr -d '\r')"
    [[ -n "$latest" ]] || { echo "no recording found in $REMOTE_DIR on $SERIAL"; exit 1; }
    base="$(basename "$latest")"
    AUDIO="$OUT_DIR/$base"
    echo "pulling $base ..."
    "$ADB" -s "$SERIAL" pull "$latest" "$AUDIO" >/dev/null
fi

stem="${AUDIO%.*}"
wav="$stem.16k.wav"
echo "converting to 16kHz wav ..."
ffmpeg -y -i "$AUDIO" -ar 16000 -ac 1 -c:a pcm_s16le "$wav" >/dev/null 2>&1

echo "transcribing with whisper (large-v3-turbo) ..."
whisper-cli -m "$MODEL" -f "$wav" -l auto -otxt -osrt -of "$stem" -t 4 >/dev/null 2>&1
rm -f "$wav"

echo "✓ transcript: $stem.txt"
echo "✓ subtitles:  $stem.srt"
echo "✓ audio kept: $AUDIO"
