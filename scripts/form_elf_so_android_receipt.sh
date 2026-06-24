#!/usr/bin/env bash
# form_elf_so_android_receipt.sh — the physical on-device receipt for form-elf-so.fk:
# a Form recipe emits a LOADABLE aarch64 ELF .so (ZERO clang — Form is the compiler,
# assembler, AND linker for the .so itself), which the Android dynamic linker dlopen's
# on a real device and whose exported form_native() runs as native code, returning 42.
#
# The only clang here is the NDK building the tiny dlopen HARNESS (a test rig, like
# form-elf-exec's qemu/adb runner) — never the .so. The .so is Form-native bytes.
#
# Skips cleanly (exit 0) when no NDK or no adb device is present; the four-way byte
# proof is tests/form-elf-so-band.fk (127). This is the runtime half.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
KERNEL="$FORM/form-kernel-rust/target/release/form-kernel-rust"
[[ -x "$KERNEL" ]] || KERNEL="$FORM/form-kernel-rust/target/debug/form-kernel-rust"
[[ -x "$KERNEL" ]] || { echo "no form-kernel-rust binary; skipping"; exit 0; }

DEV="$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{print $1; exit}')"
[[ -n "$DEV" ]] || { echo "no adb device attached; skipping (byte proof is form-elf-so-band 127)"; exit 0; }
NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
CC="$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/aarch64-linux-android*-clang 2>/dev/null | sort -V | tail -1)"
[[ -x "$CC" ]] || { echo "no NDK aarch64 clang for the harness; skipping"; exit 0; }

work="$(mktemp -d "${TMPDIR:-/tmp}/felfso.XXXXXX")"; trap 'rm -rf "$work"' EXIT
RET="${1:-42}"

# Form emits the loadable .so bytes (hex). form-elf-so.fk's defns + a hex driver.
{ sed '$ d' "$FORM/form-stdlib/form-elf-so.fk"
  cat <<DRV
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (print (str_concat "ELFSO " (hxb (elf-so (elf-so-leaf-const $RET)))))
    0)
DRV
} > "$work/emit.fk"
hex="$(cd "$FORM" && "$KERNEL" "$work/emit.fk" 2>/dev/null | grep '^ELFSO ' | sed 's/^ELFSO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no .so"; exit 1; }
echo "$hex" | xxd -r -p > "$work/form_native.so"
echo "Form-emitted ELF .so: $(wc -c < "$work/form_native.so" | tr -d ' ') bytes (ZERO clang)"
file "$work/form_native.so" | sed 's/^[^:]*: /  /'

# The dlopen harness — NDK clang builds the RIG, not the .so.
cat > "$work/harness.c" <<'C'
#include <dlfcn.h>
#include <stdio.h>
typedef long (*fn)(void);
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { printf("DLOPEN_FAIL %s\n", dlerror()); return 10; }
    fn f = (fn)dlsym(h, "form_native");
    if (!f) { printf("DLSYM_FAIL %s\n", dlerror()); return 11; }
    printf("RESULT %ld\n", f());
    return 0;
}
C
"$CC" -o "$work/harness" "$work/harness.c" || { echo "FAIL: harness build"; exit 1; }

D=/data/local/tmp/form-elf-so-receipt
adb -s "$DEV" shell "mkdir -p $D" >/dev/null 2>&1
adb -s "$DEV" push "$work/form_native.so" "$D/form_native.so" >/dev/null 2>&1
adb -s "$DEV" push "$work/harness" "$D/harness" >/dev/null 2>&1
adb -s "$DEV" shell "chmod 755 $D/harness" >/dev/null 2>&1
echo
echo "running on device $DEV — dlopen the Form-emitted .so, call form_native() (expect $RET):"
out="$(adb -s "$DEV" shell "cd $D && ./harness ./form_native.so" 2>&1 | tr -d '\r')"
echo "  $out"
adb -s "$DEV" shell "rm -rf $D" >/dev/null 2>&1
case "$out" in
  "RESULT $RET")
    echo
    echo "ON-DEVICE NATIVE, ZERO CLANG (.so): a Form recipe emitted a loadable aarch64 ELF"
    echo ".so; the Android linker dlopen'd it and its exported native form_native() ran on the"
    echo "phone, returning $RET. The native-JIT-on-ARM carrier is real, end to end." ;;
  *) echo; echo "device dlopen not yet accepted — named carrier step (bionic strictness). out: $out"; exit 2 ;;
esac
