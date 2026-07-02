#!/usr/bin/env bash
# form_asm_fam_tanh_witness.sh — the EXECUTION WITNESS for fam-tanh: tanh(x) = (e^{2x}-1)/(e^{2x}+1)
# END-TO-END as Form->asm bytes (form-asm-fam-tanh-band proves it four-way) doesn't just BYTE-MATCH the arm64
# oracle — it RUNS on this arm64 host and computes tanh(x), no rustc/clang in the COMPUTE (clang is only the
# dumb dlopen harness + reference). tanh completes the sigmoid family on the native lane and is the prerequisite
# for a native gelu-tanh (whisper's/GPT's activation).
#
# fam-tanh reuses fam-exp's whole exp(x) (range-reduce + 2^k + degree-6 exp(r) Horner + multiply), feeding it 2x,
# then wraps it in the rational tanh (e^{2x}-1)/(e^{2x}+1) — the e^{2x} form so no negate is needed. It is the
# first activation to exercise real subtraction (fa-fsub) end-to-end on hardware.
# Two proofs on hardware:
#   A. BIT-EXACT vs a C mirror of the EXACT algorithm (the identical exp mirror on 2x, then (e2x-1)/(e2x+1))
#      — so == not eps-close: the recipe computes what its bytes say.
#   B. within ~2e-7 RELATIVE of libm tanh across a moderate range of x — proving fam-tanh IS a faithful tanh.
#      (Large |x| where e^{2x} overflows in this form saturates to +/-1 and is a named follow-up; activations
#      are moderate.)
#
# Path: Form kernel emits fam-tanh's 208-byte image (38 code words incl. the alignment nop + a 56-byte 7-f64
# pool) -> form-macho .o exporting _recipe -> ld -dylib + ad-hoc sign (recipe-dylib path, no clang) ->
# dlopen + call double recipe(double).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/ftanhw.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-tanh bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
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
    (let code (fam-tanh))
    (print (str_concat "HBYTES " (hxb code)))
    (print (str_concat "MACHO " (hxb (mo-object-sym code (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"

out="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null)"
hbytes="$(echo "$out" | grep '^HBYTES ' | sed 's/^HBYTES //')"
hex="$(echo "$out" | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; cd "$FORM" && "$GO" "$work/emit.fk" 2>&1 | head; exit 1; }
echo "fam-tanh image: $(( ${#hbytes} / 2 )) bytes — 38 code words (incl. alignment nop) + a 56-byte 7-f64 pool (no rustc/clang in this compute)"

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
#include <stdint.h>
typedef double (*h_fn)(double x);
/* the SAME exp algorithm fam-exp/fam-tanh emit: roundeven range-reduce, (k+1023)<<52 reinterpret, the
   identical degree-6 fma Horner over the identical pooled coefficients, final multiply. */
static double mexp(double x){
    double kf = __builtin_roundeven(x * 0x1.71547652b82fep0);   /* log2e */
    int64_t ki = (int64_t)kf;
    double r  = __builtin_fma(kf, -0x1.62e42fefa39efp-1, x);
    union { uint64_t u; double d; } v; v.u = ((uint64_t)(ki + 1023)) << 52;
    double pk = v.d;
    double p = 1.0/720.0;
    p = __builtin_fma(p, r, 1.0/120.0);
    p = __builtin_fma(p, r, 1.0/24.0);
    p = __builtin_fma(p, r, 1.0/6.0);
    p = __builtin_fma(p, r, 1.0/2.0);
    p = __builtin_fma(p, r, 1.0);
    p = __builtin_fma(p, r, 1.0);
    return p * pk;
}
/* tanh mirror: (e^{2x}-1)/(e^{2x}+1) — the exact instruction sequence fam-tanh emits (exp on 2x, then rational). */
static double mirror(double x){ double e2 = mexp(2.0*x); return (e2 - 1.0) / (e2 + 1.0); }
static int check_exact(h_fn h, double x){
    double got = h(x), expect = mirror(x);
    int ok = (got == expect);
    printf("EXACT  x=%-12g got=%.17g expected=%.17g %s\n", x, got, expect, ok?"MATCH":"FAIL");
    return ok;
}
static int check_tanh(h_fn h, double x){
    double got = h(x), ref = tanh(x);                 /* libm tanh */
    double rel = fabs(got - ref) / (fabs(ref) + 1e-300);
    int ok = (rel < 2e-7);
    printf("APPROX x=%-12g fam-tanh=%.12g tanh=%.12g rel=%.3e %s\n", x, got, ref, rel, ok?"OK":"FAIL");
    return ok;
}
int main(int argc, char **argv){
    void *h = dlopen(argv[1], RTLD_NOW);
    if(!h){ fprintf(stderr,"dlopen fail: %s\n", dlerror()); return 2; }
    h_fn p = (h_fn)dlsym(h, "recipe");
    if(!p){ fprintf(stderr,"dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    /* A. bit-exact vs the C mirror of the exact algorithm */
    all &= check_exact(p, 0.0);
    all &= check_exact(p, 1.0);
    all &= check_exact(p, -1.0);
    all &= check_exact(p, 2.5);
    all &= check_exact(p, -3.7);
    all &= check_exact(p, 0.6931471805599453);
    /* B. faithful tanh across a moderate range (the interval activations live in) */
    all &= check_tanh(p, 0.0);
    all &= check_tanh(p, 0.5);
    all &= check_tanh(p, 1.0);
    all &= check_tanh(p, -1.0);
    all &= check_tanh(p, 2.0);
    all &= check_tanh(p, -2.0);
    all &= check_tanh(p, 3.0);
    all &= check_tanh(p, -3.0);
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted tanh(x) RUNS and MATCHES on $(uname -m)."
    echo "  fam-tanh's 208 bytes (exp(2x) via fam-exp's body + (e^{2x}-1)/(e^{2x}+1), four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  Bit-exact vs the C mirror of the exact algorithm; within ~2e-7 relative of libm tanh across the activation range."
else
    echo "WITNESS FAIL (rc=$rc)."
fi
exit $rc
