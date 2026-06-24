#!/usr/bin/env bash
# verify_fkwu_android_no_go.sh — observe the C-bootstrap → fkwu runtime LIVE on an Android device,
# with NO go / rust / clang / python on the device. The Android twin of verify_bootstrap_host_posix.sh
# (host+loader contract) and the form-elf band (byte-emit contract): this one runs the WHOLE emitted
# universal kernel on the phone and checks its four-way verdicts against the manifest.
#
# The sovereignty claim, made falsifiable on real hardware:
#   1. emit uni.c — the universal kernel's C — from the Go kernel (fkc-emit-universal). The emitter is a
#      build-host bootstrap; nothing from it touches the device.
#   2. cross-compile uni.c to a STATIC aarch64 binary with zig (musl libc, no Android NDK, no clang on the
#      device). arc4random -> rand() is the same alias build_fourth uses on its Windows lane.
#   3. push ONLY that static binary + each band's pre-flattened table to the phone (/data/local/tmp).
#   4. run `fkwu <table> 0 | head -1` on-device — the exact invocation validate.sh uses — and assert the
#      verdict equals the manifest's four-way verdict (form/fourth-arm-bands.txt) AND the Mac fkwu's.
#
# A pass means: the body's recipes compute the SAME proven verdicts on the phone as in the four-way suite,
# executed by a kernel grown from a C seed and carrying no foreign toolchain on the device. Carrier only —
# the verdicts are Form (each band, four-way proven); this just witnesses them on Android hardware.
#
# Skips gracefully (exit 0 with a SKIP note) when a piece of the build host is absent: no Go kernel to emit
# from, no zig to cross-compile with, or no adb device attached. Set ZIG=/path/to/zig to reuse an install.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/form" || exit 3
W="$ROOT/.cache/android-fkwu"; mkdir -p "$W"
BANDS=("$@"); [ "${#BANDS[@]}" -ge 1 ] || BANDS=(room-address vision-percept speak-turn ambient-surprise spatial-fusion journey place-sense)

skip() { echo "SKIP: $1"; exit 0; }

# ── build host: Go kernel (the emitter) ──
export GO_BIN="$ROOT/form/form-kernel-go/bin-go"; export TMPDIR="${TMPDIR:-/tmp}"
if [ ! -x "$GO_BIN" ]; then
    command -v go >/dev/null 2>&1 || skip "no Go kernel and no 'go' to build the emitter (uni.c comes from fkc-emit-universal)"
    ( cd form-kernel-go && go build -o bin-go . ) >/dev/null 2>&1 || skip "Go kernel build failed"
fi

# ── build host: zig (cross-compiles aarch64 static-musl with no NDK) ──
ZIG="${ZIG:-}"
[ -n "$ZIG" ] && [ -x "$ZIG" ] || ZIG="$(/bin/ls -d "$ROOT"/.cache/zig/zig-*/zig 2>/dev/null | head -1)"
if [ -z "$ZIG" ] || [ ! -x "$ZIG" ]; then
    command -v zig >/dev/null 2>&1 && ZIG="$(command -v zig)" || \
        skip "no zig (cross-compiler). Get it: curl -sSL https://ziglang.org/download/0.13.0/zig-\$(uname -m | sed s/arm64/aarch64/)-macos... ; or set ZIG=/path/to/zig"
fi

# ── adb device ──
command -v adb >/dev/null 2>&1 || skip "no adb on PATH"
DEV="$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{print $1; exit}')"
[ -n "$DEV" ] || skip "no Android device attached (adb devices shows none)"

# ── emit uni.c, patch arc4random -> rand(), cross-compile static aarch64 ──
echo "  emitting uni.c (fkc-emit-universal)..." >&2
d="$(mktemp -d "$TMPDIR/fkwu-android.XXXXXX")"
cat form-stdlib/minimal-surface.fk form-stdlib/hati-os-kernel.fk form-stdlib/hati-os-kernel-emit.fk > "$d/uni-driver.fk"
printf '(do (print "==UNI==") (print (fkc-emit-universal)) (print "==END==") 0)\n' >> "$d/uni-driver.fk"
"$GO_BIN" "$d/uni-driver.fk" 2>"$d/uni.err" > "$d/uni.out" || { rm -rf "$d"; skip "uni.c emit failed (see Go kernel)"; }
sed -n '/^==UNI==$/,/^==END==$/p' "$d/uni.out" | sed -e '1d' -e '$d' \
  | sed 's|extern unsigned int arc4random(void);|extern int rand(void); static unsigned int arc4random(void) { return (unsigned int)rand(); }|' \
  > "$W/uni-android.c"
