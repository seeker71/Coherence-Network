#!/usr/bin/env bash
# mac-room-ear.sh — the room ear's understanding lane (Track B). A clip of room audio becomes WORDS,
# the words become an answer, on the proven body-first path — the rented-mind loop the phone's broken
# on-device STT could never carry. Thin CARRIER: the engines are whisper.cpp (audio -> text) and
# scripts/form_cli_ask.sh (text -> grounded answer, body-first, escalating to the oracle only when local
# is not enough). This is the Mac end of phone-audio -> proxy -> agent -> back.
#
# Run:  mac-room-ear.sh <clip.wav>          transcribe a clip, then answer it body-first
#       mac-room-ear.sh --pull              pull a fresh clip off the phone over adb, then the same
#
# NEEDS: whisper-cli + a ggml model ($ROOM_EAR_MODEL, default ~/.coherence-whisper/ggml-base.en.bin),
# and scripts/form_cli_ask.sh. Local only — the clip and transcript never leave this Mac except as the
# question the agent already answers locally.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODEL="${ROOM_EAR_MODEL:-$HOME/.coherence-whisper/ggml-base.en.bin}"
WHISPER="${ROOM_EAR_WHISPER:-whisper-cli}"
D="${ADB_SERIAL:-192.168.1.223:5555}"

transcribe() {  # $1 = wav -> stdout transcript (one line)
    "$WHISPER" -m "$MODEL" -f "$1" -nt -l en 2>/dev/null | tr -s ' \n' ' ' | sed 's/^ *//; s/ *$//'
}

clip="${1:-}"
if [[ "$clip" == "--pull" ]]; then
    # record a short clip on the phone's mic over adb (the always-on ear logs energy; this grabs raw
    # audio for transcription on demand). Uses the phone's own recorder; pulls the wav back.
    clip=/tmp/room-ear-clip.wav
    echo "[room-ear] recording 6s on the phone..."
    adb -s "$D" shell "rm -f /sdcard/room-ear.amr; am start -W -a android.provider.MediaStore.RECORD_SOUND >/dev/null 2>&1" || true
    echo "[room-ear] (manual clip path) — pass a wav instead; --pull needs a recorder wired. Falling back."
    exit 2
fi
[[ -f "$clip" ]] || { echo "usage: $0 <clip.wav>   (16kHz mono wav)"; exit 1; }
[[ -s "$MODEL" ]] || { echo "[room-ear] no whisper model at $MODEL — set ROOM_EAR_MODEL"; exit 1; }

echo "[room-ear] hearing the clip..."
text="$(transcribe "$clip")"
echo "  heard: \"$text\""
[[ -n "$text" ]] || { echo "  (silence — nothing to answer)"; exit 0; }

echo "[room-ear] understanding (body-first agent)..."
bash "$ROOT/scripts/form_cli_ask.sh" "$text" 2>/dev/null
echo "[room-ear] (recipe: form_cli_ask body-first + oracle-escalation; transcription: whisper.cpp; local)"
