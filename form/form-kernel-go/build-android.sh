#!/usr/bin/env bash
# build-android.sh — cross-compile the Form Go kernel for Android ARM64.
#
# Why: the gen conductor (form-stdlib/form-gen.fk — "form-cli that can generate
# → RAM / disk / content-addressed store → execute → share") lives where the
# compiler lives. Its one essential primitive, form_compile, is a Go-kernel
# native — so to run the conductor on a phone, the GO kernel must build for
# Android. The Rust kernel already cross-compiles (build-android.sh, sibling);
# the fkwu C arm cross-compiles too but cannot compile (no form_compile). This
# is the missing Go arm.
#
# Two targets, best-first:
#   BIONIC  (NDK present)  GOOS=android GOARCH=arm64 CGO_ENABLED=1 CC=<ndk clang>
#           → "ELF ... ARM aarch64 ... interpreter /system/bin/linker64", the
#             genuine Android binary (runs on a device and natively in Termux),
#             same class the Rust kernel build produces.
#   STATIC  (no NDK)       GOOS=linux GOARCH=arm64 CGO_ENABLED=0
#           → a statically linked ARM aarch64 ELF, runnable via Termux / adb and
#             under qemu-aarch64. No NDK, no cgo (the cgo dylib-JIT degrades to
#             jit_inram_other, which the interpreter never needs).
#
# Install the NDK for the bionic target: brew install android-ndk.
# See docs/coherence-substrate/kernel-on-android.form for the on-device wiring.
set -euo pipefail
cd "$(dirname "$0")"

OUT="bin-go-android"
FORMGEN="../form-stdlib/form-gen.fk"

# Resolve the NDK the way the Rust sibling does: env first, then the brew Cask,
# then the SDK ndk dir. Find an aarch64 android clang inside it (prebuilt host
# dir is darwin-x86_64 on a Mac — runs under Rosetta — or linux-x86_64 on CI).
NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
[ -n "$NDK" ] || NDK="$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*/Contents/NDK 2>/dev/null | head -1 || true)"
[ -n "$NDK" ] || NDK="$(ls -d "$HOME"/Library/Android/sdk/ndk/* 2>/dev/null | sort -V | tail -1 || true)"
CC=""
[ -n "$NDK" ] && CC="$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/aarch64-linux-android21-clang 2>/dev/null | head -1 || true)"

if [ -n "$CC" ]; then
  echo "→ NDK found ($NDK)"
  echo "→ bionic build: GOOS=android GOARCH=arm64 CGO_ENABLED=1 (NDK clang) ..."
  GOOS=android GOARCH=arm64 CGO_ENABLED=1 CC="$CC" go build -o "$OUT" .
  VARIANT="bionic (linker64)"
else
  echo "→ no NDK (set ANDROID_NDK_HOME or: brew install android-ndk) — static fallback"
  echo "→ static build: GOOS=linux GOARCH=arm64 CGO_ENABLED=0 ..."
  GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -o "$OUT" .
  VARIANT="static (Termux/qemu)"
fi

echo
file "$OUT"
case "$(file "$OUT")" in
  *"ARM aarch64"*) echo "✓ Android ARM64 Go kernel binary [$VARIANT] at $OUT" ;;
  *) echo "✗ not an ARM aarch64 ELF — investigate"; exit 1 ;;
esac

# The gen conductor must be IN the binary — the whole point of the android arm.
echo
echo "→ verifying the gen conductor's primitives ride along:"
# Dump the symbol strings ONCE to a file and grep the file — piping
# `strings | grep -q` trips SIGPIPE under `set -o pipefail` (grep -q exits early,
# strings dies 141, the pipeline reads as failure even on a match).
syms="$(mktemp)"; strings "$OUT" > "$syms"
miss=0
for n in form_compile form_walk recipe_to_bytes bytes_to_recipe write_file_bytes read_file_bytes; do
  if grep -qF "$n" "$syms"; then echo "  ✓ $n"; else echo "  ✗ $n MISSING"; miss=1; fi
done
rm -f "$syms"
[ "$miss" = 0 ] || { echo "✗ a conductor primitive is missing — investigate"; exit 1; }

# Execution. Best is a real device over adb (works for the bionic binary). Else
# a static binary under qemu-aarch64 (Linux CI ships it; a macOS host does not).
# Else the ELF type + carries-conductor IS the proof here (the bar the Rust
# android build is proven at), and on-device is one adb push away.
echo
DEV="$(command -v adb >/dev/null 2>&1 && adb get-state 2>/dev/null || true)"
printf '(fg-dispatch "gen (add (mul 6 7) 1)")\n' > /tmp/gen-android-cmd.fk
if [ "$DEV" = "device" ]; then
  echo "→ device attached — running the gen conductor on Android via adb:"
  adb push "$OUT" /data/local/tmp/bin-go-android >/dev/null
  adb push ../form-stdlib /data/local/tmp/ >/dev/null
  adb push /tmp/gen-android-cmd.fk /data/local/tmp/ >/dev/null
  val="$(adb shell 'cd /data/local/tmp && ./bin-go-android form-stdlib/form-gen.fk gen-android-cmd.fk' 2>&1 | tail -1)"
  echo "  gen \"(add (mul 6 7) 1)\" -> $val"
  case "$val" in *43*) echo "✓ the gen conductor EXECUTES ON ANDROID (device)";; *) echo "✗ unexpected — investigate"; exit 1;; esac
elif [ "$VARIANT" = "static (Termux/qemu)" ] && command -v qemu-aarch64 >/dev/null 2>&1; then
  echo "→ qemu-aarch64 present — running the static binary (emulated ARM64):"
  val="$(qemu-aarch64 "$OUT" "$FORMGEN" /tmp/gen-android-cmd.fk 2>&1 | tail -1)"
  echo "  gen \"(add (mul 6 7) 1)\" -> $val"
  case "$val" in *43*) echo "✓ the gen conductor EXECUTES on ARM64 (emulated)";; *) echo "✗ unexpected — investigate"; exit 1;; esac
else
  echo "  no device/qemu on this host — ELF + carries-conductor is the proof here."
  echo "  on a device:  adb push $OUT /data/local/tmp/  &&  adb push ../form-stdlib /data/local/tmp/"
  echo "                adb shell /data/local/tmp/$OUT form-stdlib/form-gen.fk cmd.fk   (or Termux)"
fi

echo
echo "✓ the gen conductor cross-compiles to a genuine Android ARM64 binary [$VARIANT]."
