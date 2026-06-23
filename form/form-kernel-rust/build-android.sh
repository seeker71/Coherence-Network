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
#    Runnable on a device via adb/Termux; the parity_suite + CLI surface.
cd "$(dirname "$0")"
cargo ndk -t arm64-v8a build --release --bin form-kernel-rust

BIN="target/aarch64-linux-android/release/form-kernel-rust"
echo
file "$BIN"
case "$(file "$BIN")" in
  *"ARM aarch64"*) echo "✓ Android ARM64 kernel binary at $BIN" ;;
  *) echo "✗ not an ARM aarch64 ELF — investigate"; exit 1 ;;
esac

# 4. Cross-compile the APP-LOADABLE library — the cdylib with the C-ABI surface
#    (--features cabi). This is what an Android app loads via System.loadLibrary
#    + JNI: a .so exporting `form_eval(src)->display-text` over the SAME evaluator
#    (kernel::run_source) the binary runs. PROVEN 2026-06-09: ARM aarch64 shared
#    object exporting form_eval / form_eval_free, ~4 MB. No Python (pyo3 stays off).
cargo ndk -t arm64-v8a build --release --lib --features cabi

SO="target/aarch64-linux-android/release/libform_kernel_rust.so"
echo
file "$SO"
NM="$(ls "$ANDROID_NDK_HOME"/toolchains/llvm/prebuilt/*/bin/llvm-nm 2>/dev/null | head -1)"
case "$(file "$SO")" in
  *"shared object"*"ARM aarch64"*)
    echo "✓ Android ARM64 cdylib at $SO"
    [ -x "$NM" ] && "$NM" -D "$SO" | grep -q form_eval \
      && echo "✓ exports form_eval / form_eval_free (JNI-callable)" \
      || echo "  (llvm-nm not found; the file check above is the proof)" ;;
  *) echo "✗ cdylib is not an ARM aarch64 shared object — investigate"; exit 1 ;;
esac

# 5. Drop the .so into the app so the gradle build packages it. The .so is
#    gitignored (a 4 MB build artifact), so the APK build depends on THIS step
#    having run — both build scripts (build_signed_release.sh,
#    verify_android_sense_public_handshake.sh) invoke build-android.sh first.
APP="$(cd "$(dirname "$0")/../../experiments/coherence-sense-android" && pwd)"
JNILIBS="$APP/app/src/main/jniLibs/arm64-v8a"
RECIPES="$APP/app/src/main/assets/recipes"
STDLIB="$(cd "$(dirname "$0")/../form-stdlib" && pwd)"
mkdir -p "$JNILIBS" "$RECIPES"
cp "$SO" "$JNILIBS/libform_kernel_rust.so"
echo "✓ .so → $JNILIBS/libform_kernel_rust.so"
# Refresh the bundled recipe assets from the single source of truth (form-stdlib)
# so the on-device kernel runs the SAME proven recipes (no drift). The phone-native
# recognition (FormKernel.kt) loads these from assets/recipes/ at runtime.
for fk in signal-derivative.fk; do cp "$STDLIB/$fk" "$RECIPES/$fk"; done
cp "$STDLIB/tests/signal-derivative-band.fk" "$RECIPES/signal-derivative-band.fk"
echo "✓ recipe assets refreshed → $RECIPES"

# DONE (2026-06-23): the JNI shim is live. FormKernel.kt binds
# Java_com_coherence_sense_FormKernel_eval (this .so, built with --features cabi);
# MainActivity runs the proven signal-derivative recipe in-process — the phone
# recognizes WITHOUT the Mac (self-test reproduces the four-way band verdict 127,
# verified on a Galaxy S23 Ultra). See docs/coherence-substrate/kernel-on-android.form.
