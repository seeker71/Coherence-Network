#!/usr/bin/env bash
# form_asm_frintn_witness.sh — the EXECUTION WITNESS for fam-frintn: the Form-emitted round-to-nearest
# (ties-to-even) of a double (form-asm-frintn-band proves it four-way) doesn't just BYTE-MATCH the arm64
# oracle — it actually RUNS roundeven(x) on this arm64 host, no rustc/clang in the COMPUTE (clang is only
# the dumb dlopen harness).
#
# Sibling of form_asm_rsqrt_witness.sh. fam-frintn is the RANGE-REDUCTION rounding floor the native exp lane
# needs: exp(x) reduces as k = round(x*log2e), r = x - k*ln2, then 2^k * Horner(r). The pooled-coefficient
# fma (fam-pool-fma, carrying ln2/log2e) is already on the lane; the k = round(...) step had no encoder.
# This adds the FIRST fa-frintn — ties-to-EVEN (frintn 1e644000), DISTINCT from frinta's ties-away — so the
# half-integer cases (0.5, 1.5, 2.5, -0.5) round the way exp range reduction wants.
#
# Path:
#   1. Form kernel emits fam-frintn's 2-instruction (8-byte) arm64 program, then wraps it via form-macho's
#      mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts `_recipe` to the ABI  double recipe(double x)  (arm64 arg lands
#      in d0, result in d0 — exactly the recipe's register plan), and calls it with real scalars.
#   4. Assert recipe(x) == __builtin_roundeven(x), bit-for-bit — the harness uses the SAME roundeven the
#      recipe folds (a single frintn d0,d0), so it is == not epsilon-close. The half-integer inputs PROVE
#      ties-to-even (0.5->0, 1.5->2, 2.5->2, -0.5->-0), distinguishing frintn from frinta's ties-away.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/ffrintn.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-frintn bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-frintn))
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
echo "fam-frintn program: $(( ${#fnbytes} / 2 )) bytes (no rustc/clang in this compute)"
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

# The dumb loader: dlopen, cast _recipe to the frintn ABI, call with real scalars (incl. half-integers).
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
typedef double (*fn_fn)(double x);
static int check(fn_fn fn, const char *name, double x) {
    /* reference: the SAME frintn (round half to EVEN) the recipe computes — so == not epsilon-close */
    double expect = __builtin_roundeven(x);
    double got = fn(x);
    int ok = (got == expect);
    printf("EXEC %-8s x=%-12g got=%.17g expected=%.17g %s\n", name, x, got, expect, ok ? "MATCH" : "FAIL");
    return ok;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    fn_fn fn = (fn_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!fn) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    all &= check(fn, "2.3",   2.3);        /* down to 2 */
    all &= check(fn, "2.7",   2.7);        /* up to 3 */
    all &= check(fn, "0.5",   0.5);        /* ties-to-even: -> 0, NOT 1 (frinta would give 1) */
    all &= check(fn, "1.5",   1.5);        /* ties-to-even: -> 2 */
    all &= check(fn, "2.5",   2.5);        /* ties-to-even: -> 2, NOT 3 */
    all &= check(fn, "-0.5",  -0.5);       /* ties-to-even: -> -0 */
    all &= check(fn, "-2.5",  -2.5);       /* ties-to-even: -> -2 */
    all &= check(fn, "1e8",   1e8);        /* fp stress: already integral, unchanged */
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted round-to-nearest-even (roundeven) RUNS and MATCHES on $(uname -m)."
    echo "  fam-frintn's 8 bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The range-reduction rounding floor (k = round(x*log2e) for exp/softmax) is sovereign native bytes;"
    echo "  first fa-frintn (ties-to-even) on the lane — half-integers prove it (0.5->0, 2.5->2), not frinta's ties-away."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
