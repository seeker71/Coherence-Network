#!/usr/bin/env bash
# form_asm_rsqrt_witness.sh — the EXECUTION WITNESS for fam-rsqrt: the Form-emitted reciprocal-sqrt
# 1/sqrt(x) (form-asm-rsqrt-band proves it four-way) doesn't just BYTE-MATCH the arm64 oracle — it
# actually RUNS 1/sqrt(x) on this arm64 host, no rustc/clang in the COMPUTE (clang is only the dumb
# dlopen harness).
#
# Sibling of form_asm_ss_sqrt_witness.sh. fam-rsqrt is the NEXT nonlinear rung on the native lane after
# fam-ss-sqrt: where ss-sqrt ENDED in fsqrt, this one closes the transcendental in a RECIPROCAL — the
# RMSNorm/RoPE/SwiGLU normalizer core (RMSNorm scale = g/sqrt(mean(x^2)+eps); RoPE inv-freq =
# 1/base^(2i/d)). It introduces the FIRST float constant on the lane (fa-fmov-imm #1.0) and the FIRST
# fa-fdiv (a reciprocal division), the primitives every later nonlinear op needs.
#
# Path:
#   1. Form kernel emits fam-rsqrt's 4-instruction (16-byte) arm64 program, then wraps it via
#      form-macho's mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts `_recipe` to the ABI  double recipe(double x)  (arm64 arg lands
#      in d0, result in d0 — exactly the recipe's register plan), and calls it with real scalars.
#   4. Assert recipe(x) == 1.0/sqrt(x), bit-for-bit — the harness uses the SAME fsqrt then 1.0/y the
#      recipe folds (fsqrt d0,d0 ; fdiv d0,d1,d0 with d1=1.0), so it is == not epsilon-close.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/frsqrt.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-rsqrt bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-rsqrt))
    (print (str_concat "RSBYTES " (hxb code)))
    ; _recipe = 95 114 101 99 105 112 101 (the recipe-dylib export name)
    (print (str_concat "MACHO " (hxb (mo-object-sym code (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"

out="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null)"
rsbytes="$(echo "$out" | grep '^RSBYTES ' | sed 's/^RSBYTES //')"
hex="$(echo "$out" | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; cd "$FORM" && "$GO" "$work/emit.fk" 2>&1 | head; exit 1; }
echo "fam-rsqrt program: $(( ${#rsbytes} / 2 )) bytes (no rustc/clang in this compute)"
echo "  arm64 bytes: $rsbytes"

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

# The dumb loader: dlopen, cast _recipe to the rsqrt ABI, call with real scalars.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
typedef double (*rs_fn)(double x);
static int check(rs_fn rs, const char *name, double x) {
    /* reference: the SAME fsqrt then 1.0/y the recipe computes — so == not epsilon-close */
    double expect = 1.0 / sqrt(x);
    double got = rs(x);
    int ok = (got == expect);
    printf("EXEC %-8s x=%-12g got=%.17g expected=%.17g %s\n", name, x, got, expect, ok ? "MATCH" : "FAIL");
    return ok;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    rs_fn rs = (rs_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!rs) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    all &= check(rs, "4.0",   4.0);       /* 0.5, the classic */
    all &= check(rs, "1.0",   1.0);       /* 1.0 */
    all &= check(rs, "0.25",  0.25);      /* 2.0 */
    all &= check(rs, "100.0", 100.0);     /* 0.1 */
    all &= check(rs, "2.0",   2.0);       /* irrational 1/sqrt(2) — full mantissa */
    all &= check(rs, "1e8",   1e8);       /* fp stress: large */
    all &= check(rs, "1e-8",  1e-8);      /* fp stress: small -> 10000 */
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" -lm || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted rsqrt (1/sqrt(x)) RUNS and MATCHES on $(uname -m)."
    echo "  fam-rsqrt's 16 bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The RMSNorm/RoPE/SwiGLU normalizer core is sovereign native bytes; first fmov-imm + fdiv on the lane."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
