#!/usr/bin/env bash
# real_mesh_training_emitters.sh - host/device/model carrier for real mesh training.
#
# Form owns the receipt validity in form/form-stdlib/real-mesh-training-*.fk.
# This script only gathers physical host evidence: local witness endpoints,
# adb visibility, bounded content-addressed file roots, and optional local
# model process runs. It emits an active receipt only when the hard data floor
# is actually present.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR=""
WITNESS_URL="http://127.0.0.1:8800/state"
TRANSCRIPT_URL="http://127.0.0.1:8799/state"
OLLAMA_MODEL="llama3.2:3b"
WHISPER_MODEL=""
RUN_MODELS=0
REQUIRE_ACTIVE=0
LABEL_COUNT=0
TRAIN_ROOTS=()
HELDOUT_ROOTS=()

MIN_TRAIN_BYTES=314572800
MIN_HELDOUT_BYTES=104857600
MIN_LABELS=10000

usage() {
    cat <<'USAGE'
Usage: scripts/real_mesh_training_emitters.sh [options]

Options:
  --out DIR                 Receipt output directory.
  --witness-url URL         Mac/Android witness state endpoint.
  --transcript-url URL      Local STT/transcript witness endpoint.
  --data-root DIR           Repeatable training data root.
  --heldout-root DIR        Repeatable heldout data root.
  --label-count N           External label count when labels live outside roots.
  --run-models              Execute local model probes instead of inventory only.
  --ollama-model NAME       Ollama model for NL/sentiment/confidence probes.
  --whisper-model FILE      whisper.cpp model for optional STT probe.
  --require-active          Exit nonzero unless the hard active floor is met.
  -h, --help                Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out)
            OUT_DIR="$2"
            shift 2
            ;;
        --witness-url)
            WITNESS_URL="$2"
            shift 2
            ;;
        --transcript-url)
            TRANSCRIPT_URL="$2"
            shift 2
            ;;
        --data-root)
            TRAIN_ROOTS+=("$2")
            shift 2
            ;;
        --heldout-root)
            HELDOUT_ROOTS+=("$2")
            shift 2
            ;;
        --label-count)
            LABEL_COUNT="$2"
            shift 2
            ;;
        --run-models)
            RUN_MODELS=1
            shift
            ;;
        --ollama-model)
            OLLAMA_MODEL="$2"
            shift 2
            ;;
        --whisper-model)
            WHISPER_MODEL="$2"
            shift 2
            ;;
        --require-active)
            REQUIRE_ACTIVE=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$OUT_DIR" ]]; then
    OUT_DIR="$ROOT/.cache/real-mesh-training/windows/$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "$OUT_DIR"/{sources,processes}

TOOLS_JSONL="$OUT_DIR/tools.jsonl"
SOURCES_JSONL="$OUT_DIR/sources.jsonl"
PROCESSES_JSONL="$OUT_DIR/processes.jsonl"
BLOCKS_JSONL="$OUT_DIR/blocks.jsonl"
: > "$TOOLS_JSONL"
: > "$SOURCES_JSONL"
: > "$PROCESSES_JSONL"
: > "$BLOCKS_JSONL"

json_string() {
    jq -Rs . <<<"${1:-}"
}

sha256_file() {
    if [[ -s "$1" ]]; then
        shasum -a 256 "$1" | awk '{print "sha256:" $1}'
    else
        printf ''
    fi
}

add_block() {
    local code="$1"
    local detail="$2"
    jq -nc --arg code "$code" --arg detail "$detail" \
        '{code:$code, detail:$detail}' >> "$BLOCKS_JSONL"
}

add_tool() {
    local name="$1"
    local path status
    if path="$(command -v "$name" 2>/dev/null)"; then
        status="present"
    else
        path=""
        status="absent"
    fi
    jq -nc --arg name "$name" --arg path "$path" --arg status "$status" \
        '{name:$name, path:$path, status:$status}' >> "$TOOLS_JSONL"
    [[ "$status" == "present" ]]
}

