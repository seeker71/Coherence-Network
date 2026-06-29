#!/usr/bin/env bash
# form_asm_ss_sqrt_witness.sh — the EXECUTION WITNESS for fam-ss-sqrt: the Form-emitted RMSNorm/LayerNorm
# reduction core (form-asm-ss-sqrt-band proves it four-way) doesn't just BYTE-MATCH the arm64 oracle — it
# actually RUNS sqrt(sum_j x[j]^2) on this arm64 host, no rustc/clang in the COMPUTE (clang is only the
# dumb dlopen harness).
#
# This is the sibling of form_asm_matvec_2d_witness.sh. fam-ss-sqrt is the first NONLINEAR op on the
# native lane (the gap form-native-models.form names: exp/sin/cos/rsqrt for softmax/RoPE/RMSNorm/SwiGLU
# as asm) — a counted accumulate loop that ENDS in fsqrt, the L2 norm = sqrt(n)*RMS that every
# normalization layer needs.
#
# Path:
#   1. Form kernel emits fam-ss-sqrt's 13-instruction (52-byte) arm64 program, then wraps it via
#      form-macho's mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts `_recipe` to the ABI  double recipe(const double *x, long n)
#      (arm64 args land in x0=x x1=n, result in d0 — exactly the recipe's register plan), and calls it
#      with real vectors.
#   4. Assert recipe(x,n) == sqrt(sum_j x[j]^2), bit-for-bit — the harness accumulates the SAME upward
#      order (j=0..n-1) the recipe folds, then sqrt, so it is == not epsilon-close.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fsssqrt.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-ss-sqrt bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-ss-sqrt))
    (print (str_concat "SSBYTES " (hxb code)))
    ; _recipe = 95 114 101 99 105 112 101 (the recipe-dylib export name)
    (print (str_concat "MACHO " (hxb (mo-object-sym code (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"

out="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null)"
ssbytes="$(echo "$out" | grep '^SSBYTES ' | sed 's/^SSBYTES //')"
hex="$(echo "$out" | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; cd "$FORM" && "$GO" "$work/emit.fk" 2>&1 | head; exit 1; }
echo "fam-ss-sqrt program: $(( ${#ssbytes} / 2 )) bytes (no rustc/clang in this compute)"
echo "  arm64 bytes: $ssbytes"

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

# The dumb loader: dlopen, cast _recipe to the ss-sqrt ABI, call with real n-vectors.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
typedef double (*ss_fn)(const double *x, long n);
static int check(ss_fn ss, const char *name, const double *x, long n) {
    /* reference: SAME upward fold (j=0..n-1) the recipe uses, then sqrt — so == not epsilon-close */
    double acc = 0.0;
    for (long j = 0; j < n; j++) acc += x[j] * x[j];
    double expect = sqrt(acc);
    double got = ss(x, n);
    int ok = (got == expect);
    printf("EXEC %-10s n=%ld  got=%.17g expected=%.17g %s\n", name, n, got, expect, ok ? "MATCH" : "FAIL");
    return ok;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    ss_fn ss = (ss_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!ss) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    { double x[] = {3,4};            all &= check(ss, "3-4",   x, 2); }   /* 5.0, the classic */
    { double x[] = {1,1,1,1};        all &= check(ss, "ones4", x, 4); }   /* 2.0 */
    { double x[] = {0,0,0};          all &= check(ss, "zeros", x, 3); }   /* 0.0, empty-ish acc */
    { double x[] = {-2,0.5,1e8,1e-8};all &= check(ss, "mixed", x, 4); }   /* fp stress: large+small+neg */
    { double x[] = {0.1,0.2,0.3,0.4,0.5,0.6}; all &= check(ss, "rms6", x, 6); }
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted ss-sqrt (sqrt(sum x^2)) RUNS and MATCHES on $(uname -m)."
    echo "  fam-ss-sqrt's 52 bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The first nonlinear reduction (the RMSNorm/LayerNorm denominator-root) is sovereign native bytes."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
