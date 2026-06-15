#!/usr/bin/env bash
# Build a native arm64 core-axiom receipt library into the Android APK and
# verify the packaged lib entry by SHA-256.
#
# Usage:
#   scripts/android_core_axiom_apk_receipt.sh [samples] [width]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANDROID_DIR="$ROOT/experiments/coherence-sense-android"
APP_DIR="$ANDROID_DIR/app"
WORK="$ROOT/.cache/android_core_axiom_apk_receipt"
SRC="$WORK/core_axiom_apk_receipt.c"
LIB="$WORK/libcoherence_core_axiom_receipt.so"
EXTRACTED="$WORK/libcoherence_core_axiom_receipt.extracted.so"
APK_ENTRIES="$WORK/apk.entries"
OUT="$WORK/latest.json"
STAGED_DIR="$APP_DIR/src/main/jniLibs/arm64-v8a"
STAGED_LIB="$STAGED_DIR/libcoherence_core_axiom_receipt.so"
APK="$APP_DIR/build/outputs/apk/debug/app-debug.apk"
ENTRY="lib/arm64-v8a/libcoherence_core_axiom_receipt.so"
SAMPLES="${1:-2048}"
WIDTH="${2:-8}"
JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21}"
LOCAL_PROPERTIES="$ANDROID_DIR/local.properties"
CREATED_LOCAL_PROPERTIES=0

mkdir -p "$WORK"

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

cleanup() {
  rm -f "$STAGED_LIB"
  if [[ "$CREATED_LOCAL_PROPERTIES" == "1" ]]; then
    rm -f "$LOCAL_PROPERTIES"
  fi
  rmdir "$STAGED_DIR" "$APP_DIR/src/main/jniLibs" "$APP_DIR/src/main" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ "$SAMPLES" -le 0 || "$WIDTH" -le 0 || "$WIDTH" -gt 32 ]]; then
  echo "samples and width must be positive; width <= 32" >&2
  exit 2
fi

NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
ANDROID_CLANG="${ANDROID_CLANG:-}"
if [[ -z "$ANDROID_CLANG" && -d "$NDK" ]]; then
  ANDROID_CLANG="$(find "$NDK/toolchains/llvm/prebuilt" -type f -name 'aarch64-linux-android34-clang' 2>/dev/null | head -1)"
fi
if [[ -z "$ANDROID_CLANG" ]]; then
  echo "Android NDK clang not found; install android-ndk or set ANDROID_CLANG" >&2
  exit 1
fi
if [[ ! -x "$ANDROID_DIR/gradlew" ]]; then
  echo "Gradle wrapper is not executable: $ANDROID_DIR/gradlew" >&2
  exit 1
fi
if [[ -d "$JAVA_HOME/bin" ]]; then
  export PATH="$JAVA_HOME/bin:$PATH"
fi
if [[ ! -f "$LOCAL_PROPERTIES" ]]; then
  sdk=""
  for candidate in "$HOME/.android-sdk-codex" "$HOME/Library/Android/sdk" "/opt/android-sdk" "/opt/homebrew/share/android-sdk"; do
    if [[ -d "$candidate/platforms" && -d "$candidate/build-tools" ]]; then
      sdk="$candidate"
      break
    fi
  done
  if [[ -z "$sdk" ]]; then
    echo "Android SDK not found; create $LOCAL_PROPERTIES with sdk.dir=<path>" >&2
    exit 1
  fi
  printf 'sdk.dir=%s\n' "$sdk" > "$LOCAL_PROPERTIES"
  CREATED_LOCAL_PROPERTIES=1
fi

cat > "$SRC" <<'C'
#include <stdint.h>

static int64_t next_value(uint64_t *seed) {
    *seed = (*seed * 1103515245ULL + 12345ULL) & 0x7fffffffULL;
    return (int64_t)((*seed >> 8) % 11) - 5;
}

