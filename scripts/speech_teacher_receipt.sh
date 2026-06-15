#!/usr/bin/env bash
# speech_teacher_receipt.sh - live local TTS -> STT teacher receipt.
#
# Floor: generate inspectable local macOS TTS audio, convert it to 16 kHz mono
# PCM, transcribe it with local whisper-cli, and write a bounded JSON receipt.
# This script is a carrier witness only; Form owns the learning contract in
# speech-model-learning.fk and speech-teacher-receipt-band.fk.
#
# North star: every local/remote speech teacher call becomes native training
# data until Form-native STT/TTS candidates win by heldout receipts with lower
# token, energy, nutrition, and higher sovereignty/trust.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXT="${1:-form native speech teacher receipt}"
MODEL="${WHISPER_MODEL:-/Users/ursmuff/whisper-models/ggml-large-v3-turbo.bin}"
VOICE="${SPEECH_TEACHER_VOICE:-Samantha}"
OUT_DIR="${SPEECH_TEACHER_OUT:-$ROOT/.cache/speech-teacher-receipt/$(date -u +%Y%m%dT%H%M%SZ)}"

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "FAIL missing required tool: $1" >&2
        exit 1
    fi
}

need say
need afconvert
need sox
need whisper-cli
need jq
need shasum
need awk
need tr
need wc

if [[ ! -f "$MODEL" ]]; then
    echo "FAIL missing whisper model: $MODEL" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
AIFF="$OUT_DIR/teacher.aiff"
WAV="$OUT_DIR/teacher.wav"
STATS="$OUT_DIR/audio.stats"
PREFIX="$OUT_DIR/transcript"
TRANSCRIPT_JSON="$PREFIX.json"
STDOUT_LOG="$OUT_DIR/whisper.stdout"
STDERR_LOG="$OUT_DIR/whisper.stderr"
RECEIPT="$OUT_DIR/speech-teacher-receipt.json"

normalize_text() {
    printf '%s' "$1" \
        | tr '[:upper:]' '[:lower:]' \
        | tr -cd '[:alnum:] ' \
        | awk '{$1=$1; print}'
}

token_overlap_percent() {
    local expected_norm="$1"
    local actual_norm="$2"
    local total=0
    local hit=0
    local word
    for word in $expected_norm; do
        total=$((total + 1))
        case " $actual_norm " in
            *" $word "*) hit=$((hit + 1)) ;;
        esac
    done
    if [[ "$total" -eq 0 ]]; then
        printf '0'
    else
        awk -v h="$hit" -v t="$total" 'BEGIN { printf "%d", int((h * 100 / t) + 0.5) }'
    fi
}

started_s="$(date +%s)"
say -v "$VOICE" -o "$AIFF" "$TEXT"
afconvert -f WAVE -d LEI16@16000 -c 1 "$AIFF" "$WAV"
sox "$WAV" -n stat >"$STATS" 2>&1

set +e
whisper-cli -m "$MODEL" -f "$WAV" -l en -nt -np -oj -of "$PREFIX" >"$STDOUT_LOG" 2>"$STDERR_LOG"
whisper_status=$?
set -e
ended_s="$(date +%s)"

if [[ "$whisper_status" -ne 0 ]]; then
    echo "FAIL whisper-cli exited $whisper_status; stderr=$STDERR_LOG" >&2
    exit "$whisper_status"
fi
if [[ ! -s "$TRANSCRIPT_JSON" ]]; then
    echo "FAIL whisper-cli did not write transcript JSON: $TRANSCRIPT_JSON" >&2
    exit 1
fi

transcript="$(jq -r '[.transcription[].text] | join(" ")' "$TRANSCRIPT_JSON")"
expected_norm="$(normalize_text "$TEXT")"
transcript_norm="$(normalize_text "$transcript")"
overlap="$(token_overlap_percent "$expected_norm" "$transcript_norm")"
match_status="pass"
if [[ "$overlap" -lt 80 ]]; then
    match_status="blocked"
fi

