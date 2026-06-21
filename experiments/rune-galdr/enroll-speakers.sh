#!/usr/bin/env bash
# enroll-speakers.sh — build a private speaker roster from PUBLIC voice recordings.
#
# For each named speaker, fetch a ~90s clip from their own public channel, lift the voice
# off any background music with Demucs, and measure a voiceprint (voiceprint.sh). The roster
# is written PRIVATE — ~/.coherence-network/recordings/speakers.json — and never committed;
# voiceprints are biometric. The match itself is form-stdlib/speaker-id.fk (four-way proven).
#
# Default speakers are the Anchor the Light Ceremony cells the body already holds, using the
# public anchors on their presence pages. Override:  enroll-speakers.sh "name|ytsearch query" ...
set -uo pipefail
DIR="$HOME/.coherence-network/recordings/speakers"; mkdir -p "$DIR"
ROSTER="$HOME/.coherence-network/recordings/speakers.json"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SRC_DIR/voiceprint.sh"
VENV="$HOME/.coherence-network/demucs-venv"

SPEAKERS=("$@")
if [[ ${#SPEAKERS[@]} -eq 0 ]]; then
  SPEAKERS=(
    "ubbe|Ubbe MacLean Anchor the Light guided meditation"
    "brigitte|Brigitte Mars herbalist interview"
    "angelia|Angelia LaRue crystal arrays"
  )
fi

echo "[" > "$ROSTER.tmp"; first=1
for s in "${SPEAKERS[@]}"; do
  name="${s%%|*}"; query="${s#*|}"; wav="$DIR/$name.16k.wav"
  if [[ ! -f "$wav" ]]; then
    yt-dlp --no-warnings --download-sections "*30-120" -x --audio-format wav \
      -o "$DIR/$name.%(ext)s" "ytsearch1:$query" >/dev/null 2>&1 || true
    [[ -f "$DIR/$name.wav" ]] && sox "$DIR/$name.wav" -c 1 -r 16000 "$wav" 2>/dev/null
  fi
  if [[ ! -f "$wav" ]]; then echo "  $name: download failed ($query)" >&2; continue; fi
  # lift voice off any background music
  voice="$wav"
  if [[ -x "$VENV/bin/demucs" ]]; then
    "$VENV/bin/demucs" --two-stems=vocals -o "$DIR/sep" "$wav" >/dev/null 2>&1 || true
    cand="$DIR/sep/htdemucs/$name/vocals.wav"
    [[ -f "$cand" ]] && { sox "$cand" -c 1 -r 16000 "$DIR/$name.voice.wav" 2>/dev/null; voice="$DIR/$name.voice.wav"; }
  fi
  vid="$(yt-dlp --no-warnings "ytsearch1:$query" --print "%(id)s|%(title).45s" --skip-download 2>/dev/null | head -1)"
  vp="$(voiceprint "$voice")"
  echo "  enrolled $name: voiceprint=[$vp]  source=$vid" >&2
  [[ $first -eq 0 ]] && echo "," >> "$ROSTER.tmp"; first=0
  printf '  ["%s", [%s]]' "$name" "$(echo "$vp" | tr ' ' ',')" >> "$ROSTER.tmp"
done
echo "" >> "$ROSTER.tmp"; echo "]" >> "$ROSTER.tmp"
mv "$ROSTER.tmp" "$ROSTER"
echo "[enroll] roster → $ROSTER"; cat "$ROSTER"
