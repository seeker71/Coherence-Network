#!/usr/bin/env bash
# satsang-analyze.sh — clean a far-mic satsang recording and transcribe it in multiple
# passes. The mic was distant (mean ~-38dB), so speech is lifted and denoised before
# whisper sees it. Everything stays local (private circle audio never leaves the Mac).
#
#   ./satsang-analyze.sh <recording.m4a>
#
# Outputs beside the recording:
#   <name>.clean.wav                 the enhanced 16kHz audio (what whisper reads)
#   <name>.clean.{txt,srt,json}      pass A: transcription of the CLEANED audio
#   <name>.raw.{txt,srt}             pass B: transcription of the RAW audio (for comparison)
set -euo pipefail

IN="${1:?usage: satsang-analyze.sh <recording.m4a>}"
MODEL="${WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"
LANG="${SATSANG_LANG:-auto}"
stem="${IN%.*}"
clean="$stem.clean.wav"
rawwav="$stem.raw.wav"

echo "[analyze] $(date -u +%H:%M:%S) cleaning far-mic audio ..."
# highpass: cut rumble/HVAC; afftdn: FFT denoise the steady room noise; dynaudnorm: lift the
# quiet distant speech without pumping; alimiter: catch peaks. Then 16kHz mono for whisper.
ffmpeg -y -i "$IN" \
    -af "highpass=f=85,afftdn=nr=12:nf=-25,dynaudnorm=p=0.9:m=15:s=5,loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.97" \
    -ar 16000 -ac 1 -c:a pcm_s16le "$clean" 2>/dev/null
echo "[analyze] $(date -u +%H:%M:%S) cleaned -> $(basename "$clean")"

echo "[analyze] $(date -u +%H:%M:%S) pass A: transcribing CLEANED audio (beam 5) ..."
whisper-cli -m "$MODEL" -f "$clean" -l "$LANG" -bs 5 -bo 5 -otxt -osrt -oj -of "$stem.clean" -t 6 2>/dev/null
echo "[analyze] $(date -u +%H:%M:%S) pass A done -> $(basename "$stem").clean.txt"

echo "[analyze] $(date -u +%H:%M:%S) pass B: transcribing RAW audio for comparison ..."
ffmpeg -y -i "$IN" -ar 16000 -ac 1 -c:a pcm_s16le "$rawwav" 2>/dev/null
whisper-cli -m "$MODEL" -f "$rawwav" -l "$LANG" -bs 5 -otxt -osrt -of "$stem.raw" -t 6 2>/dev/null
rm -f "$rawwav"
echo "[analyze] $(date -u +%H:%M:%S) pass B done -> $(basename "$stem").raw.txt"

echo "[analyze] $(date -u +%H:%M:%S) ALL DONE. clean vs raw transcripts ready beside the recording."