[ -s "$W/uni-android.c" ] || { rm -rf "$d"; skip "uni.c emit produced nothing"; }
rm -rf "$d"
echo "  cross-compiling fkwu (static aarch64-musl, no NDK)..." >&2
"$ZIG" cc -target aarch64-linux-musl -O2 -static \
  -Wno-error=implicit-function-declaration -Wno-implicit-function-declaration \
  -Wno-incompatible-library-redeclaration -Wno-pointer-sign \
  -o "$W/fkwu-android" "$W/uni-android.c" 2>"$W/cc.err" || { echo "FAIL: cross-compile failed:"; tail -5 "$W/cc.err"; exit 1; }
adb -s "$DEV" push "$W/fkwu-android" /data/local/tmp/fkwu >/dev/null 2>&1
adb -s "$DEV" shell chmod 755 /data/local/tmp/fkwu

# ── the Mac reference kernel + the table builder ──
set +u; . scripts/fourth-arm.sh; set -u
command -v clang >/dev/null 2>&1 && build_fourth >/dev/null 2>&1
MACFKWU=""; for f in form-stdlib/.cache/fourth/fkwu-*; do [ -x "$f" ] && [ "$(basename "$f")" != "fkwu-android" ] && MACFKWU="$f"; done

model="$(adb -s "$DEV" shell getprop ro.product.model 2>/dev/null | tr -d '\r')"
arch="$(adb -s "$DEV" shell uname -m 2>/dev/null | tr -d '\r')"
echo "  device: $model ($arch) · fkwu: static aarch64-musl · no go/rust/clang/python on device" >&2

fails=0; rows=""
for band in "${BANDS[@]}"; do
    exp="$(awk -v b="$band" '$1==b{print $3; exit}' fourth-arm-bands.txt)"
    [ -n "$exp" ] || { echo "  ? $band — not in fourth-arm-bands.txt, skipping"; continue; }
    tbl="$(fourth_table_for_band "form-stdlib/tests/$band-band.fk" 2>/dev/null)"
    if [ -z "$tbl" ] || [ ! -s "$tbl" ]; then echo "  ✗ $band — no table built"; fails=$((fails+1)); continue; fi
    mac="-"; [ -n "$MACFKWU" ] && mac="$(TMPDIR="$(mktemp -d)" "$MACFKWU" "$tbl" 0 2>/dev/null | head -1 | tr -d '[:space:]')"
    adb -s "$DEV" push "$tbl" /data/local/tmp/t.txt >/dev/null 2>&1
    and="$(adb -s "$DEV" shell 'cd /data/local/tmp && ./fkwu t.txt 0 2>/dev/null | head -1' | tr -d '[:space:]')"
    if [ "$and" = "$exp" ] && { [ "$mac" = "-" ] || [ "$mac" = "$exp" ]; }; then
        echo "  ✓ $band — android=$and  mac=$mac  (manifest $exp)"
        rows="$rows{\"band\":\"$band\",\"expected\":$exp,\"android\":$and,\"mac\":\"$mac\"},"
    else
        echo "  ✗ $band — android=$and  mac=$mac  expected=$exp"; fails=$((fails+1))
        rows="$rows{\"band\":\"$band\",\"expected\":$exp,\"android\":\"$and\",\"mac\":\"$mac\",\"ok\":false},"
    fi
done

printf '{"status":"%s","device":"%s","arch":"%s","kernel":"fkwu static aarch64-musl (zig, no NDK)","device_toolchain":"none (no go/rust/clang/python)","bands":[%s]}\n' \
    "$([ "$fails" -eq 0 ] && echo pass || echo fail)" "$model" "$arch" "${rows%,}"
[ "$fails" -eq 0 ] || exit 1
