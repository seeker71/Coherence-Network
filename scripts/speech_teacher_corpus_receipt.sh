#!/usr/bin/env bash
# speech_teacher_corpus_receipt.sh - live local speech teacher corpus receipt.
#
# Floor: collect several real local macOS TTS -> 16 kHz PCM -> whisper-cli
# receipts into one inspectable corpus receipt with aggregate hashes and audio
# metrics. This is a carrier witness only; Form owns the corpus contract in
# speech-model-learning.fk and speech-teacher-corpus-band.fk.
#
# North star: speech training windows are native channel corpora whose examples,
# artifacts, labels, metrics, and teacher authority can be shared, replayed, and
# retired by heldout evidence across macOS, Android, and mesh organs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${SPEECH_TEACHER_CORPUS_OUT:-$ROOT/.cache/speech-teacher-corpus/$(date -u +%Y%m%dT%H%M%SZ)}"
RECEIPT="$OUT_DIR/speech-teacher-corpus-receipt.json"
RECEIPTS_JSON="$OUT_DIR/sample-receipts.json"

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "FAIL missing required tool: $1" >&2
        exit 1
    fi
}

need jq
need shasum
need awk
need tee

mkdir -p "$OUT_DIR"

if [[ "$#" -gt 0 ]]; then
    phrases=("$@")
else
    phrases=(
        "form native speech teacher receipt"
        "cells learn from real audio"
        "the local model returns a transcript"
        "speech receipts guide native learning"
    )
fi

if [[ "${#phrases[@]}" -lt 3 ]]; then
    echo "FAIL corpus needs at least 3 phrases; got ${#phrases[@]}" >&2
    exit 1
fi

receipt_paths=()
idx=0
for phrase in "${phrases[@]}"; do
    sample_dir="$OUT_DIR/sample-$(printf '%03d' "$idx")"
    SPEECH_TEACHER_OUT="$sample_dir" "$ROOT/scripts/speech_teacher_receipt.sh" "$phrase" | tee "$sample_dir.stdout"
    receipt_paths+=("$sample_dir/speech-teacher-receipt.json")
    idx=$((idx + 1))
done

jq -s '.' "${receipt_paths[@]}" > "$RECEIPTS_JSON"
corpus_sha="$(
    jq -r '.[] | [.audio_sha256, .transcript_sha256, (.text | tostring)] | @tsv' "$RECEIPTS_JSON" \
        | shasum -a 256 \
        | awk '{print $1}'
)"

jq \
    --arg corpus_sha "sha256:$corpus_sha" \
    --arg out_dir "$OUT_DIR" \
    --arg floor "a corpus needs at least 3 pass receipts, all with retained audio, nonzero metrics, and transcript overlap at or above 80 percent" \
    --arg north_star "speech corpora become native channel training windows that retire teacher authority only by heldout native wins" \
    '{
        kind:"speech-teacher-corpus-receipt",
        status:(if ((length >= 3) and all(.[]; .status == "pass" and .transcript_overlap_percent >= 80 and .raw_audio_retained == 1 and .duration_ms > 0 and .samples > 0)) then "pass" else "blocked" end),
        sample_count:length,
        pass_count:([.[] | select(.status == "pass")] | length),
        min_overlap_percent:([.[].transcript_overlap_percent] | min),
        total_wav_bytes:([.[].wav_bytes] | add),
        total_samples:([.[].samples] | add),
        total_duration_ms:([.[].duration_ms] | add),
        model_names:([.[].stt_model] | unique),
        tts_providers:([.[].tts_provider] | unique),
        stt_providers:([.[].stt_provider] | unique),
        corpus_sha256:$corpus_sha,
        raw_audio_retained:1,
        out_dir:$out_dir,
        sample_receipts:.,
        floor:$floor,
        north_star:$north_star
    }' "$RECEIPTS_JSON" > "$RECEIPT"

if [[ "$(jq -r '.status' "$RECEIPT")" != "pass" ]]; then
    echo "FAIL speech-teacher-corpus receipt=$RECEIPT" >&2
    jq '{status, sample_count, pass_count, min_overlap_percent, total_duration_ms}' "$RECEIPT" >&2
    exit 1
fi

echo "PASS speech-teacher-corpus receipt=$RECEIPT samples=$(jq -r '.sample_count' "$RECEIPT") min_overlap=$(jq -r '.min_overlap_percent' "$RECEIPT") total_duration_ms=$(jq -r '.total_duration_ms' "$RECEIPT") sha=$(jq -r '.corpus_sha256' "$RECEIPT")"