static int64_t pred(const int64_t *weights, const int64_t *x, int width, int64_t b) {
    int64_t sum = b;
    for (int i = 0; i < width; i++) {
        sum += weights[i] * x[i];
    }
    return sum;
}

static int64_t loss(const int64_t *weights, const int64_t *x, int width, int64_t b, int64_t target) {
    int64_t err = pred(weights, x, width, b) - target;
    return err * err;
}

__attribute__((visibility("default")))
int coherence_core_axiom_receipt(int samples, int width, int64_t *checksum_out) {
    if (samples <= 0 || width <= 0 || width > 32 || !checksum_out) {
        return -1;
    }
    int64_t weights[32];
    int64_t x[32];
    uint64_t seed = 0xC0A11CEULL;
    int failed = 0;
    int64_t checksum = 17;

    for (int i = 0; i < width; i++) {
        weights[i] = next_value(&seed);
    }
    int64_t bias = next_value(&seed);

    for (int s = 0; s < samples; s++) {
        for (int i = 0; i < width; i++) {
            x[i] = next_value(&seed);
        }
        int64_t target = next_value(&seed);
        int64_t y = pred(weights, x, width, bias);
        int64_t l = loss(weights, x, width, bias, target);
        int64_t err = y - target;
        if (l != err * err) {
            failed++;
        }
        checksum = checksum * 131 + y * 17 + l * 3 + target;
    }
    *checksum_out = checksum;
    return failed;
}
C

"$ANDROID_CLANG" -O2 -Wall -Wextra -shared -fPIC \
  -Wl,-soname,libcoherence_core_axiom_receipt.so \
  -o "$LIB" "$SRC"

lib_desc="$(file "$LIB")"
case "$lib_desc" in
  *"ELF 64-bit"*"shared object"*"ARM aarch64"*) ;;
  *"ELF 64-bit"*"ARM aarch64"*"shared object"*) ;;
  *"ELF 64-bit"*"shared object"*"AArch64"*) ;;
  *"ELF 64-bit"*"AArch64"*"shared object"*) ;;
  *) echo "Android receipt library is not an arm64 shared object: $lib_desc" >&2; exit 1 ;;
esac

mkdir -p "$STAGED_DIR"
cp "$LIB" "$STAGED_LIB"

JAVA_HOME="$JAVA_HOME" "$ANDROID_DIR/gradlew" -p "$ANDROID_DIR" :app:clean :app:assembleDebug >/dev/null
[[ -f "$APK" ]] || { echo "FAIL debug APK missing: $APK" >&2; exit 1; }

zipinfo -1 "$APK" > "$APK_ENTRIES"
if ! grep -Fxq "$ENTRY" "$APK_ENTRIES"; then
  echo "FAIL APK missing native receipt entry: $ENTRY" >&2
  exit 1
fi
unzip -p "$APK" "$ENTRY" > "$EXTRACTED"

source_sha="$(sha256_file "$SRC")"
lib_sha="$(sha256_file "$LIB")"
apk_sha="$(sha256_file "$APK")"
entry_sha="$(sha256_file "$EXTRACTED")"
if [[ "$lib_sha" != "$entry_sha" ]]; then
  echo "FAIL packaged entry SHA mismatch: lib=$lib_sha entry=$entry_sha" >&2
  exit 1
fi

lib_desc_json="$(json_escape "$lib_desc")"
cat > "$OUT" <<JSON
{"kind":"core-axiom-apk-native-lib-receipt","apk":"$APK","apk_sha256":"$apk_sha","entry":"$ENTRY","entry_sha256":"$entry_sha","generated_source_sha256":"$source_sha","library_sha256":"$lib_sha","library_file":"$lib_desc_json","abi":"arm64-v8a","samples":$SAMPLES,"width":$WIDTH,"packaged":true,"executed_on_device":false,"status":"pass"}
JSON

printf 'PASS apk=%s entry=%s sha256=%s receipt=%s\n' "$APK" "$ENTRY" "$entry_sha" "$OUT"
cat "$OUT"
