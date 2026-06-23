#!/usr/bin/env bash
# build-android-form-cli.sh — cross-compile the C-bootstrapped native form-cli for Android ARM64.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FORM="$ROOT/form"
APP="$ROOT/experiments/coherence-sense-android"
# Android reliably extracts jniLibs to an executable nativeLibraryDir. The file is
# an executable PIE even though the APK packaging lane needs a .so suffix.
OUT="${1:-$APP/app/src/main/jniLibs/arm64-v8a/libform_cli_exec.so}"

NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
[[ -d "$NDK" ]] || { echo "Android NDK not found — run: brew install android-ndk"; exit 1; }

HOST_TAG=""
case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) HOST_TAG="darwin-x86_64" ;;
    Darwin-*) HOST_TAG="darwin-x86_64" ;;
    Linux-x86_64) HOST_TAG="linux-x86_64" ;;
    *) echo "Unsupported NDK host: $(uname -s)-$(uname -m)" >&2; exit 2 ;;
esac

CC_ARM64="$NDK/toolchains/llvm/prebuilt/$HOST_TAG/bin/aarch64-linux-android24-clang"
[[ -x "$CC_ARM64" ]] || { echo "Android ARM64 clang not found at $CC_ARM64"; exit 1; }

mkdir -p "$(dirname "$OUT")"
(cd "$FORM" && CC="$CC_ARM64" ./build-form-cli.sh "$OUT")

case "$(file "$OUT")" in
    *"ELF 64-bit"*"ARM aarch64"*) echo "✓ Android native form-cli → $OUT" ;;
    *) echo "✗ expected Android ARM64 ELF at $OUT"; file "$OUT"; exit 1 ;;
esac
