#!/usr/bin/env bash
# Build Coherence Sense public assets and prove the local Mac witness + Hati mesh handshake.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="${ANDROID_SENSE_PROOF_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"
OUT="$ROOT/.cache/android-sense-public-handshake/$STAMP"
ANDROID_DIR="$ROOT/experiments/coherence-sense-android"
APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
ASSET_OUT="$ROOT/.cache/hati-os-public-assets/$STAMP"
ASSET_SUMMARY="$ASSET_OUT/hati-os-public-assets-summary.json"
API_HOST="${ANDROID_SENSE_API_HOST:-127.0.0.1}"
RELEASE_TAG="${HATI_OS_RELEASE_TAG:-hati-os-v0.1.0-20260613}"
PUBLISH=0

for arg in "$@"; do
    case "$arg" in
        --publish) PUBLISH=1 ;;
        *) echo "usage: $0 [--publish]" >&2; exit 2 ;;
    esac
done

need() {
    command -v "$1" >/dev/null || { echo "FAIL missing required command: $1" >&2; exit 1; }
}

wait_url() {
    local url="$1"
    local name="$2"
    for _ in $(seq 1 80); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.25
    done
    echo "FAIL $name did not become ready at $url" >&2
    return 1
}

post_json() {
    local url="$1"
    local body="$2"
    local out="$3"
    curl -fsS -X POST "$url" -H "Content-Type: application/json" -d "$body" > "$out"
}

cleanup() {
    if [[ -n "${WITNESS_PID:-}" ]]; then kill "$WITNESS_PID" >/dev/null 2>&1 || true; fi
    if [[ -n "${API_PID:-}" ]]; then kill "$API_PID" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT

need curl
need python3
need shasum
need zstd
if [[ "$PUBLISH" == "1" ]]; then need gh; fi

pick_free_port() {
    python3 - <<'PY'
import socket
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
}

API_PORT="${ANDROID_SENSE_API_PORT:-$(pick_free_port)}"
WITNESS_PORT="${ANDROID_SENSE_WITNESS_PORT:-$(pick_free_port)}"
API_URL="http://$API_HOST:$API_PORT/api"
WITNESS_URL="http://127.0.0.1:$WITNESS_PORT"

mkdir -p "$OUT"

echo "== cross-compile + bundle the Form kernel (.so + recipes) into the app =="
# The phone-native kernel (libform_kernel_rust.so) is gitignored, so the APK build
# depends on this running first: it drops the .so into jniLibs and refreshes the
# bundled recipe assets so the app recognizes on-device (FormKernel.kt).
"$ROOT/form/form-kernel-rust/build-android.sh"

echo "== build Android APK =="
(cd "$ANDROID_DIR" && JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21}" ./gradlew :app:assembleDebug)
[[ -f "$APK" ]] || { echo "FAIL APK not found at $APK" >&2; exit 1; }
APK_SHA="$(shasum -a 256 "$APK" | awk '{print $1}')"

echo "== build signed Android release APK =="
"$ANDROID_DIR/build_signed_release.sh" > "$OUT/android-release-signing.log"

echo "== build Hati public asset bundle =="
HATI_OS_ASSET_STAMP="$STAMP" "$ROOT/scripts/build_hati_os_public_assets.sh" > "$OUT/hati-assets.log"
[[ -f "$ASSET_SUMMARY" ]] || { echo "FAIL asset summary not found at $ASSET_SUMMARY" >&2; exit 1; }

echo "== start Mac witness =="
python3 "$ANDROID_DIR/mac-witness-server.py" --port "$WITNESS_PORT" > "$OUT/mac-witness.log" 2>&1 &
WITNESS_PID=$!
wait_url "$WITNESS_URL/state" "Mac witness"
curl -fsS "$WITNESS_URL/.well-known/hati-witness" > "$OUT/mac-witness-discovery.json"

echo "== prove Mac witness /sense =="
post_json "$WITNESS_URL/sense" '{
  "organ_id":"hati-organ-android-local-proof",
  "accel":[0.10,0.20,9.80],
  "gyro":[0.01,0.02,0.03],
  "light":42.0,
  "mag":[1.0,2.0,3.0],
  "organs_active":["accelerometer","gyroscope","light","magnetometer","screen","network"],
  "channels_offered":["wifi","screen","audio","video","ble"],
  "tick":1
}' "$OUT/mac-witness-sense.json"
curl -fsS "$WITNESS_URL/state" > "$OUT/mac-witness-state.json"

