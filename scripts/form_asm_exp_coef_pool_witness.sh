#!/usr/bin/env bash
# form_asm_exp_coef_pool_witness.sh — the EXECUTION WITNESS for fam-pool-fma carrying REAL transcendental
# coefficients. The coefficient-parameterized constant-pool emitter (form-asm-exp-coef-pool-band proves it
# four-way) fills its pool by computing the 8 IEEE754 bytes from the VALUES via f64-bytes — so the pool can
# carry ANY constant, not just the repeating-nibble ones a hand-pattern can write. Here it carries ln2 and
# log2e — the two constants exp's range reduction uses (x = n*ln2 + r, n = round(x*log2e)). This proves the
# self-contained, computed-pool image RUNS bit-exact on this arm64 host, no rustc/clang in the COMPUTE.
#
# Sibling of form_asm_poly_pool_witness.sh. The ONLY change from poly-pool's image is the POOL CONTENTS (the
# code path ldr/fmadd/ret is already witnessed in poly-pool); the new ground is that f64-bytes computed those
# pool bytes from irregular-mantissa transcendental constants, and they load+fold correctly on the metal.
#
# Path:
#   1. Form kernel emits fam-pool-fma's 4-instruction + 2-f64-pool (32-byte) arm64 image (the pool COMPUTED by
#      f64-bytes from ln2, log2e), then wraps it via form-macho's mo-object-sym into a Mach-O .o exporting _recipe.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts _recipe to  double recipe(double x), and calls it with real scalars.
#   4. Assert recipe(x) == fma(x, ln2, log2e), bit-for-bit — the harness uses the SAME single fused multiply-add
#      reading the SAME pooled doubles, so it is == not eps-close.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fexppool.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-pool-fma(ln2, log2e) bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
# fam-pool-fma calls f64-bytes (needs format-arith + f64-bytes, deps-first) to compute the pool from the values.
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
    (let code (fam-pool-fma 0.6931471805599453 1.4426950408889634))
    (print (str_concat "HBYTES " (hxb code)))
    ; _recipe = 95 114 101 99 105 112 101 (the recipe-dylib export name)
    (print (str_concat "MACHO " (hxb (mo-object-sym code (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"

out="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null)"
hbytes="$(echo "$out" | grep '^HBYTES ' | sed 's/^HBYTES //')"
hex="$(echo "$out" | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; cd "$FORM" && "$GO" "$work/emit.fk" 2>&1 | head; exit 1; }
echo "fam-pool-fma(ln2,log2e) image: $(( ${#hbytes} / 2 )) bytes — 16 code + 16 COMPUTED pool (no rustc/clang in this compute)"
echo "  arm64 bytes: $hbytes"

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

# The dumb loader: dlopen, cast _recipe to the recipe ABI, call with real scalars.
# The reference uses the EXACT doubles the pool carries (bit-identical to f64-bytes' encoding), one fma -> == not eps.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <math.h>
typedef double (*h_fn)(double x);
static const double LN2   = 0.6931471805599453;
static const double LOG2E = 1.4426950408889634;
static int check(h_fn h, const char *name, double x) {
    double expect = fma(x, LN2, LOG2E);
    double got = h(x);
    int ok = (got == expect);
    printf("EXEC %-8s x=%-12g got=%.17g expected=%.17g %s\n", name, x, got, expect, ok ? "MATCH" : "FAIL");
    return ok;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    h_fn p = (h_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!p) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    all &= check(p, "0.0",   0.0);        /* p(0) = log2e (the pooled bias alone) */
    all &= check(p, "1.0",   1.0);        /* p(1) = ln2 + log2e */
    all &= check(p, "2.0",   2.0);        /* p(2) = 2*ln2 + log2e */
    all &= check(p, "-1.0", -1.0);        /* p(-1) = -ln2 + log2e */
    all &= check(p, "0.5",   0.5);        /* p(0.5) = ln2/2 + log2e */
    all &= check(p, "1e8",   1e8);        /* fp stress: large * ln2 with tiny pooled tail */
    all &= check(p, "1e-8",  1e-8);       /* fp stress: small -> ~log2e with tiny lead */
    all &= check(p, "3.14159265358979", 3.14159265358979); /* irrational fold over the pooled ln2 */
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted Horner step fma(x, ln2, log2e) RUNS and MATCHES on $(uname -m)."
    echo "  fam-pool-fma's 32 bytes (16 code + a 16-byte COMPUTED f64 pool, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The pool's transcendental coefficients were COMPUTED from the values by f64-bytes — any constant, not just hand patterns."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
