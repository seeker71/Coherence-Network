#!/usr/bin/env bash
# form_asm_poly_pool_witness.sh — the EXECUTION WITNESS for fam-poly-pool: the Form-emitted Horner step
# p(x) = fma(x, 1/6, 1/120) (form-asm-poly-pool-band proves it four-way) doesn't just BYTE-MATCH the arm64
# oracle — it actually RUNS on this arm64 host with a SELF-CONTAINED CONSTANT POOL, no rustc/clang in the
# COMPUTE (clang is only the dumb dlopen harness).
#
# Sibling of form_asm_horner_witness.sh. fam-poly-pool is the FIRST literal constant pool on the native lane:
# where fam-horner2 folded VFP-immediate coefficients (2.0/3.0/4.0), the REAL coefficients every transcendental
# needs (1/6, 1/120, 1/5040 for sin; ln2, 1/2!, 1/3! for exp) are NOT VFP-modified-immediate-expressible — they
# must live in a pool the function carries itself, loaded position-independently via the new fa-ldr-d-lit
# (PC-relative LITERAL load). This proves a self-contained function — two real f64 appended after `ret`, loaded
# PC-relative, folded with fa-fmadd — runs bit-exact on hardware, the precondition for a real exp/sin/cos kernel.
#
# Path:
#   1. Form kernel emits fam-poly-pool's 4-instruction + 2-f64-pool (32-byte) arm64 image, then wraps it via
#      form-macho's mo-object-sym into a Mach-O .o exporting `_recipe`. The PC-relative ldr loads from the pool
#      INSIDE the same __text section — position-independent, no relocation.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts `_recipe` to the ABI  double recipe(double x)  (arm64 arg in d0,
#      result in d0 — exactly the recipe's register plan), and calls it with real scalars.
#   4. Assert recipe(x) == fma(x, 1.0/6.0, 1.0/120.0), bit-for-bit — the harness uses the SAME single fused
#      multiply-add the recipe folds (one rounding), reading the SAME pooled constants, so it is == not eps-close.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fpoolpool.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-poly-pool bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-poly-pool))
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
echo "fam-poly-pool image: $(( ${#hbytes} / 2 )) bytes — 16 code + 16 pool (no rustc/clang in this compute)"
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

# The dumb loader: dlopen, cast _recipe to the poly ABI, call with real scalars.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
typedef double (*h_fn)(double x);
static int check(h_fn h, const char *name, double x) {
    /* reference: the SAME single fused multiply-add over the SAME pooled coefficients — so == not eps-close */
    double expect = fma(x, 1.0/6.0, 1.0/120.0);
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
    all &= check(p, "0.0",   0.0);        /* p(0) = 1/120 = 0.00833... (the pooled bias alone) */
    all &= check(p, "1.0",   1.0);        /* p(1) = 1/6 + 1/120 = 0.175 */
    all &= check(p, "6.0",   6.0);        /* p(6) = 1 + 1/120 */
    all &= check(p, "-1.0", -1.0);        /* p(-1) = -1/6 + 1/120 */
    all &= check(p, "0.5",   0.5);        /* p(0.5) = 1/12 + 1/120 */
    all &= check(p, "1e8",   1e8);        /* fp stress: large * 1/6 -> big with tiny pooled tail */
    all &= check(p, "1e-8",  1e-8);       /* fp stress: small -> ~1/120 with tiny lead */
    all &= check(p, "3.14159265358979", 3.14159265358979); /* irrational fold over the pooled 1/6 */
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted Horner step fma(x, 1/6, 1/120) RUNS and MATCHES on $(uname -m)."
    echo "  fam-poly-pool's 32 bytes (16 code + a 16-byte SELF-CONTAINED f64 pool, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The first PC-relative literal pool on the witnessed lane; a function carries its OWN real (non-VFP) coefficients."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
