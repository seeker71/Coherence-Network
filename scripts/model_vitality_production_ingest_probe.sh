#!/usr/bin/env bash
# model_vitality_production_ingest_probe.sh — capture live production pulse/runtime slices for Form model vitality rows.
#
# Floor: use curl against public Coherence endpoints, preserve headers/body in
# .cache/model-vitality-production, and print the production row facts needed by
# form-stdlib/model-vitality.fk. jq is only a witness parser here; Form owns the
# row grammar and routing semantics.
#
# North star: deployed wellness, pulse, front-door, release, and model-vitality
# rows arrive as native substrate channels. This script disappears when the
# fourth kernel can capture external HTTPS slices into the same rows directly.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v curl >/dev/null; then
    echo "FAIL missing curl"
    exit 1
fi
if ! command -v jq >/dev/null; then
    echo "FAIL missing jq"
    exit 1
fi

ts="$(date -u +"%Y%m%dT%H%M%SZ")"
out_dir="$ROOT/.cache/model-vitality-production/$ts"
mkdir -p "$out_dir"

api_pulse_url="https://api.coherencycoin.com/api/pulse/now"
witness_pulse_url="https://pulse.coherencycoin.com/pulse/now"
runtime_url="https://api.coherencycoin.com/api/runtime/endpoints/summary?limit=5"

curl -sS --max-time 12 \
    -w 'http_code=%{http_code}\ntime_total=%{time_total}\nsize_download=%{size_download}\n' \
    -D "$out_dir/api-pulse.headers" \
    -o "$out_dir/api-pulse.json" \
    -H 'Accept: application/json' \
    "$api_pulse_url" > "$out_dir/api-pulse.metrics"

curl -sS --max-time 12 \
    -w 'http_code=%{http_code}\ntime_total=%{time_total}\nsize_download=%{size_download}\n' \
    -D "$out_dir/witness-pulse.headers" \
    -o "$out_dir/witness-pulse.json" \
    -H 'Accept: application/json' \
    "$witness_pulse_url" > "$out_dir/witness-pulse.metrics"

curl -sS --max-time 12 \
    -w 'http_code=%{http_code}\ntime_total=%{time_total}\nsize_download=%{size_download}\n' \
    -D "$out_dir/runtime.headers" \
    -o "$out_dir/runtime.json" \
    -H 'Accept: application/json' \
    "$runtime_url" > "$out_dir/runtime.metrics"

metric() {
    awk -F= -v key="$2" '$1 == key {print $2}' "$1"
}

header_value() {
    awk -F': ' -v key="$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')" '
        tolower($1) == key {gsub("\r", "", $2); print $2; exit}
    ' "$1"
}

api_code="$(metric "$out_dir/api-pulse.metrics" http_code)"
witness_code="$(metric "$out_dir/witness-pulse.metrics" http_code)"
runtime_code="$(metric "$out_dir/runtime.metrics" http_code)"

if [[ "$api_code" != "200" ]]; then
    echo "FAIL api-pulse http_code=$api_code url=$api_pulse_url cache=$out_dir"
    exit 1
fi
if [[ "$witness_code" != "200" ]]; then
    echo "FAIL witness-pulse http_code=$witness_code url=$witness_pulse_url cache=$out_dir"
    exit 1
fi
if [[ "$runtime_code" != "200" ]]; then
    echo "FAIL runtime http_code=$runtime_code url=$runtime_url cache=$out_dir"
    exit 1
fi

api_overall="$(jq -r '.overall // ""' "$out_dir/api-pulse.json")"
api_silences="$(jq -r '.silences // 0' "$out_dir/api-pulse.json")"
api_instance="$(jq -r '.instance_id // ""' "$out_dir/api-pulse.json")"
api_as_of="$(jq -r '.as_of // .checked_at // ""' "$out_dir/api-pulse.json")"
api_duration="$(jq -r '.sample_duration_ms // 0' "$out_dir/api-pulse.json")"
api_bytes="$(wc -c < "$out_dir/api-pulse.json" | tr -d ' ')"