echo "== start local Hati mesh API =="
API_PY="$ROOT/api/.venv/bin/python"
if [[ ! -x "$API_PY" ]]; then API_PY="python3"; fi
(cd "$ROOT/api" && "$API_PY" -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT") > "$OUT/api.log" 2>&1 &
API_PID=$!
wait_url "$API_URL/hati/mesh/organs?limit=1" "Hati mesh API"

echo "== prove mesh announce/heartbeat/list/offer/list =="
ANDROID_ID="hati-organ-android-local-proof"
MAC_ID="hati-organ-macos-local-proof"
post_json "$API_URL/hati/mesh/organs/announce" "{
  \"organ_id\":\"$MAC_ID\",
  \"organ_kind\":\"host-kernel\",
  \"app\":\"hati-os\",
  \"app_version\":\"0.2\",
  \"target\":\"macos-arm64\",
  \"capabilities\":[\"cap.mesh.presence\",\"cap.sensor.read\",\"cap.screen.write\"],
  \"lanes\":[\"hati.mesh:presence\",\"sensor:signal\",\"screen:write\",\"network:http\"]
}" "$OUT/mesh-announce-mac.json"
post_json "$API_URL/hati/mesh/organs/announce" "{
  \"organ_id\":\"$ANDROID_ID\",
  \"organ_kind\":\"android-phone\",
  \"app\":\"coherence-sense\",
  \"app_version\":\"0.2\",
  \"target\":\"android-arm64\",
  \"capabilities\":[\"cap.mesh.presence\",\"cap.sensor.read\",\"cap.audio.sample\",\"cap.video.frame\",\"cap.screen.write\",\"cap.bluetooth.presence\",\"cap.network.presence\"],
  \"lanes\":[\"hati.mesh:presence\",\"sensor:signal\",\"audio:pcm16\",\"video:rgba-time\",\"screen:write\",\"network:http\",\"bluetooth:presence\"]
}" "$OUT/mesh-announce-android.json"
post_json "$API_URL/hati/mesh/organs/heartbeat" "{
  \"organ_id\":\"$ANDROID_ID\",
  \"listening\":true,
  \"active_channels\":[\"hati.mesh:presence\",\"sensor:signal\",\"screen:write\",\"network:http\"],
  \"sample_rate_hz\":1.0,
  \"bytes_per_second\":320.0
}" "$OUT/mesh-heartbeat-android.json"
curl -fsS "$API_URL/hati/mesh/organs?limit=10" > "$OUT/mesh-organs.json"
post_json "$API_URL/hati/mesh/channels/offer" "{
  \"from_organ_id\":\"$ANDROID_ID\",
  \"to_organ_id\":\"$MAC_ID\",
  \"protocol\":\"sensor:signal\",
  \"interface\":\"offer:observe-sensor-field\",
  \"capability\":\"cap.sensor.read\",
  \"codec\":\"json\",
  \"status\":\"offered\",
  \"sample_rate_hz\":1.0,
  \"bytes_per_second\":320.0
}" "$OUT/mesh-offer.json"
curl -fsS "$API_URL/hati/mesh/channels?organ_id=$ANDROID_ID&limit=10" > "$OUT/mesh-channels.json"

python3 - "$OUT" "$APK_SHA" "$ASSET_SUMMARY" "$WITNESS_PORT" <<'PY'
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
apk_sha = sys.argv[2]
asset_summary_path = pathlib.Path(sys.argv[3])
witness_port = int(sys.argv[4])