file_size() {
    if [[ -f "$1" ]]; then
        wc -c < "$1" | tr -d ' '
    else
        printf '0'
    fi
}

now_ms() {
    printf '%s000' "$(date +%s)"
}

add_source() {
    local name="$1"
    local transport="$2"
    local status="$3"
    local bytes="$4"
    local samples="$5"
    local merkle="$6"
    local path="${7:-}"
    jq -nc \
        --arg name "$name" \
        --arg transport "$transport" \
        --arg status "$status" \
        --arg merkle "$merkle" \
        --arg path "$path" \
        --argjson bytes "$bytes" \
        --argjson samples "$samples" \
        '{name:$name, transport:$transport, status:$status, bytes:$bytes, samples:$samples, merkle:$merkle, path:$path}' \
        >> "$SOURCES_JSONL"
}

run_receipted_process() {
    local task="$1"
    local command_text="$2"
    local provider="$3"
    local model="$4"
    local output_file="${5:-}"
    local stdout_file="$OUT_DIR/processes/${task}.stdout"
    local stderr_file="$OUT_DIR/processes/${task}.stderr"
    local started ended exit_code stdout_bytes stderr_bytes duration_ms
    started="$(now_ms)"
    set +e
    bash -lc "$command_text" > "$stdout_file" 2> "$stderr_file"
    exit_code=$?
    set -e
    ended="$(now_ms)"
    duration_ms=$((ended - started))
    if [[ "$duration_ms" -le 0 ]]; then
        duration_ms=1
    fi
    stdout_bytes="$(file_size "$stdout_file")"
    if [[ -n "$output_file" && -f "$output_file" ]]; then
        stdout_bytes="$(file_size "$output_file")"
    fi
    stderr_bytes="$(file_size "$stderr_file")"
    jq -nc \
        --arg task "$task" \
        --arg command "$command_text" \
        --arg provider "$provider" \
        --arg model "$model" \
        --arg stdout_path "$stdout_file" \
        --arg stderr_path "$stderr_file" \
        --arg output_path "$output_file" \
        --argjson exit_code "$exit_code" \
        --argjson stdout_bytes "$stdout_bytes" \
        --argjson stderr_bytes "$stderr_bytes" \
        --argjson duration_ms "$duration_ms" \
        '{task:$task, command:$command, provider:$provider, model:$model, exit_code:$exit_code, stdout_bytes:$stdout_bytes, stderr_bytes:$stderr_bytes, duration_ms:$duration_ms, status:(if $exit_code == 0 then "completed" else "failed" end), stdout_path:$stdout_path, stderr_path:$stderr_path, output_path:$output_path}' \
        >> "$PROCESSES_JSONL"
}

root_receipt() {
    local kind="$1"
    local root_path="$2"
    local bytes samples hash_file merkle status
    if [[ ! -d "$root_path" ]]; then
        add_block "${kind}_root_missing" "$root_path is not a directory"
        return
    fi
    bytes=$(( $(du -sk "$root_path" | awk '{print $1}') * 1024 ))
    samples="$(find "$root_path" -type f | wc -l | tr -d ' ')"
    hash_file="$OUT_DIR/sources/${kind}-$(basename "$root_path").sha256"
    if [[ "$samples" -gt 0 ]]; then
        find "$root_path" -maxdepth 3 -type f -print0 \
            | sort -z \
            | xargs -0 shasum -a 256 \
            | shasum -a 256 > "$hash_file"
        merkle="sha256:$(awk '{print $1}' "$hash_file")"
        status="live"
    else
        merkle=""
        status="blocked"
        add_block "${kind}_root_empty" "$root_path has no files"
    fi
    add_source "${kind}-root:$(basename "$root_path")" "file-content-addressed" "$status" "$bytes" "$samples" "$merkle" "$root_path"
}

