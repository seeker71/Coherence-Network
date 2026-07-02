#!/usr/bin/env bash
# form_asm_exp_poly_witness.sh — the EXECUTION WITNESS for fam-exp-poly: the Form-emitted degree-6 Horner
# evaluator of exp(r) (form-asm-exp-poly-band proves it four-way) doesn't just BYTE-MATCH the arm64 oracle —
# it RUNS on this arm64 host with a SELF-CONTAINED 7-entry constant pool, no rustc/clang in the COMPUTE
# (clang is only the dumb dlopen harness + the reference).
#
# Sibling of form_asm_poly_pool_witness.sh. fam-horner-list is the core-lift: fam-pool-fma proved a SINGLE
# pooled fma (degree 1); this generalizes to ANY degree in one engine (coefficients as a list), and fam-exp-poly
# is its exp instance — the polynomial exp(r), r in [-ln2/2, ln2/2], that composes with fam-exp-reduce (r) and
# fam-pow2 (2^k) into the full native exp = 2^k * exp(r). Two proofs on hardware:
#   A. BIT-EXACT vs the SAME degree-6 Horner in C (identical fma order over the identical pooled coefficients)
#      — so == not eps-close, proving the recipe computes exactly what its bytes say.
#   B. within ~1.3e-7 of libm exp() for r across the reduced interval [-ln2/2, ln2/2] — proving the polynomial
#      IS a faithful exp(r) approximation there (the interval fam-exp-reduce guarantees).
#
# Path: Form kernel emits fam-exp-poly's 112-byte image (56 code + a 56-byte 7-f64 pool) -> form-macho .o
# exporting _recipe -> ld -dylib + ad-hoc sign (recipe-dylib path, no clang) -> dlopen + call double recipe(double).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fexppoly.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-exp-poly bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  cat "$FORM/form-stdlib/format-arith.fk"
  cat "$FORM/form-stdlib/f64-bytes.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-exp-poly))
    (print (str_concat "HBYTES " (hxb code)))
    (print (str_concat "MACHO " (hxb (mo-object-sym code (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"

out="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null)"
hbytes="$(echo "$out" | grep '^HBYTES ' | sed 's/^HBYTES //')"
hex="$(echo "$out" | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; cd "$FORM" && "$GO" "$work/emit.fk" 2>&1 | head; exit 1; }
echo "fam-exp-poly image: $(( ${#hbytes} / 2 )) bytes — 56 code + a 56-byte 7-f64 pool (no rustc/clang in this compute)"

echo "$hex" | xxd -r -p > "$work/recipe.o"
echo "Form-emitted Mach-O object: $(wc -c < "$work/recipe.o" | tr -d ' ') bytes, $(file "$work/recipe.o" | sed 's/^[^:]*: //')"

SDK="$(xcrun --sdk macosx --show-sdk-path 2>/dev/null)"
ld -dylib -arch arm64 -platform_version macos 11.0 11.0 \
   -o "$work/recipe.dylib" "$work/recipe.o" -lSystem -L"$SDK/usr/lib" -syslibroot "$SDK" 2>/dev/null \
   || { echo "FAIL: ld -dylib"; exit 1; }
echo "ld -dylib + ad-hoc sign: $(codesign -dv "$work/recipe.dylib" 2>&1 | grep -E '^CodeDirectory' | sed 's/ hashes.*//')"
echo

cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <math.h>
typedef double (*h_fn)(double x);
/* the SAME degree-6 Horner, identical fma order over the identical pooled coefficients -> bit-exact */
static double horner(double x){
    double p = 1.0/720.0;
    p = fma(p, x, 1.0/120.0);
    p = fma(p, x, 1.0/24.0);
    p = fma(p, x, 1.0/6.0);
    p = fma(p, x, 1.0/2.0);
    p = fma(p, x, 1.0);
    p = fma(p, x, 1.0);
    return p;
}
static int check_exact(h_fn h, double x){
    double got = h(x), expect = horner(x);
    int ok = (got == expect);
    printf("EXACT  x=%-14g got=%.17g expected=%.17g %s\n", x, got, expect, ok?"MATCH":"FAIL");
    return ok;
}
static int check_exp(h_fn h, double r){
    double got = h(r), ref = exp(r), err = fabs(got - ref);
    int ok = (err < 1.3e-7);              /* r in [-ln2/2, ln2/2] => |r^7/7!| < ~1.2e-7 */
    printf("APPROX r=%-14g poly=%.12g exp=%.12g |err|=%.3e %s\n", r, got, ref, err, ok?"OK":"FAIL");
    return ok;
}
int main(int argc, char **argv){
    void *h = dlopen(argv[1], RTLD_NOW);
    if(!h){ fprintf(stderr,"dlopen fail: %s\n", dlerror()); return 2; }
    h_fn p = (h_fn)dlsym(h, "recipe");
    if(!p){ fprintf(stderr,"dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    /* A. bit-exact vs the same C Horner, incl fp stress */
    all &= check_exact(p, 0.0);
    all &= check_exact(p, 0.25);
    all &= check_exact(p, -0.3);
    all &= check_exact(p, 1e8);
    all &= check_exact(p, 3.14159265358979);
    /* B. faithful exp(r) approximation across the reduced interval [-ln2/2, ln2/2] ~ [-0.3466, 0.3466] */
    double L = 0.34657359027997264; /* ln2/2 */
    all &= check_exp(p, 0.0);
    all &= check_exp(p,  L);
    all &= check_exp(p, -L);
    all &= check_exp(p,  L*0.5);
    all &= check_exp(p, -L*0.5);
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted degree-6 exp(r) Horner RUNS and MATCHES on $(uname -m)."
    echo "  fam-exp-poly's 112 bytes (fam-horner-list over a 7-f64 pool, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  Bit-exact vs the same C Horner; within ~1.3e-7 of libm exp across [-ln2/2, ln2/2] — the exp(r) core of native exp."
else
    echo "WITNESS FAIL (rc=$rc)."
fi
exit $rc
