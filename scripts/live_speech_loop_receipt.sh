#!/usr/bin/env bash
# live_speech_loop_receipt.sh - known text played over speaker, heard by live mics.
#
# Floor: render known text locally, play it through the Mac speaker, record the
# room through the Mac microphone, transcribe that recording with local
# whisper-cli, and capture the Android witness mic lane during the same window.
# This is a carrier witness; Form owns the acceptance contract.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXT="${1:-form native speech loop listens with two microphones}"
MODEL="${WHISPER_MODEL:-/Users/ursmuff/whisper-models/ggml-large-v3-turbo.bin}"
VOICE="${SPEECH_TEACHER_VOICE:-Samantha}"
WITNESS_URL="${SPEECH_LOOP_WITNESS_URL:-http://127.0.0.1:8800/state}"
OUT_DIR="${SPEECH_LOOP_OUT:-$ROOT/.cache/live-speech-loop/$(date -u +%Y%m%dT%H%M%SZ)}"

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "FAIL missing required tool: $1" >&2
        exit 1
    fi
}

need say
need afconvert
need afplay
need rec
need sox
need whisper-cli
need jq
need curl
need shasum
need awk
need tr
need wc

if [[ ! -f "$MODEL" ]]; then
    echo "FAIL missing whisper model: $MODEL" >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
AIFF="$OUT_DIR/teacher-playback.aiff"
REFERENCE_WAV="$OUT_DIR/teacher-reference.wav"
MAC_WAV="$OUT_DIR/mac-mic-room.wav"
MAC_STATS="$OUT_DIR/mac-mic.stats"
ANDROID_JSONL="$OUT_DIR/android-mic-window.jsonl"
PREFIX="$OUT_DIR/mac-mic-transcript"
TRANSCRIPT_JSON="$PREFIX.json"
STDOUT_LOG="$OUT_DIR/whisper.stdout"
STDERR_LOG="$OUT_DIR/whisper.stderr"
RECEIPT="$OUT_DIR/live-speech-loop-receipt.json"

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

say -v "$VOICE" -o "$AIFF" "$TEXT"
afconvert -f WAVE -d LEI16@16000 -c 1 "$AIFF" "$REFERENCE_WAV"
reference_seconds="$(sox "$REFERENCE_WAV" -n stat 2>&1 | awk -F: '$1 ~ /Length/ {gsub(/ /, "", $2); print $2}')"
record_seconds="$(awk -v s="${reference_seconds:-2}" 'BEGIN { printf "%.2f", s + 2.0 }')"
poll_count="$(awk -v s="$record_seconds" 'BEGIN { n=int((s / 0.25) + 8); if (n < 12) n=12; print n }')"

(
    for _ in $(seq 1 "$poll_count"); do
        ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        curl -sS --max-time 1 "$WITNESS_URL" \
            | jq --arg ts "$ts" '{t:$ts, present, frames, sample_frames, heartbeat_frames, latest:{mic_rms:.latest.mic_rms, organs_active:.latest.organs_active, channels_offered:.latest.channels_offered, body_state:.latest.body_state}}' \
            || true
        sleep 0.25
    done
) > "$ANDROID_JSONL" &
android_poll_pid=$!

rec -q -r 16000 -b 16 -c 1 "$MAC_WAV" trim 0 "$record_seconds" &
rec_pid=$!
sleep 0.45
started_s="$(date +%s)"
afplay "$AIFF"
wait "$rec_pid"
wait "$android_poll_pid" || true
ended_s="$(date +%s)"

sox "$MAC_WAV" -n stat >"$MAC_STATS" 2>&1

set +e
whisper-cli -m "$MODEL" -f "$MAC_WAV" -l en -nt -np -oj -of "$PREFIX" >"$STDOUT_LOG" 2>"$STDERR_LOG"
whisper_status=$?
set -e
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

samples="$(awk -F: '$1 ~ /Samples read/ {gsub(/ /, "", $2); print $2}' "$MAC_STATS")"
length_seconds="$(awk -F: '$1 ~ /Length/ {gsub(/ /, "", $2); print $2}' "$MAC_STATS")"
rms_amplitude="$(awk -F: '/RMS[[:space:]]+amplitude/ {gsub(/ /, "", $2); print $2}' "$MAC_STATS")"
rough_frequency="$(awk -F: '/Rough[[:space:]]+frequency/ {gsub(/ /, "", $2); print $2}' "$MAC_STATS")"
duration_ms="$(awk -v s="${length_seconds:-0}" 'BEGIN { printf "%d", int((s * 1000) + 0.5) }')"
rms_ppm="$(awk -v r="${rms_amplitude:-0}" 'BEGIN { printf "%d", int((r * 1000000) + 0.5) }')"
rough_hz="${rough_frequency:-0}"
wav_bytes="$(wc -c < "$MAC_WAV" | tr -d ' ')"
ref_bytes="$(wc -c < "$REFERENCE_WAV" | tr -d ' ')"
transcript_bytes="$(wc -c < "$TRANSCRIPT_JSON" | tr -d ' ')"

