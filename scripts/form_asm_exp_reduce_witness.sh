#!/usr/bin/env bash
# form_asm_exp_reduce_witness.sh — the EXECUTION WITNESS for fam-exp-reduce: exp's argument RANGE REDUCTION
# x -> r = x - round(x*log2e)*ln2 (form-asm-exp-reduce-band proves it four-way) doesn't just BYTE-MATCH the
# arm64 clang oracle — it actually RUNS the reduction on this arm64 host, no rustc/clang in the COMPUTE (clang
# is only the dumb dlopen harness + the == reference).
#
# Sibling of form_asm_frintn_witness.sh / form_asm_rsqrt_witness.sh. fam-exp-reduce is the FIRST COMPOSED
# transcendental step on the native asm lane: every prior brick was a single primitive ending in ret; this
# chains a MATERIALIZED constant (fa-mov-imm64 + fa-fmov-d-x, the way clang -O2 inlines an f64 without a pool)
# + fmul + frintn (round-to-nearest-even, ties the way exp wants) + fmadd into a real function. exp(x) =
# 2^k * exp(r) where k = round(x*log2e) and r in [-ln2/2, ln2/2]; this emits the k-and-r half, the precondition
# of the exp/softmax lane.
#
# Path:
#   1. Form kernel emits fam-exp-reduce's 14-instruction (56-byte) arm64 program, then wraps it via form-macho's
#      mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts `_recipe` to the ABI  double recipe(double x)  (arm64 arg lands in d0,
#      result in d0 — exactly the recipe's register plan), and calls it with real scalars.
#   4. Assert recipe(x) == fma(roundeven(x*log2e), -ln2, x), bit-for-bit — the harness computes the reduction
#      with the SAME fmul/roundeven/fma the recipe folds, so it is == not epsilon-close. It also checks the
#      reduction INVARIANT |r| <= ln2/2 (the interval a short Horner exp poly converges over).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fexpred.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-exp-reduce bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  echo '    (defn nil? (xs) (eq (len xs) 0))'
  cat "$FORM/form-stdlib/format-arith.fk"
  cat "$FORM/form-stdlib/f64-bytes.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-exp-reduce))
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
echo "fam-exp-reduce program: $(( ${#fnbytes} / 2 )) bytes (no rustc/clang in this compute)"
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

# The dumb loader: dlopen, cast _recipe to the reduction ABI, call with real scalars.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
typedef double (*fn_fn)(double x);
static const double LOG2E =  0x1.71547652b82fep0;   /* 1.4426950408889634  */
static const double LN2   =  0x1.62e42fefa39efp-1;  /* 0.6931471805599453  */
static int check(fn_fn fn, double x) {
    /* reference: the SAME fmul/roundeven/fma the recipe folds — so == not epsilon-close */
    double k = __builtin_roundeven(x * LOG2E);
    double expect = __builtin_fma(k, -LN2, x);   /* x - k*ln2 = r */
    double got = fn(x);
    int ok = (got == expect);
    /* the reduction invariant: |r| <= ln2/2 (exp's Horner poly converges over this interval) */
    int inrange = (got <= LN2/2.0 + 1e-15) && (got >= -LN2/2.0 - 1e-15);
    printf("EXEC x=%-14g k=%-6g r=%.17g expected=%.17g %s %s\n",
           x, k, got, expect, ok ? "MATCH" : "FAIL", inrange ? "|r|<=ln2/2" : "OUT-OF-RANGE!");
    return ok && inrange;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    fn_fn fn = (fn_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!fn) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    all &= check(fn, 0.0);                       /* k=0, r=0 */
    all &= check(fn, 0.6931471805599453);        /* x=ln2 -> x*log2e=1, k=1, r=0 */
    all &= check(fn, 1.0);                        /* k=1, r=1-ln2 */
    all &= check(fn, 0.5);                        /* k=round(0.72)=1 (ties-to-even edge), r=0.5-ln2 */
    all &= check(fn, 2.0);                        /* k=3, r=2-3*ln2 (negative r) */
    all &= check(fn, 10.0);                       /* k=14 */
    all &= check(fn, -1.0);                       /* negative x, k=-1 */
    all &= check(fn, 88.0);                       /* near float exp() overflow, large k */
    all &= check(fn, -87.0);                      /* near float exp() underflow */
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted exp range-reduction RUNS and MATCHES on $(uname -m)."
    echo "  fam-exp-reduce's 56 bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  x -> r = x - round(x*log2e)*ln2 is sovereign native bytes: the k-and-r half of exp(x)=2^k*exp(r),"
    echo "  first COMPOSED transcendental step on the lane (materialized constants + fmul + frintn + fmadd),"
    echo "  every r in [-ln2/2, ln2/2] — the interval the Horner exp poly (already on the lane) converges over."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