samples="$(awk -F: '$1 ~ /Samples read/ {gsub(/ /, "", $2); print $2}' "$STATS")"
length_seconds="$(awk -F: '$1 ~ /Length/ {gsub(/ /, "", $2); print $2}' "$STATS")"
rms_amplitude="$(awk -F: '/RMS[[:space:]]+amplitude/ {gsub(/ /, "", $2); print $2}' "$STATS")"
rough_frequency="$(awk -F: '/Rough[[:space:]]+frequency/ {gsub(/ /, "", $2); print $2}' "$STATS")"
duration_ms="$(awk -v s="${length_seconds:-0}" 'BEGIN { printf "%d", int((s * 1000) + 0.5) }')"
rms_ppm="$(awk -v r="${rms_amplitude:-0}" 'BEGIN { printf "%d", int((r * 1000000) + 0.5) }')"
rough_hz="${rough_frequency:-0}"
wav_bytes="$(wc -c < "$WAV" | tr -d ' ')"
if [[ "${samples:-0}" -le 0 || "$duration_ms" -le 0 || "$rms_ppm" -le 0 || "${rough_hz:-0}" -le 0 || "$wav_bytes" -le 0 ]]; then
    echo "FAIL missing nonzero audio metrics; stats=$STATS samples=${samples:-0} duration_ms=$duration_ms rms_ppm=$rms_ppm rough_hz=${rough_hz:-0} wav_bytes=$wav_bytes" >&2
    exit 1
fi
aiff_bytes="$(wc -c < "$AIFF" | tr -d ' ')"
json_bytes="$(wc -c < "$TRANSCRIPT_JSON" | tr -d ' ')"
audio_sha="$(shasum -a 256 "$WAV" | awk '{print $1}')"
aiff_sha="$(shasum -a 256 "$AIFF" | awk '{print $1}')"
transcript_sha="$(shasum -a 256 "$TRANSCRIPT_JSON" | awk '{print $1}')"
model_sha="$(shasum -a 256 "$MODEL" | awk '{print $1}')"
wall_ms=$(((ended_s - started_s) * 1000))

jq -n \
    --arg status "$match_status" \
    --arg text "$TEXT" \
    --arg expected_norm "$expected_norm" \
    --arg transcript "$transcript" \
    --arg transcript_norm "$transcript_norm" \
    --arg voice "$VOICE" \
    --arg tts_provider "macos-say" \
    --arg stt_provider "whisper-cli" \
    --arg stt_model "$(basename "$MODEL")" \
    --arg stt_model_path "$MODEL" \
    --arg model_sha "sha256:$model_sha" \
    --arg audio_sha "sha256:$audio_sha" \
    --arg aiff_sha "sha256:$aiff_sha" \
    --arg transcript_sha "sha256:$transcript_sha" \
    --arg out_dir "$OUT_DIR" \
    --arg wav_path "$WAV" \
    --arg transcript_path "$TRANSCRIPT_JSON" \
    --arg floor "local TTS audio and local Whisper transcript must be inspectable, hashed, and overlap expected text by at least 80 percent" \
    --arg north_star "speech teachers retire only when native STT/TTS candidates win heldout receipts with lower cost and retained trust" \
    --argjson overlap "$overlap" \
    --argjson samples "${samples:-0}" \
    --argjson duration_ms "$duration_ms" \
    --argjson rms_ppm "$rms_ppm" \
    --argjson rough_hz "$rough_hz" \
    --argjson wav_bytes "$wav_bytes" \
    --argjson aiff_bytes "$aiff_bytes" \
    --argjson transcript_bytes "$json_bytes" \
    --argjson wall_ms "$wall_ms" \
    --argjson raw_audio_retained 1 \
    '{
        kind:"speech-teacher-receipt",
        status:$status,
        text:$text,
        expected_norm:$expected_norm,
        transcript:$transcript,
        transcript_norm:$transcript_norm,
        transcript_overlap_percent:$overlap,
        tts_provider:$tts_provider,
        tts_voice:$voice,
        stt_provider:$stt_provider,
        stt_model:$stt_model,
        stt_model_path:$stt_model_path,
        stt_model_sha256:$model_sha,
        audio_sha256:$audio_sha,
        aiff_sha256:$aiff_sha,
        transcript_sha256:$transcript_sha,
        wav_bytes:$wav_bytes,
        aiff_bytes:$aiff_bytes,
        transcript_bytes:$transcript_bytes,
        samples:$samples,
        duration_ms:$duration_ms,
        rms_ppm:$rms_ppm,
        rough_hz:$rough_hz,
        wall_ms:$wall_ms,
        raw_audio_retained:$raw_audio_retained,
        out_dir:$out_dir,
        wav_path:$wav_path,
        transcript_path:$transcript_path,
        floor:$floor,
        north_star:$north_star
    }' > "$RECEIPT"

if [[ "$match_status" != "pass" ]]; then
    echo "FAIL speech-teacher receipt overlap=$overlap receipt=$RECEIPT" >&2
    jq '.' "$RECEIPT" >&2
    exit 1
fi

echo "PASS speech-teacher receipt=$RECEIPT overlap=$overlap wav_bytes=$wav_bytes samples=${samples:-0} rms_ppm=$rms_ppm model=$(basename "$MODEL")"