probe_endpoint() {
    local name="$1"
    local url="$2"
    local output="$OUT_DIR/sources/${name}.json"
    local status bytes samples merkle
    if curl -fsS --max-time 3 "$url" -o "$output"; then
        bytes="$(file_size "$output")"
        merkle="$(sha256_file "$output")"
        samples="$(jq -r '
            if type == "array" then length
            elif has("latest") and (.latest | type == "object") and (.latest.body_state | type == "object") then (.latest.body_state.sample_count // .latest.tick // 0)
            elif has("frames") then .frames
            elif has("heard") and (.heard | type == "array") then (.heard | length)
            elif has("events") and (.events | type == "array") then (.events | length)
            else 1 end
        ' "$output" 2>/dev/null || printf '0')"
        [[ "$samples" =~ ^[0-9]+$ ]] || samples=0
        if [[ "$bytes" -gt 0 && "$samples" -gt 0 ]]; then
            status="live"
        else
            status="blocked"
            add_block "${name}_empty" "$url returned no usable sample count"
        fi
        add_source "$name" "http-localhost" "$status" "$bytes" "$samples" "$merkle" "$url"
    else
        add_block "${name}_unreachable" "$url did not respond"
        add_source "$name" "http-localhost" "blocked" 0 0 "" "$url"
    fi
}

require_present_tool() {
    local tool="$1"
    local reason="$2"
    if ! jq -e --arg tool "$tool" 'select(.name == $tool and .status == "present")' "$TOOLS_JSONL" >/dev/null; then
        add_block "$reason" "$tool is not available on PATH"
    fi
}

add_tool curl >/dev/null || true
add_tool jq >/dev/null || true
add_tool shasum >/dev/null || true
add_tool adb >/dev/null || true
add_tool ffmpeg >/dev/null || true
add_tool ffprobe >/dev/null || true
add_tool whisper-cli >/dev/null || true
add_tool ollama >/dev/null || true
add_tool say >/dev/null || true
add_tool sox >/dev/null || true

require_present_tool curl "curl_missing"
require_present_tool jq "jq_missing"
require_present_tool shasum "shasum_missing"

probe_endpoint "mac-android-witness-state" "$WITNESS_URL"
probe_endpoint "speech-transcript-state" "$TRANSCRIPT_URL"

if jq -e 'select(.name == "adb" and .status == "present")' "$TOOLS_JSONL" >/dev/null; then
    ADB_OUT="$OUT_DIR/sources/adb-devices.txt"
    adb devices -l > "$ADB_OUT" 2>&1 || true
    ADB_DEVICE_COUNT="$(awk 'NR > 1 && $2 == "device" {count++} END {print count + 0}' "$ADB_OUT")"
    if [[ "$ADB_DEVICE_COUNT" -gt 0 ]]; then
        add_source "android-adb-devices" "adb-usb" "live" "$(file_size "$ADB_OUT")" "$ADB_DEVICE_COUNT" "$(sha256_file "$ADB_OUT")" "$ADB_OUT"
    else
        add_block "adb_device_missing" "adb devices listed no attached Android device"
        add_source "android-adb-devices" "adb-usb" "blocked" "$(file_size "$ADB_OUT")" 0 "$(sha256_file "$ADB_OUT")" "$ADB_OUT"
    fi
else
    add_block "adb_missing" "adb is not available on PATH"
fi

for root_path in "${TRAIN_ROOTS[@]+"${TRAIN_ROOTS[@]}"}"; do
    root_receipt "train" "$root_path"
done
for root_path in "${HELDOUT_ROOTS[@]+"${HELDOUT_ROOTS[@]}"}"; do
    root_receipt "heldout" "$root_path"
done

if jq -e 'select(.name == "say" and .status == "present")' "$TOOLS_JSONL" >/dev/null; then
    TTS_OUT="$OUT_DIR/processes/tts-sample.aiff"
    run_receipted_process \
        "text-to-speech" \
        "say -o $(printf '%q' "$TTS_OUT") 'Coherence mesh training emitter receipt from local macOS text to speech.'" \
        "macos-say" \
        "system-voice" \
        "$TTS_OUT"
else
    add_block "tts_unavailable" "macOS say is not available"
fi

if [[ "$RUN_MODELS" -eq 1 ]]; then
    if jq -e 'select(.name == "ollama" and .status == "present")' "$TOOLS_JSONL" >/dev/null; then
        run_receipted_process \
            "nl-to-nl" \
            "printf '%s\n' 'Return JSON with sentiment, conviction, confidence for a live mesh training receipt.' | ollama run $(printf '%q' "$OLLAMA_MODEL")" \
            "local-ollama" \
            "$OLLAMA_MODEL"
        run_receipted_process \
            "sentiment" \
            "printf '%s\n' 'Classify sentiment, conviction, and confidence: real local receipt generated from host witnesses.' | ollama run $(printf '%q' "$OLLAMA_MODEL")" \
            "local-ollama" \
            "$OLLAMA_MODEL"
    else
        add_block "ollama_missing" "ollama is not available for local model probes"
    fi

    if [[ -n "$WHISPER_MODEL" ]]; then
        if [[ -f "$WHISPER_MODEL" ]] && jq -e 'select(.name == "whisper-cli" and .status == "present")' "$TOOLS_JSONL" >/dev/null; then
            WAV_OUT="$OUT_DIR/processes/tts-sample.wav"
            if jq -e 'select(.name == "ffmpeg" and .status == "present")' "$TOOLS_JSONL" >/dev/null && [[ -f "$OUT_DIR/processes/tts-sample.aiff" ]]; then
                ffmpeg -y -hide_banner -loglevel error -i "$OUT_DIR/processes/tts-sample.aiff" "$WAV_OUT" >/dev/null 2>&1 || true
                run_receipted_process \
                    "speech-to-text" \
                    "whisper-cli -m $(printf '%q' "$WHISPER_MODEL") -f $(printf '%q' "$WAV_OUT") -otxt -of $(printf '%q' "$OUT_DIR/processes/stt-sample")" \
                    "local-whisper" \
                    "$(basename "$WHISPER_MODEL")" \
                    "$OUT_DIR/processes/stt-sample.txt"
            else
                add_block "stt_audio_missing" "ffmpeg or generated TTS audio is unavailable for STT probe"
            fi
        else
            add_block "whisper_model_missing" "whisper-cli or the requested whisper model is unavailable"
        fi
    else
        add_block "whisper_model_not_configured" "provide --whisper-model to execute a local STT probe"
    fi
else
    add_block "model_runs_not_executed" "use --run-models to execute local Ollama/Whisper probes"
fi

TOOLS_JSON="$(jq -s . "$TOOLS_JSONL")"
SOURCES_JSON="$(jq -s . "$SOURCES_JSONL")"
PROCESSES_JSON="$(jq -s . "$PROCESSES_JSONL")"
BLOCKS_JSON="$(jq -s . "$BLOCKS_JSONL")"

TRAIN_BYTES="$(jq -s '[.[] | select((.status == "live") and (.name | startswith("train-root:"))) | .bytes] | add // 0' "$SOURCES_JSONL")"
HELDOUT_BYTES="$(jq -s '[.[] | select((.status == "live") and (.name | startswith("heldout-root:"))) | .bytes] | add // 0' "$SOURCES_JSONL")"

if [[ "$LABEL_COUNT" -eq 0 ]]; then
    LABEL_COUNT="$(jq -s '[.[] | select(.status == "live") | .samples] | add // 0' "$SOURCES_JSONL")"
fi

SOURCE_BYTE_SUM="$(jq -s '[.[] | select(.status == "live") | .bytes] | add // 0' "$SOURCES_JSONL")"
LIVE_SOURCE_COUNT="$(jq -s '[.[] | select(.status == "live")] | length' "$SOURCES_JSONL")"
PROCESS_COMPLETED_COUNT="$(jq -s '[.[] | select(.status == "completed" and .exit_code == 0 and .stdout_bytes >= 32)] | length' "$PROCESSES_JSONL")"

if [[ "$TRAIN_BYTES" -lt "$MIN_TRAIN_BYTES" ]]; then
    add_block "below_training_floor" "training data bytes $TRAIN_BYTES are below $MIN_TRAIN_BYTES"
fi
if [[ "$HELDOUT_BYTES" -lt "$MIN_HELDOUT_BYTES" ]]; then
    add_block "below_heldout_floor" "heldout data bytes $HELDOUT_BYTES are below $MIN_HELDOUT_BYTES"
fi
if [[ "$LABEL_COUNT" -lt "$MIN_LABELS" ]]; then
    add_block "below_label_floor" "label count $LABEL_COUNT is below $MIN_LABELS"
fi
if [[ "$PROCESS_COMPLETED_COUNT" -lt 3 ]]; then
    add_block "below_process_floor" "fewer than three completed local process receipts are present"
fi

BLOCKS_JSON="$(jq -s . "$BLOCKS_JSONL")"
BLOCK_COUNT="$(jq 'length' <<<"$BLOCKS_JSON")"
STATUS="blocked"
if [[ "$BLOCK_COUNT" -eq 0 && "$TRAIN_BYTES" -ge "$MIN_TRAIN_BYTES" && "$HELDOUT_BYTES" -ge "$MIN_HELDOUT_BYTES" && "$LABEL_COUNT" -ge "$MIN_LABELS" && "$PROCESS_COMPLETED_COUNT" -ge 3 ]]; then
    STATUS="active"
fi

DATASET_HASH_FILE="$OUT_DIR/dataset-source-hashes.txt"
jq -r '.merkle | select(. != "")' "$SOURCES_JSONL" | sort > "$DATASET_HASH_FILE"
DATASET_MERKLE="$(sha256_file "$DATASET_HASH_FILE")"

RECEIPT="$OUT_DIR/real-mesh-training-window.json"
OBSERVED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -n \
    --arg schema "real-mesh-training-emitter.v1" \
    --arg observed_at "$OBSERVED_AT" \
    --arg status "$STATUS" \
    --arg dataset_merkle "$DATASET_MERKLE" \
    --arg witness_url "$WITNESS_URL" \
    --arg transcript_url "$TRANSCRIPT_URL" \
    --argjson tools "$TOOLS_JSON" \
    --argjson sources "$SOURCES_JSON" \
    --argjson processes "$PROCESSES_JSON" \
    --argjson blocks "$BLOCKS_JSON" \
    --argjson min_train_bytes "$MIN_TRAIN_BYTES" \
    --argjson min_heldout_bytes "$MIN_HELDOUT_BYTES" \
    --argjson min_labels "$MIN_LABELS" \
    --argjson train_bytes "$TRAIN_BYTES" \
    --argjson heldout_bytes "$HELDOUT_BYTES" \
    --argjson source_byte_sum "$SOURCE_BYTE_SUM" \
    --argjson label_count "$LABEL_COUNT" \
    --argjson live_source_count "$LIVE_SOURCE_COUNT" \
    --argjson process_completed_count "$PROCESS_COMPLETED_COUNT" \
    '{
        schema:$schema,
        observed_at:$observed_at,
        status:$status,
        witness_urls:{state:$witness_url, transcripts:$transcript_url},
        floor:{min_training_bytes:$min_train_bytes, min_heldout_bytes:$min_heldout_bytes, min_labels:$min_labels},
        window:{
            train_bytes:$train_bytes,
            heldout_bytes:$heldout_bytes,
            source_byte_sum:$source_byte_sum,
            label_count:$label_count,
            dataset_merkle:$dataset_merkle,
            lanes:["speech-to-text","text-to-speech","sentiment","conviction","confidence","nl-to-nl","vision-describe","multimodal-align","automl-router","autoresearch"]
        },
        tool_receipts:$tools,
        source_receipts:$sources,
        process_receipts:$processes,
        block_reasons:$blocks,
        counts:{live_sources:$live_source_count, completed_processes:$process_completed_count}
    }' > "$RECEIPT"

printf 'real-mesh-training-emitter status=%s receipt=%s\n' "$STATUS" "$RECEIPT"
jq -r '.block_reasons[]? | "block=" + .code + " detail=" + .detail' "$RECEIPT"

if [[ "$REQUIRE_ACTIVE" -eq 1 && "$STATUS" != "active" ]]; then
    exit 1
fi
