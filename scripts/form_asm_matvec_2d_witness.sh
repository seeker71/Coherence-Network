#!/usr/bin/env bash
# form_asm_matvec_2d_witness.sh — the EXECUTION WITNESS for fam-matvec: the Form-emitted
# FULL 2-D matvec (the outer row loop, form-asm-matvec-2d-band proves it four-way) doesn't
# just BYTE-MATCH the arm64 oracle — it actually RUNS a real m×n matvec on this arm64 host.
#
# This is the sibling of form_asm_matvec_witness.sh (which witnessed the single fam-dot2 dot).
# fam-matvec is what every later forward-pass stage needs: y = W·x for a whole weight matrix,
# one native program, no rustc/clang in the COMPUTE (clang is only the dumb dlopen harness).
#
# Path:
#   1. Form kernel emits fam-matvec's 23-instruction (92-byte) arm64 program, then wraps it
#      via form-macho's mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path).
#   3. A tiny C harness dlopens it, casts `_recipe` to the matvec ABI
#         void recipe(const double *W, const double *x, long n, long m, double *y)
#      (arm64 args land in x0=W x1=x x2=n x3=m x4=y — exactly the recipe's register plan), and
#      calls it with real row-major W, vector x, output y.
#   4. Assert every y[i] == sum_j W[i][j]*x[j], bit-for-bit (the recipe folds the SAME upward
#      order as bj-dot-fam, the tree-walker twin — so == not epsilon-close).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fmatvec2d.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-matvec bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-matvec))
    (print (str_concat "MVBYTES " (hxb code)))
    ; _recipe = 95 114 101 99 105 112 101 (the recipe-dylib export name)
    (print (str_concat "MACHO " (hxb (mo-object-sym code (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"

out="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null)"
mvbytes="$(echo "$out" | grep '^MVBYTES ' | sed 's/^MVBYTES //')"
hex="$(echo "$out" | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; cd "$FORM" && "$GO" "$work/emit.fk" 2>&1 | head; exit 1; }
echo "fam-matvec program: $(( ${#mvbytes} / 2 )) bytes (no rustc/clang in this compute)"
echo "  arm64 bytes: $mvbytes"

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

# The dumb loader: dlopen, cast _recipe to the matvec ABI, call with real m×n W / n-vector x.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
typedef void (*mv_fn)(const double *W, const double *x, long n, long m, double *y);
static int check(mv_fn mv, const char *name, const double *W, const double *x,
                 long n, long m, const double *expect) {
    double *y = calloc(m, sizeof(double));
    mv(W, x, n, m, y);
    int ok = 1;
    for (long i = 0; i < m; i++) if (y[i] != expect[i]) ok = 0;
    printf("EXEC %-10s m=%ld n=%ld  y=[", name, m, n);
    for (long i = 0; i < m; i++) printf("%s%.17g", i ? "," : "", y[i]);
    printf("] expected=[");
    for (long i = 0; i < m; i++) printf("%s%.17g", i ? "," : "", expect[i]);
    printf("] %s\n", ok ? "MATCH" : "FAIL");
    free(y);
    return ok;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    mv_fn mv = (mv_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!mv) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    /* 3x2: rows dotted with x=[4,0.5] */
    { double W[] = {2,3, 5,7, 1,1}; double x[] = {4,0.5};
      double e[] = {2*4+3*0.5, 5*4+7*0.5, 1*4+1*0.5};   /* [9.5,23.5,4.5] */
      all &= check(mv, "3x2", W, x, 2, 3, e); }
    /* 1x4: a single wide row (the output-projection shape in miniature) */
    { double W[] = {1,2,3,4}; double x[] = {1,1,1,1}; double e[] = {10};
      all &= check(mv, "1x4", W, x, 4, 1, e); }
    /* 4x4 identity: y must equal x */
    { double W[] = {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1};
      double x[] = {3,-1,2.5,7}; double e[] = {3,-1,2.5,7};
      all &= check(mv, "I4", W, x, 4, 4, e); }
    /* 2x3 with negatives + the large/small pair that stresses fp */
    { double W[] = {1e8,1e-8,0, 0,-2,0.5}; double x[] = {1e-8,1e8,9};
      double e[] = {1e8*1e-8 + 1e-8*1e8 + 0*9, 0*1e-8 + (-2)*1e8 + 0.5*9};
      all &= check(mv, "2x3", W, x, 3, 2, e); }
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted 2-D matvec RUNS and MATCHES on $(uname -m)."
    echo "  fam-matvec's 92 bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The native y = W·x IS the recipe's result, bit-for-bit. The matvec lane is whole:"
    echo "  the dominant compute of a transformer forward pass now runs as sovereign native bytes."
else
    echo "WITNESS FAILED: a matvec did not match (rc=$rc) — the emitted bytes do not compute y=W·x."
    exit 1
fi
