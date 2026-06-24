#!/usr/bin/env bash
# vulkan_matvec_android_audit.sh — Adreno GPU witness for the Form GLSL matvec emitter
# (fglsl-matvec in form/form-stdlib/form-glsl.fk): the Android twin of metal_matvec_audit.sh.
# The kernel's mouth prints the Form-emitted GLSL compute shader, glslangValidator mints the
# SPIR-V (authoring, like nvrtc->cubin), the NDK cross-compiles the headless Vulkan host carrier
# (form/native/vulkan/matvec_vk.c — driver-only: dlopen libvulkan.so + vkGetInstanceProcAddr),
# adb pushes both to the connected phone, and the harness DISPATCHES the .spv on the device's
# Adreno GPU and bit-checks every output row against its OWN CPU right-fold oracle (j DOWN,
# mul then add, val(n)=n/256 — the same op order as the recipe / PTX / MSL / CPU lanes).
#
# The shader that runs on the GPU IS the Form recipe: the emitted GLSL is asserted byte-identical
# to native/vulkan/matvec.comp (the canonical proven body) before it is ever compiled — never a
# hand-authored shader beside the recipe. `precise` -> NoContraction keeps mul+add unfused so the
# Adreno result is bit-exact (no spirv-opt: its MergeMulAddArithmetic would re-fuse).
#
# Carriers (all allowed host carriers per host-kernel.form host-resource-access — the emitter
# intelligence lives in the body): form-kernel-go (the mouth), glslangValidator (SPIR-V mint),
# the Android NDK aarch64 clang (cross-compile the carrier), adb + the on-device libvulkan.so.
#
# Skips cleanly (exit 0) when no Go kernel / glslang / NDK / connected device is present — a
# witness is a sensing readout, never a gate that fails for missing hardware.
#
# Run:  scripts/vulkan_matvec_android_audit.sh [rows cols]    (defaults 1280 1280)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMDIR="$ROOT/form"
GO_BIN="$FORMDIR/form-kernel-go/bin-go"
ROWS="${1:-1280}"; COLS="${2:-1280}"

skip() { echo "SKIP  $1"; exit 0; }

command -v glslangValidator >/dev/null || skip "no glslangValidator — the SPIR-V mint is absent (brew install glslang)"
command -v adb >/dev/null || skip "no adb — cannot reach an Android device"

