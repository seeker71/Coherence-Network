#!/usr/bin/env bash
# form_asm_max_loop_witness.sh — the EXECUTION WITNESS for fam-max-loop: the Form-emitted max-reduction
# max_j x[j] over a buffer (form-asm-max-loop-band proves it four-way) doesn't just BYTE-MATCH the arm64
# words — it actually RUNS the reduction on this arm64 host, no rustc/clang in the COMPUTE (clang is only
# the dumb dlopen harness).
#
# Sibling of form_asm_relu_witness.sh. fam-max-loop is the HEADLINE consumer of fa-fmax (#3937): fam-relu
# proved fa-fmax scalar, this folds it across a whole buffer — exactly stable softmax's max-subtract
# (softmax(x)_i = exp(x_i - m)/sum_j exp(x_j - m) with m = max_j x[j], so the largest exponent is 0 and exp
# never overflows). Every attention block runs this reduction before its softmax. It is fam-ss-sqrt's exact
# loop twin, with the square-and-add fold replaced by a single fa-fmax and the accumulator init'd to x[0]
# (ldr d0,[x0] — the max identity for n>=1, since 0.0 would be wrong for all-negative logits).
#
# Path:
#   1. Form kernel emits fam-max-loop's 10-instruction (40-byte) arm64 program, then wraps it via form-macho's
#      mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the recipe-dylib path, no clang).
#   3. A tiny C harness dlopens it, casts `_recipe` to the ABI  double recipe(const double *x, long n)  (arm64
#      arg0 -> x0 = buffer base, arg1 -> x1/w1 = n, result in d0 — exactly the recipe's register plan), and
#      calls it with real buffers.
#   4. Assert recipe(x, n) == max_j x[j], bit-for-bit — fa-fmax computes the exact max for every finite input.
#      All-negative, mixed, single-element, and a large buffer are checked.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fmaxloop.XXXXXX")"; trap 'rm -rf "$work"' EXIT

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
[[ -f "$MATVEC" ]] || { echo "FAIL: form-asm-matvec.fk not found"; exit 1; }

# Form: emit fam-max-loop bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-max-loop))
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
echo "fam-max-loop program: $(( ${#fnbytes} / 2 )) bytes (no rustc/clang in this compute)"
echo "  arm64 bytes: $fnbytes"

echo "$hex" | xxd -r -p > "$work/recipe.o"
echo "Form-emitted Mach-O object: $(wc -c < "$work/recipe.o" | tr -d ' ') bytes, $(file "$work/recipe.o" | sed 's/^[^:]*: //')"
echo "  exported symbol: $(nm "$work/recipe.o" 2>/dev/null | tr -s ' ')"
# The arm64 assembler IS the byte oracle: confirm the emitted words disassemble to the loop (oracle-as-teacher).
echo "  disassembly (otool — the assembler confirms the words):"
otool -tvVj "$work/recipe.o" 2>/dev/null | grep -E 'ldr|mov|cmp|b\.ge|fmax|add|ret|\bb\b' | sed 's/^/    /'

# ld -dylib links + ad-hoc signs (no clang) — the recipe-dylib path.
SDK="$(xcrun --sdk macosx --show-sdk-path 2>/dev/null)"
ld -dylib -arch arm64 -platform_version macos 11.0 11.0 \
   -o "$work/recipe.dylib" "$work/recipe.o" -lSystem -L"$SDK/usr/lib" -syslibroot "$SDK" 2>/dev/null \
   || { echo "FAIL: ld -dylib"; exit 1; }
echo "ld -dylib + ad-hoc sign: $(codesign -dv "$work/recipe.dylib" 2>&1 | grep -E '^CodeDirectory' | sed 's/ hashes.*//')"
echo

# The dumb loader: dlopen, cast _recipe to the max-loop ABI, call with real buffers.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
typedef double (*fn_fn)(const double *x, long n);
static double ref_max(const double *x, long n) { double m = x[0]; for (long i = 1; i < n; i++) if (x[i] > m) m = x[i]; return m; }
static int check(fn_fn fn, const char *name, const double *x, long n) {
    double expect = ref_max(x, n);
    double got = fn(x, n);
    int ok = (got == expect);
    printf("EXEC %-14s n=%-3ld got=%.17g expected=%.17g %s\n", name, n, got, expect, ok ? "MATCH" : "FAIL");
    return ok;
}
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    fn_fn fn = (fn_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!fn) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    int all = 1;
    double a[] = {3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0};        /* max in the middle */
    double b[] = {-2.0, -7.0, -3.0, -0.5};                        /* ALL negative — 0.0 init would be wrong */
    double c[] = {8.0, 2.0, 5.0, 1.0};                            /* max is the first element (init) */
    double d[] = {-1.0, 2.0, -3.0, 4.0, -5.0};                    /* mixed signs */
    double e[] = {42.5};                                          /* single element (n=1) */
    double f[1000]; for (int i = 0; i < 1000; i++) f[i] = -(double)i * 0.001; f[737] = 314.159;  /* large buffer, peak at 737 */
    all &= check(fn, "1..9",        a, 8);
    all &= check(fn, "all-negative", b, 4);
    all &= check(fn, "peak-first",  c, 4);
    all &= check(fn, "mixed",       d, 5);
    all &= check(fn, "single",      e, 1);
    all &= check(fn, "large-1000",  f, 1000);
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted max_j x[j] reduction RUNS and MATCHES on $(uname -m)."
    echo "  fam-max-loop's 40 bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The headline fa-fmax consumer is sovereign native bytes: this is stable-softmax's max-subtract,"
    echo "  the numerically-critical reduction every attention block runs before its softmax."
else
    echo "WITNESS FAIL (rc=$rc): the emitted program did not match the reference."
fi
exit $rc