android_metrics="$(
    jq -s '
      [ .[] | select(.present == true and (.latest.mic_rms != null)) | .latest.mic_rms ] as $r
      | {
          samples: ($r | length),
          min: (if ($r | length) > 0 then ($r | min) else 0 end),
          max: (if ($r | length) > 0 then ($r | max) else 0 end),
          avg: (if ($r | length) > 0 then (($r | add) / ($r | length)) else 0 end)
        }
    ' "$ANDROID_JSONL"
)"
android_samples="$(jq -r '.samples' <<<"$android_metrics")"
android_min_ppm="$(jq -r '.min' <<<"$android_metrics" | awk '{ printf "%d", int(($1 * 1000000) + 0.5) }')"
android_max_ppm="$(jq -r '.max' <<<"$android_metrics" | awk '{ printf "%d", int(($1 * 1000000) + 0.5) }')"
android_avg_ppm="$(jq -r '.avg' <<<"$android_metrics" | awk '{ printf "%d", int(($1 * 1000000) + 0.5) }')"

audio_sha="$(shasum -a 256 "$MAC_WAV" | awk '{print $1}')"
reference_sha="$(shasum -a 256 "$REFERENCE_WAV" | awk '{print $1}')"
transcript_sha="$(shasum -a 256 "$TRANSCRIPT_JSON" | awk '{print $1}')"
model_sha="$(shasum -a 256 "$MODEL" | awk '{print $1}')"
wall_ms=$(((ended_s - started_s) * 1000))

status="pass"
if [[ "$overlap" -lt 80 || "${samples:-0}" -le 0 || "$duration_ms" -le 0 || "$rms_ppm" -le 0 || "${rough_hz:-0}" -le 0 || "$wav_bytes" -le 0 || "$android_samples" -lt 3 || "$android_avg_ppm" -le 0 ]]; then
    status="blocked"
fi

jq -n \
    --arg kind "live-speech-loop-receipt" \
    --arg status "$status" \
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
    --arg reference_sha "sha256:$reference_sha" \
    --arg transcript_sha "sha256:$transcript_sha" \
    --arg out_dir "$OUT_DIR" \
    --arg mac_wav_path "$MAC_WAV" \
    --arg reference_wav_path "$REFERENCE_WAV" \
    --arg transcript_path "$TRANSCRIPT_JSON" \
    --arg android_window_path "$ANDROID_JSONL" \
    --arg witness_url "$WITNESS_URL" \
    --arg floor "known text must be played over a speaker, heard by the Mac mic, transcribed by local STT, and co-witnessed by Android mic telemetry in the same window" \
    --arg north_star "speech loops become multi-device native training windows whose STT/TTS teachers retire only when Form-native candidates win heldout dual-mic receipts" \
    --argjson overlap "$overlap" \
    --argjson samples "${samples:-0}" \
    --argjson duration_ms "$duration_ms" \
    --argjson rms_ppm "$rms_ppm" \
    --argjson rough_hz "$rough_hz" \
    --argjson wav_bytes "$wav_bytes" \
    --argjson reference_wav_bytes "$ref_bytes" \
    --argjson transcript_bytes "$transcript_bytes" \
    --argjson wall_ms "$wall_ms" \
    --argjson raw_audio_retained 1 \
    --argjson android_samples "$android_samples" \
    --argjson android_min_rms_ppm "$android_min_ppm" \
    --argjson android_max_rms_ppm "$android_max_ppm" \
    --argjson android_avg_rms_ppm "$android_avg_ppm" \
    '{
        kind:$kind,
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
        mac_mic_audio_sha256:$audio_sha,
        reference_audio_sha256:$reference_sha,
        transcript_sha256:$transcript_sha,
        mac_mic_wav_bytes:$wav_bytes,
        reference_wav_bytes:$reference_wav_bytes,
        transcript_bytes:$transcript_bytes,
        mac_mic_samples:$samples,
        duration_ms:$duration_ms,
        mac_mic_rms_ppm:$rms_ppm,
        mac_mic_rough_hz:$rough_hz,
        android_mic_samples:$android_samples,
        android_mic_min_rms_ppm:$android_min_rms_ppm,
        android_mic_max_rms_ppm:$android_max_rms_ppm,
        android_mic_avg_rms_ppm:$android_avg_rms_ppm,
        wall_ms:$wall_ms,
        raw_audio_retained:$raw_audio_retained,
        out_dir:$out_dir,
        mac_mic_wav_path:$mac_wav_path,
        reference_wav_path:$reference_wav_path,
        transcript_path:$transcript_path,
        android_window_path:$android_window_path,
        witness_url:$witness_url,
        floor:$floor,
        north_star:$north_star,
        form_teacher_receipt:{
            status:$status,
            tts_provider:$tts_provider,
            stt_provider:$stt_provider,
            stt_model:$stt_model,
            expected:$text,
            transcript:$transcript,
            overlap:$overlap,
            wav_bytes:$wav_bytes,
            samples:$samples,
            duration_ms:$duration_ms,
            rms_ppm:$rms_ppm,
            rough_hz:$rough_hz,
            audio_sha256:$audio_sha,
            transcript_sha256:$transcript_sha,
            raw_audio_retained:$raw_audio_retained
        }
    }' > "$RECEIPT"

if [[ "$status" != "pass" ]]; then
    echo "FAIL live-speech-loop receipt=$RECEIPT overlap=$overlap android_samples=$android_samples android_avg_rms_ppm=$android_avg_ppm" >&2
    jq '{status, transcript_overlap_percent, transcript, mac_mic_rms_ppm, android_mic_samples, android_mic_avg_rms_ppm}' "$RECEIPT" >&2
    exit 1
fi

echo "PASS live-speech-loop receipt=$RECEIPT overlap=$overlap mac_samples=${samples:-0} android_samples=$android_samples android_avg_rms_ppm=$android_avg_ppm"
