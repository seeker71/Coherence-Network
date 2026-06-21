#!/usr/bin/env bash
# android_matvec_vk_run.sh — prove the Form-minted matvec.spv on a REAL Android phone GPU.
#
# This closes the "on-device RUN" gap (GPU_GAPS.md section E): the arm64-android Vulkan carrier was
# already cross-compiled-proven, but never RUN — that needs an actual device on adb. This script is
# the one command that does it: mint matvec.spv (glslang, vulkan1.1 so float-controls/RoundingModeRTE
# are available), cross-compile matvec_vk.c for arm64-android (NDK clang, -ffp-contract=off so the C
# oracle's right-fold never fuses to FMA), push both to /data/local/tmp, run, and gate BIT-EXACT
# (uint32, no tolerance) — the phone's Adreno/Mali driver computes the SAME bits as the recipe oracle.
#
# The .spv is hardware-neutral SPIR-V; the only thing that makes this the ANDROID proof (vs the RTX
# Vulkan proof) is that it runs on the phone's GPU through libvulkan.so (bionic), not vulkan-1.dll.
#
# Deps: adb (a connected device), glslangValidator (brew install glslang), NDK r27 clang
#   (~/Library/Android/ndk/android-ndk-r27c, or set NDK=). Vulkan-Headers in form/native/vulkan/.tools/.
# Run:  scripts/android_matvec_vk_run.sh [rows cols]   (defaults 256 256)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VK="$ROOT/form/native/vulkan"
TOOLS="$VK/.tools"
BUILD="$TOOLS/build"
ROWS="${1:-256}"; COLS="${2:-256}"
NDK="${NDK:-$HOME/Library/Android/ndk/android-ndk-r27c}"
mkdir -p "$BUILD"

# ── 1. device first — a missing phone is a named gate, not a failure ──
if ! command -v adb >/dev/null; then echo "SKIP  adb not installed (brew install android-platform-tools)"; exit 2; fi
serial="$(adb devices | awk 'NR>1 && $2=="device"{print $1; exit}')"
if [[ -z "$serial" ]]; then
    echo "SKIP  no Android device on adb — connect the phone (USB + authorize the debugging prompt,"
    echo "      or wireless: adb pair / adb connect <ip:port>), confirm with 'adb devices', then re-run."
    echo "      Everything else is ready: the .spv mints and the arm64 ELF cross-compiles below on demand."
    exit 2
fi
model="$(adb -s "$serial" shell getprop ro.product.model 2>/dev/null | tr -d '\r')"
abi="$(adb -s "$serial" shell getprop ro.product.cpu.abi 2>/dev/null | tr -d '\r')"
andv="$(adb -s "$serial" shell getprop ro.build.version.release 2>/dev/null | tr -d '\r')"
echo "device: $model  (abi=$abi, Android $andv, serial=$serial)"
if [[ "$abi" != arm64* ]]; then echo "FAIL  device abi $abi is not arm64 — this carrier is arm64-android"; exit 1; fi

# ── 2. mint matvec.spv (vulkan1.1; do NOT run spirv-opt — it re-fuses FMA on Adreno) ──
SPV="$BUILD/matvec.spv"
if command -v glslangValidator >/dev/null; then
    glslangValidator --target-env vulkan1.1 -V "$VK/matvec.comp" -o "$SPV" >/dev/null 2>"$BUILD/glslang.err" \
        || { echo "FAIL  glslang could not mint matvec.spv:"; cat "$BUILD/glslang.err"; exit 1; }
elif [[ ! -f "$SPV" ]]; then
    echo "FAIL  no glslangValidator (brew install glslang) and no prebuilt $SPV"; exit 1
fi
echo "shader: matvec.spv $(wc -c < "$SPV" | tr -d ' ') bytes (Form-emitted matvec.comp, vulkan1.1, NoContraction)"

# ── 3. cross-compile the arm64-android Vulkan carrier ──
BIN="$BUILD/matvec_vk_android"
CLANG="$NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android24-clang"
[[ -x "$CLANG" ]] || CLANG="$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/aarch64-linux-android24-clang 2>/dev/null | head -1)"
if [[ -x "$CLANG" && -d "$TOOLS/Vulkan-Headers/include" ]]; then
    "$CLANG" -O2 -ffp-contract=off -I "$TOOLS/Vulkan-Headers/include" "$VK/matvec_vk.c" -o "$BIN" -ldl -lm \
        2>"$BUILD/clang.err" || { echo "FAIL  NDK clang could not build the carrier:"; cat "$BUILD/clang.err"; exit 1; }
elif [[ ! -x "$BIN" ]]; then
    echo "FAIL  no NDK clang ($CLANG) or Vulkan-Headers ($TOOLS/Vulkan-Headers), and no prebuilt $BIN"
    echo "      NDK: download android-ndk-r27c, or set NDK=<path>.  Headers: git clone KhronosGroup/Vulkan-Headers into $TOOLS/"
    exit 1
fi
echo "carrier: $(file "$BIN" | sed 's/^[^:]*: //')"

# ── 4. push + run on the phone, gate bit-exact ──
REMOTE=/data/local/tmp
adb -s "$serial" push "$BIN" "$REMOTE/matvec_vk_android" >/dev/null
adb -s "$serial" push "$SPV" "$REMOTE/matvec.spv" >/dev/null
adb -s "$serial" shell "chmod 755 $REMOTE/matvec_vk_android"
echo "── running on the phone GPU ──"
out="$(adb -s "$serial" shell "cd $REMOTE && ./matvec_vk_android matvec.spv $ROWS $COLS" 2>&1)"
printf '%s\n' "$out" | sed 's/^/  /'
adb -s "$serial" shell "rm -f $REMOTE/matvec_vk_android $REMOTE/matvec.spv" >/dev/null 2>&1 || true

if printf '%s\n' "$out" | grep -q '^ok'; then
    gpu="$(printf '%s\n' "$out" | sed -n 's/^device=//p')"
    par="$(printf '%s\n' "$out" | sed -n 's/^parity_//p')"
    echo
    echo "ok — Form-minted matvec.spv ran on the REAL phone GPU ($gpu), $par"
    echo "the Android Vulkan lane is proven on-device, not just cross-compiled."
    exit 0
fi
echo "FAIL  on-device run did not reach bit-exact — see output above (name the op + ULP delta, do not fake a pass)"
exit 1
