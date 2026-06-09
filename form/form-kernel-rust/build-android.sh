#!/usr/bin/env bash
# build-android.sh — cross-compile the Form Rust kernel for Android ARM64 (aarch64-linux-android).
#
# PROVEN 2026-06-09: produces a genuine Android ELF —
#   "ELF 64-bit LSB pie executable, ARM aarch64 ... interpreter /system/bin/linker64"
# The whole engine + dep tree (tokio-postgres, rustls, ureq) builds in ~70s. pyo3 stays OFF
# (it is an opt-in feature, default = []), so there is NO Python-for-Android dependency.
#
# Prereqs (one-time): brew install android-ndk ; cargo install cargo-ndk
set -euo pipefail

# 1. The NDK. brew installs it under the Caskroom; find the real NDK root (…/Contents/NDK).
NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
[ -d "$NDK" ] || { echo "Android NDK not found — run: brew install android-ndk"; exit 1; }
export ANDROID_NDK_HOME="$NDK"

# 2. THE GOTCHA that cost two build attempts: a Homebrew `rustc` in PATH is standalone and has NO
#    cross-compile std, so `rustup target add` (which targets the rustup toolchain) is invisible to it
#    — the build fails with "can't find crate for `core`". And cargo-ndk shells out to `cargo build`
#    as a SUBPROCESS, which re-resolves cargo/rustc from PATH. So the rustup toolchain's bin must come
#    FIRST in PATH, so BOTH the outer cargo-ndk and its inner cargo build use rustup's rustc (with the
#    ARM std), not Homebrew's.
RUSTUP_BIN="$HOME/.rustup/toolchains/stable-aarch64-apple-darwin/bin"
[ -d "$RUSTUP_BIN" ] || { echo "rustup stable toolchain not found at $RUSTUP_BIN"; exit 1; }
export PATH="$RUSTUP_BIN:$HOME/.cargo/bin:$PATH"
rustup target list --installed | grep -q aarch64-linux-android || rustup target add aarch64-linux-android

# 3. Cross-compile the kernel binary for arm64-v8a (default features — no pyo3).
cd "$(dirname "$0")"
cargo ndk -t arm64-v8a build --release --bin form-kernel-rust

BIN="target/aarch64-linux-android/release/form-kernel-rust"
echo
file "$BIN"
case "$(file "$BIN")" in
  *"ARM aarch64"*) echo "✓ Android ARM64 kernel at $BIN" ;;
  *) echo "✗ not an ARM aarch64 ELF — investigate"; exit 1 ;;
esac

# NEXT (not done here): the engine lives in main.rs (a binary — runnable on a device via adb/Termux
# today). For an APP-loadable library, extract the engine into a shared module and add a
# `#[no_mangle] pub extern "C" fn` evaluate(recipe_text)->result entry, then build crate-type cdylib
# with cargo-ndk to emit a per-ABI .so for jniLibs. See docs/coherence-substrate/kernel-on-android.form.
