#!/usr/bin/env bash
# separate-galdr.sh — lift the galdr VOICE off the ritual DRUM (source separation carrier).
#
# A frame drum and the sung galdr overlap in the formant range, so band filtering alone
# can't part them. Demucs (htdemucs) is the separation ORACLE — like whisper-cli is the STT
# oracle: a tool the carrier calls, never the body's logic. It splits an audio file into a
# vocals stem (the galdr) and a no_vocals stem (the drum + room), so the rune flow-match
# (rune-frequency.fk) can read the voice alone.
#
#   separate-galdr.sh input.wav [START DUR]   # -> <input>.vocals.16k.wav  (+ .drum.16k.wav)
# Needs the demucs venv: ~/.coherence-network/demucs-venv (python3.11 -m venv … ; pip install demucs soundfile).
set -uo pipefail
VENV="$HOME/.coherence-network/demucs-venv"
DEMUCS="$VENV/bin/demucs"
[[ -x "$DEMUCS" ]] || { echo "FAIL demucs not installed — python3.11 -m venv $VENV && $VENV/bin/pip install demucs soundfile"; exit 1; }
SRC="${1:?need an audio file}"; START="${2:-}"; DUR="${3:-}"
TMP="$(mktemp -d /tmp/sep-galdr.XXXX)"; trap 'rm -rf "$TMP"' EXIT
base="${SRC%.*}"

in="$SRC"
if [[ -n "$START" ]]; then
    in="$TMP/clip.wav"; sox "$SRC" "$in" trim "$START" "${DUR:-60}" 2>/dev/null
fi
echo "[separate] demucs --two-stems=vocals on $(basename "$in") …"
"$DEMUCS" --two-stems=vocals -o "$TMP/out" "$in" >/dev/null 2>&1
stem="$TMP/out/htdemucs/$(basename "${in%.*}")"
[[ -f "$stem/vocals.wav" ]] || { echo "FAIL demucs produced no vocals stem"; exit 2; }
sox "$stem/vocals.wav"    -c 1 -r 16000 "$base.vocals.16k.wav" 2>/dev/null
sox "$stem/no_vocals.wav" -c 1 -r 16000 "$base.drum.16k.wav"   2>/dev/null
echo "[separate] voice → $base.vocals.16k.wav"
echo "[separate] drum  → $base.drum.16k.wav"
# report how much drum (<150 Hz) each stem holds — the separation receipt
dv=$(sox "$base.vocals.16k.wav" -n lowpass 150 stat 2>&1 | awk '/RMS +amplitude/{print $3}')
dd=$(sox "$base.drum.16k.wav"   -n lowpass 150 stat 2>&1 | awk '/RMS +amplitude/{print $3}')
echo "[separate] drum<150Hz energy — voice stem: ${dv}   drum stem: ${dd}"