witness_overall="$(jq -r '.overall // ""' "$out_dir/witness-pulse.json")"
witness_checked="$(jq -r '.checked_at // .as_of // ""' "$out_dir/witness-pulse.json")"
witness_bytes="$(wc -c < "$out_dir/witness-pulse.json" | tr -d ' ')"

runtime_handler="$(header_value "$out_dir/runtime.headers" x-form-handler)"
runtime_router="$(header_value "$out_dir/runtime.headers" x-form-router)"
runtime_python_authority="$(header_value "$out_dir/runtime.headers" x-form-python-authority)"
runtime_time_s="$(metric "$out_dir/runtime.metrics" time_total)"
runtime_bytes="$(wc -c < "$out_dir/runtime.json" | tr -d ' ')"
runtime_time_ms="$(awk -v t="$runtime_time_s" 'BEGIN {printf "%d", t * 1000}')"

if [[ -z "$api_overall" || -z "$api_as_of" ]]; then
    echo "FAIL api-pulse missing overall/as_of cache=$out_dir"
    exit 1
fi
if [[ -z "$witness_overall" || -z "$witness_checked" ]]; then
    echo "FAIL witness-pulse missing overall/checked_at cache=$out_dir"
    exit 1
fi
if [[ "$runtime_router" != "native-kernel" || "$runtime_python_authority" != "false" || -z "$runtime_handler" ]]; then
    echo "FAIL runtime native headers router=$runtime_router handler=$runtime_handler python_authority=$runtime_python_authority cache=$out_dir"
    exit 1
fi

pulse_state="breathing"
if [[ "$api_silences" != "0" || "$api_overall" == "silent" ]]; then
    pulse_state="silent"
fi

wellness_state="clear"
if [[ "$api_overall" == "deploy-lag" ]]; then
    wellness_state="deploy-lag"
elif [[ "$api_overall" == "strained" ]]; then
    wellness_state="strained"
fi

release_state="fast"
if [[ "$runtime_time_ms" -gt 1000 ]]; then
    release_state="slow"
fi

cat > "$out_dir/production-model-vitality-row.json" <<JSON
{
  "observed_at": "$ts",
  "api_pulse": {
    "source": "api-pulse",
    "url": "$api_pulse_url",
    "as_of": "$api_as_of",
    "overall": "$api_overall",
    "silences": $api_silences,
    "sample_duration_ms": $api_duration,
    "body_bytes": $api_bytes,
    "instance_id": "$api_instance"
  },
  "witness_pulse": {
    "source": "pulse-front-door",
    "url": "$witness_pulse_url",
    "checked_at": "$witness_checked",
    "overall": "$witness_overall",
    "body_bytes": $witness_bytes
  },
  "runtime": {
    "url": "$runtime_url",
    "status": 200,
    "handler": "$runtime_handler",
    "router": "$runtime_router",
    "python_authority": "$runtime_python_authority",
    "latency_ms": $runtime_time_ms,
    "body_bytes": $runtime_bytes
  },
  "derived_route_states": {
    "wellness_state": "$wellness_state",
    "pulse_state": "$pulse_state",
    "release_state": "$release_state"
  }
}
JSON

echo "PASS production-pulse source=api-pulse overall=$api_overall silences=$api_silences latency_ms=$api_duration bytes=$api_bytes instance=$api_instance as_of=$api_as_of"
echo "PASS production-witness-pulse source=pulse-front-door overall=$witness_overall bytes=$witness_bytes checked_at=$witness_checked"
echo "PASS production-runtime status=200 router=$runtime_router handler=$runtime_handler python_authority=$runtime_python_authority latency_ms=$runtime_time_ms bytes=$runtime_bytes"
echo "PASS model-vitality-production-row wellness_state=$wellness_state pulse_state=$pulse_state release_state=$release_state cache=$out_dir/production-model-vitality-row.json"
