#!/usr/bin/env bash
# Verify Hati-domain public Hati-OS assets through DNS and HTTPS redirects.
set -euo pipefail

DNS_SERVER="${HATI_EARTH_DNS_SERVER:-1.1.1.1}"
BASE_HOST="${HATI_EARTH_HOST:-hati.earth}"
SENSE_HOST="${HATI_EARTH_SENSE_HOST:-sense.hati.earth}"
CURL_TIMEOUT="${HATI_EARTH_CURL_TIMEOUT:-45}"

need() {
    command -v "$1" >/dev/null || { echo "FAIL missing required command: $1" >&2; exit 1; }
}

need awk
need curl
need dig
need head
need sed
need tr

resolve_a() {
    local host="$1"
    dig +short "@$DNS_SERVER" "$host" A | awk '/^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ { print }'
}

pick_ip() {
    local host="$1"
    local ip
    ip="$(resolve_a "$host" | head -n 1)"
    if [[ -z "$ip" ]]; then
        echo "FAIL $host has no A record from $DNS_SERVER" >&2
        return 1
    fi
    printf '%s\n' "$ip"
}

probe_headers() {
    local host="$1"
    local ip="$2"
    local url="$3"
    curl -4 -sSIL --max-time "$CURL_TIMEOUT" --resolve "$host:443:$ip" "$url"
}

assert_asset() {
    local label="$1"
    local path="$2"
    local expected_length="$3"
    local expected_type="$4"
    local ip="$5"
    local url="https://$BASE_HOST$path"
    local headers
    headers="$(probe_headers "$BASE_HOST" "$ip" "$url")"

    local statuses final_status final_length final_type
    statuses="$(awk '/^HTTP\// { printf "%s%s", (seen++ ? " -> " : ""), $2 } END { print "" }' <<<"$headers")"
    final_status="$(awk '/^HTTP\// { code=$2 } END { print code }' <<<"$headers")"
    final_length="$(awk 'BEGIN{IGNORECASE=1} /^content-length:/ { v=$0; sub(/^[^:]+:[[:space:]]*/, "", v); gsub(/\r/, "", v); len=v } END { print len }' <<<"$headers")"
    final_type="$(awk 'BEGIN{IGNORECASE=1} /^content-type:/ { v=$0; sub(/^[^:]+:[[:space:]]*/, "", v); gsub(/\r/, "", v); type=v } END { print type }' <<<"$headers")"

    if [[ "$final_status" != "200" ]]; then
        echo "FAIL $label final status expected 200, got $final_status; statuses=$statuses" >&2
        return 1
    fi
    if [[ "$final_length" != "$expected_length" ]]; then
        echo "FAIL $label content-length expected $expected_length, got $final_length; statuses=$statuses" >&2
        return 1
    fi
    if [[ "$final_type" != "$expected_type" ]]; then
        echo "FAIL $label content-type expected $expected_type, got $final_type; statuses=$statuses" >&2
        return 1
    fi
    echo "PASS $label statuses=$statuses final_content_length=$final_length final_content_type=$final_type"
}

assert_page() {
    local label="$1"
    local host="$2"
    local ip="$3"
    local url="https://$host"
    local headers
    headers="$(probe_headers "$host" "$ip" "$url")"

    local statuses final_status final_type
    statuses="$(awk '/^HTTP\// { printf "%s%s", (seen++ ? " -> " : ""), $2 } END { print "" }' <<<"$headers")"
    final_status="$(awk '/^HTTP\// { code=$2 } END { print code }' <<<"$headers")"
    final_type="$(awk 'BEGIN{IGNORECASE=1} /^content-type:/ { v=$0; sub(/^[^:]+:[[:space:]]*/, "", v); gsub(/\r/, "", v); type=v } END { print type }' <<<"$headers")"

    if [[ "$final_status" != "200" ]]; then
        echo "FAIL $label final status expected 200, got $final_status; statuses=$statuses" >&2
        return 1
    fi
    case "$final_type" in
        text/html*) ;;
        *)
            echo "FAIL $label content-type expected text/html, got $final_type; statuses=$statuses" >&2
            return 1
            ;;
    esac
    echo "PASS $label statuses=$statuses final_content_type=$final_type"
}

echo "== DNS =="
base_ip="$(pick_ip "$BASE_HOST")"
sense_ip="$(pick_ip "$SENSE_HOST")"
echo "PASS $BASE_HOST A via $DNS_SERVER -> $(resolve_a "$BASE_HOST" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
echo "PASS $SENSE_HOST A via $DNS_SERVER -> $(resolve_a "$SENSE_HOST" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"

echo "== assets =="
assert_asset \
    "hati-os-macos-arm64.tar.zst" \
    "/downloads/hati-os/macos/arm64/hati-os-macos-arm64.tar.zst" \
    "2858" \
    "application/octet-stream" \
    "$base_ip"
assert_asset \
    "hati-os-android-arm64.tar.zst" \
    "/downloads/hati-os/android/arm64/hati-os-android-arm64.tar.zst" \
    "2556719" \
    "application/octet-stream" \
    "$base_ip"
assert_asset \
    "coherence-sense-hati-mesh-debug.apk" \
    "/downloads/hati-os/android/arm64/coherence-sense-hati-mesh-debug.apk" \
    "3567172" \
    "application/vnd.android.package-archive" \
    "$base_ip"
assert_asset \
    "coherence-sense-hati-mesh-release.apk" \
    "/downloads/hati-os/android/arm64/coherence-sense-hati-mesh-release.apk" \
    "2756021" \
    "application/vnd.android.package-archive" \
    "$base_ip"

echo "== app doors =="
assert_page "sense.hati.earth" "$SENSE_HOST" "$sense_ip"

echo "PASS Hati earth public assets"
