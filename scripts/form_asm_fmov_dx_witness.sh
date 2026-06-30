#!/usr/bin/env bash
# form_asm_fmov_dx_witness.sh — the EXECUTION WITNESS for fam-fmov-bits: the Form-emitted GP->FP bit
# reinterpret (form-asm-fmov-dx-band proves it four-way) doesn't just BYTE-MATCH the arm64 oracle — it
# actually RUNS the reinterpret on this arm64 host, no rustc/clang in the COMPUTE (clang is only the dumb
# dlopen harness).
#
# Sibling of form_asm_frintn_witness.sh. fa-fmov-d-x is the keystone the native 2^k/ldexp step needs — the
# LAST missing primitive of the exp lane. exp(x) = 2^k * Horner(r): fam-frintn gives k = round(x*log2e),
# fam-pool-fma gives r over pooled ln2/log2e, the Horner poly is on the lane. The only piece that could NOT
# be synthesized from existing bytes is BUILDING 2^k = REINTERPRET((k+1023)<<52). fa-scvtf converts the
# integer VALUE (wrong); fa-fmov-d-x preserves the BITS, so the assembled exponent field becomes the power
# of two. This witness proves that on real silicon: (1) raw bit patterns reinterpret bit-for-bit to the f64
# they encode, and (2) the actual 2^k construction (k+1023)<<52 -> recipe -> ldexp(1,k) holds for real k.
#
# Path:
#   1. Form kernel emits fam-fmov-bits' 2-instruction (8-byte) arm64 program, then wraps it via form-macho's
#      mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts `_recipe` to the ABI  double recipe(unsigned long bits)  (arm64
#      integer arg lands in x0, f64 result in d0 — exactly the recipe's register plan: fmov d0,x0; ret).
#   4. Assert recipe(bits) == the f64 those bits encode (memcpy reinterpret), bit-for-bit. The 2^k cases
#      additionally assert recipe((k+1023)<<52) == ldexp(1.0, k) — the exact next-stone use.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/ffmovdx.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-fmov-bits bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-fmov-bits))
    (print (str_concat "FNBYTES " (hxb code)))
    ; _recipe = 95 114 101 99 105 112 101 (the recipe-dylib export name)
    (print (str_concat "MACHO " (hxb (mo-object-sym code (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"

out="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null)"
fnbytes="$(echo "$out" | grep '^FNBYTES ' | sed 's/^FNBYTES //')"
hex="$(echo "$out" | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; cd "$FORM" && "$GO" "$work/emit.fk" 2>&1 | head; exit 1; }
echo "fam-fmov-bits program: $(( ${#fnbytes} / 2 )) bytes (no rustc/clang in this compute)"
echo "  arm64 bytes: $fnbytes"

echo "$hex" | xxd -r -p > "$work/recipe.o"
echo "Form-emitted Mach-O object: $(wc -c < "$work/recipe.o" | tr -d ' ') bytes, $(file "$work/recipe.o" | sed 's/^[^:]*: //')"
echo "  exported symbol: $(nm "$work/recipe.o" 2>/dev/null | tr -s ' ')"

# ld -dylib links + ad-hoc signs (no clang) — the recipe-dylib path.
SDK="$(xcrun --sdk macosx --show-sdk-path 2>/dev/null)"
ld -dylib -arch arm64 -platform_version macos 11.0 11.0 \
   -o "$work/recipe.dylib" "$work/recipe.o" -lSystem -L"$SDK/usr/lib" -syslibroot "$SDK" 2>/dev/null \
   || { echo "FAIL: ld -dylib"; exit 1; }
echo "ld -dylib + ad-hoc sign: $(codesign -dv "$work/recipe.dylib" 2>&1 | grep -E '^CodeDirectory' | sed 's/ hashes.*//')"
echo

# The dumb loader: dlopen, cast _recipe to the bit-reinterpret ABI, call with raw bit patterns AND the 2^k
# construction (k+1023)<<52 the native ldexp step will assemble.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdint.h>
#include <math.h>
typedef double (*fn_fn)(unsigned long bits);
static int check_bits(fn_fn fn, const char *name, unsigned long bits) {
    /* reference: the SAME bit reinterpret the recipe computes — so == not epsilon-close */
    double expect; __builtin_memcpy(&expect, &bits, 8);
    double got = fn(bits);
    int ok = (got == expect) || (expect != expect && got != got); /* NaN==NaN by bit identity */
    printf("EXEC bits 0x%016lx  got=%.17g expected=%.17g  %-6s %s\n", bits, got, expect, name, ok ? "MATCH" : "FAIL");
    return ok;
}
static int check_pow2(fn_fn fn, long k) {
    /* the EXACT native-ldexp use: 2^k = reinterpret((k+1023)<<52) */
    unsigned long bits = (unsigned long)(k + 1023) << 52;
    double got = fn(bits);
    double expect = ldexp(1.0, (int)k);   /* == 2^k */
    int ok = (got == expect);
    printf("EXEC 2^%-4ld (k+1023)<<52=0x%016lx  got=%.17g expected=%.17g  %s\n", k, bits, got, expect, ok ? "MATCH" : "FAIL");
    return ok;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    fn_fn fn = (fn_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!fn) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    /* raw bit patterns -> the f64 they encode */
    all &= check_bits(fn, "1.0",  0x3FF0000000000000UL);
    all &= check_bits(fn, "2.0",  0x4000000000000000UL);
    all &= check_bits(fn, "3.0",  0x4008000000000000UL);
    all &= check_bits(fn, "-2.0", 0xC000000000000000UL);
    all &= check_bits(fn, "1.5",  0x3FF8000000000000UL);
    all &= check_bits(fn, "0.0",  0x0000000000000000UL);
    all &= check_bits(fn, "inf",  0x7FF0000000000000UL);
    /* the keystone: the native 2^k/ldexp construction the exp lane needs */
    all &= check_pow2(fn, 0);     /* 2^0  = 1   */
    all &= check_pow2(fn, 5);     /* 2^5  = 32  */
    all &= check_pow2(fn, -3);    /* 2^-3 = 0.125 */
    all &= check_pow2(fn, 10);    /* 2^10 = 1024 */
    all &= check_pow2(fn, -10);   /* 2^-10 = small */
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted GP->FP bit reinterpret RUNS and MATCHES on $(uname -m)."
    echo "  fam-fmov-bits' 8 bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The 2^k cases prove the native ldexp construction: (k+1023)<<52 reinterprets to 2^k bit-for-bit;"
    echo "  with fam-frintn (k=round) + fam-pool-fma (r) + Horner already on the lane, the exp range-reduction"
    echo "  scaling is now sovereign native bytes. The last non-synthesizable primitive — moving raw bits"
    echo "  between the integer and f64 register files — is form-emitted and witnessed on real silicon."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
