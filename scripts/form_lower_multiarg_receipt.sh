#!/usr/bin/env bash
# form_lower_multiarg_receipt.sh — the physical on-device receipt for the N-ARG native
# lane: a Form recipe ((a*b)+c) is LOWERED by form-lower to an arm64 byte body (AAPCS64:
# args in w0,w1,w2; result in w0), wrapped by elf-so-body into a LOADABLE aarch64 ELF .so
# (ZERO clang — Form is compiler, assembler, AND linker for the .so), which the Android
# dynamic linker dlopen's on a real device, and whose exported form_native(a,b,c) runs as
# native code returning a*b+c. The script also evaluates the SAME recipe through the Form
# interpreter and asserts native == interpreter for the same args — one recipe, two carriers.
#
# The only clang here is the NDK building the tiny dlopen HARNESS (a test rig); never the
# .so. Skips cleanly (exit 0) when no NDK or no adb device is present; the four-way byte +
# interpreter==native-intent proof is tests/form-lower-multiarg-band.fk (127). This is the
# runtime half — the form-lower -> elf-so-body -> dlopen native-JIT-on-ARM lane, on a phone.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"
KERNEL="$FORM/form-kernel-rust/target/release/form-kernel-rust"
[[ -x "$KERNEL" ]] || KERNEL="$FORM/form-kernel-rust/target/debug/form-kernel-rust"
[[ -x "$KERNEL" ]] || { echo "no form-kernel-rust binary; skipping"; exit 0; }

DEV="$(adb devices 2>/dev/null | awk 'NR>1 && $2=="device"{print $1; exit}')"
[[ -n "$DEV" ]] || { echo "no adb device attached; skipping (byte proof is form-lower-multiarg-band 127)"; exit 0; }
NDK="${ANDROID_NDK_HOME:-$(ls -d /opt/homebrew/Caskroom/android-ndk/*/AndroidNDK*.app/Contents/NDK 2>/dev/null | head -1)}"
CC="$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/aarch64-linux-android*-clang 2>/dev/null | sort -V | tail -1)"
[[ -x "$CC" ]] || { echo "no NDK aarch64 clang for the harness; skipping"; exit 0; }

work="$(mktemp -d "${TMPDIR:-/tmp}/flma.XXXXXX")"; trap 'rm -rf "$work"' EXIT
A="${1:-7}"; B="${2:-6}"; C="${3:-5}"

# Form lowers the recipe, wraps the .so, AND walks the interpreter — one engine.
# Merge form-asm + form-lower + form-elf-so module bodies into one (do ...) (their
# own (do/0) wrappers stripped) so the recipe sees every defn it needs.
asm_body="$(sed '1,/^(do$/d' "$FORM/form-stdlib/form-asm.fk" | sed '$ d')"
low_body="$(sed '1,/^(do$/d' "$FORM/form-stdlib/form-lower.fk" | sed '$ d')"
so_body="$(sed '1,/^(do$/d' "$FORM/form-stdlib/form-elf-so.fk" | sed '$ d')"
{
  echo "(do"
  echo "$asm_body"
  echo "$low_body"
  echo "$so_body"
  cat <<DRV
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    ; the recipe ((a*b)+c) as an op-tagged tree; ARG slot 1 = argument index
    (defn me-row (prog i) (nth prog i))
    (defn me-tag (prog i) (nth (me-row prog i) 0))
    (defn me-eval (prog i args)
        (if (eq (me-tag prog i) 1) (nth (me-row prog i) 1)
        (if (eq (me-tag prog i) 2) (nth args (nth (me-row prog i) 1))
        (if (eq (me-tag prog i) 5) (mul (me-eval prog (nth (me-row prog i) 1) args) (me-eval prog (nth (me-row prog i) 2) args))
        (if (eq (me-tag prog i) 3) (add (me-eval prog (nth (me-row prog i) 1) args) (me-eval prog (nth (me-row prog i) 2) args))
            0)))))
    (let prog (list (list 2 0 0 0) (list 2 1 0 0) (list 5 0 1 0) (list 2 2 0 0) (list 3 2 3 0)))
    (let body (lo-compile-fn-n prog 4 3))
    (print (str_concat "INTERP " (hxb (list (me-eval prog 4 (list $A $B $C))))))
    (print (str_concat "ELFSO " (hxb (elf-so-body body))))
    0)
DRV
} > "$work/emit.fk"
emit="$(cd "$FORM" && "$KERNEL" "$work/emit.fk" 2>/dev/null)"
hex="$(echo "$emit" | grep '^ELFSO ' | sed 's/^ELFSO //')"
interp_hex="$(echo "$emit" | grep '^INTERP ' | sed 's/^INTERP //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no .so"; exit 1; }
INTERP=$((16#$interp_hex))
echo "$hex" | xxd -r -p > "$work/form_native.so"
echo "Form-emitted ELF .so: $(wc -c < "$work/form_native.so" | tr -d ' ') bytes (ZERO clang) — recipe ((a*b)+c)"
file "$work/form_native.so" | sed 's/^[^:]*: /  /'
echo "Form interpreter walk:  form_native($A,$B,$C) = $INTERP"

# The dlopen harness — NDK clang builds the RIG, not the .so. It calls form_native(a,b,c).
cat > "$work/harness.c" <<'C'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
typedef long (*fn)(long, long, long);
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { printf("DLOPEN_FAIL %s\n", dlerror()); return 10; }
    fn f = (fn)dlsym(h, "form_native");
    if (!f) { printf("DLSYM_FAIL %s\n", dlerror()); return 11; }
    long a = atol(argv[2]), b = atol(argv[3]), c = atol(argv[4]);
    printf("RESULT %ld\n", f(a, b, c));
    return 0;
}
C
"$CC" -o "$work/harness" "$work/harness.c" || { echo "FAIL: harness build"; exit 1; }

D=/data/local/tmp/form-lower-multiarg-receipt
adb -s "$DEV" shell "mkdir -p $D" >/dev/null 2>&1
adb -s "$DEV" push "$work/form_native.so" "$D/form_native.so" >/dev/null 2>&1
adb -s "$DEV" push "$work/harness" "$D/harness" >/dev/null 2>&1
adb -s "$DEV" shell "chmod 755 $D/harness" >/dev/null 2>&1
echo
echo "running on device $DEV — dlopen the Form-emitted .so, call form_native($A,$B,$C) (expect $INTERP):"
out="$(adb -s "$DEV" shell "cd $D && ./harness ./form_native.so $A $B $C" 2>&1 | tr -d '\r')"
echo "  $out"
adb -s "$DEV" shell "rm -rf $D" >/dev/null 2>&1
case "$out" in
  "RESULT $INTERP")
    echo
    echo "ON-DEVICE NATIVE, ZERO CLANG (.so): a Form recipe ((a*b)+c) was LOWERED to arm64"
    echo "bytes, wrapped into a loadable aarch64 ELF .so; the Android linker dlopen'd it and"
    echo "its exported native form_native($A,$B,$C) ran on the phone, returning $INTERP — equal"
    echo "to the SAME recipe walked by the Form interpreter. The native-JIT-on-ARM lane carries"
    echo "a real multi-arg recipe, end to end." ;;
  *) echo; echo "device dlopen/call did not match the interpreter — named carrier step. out: $out (interp=$INTERP)"; exit 2 ;;
esac
