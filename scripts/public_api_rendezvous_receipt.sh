#!/usr/bin/env bash
# public_api_rendezvous_receipt.sh — live public API nonce-hash rendezvous receipt.
#
# The carrier is the existing public runtime telemetry route. The nonce stays
# local; only its SHA-256 hash and bounded rendezvous metadata are written.
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
if ! command -v openssl >/dev/null; then
    echo "FAIL missing openssl"
    exit 1
fi

api_base="${1:-https://api.coherencycoin.com}"
ttl_ms="${2:-600000}"
api_base="${api_base%/}"
post_url="$api_base/api/runtime/events"
read_url="$api_base/api/runtime/events?limit=200&source=worker&force_refresh=true"

ts="$(date -u +"%Y%m%dT%H%M%SZ")"
out_dir="$ROOT/.cache/public-api-rendezvous/$ts"
mkdir -p "$out_dir"

nonce="$(openssl rand -hex 32)"
nonce_hash="$(printf '%s' "$nonce" | shasum -a 256 | awk '{print $1}')"
rendezvous_id="public-api-rendezvous-$ts-$(openssl rand -hex 4)"

cat > "$out_dir/post-payload.json" <<JSON
{
  "source": "worker",
  "endpoint": "/api/runtime/events",
  "raw_endpoint": "/api/runtime/events",
  "method": "POST",
  "status_code": 201,
  "runtime_ms": 1.0,
  "idea_id": "public-audio-rendezvous",
  "metadata": {
    "tracking_kind": "public_rendezvous_receipt",
    "receipt_kind": "public-rendezvous-cell",
    "carrier": "coherence-public-api",
    "rendezvous_id": "$rendezvous_id",
    "nonce_hash": "$nonce_hash",
    "nonce_hash_len": 64,
    "ttl_ms": $ttl_ms,
    "raw_nonce_retained": false
  }
}
JSON

now_ms() {
    perl -MTime::HiRes=time -e 'printf "%d\n", time() * 1000'
}

write_start_ms="$(now_ms)"
post_code="$(curl -sS --max-time 15 \
    -o "$out_dir/post-response.json" \
    -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json' \
    -X POST "$post_url" \
    --data-binary @"$out_dir/post-payload.json")"
write_end_ms="$(now_ms)"
write_ms=$((write_end_ms - write_start_ms))

if [[ "$post_code" != "201" ]]; then
    echo "FAIL public-api-rendezvous post_status=$post_code url=$post_url cache=$out_dir"
    exit 1
fi

read_start_ms="$(now_ms)"
read_code="$(curl -sS --max-time 15 \
    -o "$out_dir/read-response.json" \
    -w '%{http_code}' \
    -H 'Accept: application/json' \
    "$read_url")"
read_end_ms="$(now_ms)"
read_ms=$((read_end_ms - read_start_ms))

if [[ "$read_code" != "200" ]]; then
    echo "FAIL public-api-rendezvous read_status=$read_code url=$read_url cache=$out_dir"
    exit 1
fi

found_count="$(
    jq --arg rid "$rendezvous_id" --arg hash "$nonce_hash" '
        [.items[]? | select(.metadata.rendezvous_id == $rid and .metadata.nonce_hash == $hash)] | length
    ' "$out_dir/read-response.json"
)"

if [[ "$found_count" != "1" ]]; then
    echo "FAIL public-api-rendezvous found_count=$found_count rendezvous_id=$rendezvous_id cache=$out_dir"
    exit 1
fi

event_id="$(
    jq -r --arg rid "$rendezvous_id" --arg hash "$nonce_hash" '
        [.items[]? | select(.metadata.rendezvous_id == $rid and .metadata.nonce_hash == $hash)][0].id // ""
    ' "$out_dir/read-response.json"
)"

cat > "$out_dir/public-api-rendezvous-receipt.json" <<JSON
{
  "carrier": "coherence-public-api",
  "endpoint_kind": "public-rendezvous-cell",
  "api_base": "$api_base",
  "post_url": "$post_url",
  "read_url": "$read_url",
  "rendezvous_id": "$rendezvous_id",
  "runtime_event_id": "$event_id",
  "nonce_hash": "$nonce_hash",
  "nonce_hash_len": 64,
  "write_ms": $write_ms,
  "read_ms": $read_ms,
  "ttl_ms": $ttl_ms,
  "public_readable": 1,
  "post_status": $post_code,
  "read_status": $read_code,
  "found_count": $found_count,
  "raw_nonce_retained": 0,
  "status": "pass"
}
JSON

cp "$out_dir/public-api-rendezvous-receipt.json" "$ROOT/.cache/public-api-rendezvous/latest.json"

echo "PASS public-api-rendezvous carrier=coherence-public-api event_id=$event_id nonce_hash_len=64 write_ms=$write_ms read_ms=$read_ms ttl_ms=$ttl_ms public_readable=1 cache=$out_dir/public-api-rendezvous-receipt.json"
