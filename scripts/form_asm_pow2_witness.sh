#!/usr/bin/env bash
# form_asm_pow2_witness.sh — the EXECUTION WITNESS for fam-pow2: the Form-emitted 2^k / ldexp(1,k) step
# (form-asm-pow2-band proves it four-way) doesn't just BYTE-MATCH the arm64 words — it actually RUNS the
# exponent assembly on this arm64 host, no rustc/clang in the COMPUTE (clang is only the dumb dlopen harness).
#
# Sibling of form_asm_max_loop_witness.sh. fam-pow2 is the exponent-ASSEMBLY step the native exp lane lacked:
# exp(x) = 2^k * exp(r) with k = round(x*log2e) and r the pooled range reduction; BUILDING 2^k is the piece
# that had no path. An IEEE754 f64 with biased exponent field (k+1023) and zero mantissa IS exactly 2^k, so
# fam-pow2 biases k (fa-add-x-imm), shifts it into the exponent bits (the new fa-lsl-x-imm, <<52), and
# reinterprets the raw bits as an f64 (fa-fmov-d-x — NOT fa-scvtf, which would give k's VALUE as a float).
#
# Path:
#   1. Form kernel emits fam-pow2's 4-instruction (16-byte) arm64 program, then wraps it via form-macho's
#      mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts `_recipe` to the ABI  double recipe(long k)  (arm64 arg0 -> x0 = k,
#      result in d0 — exactly the recipe's register plan), and calls it with real exponents.
#   4. Assert recipe(k) == ldexp(1.0, k) == 2^k, bit-for-bit, across the normal-double exponent range.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fpow2.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-pow2 bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-pow2))
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
echo "fam-pow2 program: $(( ${#fnbytes} / 2 )) bytes (no rustc/clang in this compute)"
echo "  arm64 bytes: $fnbytes"

echo "$hex" | xxd -r -p > "$work/recipe.o"
echo "Form-emitted Mach-O object: $(wc -c < "$work/recipe.o" | tr -d ' ') bytes, $(file "$work/recipe.o" | sed 's/^[^:]*: //')"
echo "  exported symbol: $(nm "$work/recipe.o" 2>/dev/null | tr -s ' ')"
# The arm64 assembler IS the byte oracle: confirm the emitted words disassemble to the sequence (oracle-as-teacher).
echo "  disassembly (otool — the assembler confirms the words):"
otool -tvVj "$work/recipe.o" 2>/dev/null | grep -E 'add|lsl|fmov|ret' | sed 's/^/    /'

# ld -dylib links + ad-hoc signs (no clang) — the recipe-dylib path.
SDK="$(xcrun --sdk macosx --show-sdk-path 2>/dev/null)"
ld -dylib -arch arm64 -platform_version macos 11.0 11.0 \
   -o "$work/recipe.dylib" "$work/recipe.o" -lSystem -L"$SDK/usr/lib" -syslibroot "$SDK" 2>/dev/null \
   || { echo "FAIL: ld -dylib"; exit 1; }
echo "ld -dylib + ad-hoc sign: $(codesign -dv "$work/recipe.dylib" 2>&1 | grep -E '^CodeDirectory' | sed 's/ hashes.*//')"
echo

# The dumb loader: dlopen, cast _recipe to the pow2 ABI, call with real exponents.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <math.h>
typedef double (*fn_fn)(long k);
static int check(fn_fn fn, long k) {
    double expect = ldexp(1.0, k);   /* = 2^k, the libm reference */
    double got = fn(k);
    int ok = (got == expect);
    printf("EXEC 2^%-5ld got=%.17g expected=%.17g %s\n", k, got, expect, ok ? "MATCH" : "FAIL");
    return ok;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    fn_fn fn = (fn_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!fn) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    long ks[] = {0, 1, 5, 10, -1, -3, -10, 52, 127, -126, 1023, -1022};  /* incl. the normal-double boundaries */
    for (unsigned i = 0; i < sizeof(ks)/sizeof(ks[0]); i++) all &= check(fn, ks[i]);
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted 2^k exponent assembly RUNS and MATCHES on $(uname -m)."
    echo "  fam-pow2's 16 bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The last exp-lane primitive is sovereign native bytes: bias + <<52 shift + bit-reinterpret ="
    echo "  ldexp(1,k), the 2^k scaling every exp/softmax/gelu multiplies its Horner(r) by."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
