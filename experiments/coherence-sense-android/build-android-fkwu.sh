#!/usr/bin/env bash
# build-android-fkwu.sh — cross-compile the C-bootstrapped fkwu universal kernel for
# Android ARM64 and stage the proven loop-table, so LiveSenseActivity can run a Form
# sense recipe natively on the phone.
#
# The kernel binary is gitignored (*.so): it is a regenerable artifact, never a
# committed blob — the same convention as build-android-form-cli.sh. The body is
# runtime/fkwu-uni.c in the coherence-kernel repo; this only emits the carrier.
set -euo pipefail

APP="$(cd "$(dirname "$0")" && pwd)"
# The clean kernel repo lives beside Coherence-Network by default; override with KERNEL_ROOT.
KERNEL_ROOT="${KERNEL_ROOT:-$(cd "$APP/../../.." && pwd)/coherence-kernel}"
KERNEL_SRC="$KERNEL_ROOT/runtime/fkwu-uni.c"
LOOP_TABLE="${LOOP_TABLE:-$KERNEL_ROOT/flatten/loop-table.txt}"

OUT="$APP/app/src/main/jniLibs/arm64-v8a/libfkwu_exec.so"
ASSET_TABLE="$APP/app/src/main/assets/native/loop-table.txt"

[[ -f "$KERNEL_SRC" ]] || { echo "kernel source not found: $KERNEL_SRC (set KERNEL_ROOT)"; exit 1; }

NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
[[ -d "$NDK" ]] || { echo "Android NDK not found — brew install android-ndk"; exit 1; }

case "$(uname -s)-$(uname -m)" in
    Darwin-*) HOST_TAG="darwin-x86_64" ;;
    Linux-x86_64) HOST_TAG="linux-x86_64" ;;
    *) echo "Unsupported NDK host: $(uname -s)-$(uname -m)" >&2; exit 2 ;;
esac
CC="$NDK/toolchains/llvm/prebuilt/$HOST_TAG/bin/aarch64-linux-android34-clang"
[[ -x "$CC" ]] || { echo "Android ARM64 clang not found at $CC"; exit 1; }

mkdir -p "$(dirname "$OUT")" "$(dirname "$ASSET_TABLE")"
"$CC" -O2 -pthread "$KERNEL_SRC" -o "$OUT"
case "$(file "$OUT")" in
    *"ELF 64-bit"*"ARM aarch64"*) echo "✓ Android fkwu → $OUT" ;;
    *) echo "✗ expected Android ARM64 ELF at $OUT"; file "$OUT"; exit 1 ;;
esac

# Stage the loop-table (the form-eval read-eval table fkwu walks). If a freshly
# flattened table exists in the kernel repo, prefer it; else keep the staged asset.
if [[ -f "$LOOP_TABLE" ]]; then
    cp "$LOOP_TABLE" "$ASSET_TABLE"
    echo "✓ loop-table asset ← $LOOP_TABLE"
elif [[ -f "$ASSET_TABLE" ]]; then
    echo "• reusing staged loop-table asset: $ASSET_TABLE"
else
    echo "✗ no loop-table available (set LOOP_TABLE to a flattened form-eval table)"; exit 1
fi
