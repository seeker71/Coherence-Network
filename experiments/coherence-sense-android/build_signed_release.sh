#!/usr/bin/env bash
# Build a locally signed Coherence Sense release APK.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ANDROID_DIR="$ROOT/experiments/coherence-sense-android"
CONFIG="$ANDROID_DIR/signing.properties"
KEYSTORE_DIR="$HOME/.coherence-network/android"
KEYSTORE="$KEYSTORE_DIR/coherence-sense-release.jks"
ALIAS="coherence-sense"
APK="$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk"
JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21}"
if [[ -d "$JAVA_HOME/bin" ]]; then
    PATH="$JAVA_HOME/bin:$PATH"
fi

need() {
    command -v "$1" >/dev/null || { echo "FAIL missing required command: $1" >&2; exit 1; }
}

random_secret() {
    python3 - <<'PY'
import secrets
import string

alphabet = string.ascii_letters + string.digits
print("".join(secrets.choice(alphabet) for _ in range(32)))
PY
}

sdk_dir() {
    local local_properties="$ANDROID_DIR/local.properties"
    if [[ -f "$local_properties" ]]; then
        sed -n 's/^sdk.dir=//p' "$local_properties" | head -1
    fi
}

find_apksigner() {
    if command -v apksigner >/dev/null; then
        command -v apksigner
        return 0
    fi
    local sdk
    sdk="$(sdk_dir)"
    if [[ -n "$sdk" && -d "$sdk/build-tools" ]]; then
        find "$sdk/build-tools" -name apksigner -type f | sort -V | tail -1
        return 0
    fi
    return 1
}

write_config_if_missing() {
    if [[ -f "$CONFIG" ]]; then
        return
    fi
    need "$JAVA_HOME/bin/keytool"
    mkdir -p "$KEYSTORE_DIR"
    chmod 700 "$KEYSTORE_DIR"
    local storepass keypass
    storepass="$(random_secret)"
    keypass="$storepass"
    if [[ ! -f "$KEYSTORE" ]]; then
        "$JAVA_HOME/bin/keytool" -genkeypair \
            -keystore "$KEYSTORE" \
            -storepass "$storepass" \
            -keypass "$keypass" \
            -alias "$ALIAS" \
            -keyalg RSA \
            -keysize 4096 \
            -validity 10000 \
            -dname "CN=Coherence Sense,O=Hati Mesh,C=ID" \
            >/dev/null
        chmod 600 "$KEYSTORE"
    fi
    cat > "$CONFIG" <<EOF
storeFile=$KEYSTORE
storePassword=$storepass
keyAlias=$ALIAS
keyPassword=$keypass
EOF
    chmod 600 "$CONFIG"
}

repair_generated_pkcs12_config() {
    [[ -f "$CONFIG" ]] || return
    local store_file store_password key_password
    store_file="$(sed -n 's/^storeFile=//p' "$CONFIG" | head -1)"
    store_password="$(sed -n 's/^storePassword=//p' "$CONFIG" | head -1)"
    key_password="$(sed -n 's/^keyPassword=//p' "$CONFIG" | head -1)"
    if [[ "$store_file" == "$KEYSTORE" && -n "$store_password" && "$key_password" != "$store_password" ]]; then
        awk -v sp="$store_password" '
            /^keyPassword=/ { print "keyPassword=" sp; next }
            { print }
        ' "$CONFIG" > "$CONFIG.tmp"
        mv "$CONFIG.tmp" "$CONFIG"
        chmod 600 "$CONFIG"
    fi
}

write_config_if_missing
repair_generated_pkcs12_config

JAVA_HOME="$JAVA_HOME" "$ANDROID_DIR/gradlew" -p "$ANDROID_DIR" :app:assembleRelease
[[ -f "$APK" ]] || { echo "FAIL signed release APK missing: $APK" >&2; exit 1; }

APKSIGNER="$(find_apksigner || true)"
if [[ -z "$APKSIGNER" ]]; then
    echo "FAIL apksigner not found in PATH or Android SDK build-tools" >&2
    exit 1
fi
"$APKSIGNER" verify --print-certs "$APK" > "$ANDROID_DIR/app/build/outputs/apk/release/app-release.apksigner.txt"
shasum -a 256 "$APK" | tee "$ANDROID_DIR/app/build/outputs/apk/release/app-release.apk.sha256"
echo "PASS signed release APK: $APK"
echo "signature proof: $ANDROID_DIR/app/build/outputs/apk/release/app-release.apksigner.txt"