def load(name):
    return json.loads((out / name).read_text(encoding="utf-8"))

witness = load("mac-witness-state.json")
discovery = load("mac-witness-discovery.json")
organs = load("mesh-organs.json")
channels = load("mesh-channels.json")
announce_android = load("mesh-announce-android.json")
heartbeat_android = load("mesh-heartbeat-android.json")
asset_summary = json.loads(asset_summary_path.read_text(encoding="utf-8"))

assert witness["frames"] >= 1, "Mac witness did not record a frame"
assert witness["present"] is True, "Mac witness did not mark organ present"
assert "accel" in witness["latest"], "Mac witness did not retain accel sample"
assert discovery["service_type"] == "_hati-witness._tcp", "Mac witness discovery service type mismatch"
assert discovery["port"] == witness_port, "Mac witness discovery port mismatch"
assert discovery["sense_path"] == "/sense", "Mac witness discovery missing /sense path"
assert discovery["state_path"] == "/state", "Mac witness discovery missing /state path"

ids = {item.get("organ_id") for item in organs.get("items", [])}
assert "hati-organ-android-local-proof" in ids, "Android organ missing from mesh list"
assert "hati-organ-macos-local-proof" in ids, "Mac organ missing from mesh list"

assert announce_android["receipt"]["runtime_event_id"], "Android announce missing receipt"
assert heartbeat_android["receipt"]["runtime_event_id"], "Android heartbeat missing receipt"
assert any(row.get("protocol") == "sensor:signal" for row in channels.get("items", [])), "sensor channel offer missing"

assets = {item["name"]: item for item in asset_summary["assets"]}
assert assets["hati-os-macos-arm64.tar.zst"]["status"] == "pass", "macOS asset did not pass"
assert assets["hati-os-android-arm64.tar.zst"]["status"] == "pass", "Android native asset did not pass"
assert assets["coherence-sense-hati-mesh-debug.apk"]["status"] == "pass", "APK asset did not pass"
assert assets["coherence-sense-hati-mesh-release.apk"]["status"] == "pass", "signed release APK asset did not pass"
assert assets["coherence-sense-hati-mesh-release.apk"]["update_protocol"] == "signed-apk-download-user-consent-installer", "signed release APK update protocol missing"

summary = {
    "status": "pass",
    "apk_sha256": apk_sha,
    "asset_summary": str(asset_summary_path),
    "mesh": {
        "organs_count": organs.get("count"),
        "channels_count": channels.get("count"),
        "android_announce_receipt": announce_android["receipt"]["runtime_event_id"],
        "android_heartbeat_receipt": heartbeat_android["receipt"]["runtime_event_id"],
    },
    "mac_witness": {
        "frames": witness["frames"],
        "present": witness["present"],
        "organs": witness["organs"],
        "discovery": discovery,
    },
    "assets": asset_summary["assets"],
}
(out / "android-sense-public-handshake-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2))
PY

if [[ "$PUBLISH" == "1" ]]; then
    echo "== publish assets to GitHub release $RELEASE_TAG =="
    gh release upload "$RELEASE_TAG" \
        "$ASSET_OUT/hati-os-macos-arm64.tar.zst" \
        "$ASSET_OUT/hati-os-macos-arm64.tar.zst.sha256" \
        "$ASSET_OUT/hati-os-android-arm64.tar.zst" \
        "$ASSET_OUT/hati-os-android-arm64.tar.zst.sha256" \
        "$ASSET_OUT/coherence-sense-hati-mesh-debug.apk" \
        "$ASSET_OUT/coherence-sense-hati-mesh-debug.apk.sha256" \
        "$ASSET_OUT/coherence-sense-hati-mesh-release.apk" \
        "$ASSET_OUT/coherence-sense-hati-mesh-release.apk.sha256" \
        "$ASSET_SUMMARY" \
        --clobber
fi

echo "PASS android sense public handshake proof: $OUT/android-sense-public-handshake-summary.json"
