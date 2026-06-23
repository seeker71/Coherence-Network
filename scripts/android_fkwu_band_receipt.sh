#!/usr/bin/env bash
# android_fkwu_band_receipt.sh — the standard-receipt ANDROID row for fkwu: emit the universal
# walker C (fkwu, Form-emitted), cross-compile it for aarch64-android with the NDK clang into an
# ELF, push it to the phone with a flattened band table, and run the band ON THE DEVICE -> a verdict.
#
# The fkwu binary has NO Go/Rust/TS/python in its runtime path. Go appears only as the build-time
# FLATTENER (the band table); NDK clang only as the C bootstrap (the standard-receipt c-bootstrap
# row, honest until form-elf emits the ELF bytes directly and drops clang too). This is the
# "observe what the on-device fkwu run actually does" loop — implement, run, adjust.
#
# Usage: android_fkwu_band_receipt.sh [module.fk ... band.fk]   (default: field-identity, expect 511)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT/form" || exit 3
export GO_BIN="$ROOT/form/form-kernel-go/bin-go"; export TMPDIR="${TMPDIR:-/tmp}"
[ -x "$GO_BIN" ] || (cd form-kernel-go && go build -o bin-go .) >/dev/null 2>&1 || true
RECIPES=("$@"); [ "${#RECIPES[@]}" -ge 1 ] || RECIPES=(form-stdlib/field-identity.fk form-stdlib/tests/field-identity-band.fk)
last="${RECIPES[$((${#RECIPES[@]}-1))]}"; mods=("${RECIPES[@]:0:$((${#RECIPES[@]}-1))}")

DEV="$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{print $1; exit}')"
[ -n "$DEV" ] || { echo "no adb device; skipping"; exit 0; }
NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
CC="$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/aarch64-linux-android*-clang 2>/dev/null | sort -V | tail -1)"
[ -x "$CC" ] || { echo "no NDK aarch64 clang; skipping"; exit 0; }

set +u; . scripts/fourth-arm.sh; set -u
FOURTH_SHIM="form-stdlib/fourth-shim.fk"
d="$(mktemp -d "${TMPDIR}/afkwu.XXXXXX")"; trap 'rm -rf "$d"' EXIT

# 1. emit the universal walker C (Form-emitted: fkc-emit-universal)
cat form-stdlib/minimal-surface.fk form-stdlib/hati-os-kernel.fk form-stdlib/hati-os-kernel-emit.fk > "$d/uni-driver.fk"
printf '(do (print "==UNI==") (print (fkc-emit-universal)) (print "==END==") 0)\n' >> "$d/uni-driver.fk"
"$GO_BIN" "$d/uni-driver.fk" 2>/dev/null | sed -n '/^==UNI==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$d/uni.c"
[ -s "$d/uni.c" ] || { echo "FAIL: emit produced no C"; exit 1; }
echo "emitted fkwu C: $(wc -l < "$d/uni.c") lines"

# 2. cross-compile the SAME C for aarch64-android (the only clang in the loop, the c-bootstrap)
"$CC" -O2 -Wno-implicit-function-declaration -Wno-incompatible-library-redeclaration -pthread \
    -o "$d/fkwu-android" "$d/uni.c" 2>"$d/cc.err" || { echo "FAIL: android compile:"; sed -n '1,15p' "$d/cc.err"; exit 1; }
file "$d/fkwu-android" | sed 's/^/  /'

# 3. flatten the band into an fkwu node-table (Go = build-time flattener only)
modexpr=" (read_file \"$FOURTH_SHIM\")"; for m in "${mods[@]}"; do modexpr="$modexpr (read_file \"$m\")"; done
cat "${FOURTH_CHAIN[@]}" > "$d/fdriver.fk"
printf '(print (fks-table-file (flt-band-sources-fns (list%s) (read_file "%s")) (flt-band-sources-pool (list%s) (read_file "%s"))))\n' \
    "$modexpr" "$last" "$modexpr" "$last" >> "$d/fdriver.fk"
"$GO_BIN" "$d/fdriver.fk" 2>/dev/null > "$d/table.txt"
[ -s "$d/table.txt" ] || { echo "FAIL: flatten produced no table"; exit 1; }
printf '' > "$d/bundle"
echo "flattened table: $(wc -c < "$d/table.txt") bytes"

# 4. push to the phone and run fkwu ON THE DEVICE
R="/data/local/tmp/fkwu-recv-$$"
adb -s "$DEV" push "$d/fkwu-android" "${R}.bin" >/dev/null 2>&1
adb -s "$DEV" push "$d/table.txt" "${R}.tbl" >/dev/null 2>&1
adb -s "$DEV" push "$d/bundle" "${R}.bun" >/dev/null 2>&1
V="$(adb -s "$DEV" shell "chmod 755 ${R}.bin; cd /data/local/tmp; ./fkwu-recv-$$.bin ${R}.tbl 0 ${R}.bun" 2>&1 | head -1 | tr -d '\r')"
DEVMODEL="$(adb -s "$DEV" shell getprop ro.product.model 2>/dev/null | tr -d '\r')"
ABI="$(adb -s "$DEV" shell getprop ro.product.cpu.abi 2>/dev/null | tr -d '\r')"
adb -s "$DEV" shell "rm -f ${R}.bin ${R}.tbl ${R}.bun" >/dev/null 2>&1
echo
echo "ON-DEVICE fkwu run — $DEVMODEL ($ABI), device $DEV"
echo "  band: $last"
echo "  verdict on the phone's fkwu: $V"