# Locate an Android NDK aarch64 clang (env first, then the usual install roots).
find_ndk_cc() {
    local roots=()
    [[ -n "${ANDROID_NDK_HOME:-}" ]] && roots+=("$ANDROID_NDK_HOME")
    [[ -n "${ANDROID_NDK_ROOT:-}" ]] && roots+=("$ANDROID_NDK_ROOT")
    roots+=("$HOME/Library/Android/ndk"/* "$HOME/Library/Android/sdk/ndk"/* "$HOME/Android/Sdk/ndk"/*)
    local r cc
    for r in "${roots[@]}"; do
        [[ -d "$r" ]] || continue
        cc="$(find "$r/toolchains/llvm/prebuilt" -name 'aarch64-linux-android30-clang' 2>/dev/null | head -1)"
        [[ -z "$cc" ]] && cc="$(find "$r/toolchains/llvm/prebuilt" -name 'aarch64-linux-android*-clang' 2>/dev/null | sort | tail -1)"
        if [[ -n "$cc" ]]; then echo "$cc"; return 0; fi
    done
    return 1
}
CC="$(find_ndk_cc)" || skip "no Android NDK aarch64 clang found (set ANDROID_NDK_HOME)"
SYSINC="$(dirname "$(dirname "$CC")")/sysroot/usr/include"
[[ -f "$SYSINC/vulkan/vulkan.h" ]] || skip "NDK at $CC has no vulkan/vulkan.h in its sysroot"

DEV="$(adb devices | awk 'NR>1 && $2=="device" {print $1; exit}')"
[[ -n "$DEV" ]] || skip "no Android device in 'adb devices' (connect a phone + authorize)"

if [[ ! -x "$GO_BIN" ]]; then
    echo "  building go kernel..." >&2
    (cd "$FORMDIR/form-kernel-go" && go build -o bin-go .) || skip "go kernel build failed"
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/fkvkadreno.XXXXXX")"
trap 'rm -rf "$work"' EXIT

# ── 1. Form emits the GLSL; the kernel is only the mouth ─────────────────
printf '(print "==GLSL==")\n(print (fglsl-matvec "64"))\n(print "==END==")\n' > "$work/print.fk"
(cd "$FORMDIR" && "$GO_BIN" form-stdlib/form-glsl.fk "$work/print.fk" 2>/dev/null) > "$work/emit.out"
# Strip the print frame; the recipe string already ends in \n, print adds one more — drop exactly that.
sed -n '/^==GLSL==$/,/^==END==$/p' "$work/emit.out" | sed -e '1d' -e '$d' \
    | perl -0777 -pe 's/\n\z//' > "$work/matvec.comp"
if ! grep -q 'void main' "$work/matvec.comp"; then
    echo "FAIL  GLSL emission did not produce the compute shader — see $work/emit.out"; exit 1
fi
EMITTED_SHA="$(shasum -a 256 "$work/matvec.comp" | cut -d' ' -f1)"
CANON_SHA="$(shasum -a 256 "$FORMDIR/native/vulkan/matvec.comp" | cut -d' ' -f1)"
echo "emitted GLSL: $(wc -c < "$work/matvec.comp" | tr -d ' ') bytes, sha256 $EMITTED_SHA — every byte authored by fglsl-matvec"
if [[ "$EMITTED_SHA" != "$CANON_SHA" ]]; then
    echo "FAIL  emitted shader differs from the canonical proven body native/vulkan/matvec.comp ($CANON_SHA)"; exit 1
fi
echo "  byte-identical to the canonical proven matvec.comp — the recipe IS the shader"

# ── 2. glslangValidator mints the SPIR-V ─────────────────────────────────
glslangValidator -V --target-env vulkan1.1 "$work/matvec.comp" -o "$work/matvec.spv" >/dev/null 2>&1 || {
    echo "FAIL  glslangValidator could not mint SPIR-V"; exit 1; }
SPV_SHA="$(shasum -a 256 "$work/matvec.spv" | cut -d' ' -f1)"
echo "minted SPIR-V: $(wc -c < "$work/matvec.spv" | tr -d ' ') bytes, sha256 $SPV_SHA"

# ── 3. The NDK cross-compiles the headless Vulkan carrier ────────────────
"$CC" -O2 -I"$SYSINC" "$FORMDIR/native/vulkan/matvec_vk.c" -o "$work/matvec_vk" -ldl 2>"$work/cc.err" || {
    echo "FAIL  NDK could not cross-compile the Vulkan carrier:"; cat "$work/cc.err"; exit 1; }
echo "cross-compiled the host carrier for aarch64-android ($(basename "$CC"))"

# ── 4. adb push + dispatch on the device's Adreno; the harness gates parity ──
DD="/data/local/tmp/fkvkadreno.$$"
adb -s "$DEV" shell "mkdir -p $DD" >/dev/null 2>&1
adb -s "$DEV" push "$work/matvec_vk" "$DD/matvec_vk" >/dev/null 2>&1
adb -s "$DEV" push "$work/matvec.spv" "$DD/matvec.spv" >/dev/null 2>&1
adb -s "$DEV" shell "chmod 755 $DD/matvec_vk" >/dev/null 2>&1
MODEL="$(adb -s "$DEV" shell getprop ro.product.model | tr -d '\r')"
echo
echo "witness on device $DEV ($MODEL), ${ROWS}x${COLS} Form-emitted matvec on the Adreno GPU:"
out="$(adb -s "$DEV" shell "cd $DD && ./matvec_vk matvec.spv $ROWS $COLS" 2>&1)"
rc_run=$?
echo "$out" | sed 's/^/  /'
adb -s "$DEV" shell "rm -rf $DD" >/dev/null 2>&1   # hold the device only as long as the dispatch needs

echo
echo "conditions: emit (form-kernel-go) -> SPIR-V (glslangValidator vulkan1.1) -> aarch64-android (NDK)" \
     "-> adb dispatch on the device's Vulkan driver alone (libvulkan.so), parity = the harness's own CPU" \
     "right-fold (j DOWN, mul then add, val(n)=n/256), precise -> NoContraction so no FMA re-fusion"
if [[ "$rc_run" != "0" ]] || ! echo "$out" | grep -q "parity_bitexact_rows=${ROWS}/${ROWS}"; then
    echo "FAIL  the Adreno output is not bit-exact to the recipe right-fold — diagnose the divergence"; exit 1
fi
echo "ok — the Form-emitted GLSL matvec ran on the real Adreno GPU, bit-exact to the recipe; emitter is form-stdlib/form-glsl.fk (fglsl-matvec)"
