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
# Default target: linux/arm64, CGO_ENABLED=0 — a STATICALLY LINKED ARM aarch64
# ELF, runnable on a device via Termux / adb. No NDK, no cgo: the gen conductor
# is pure interpreter, and the cgo dylib-JIT degrades to jit_inram_other on this
# build (the conductor never needs it). For a bionic / linker64 system-linked
# binary (app-embeddable), the GOOS=android path needs: brew install android-ndk
# + CC=<ndk-clang> CGO_ENABLED=1 GOOS=android GOARCH=arm64.
#
# See docs/coherence-substrate/kernel-on-android.form for the on-device wiring.
set -euo pipefail
cd "$(dirname "$0")"

OUT="bin-go-android"
FORMGEN="../form-stdlib/form-gen.fk"

echo "→ cross-compiling the Go kernel for android/arm64 (linux/arm64, CGO_ENABLED=0) ..."
GOOS=linux GOARCH=arm64 CGO_ENABLED=0 go build -o "$OUT" .

echo
file "$OUT"
case "$(file "$OUT")" in
  *"ARM aarch64"*) echo "✓ Android ARM64 Go kernel binary at $OUT" ;;
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

# Execution proof where the tooling exists. Linux CI ships qemu-aarch64 (see
# scripts/cross_isa_assembly_audit.sh); a macOS host does not ship qemu-user, so
# there the ELF type + carries-conductor IS the proof (same bar the Rust android
# build is proven at). On a device: adb push + run, or Termux.
echo
if command -v qemu-aarch64 >/dev/null 2>&1; then
  echo "→ qemu-aarch64 present — running the gen conductor on the ARM64 binary:"
  printf '(fg-dispatch "gen (add (mul 6 7) 1)")\n' > /tmp/gen-android-cmd.fk
  val="$(qemu-aarch64 "$OUT" "$FORMGEN" /tmp/gen-android-cmd.fk 2>&1 | tail -1)"
  echo "  gen \"(add (mul 6 7) 1)\" -> $val"
  case "$val" in
    *43*) echo "✓ the gen conductor EXECUTES on ARM64 (emulated)" ;;
    *) echo "✗ unexpected result — investigate"; exit 1 ;;
  esac
else
  echo "  qemu-aarch64 absent on this host — ELF + carries-conductor is the proof here."
  echo "  on a device:  adb push $OUT /data/local/tmp/  &&  adb push ../form-stdlib /data/local/tmp/"
  echo "                adb shell /data/local/tmp/$OUT form-stdlib/form-gen.fk cmd.fk   (or Termux)"
fi

echo
echo "✓ the gen conductor cross-compiles to a genuine Android ARM64 binary."
