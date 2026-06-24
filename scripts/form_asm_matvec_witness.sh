#!/usr/bin/env bash
# form_asm_matvec_witness.sh — the EXECUTION WITNESS for fam-dot2: the Form-emitted
# matvec inner product doesn't just BYTE-MATCH the clang oracle (form-asm-matvec-band
# proves that four-way), it actually RUNS correctly on this arm64 host.
#
# Path, zero rustc/clang in the COMPUTE (clang here is only the dumb loader-harness
# carrier, like form/native/bootstrap/form_bootstrap_host.c — the bytes it calls are
# Form's):
#   1. Form kernel emits fam-dot2's 8-instruction (32-byte) arm64 program, then wraps
#      it via form-macho's mo-object-sym into a Mach-O .o exporting `_recipe`.
#   2. `ld -dylib` links + ad-hoc signs the .o into a dlopen-able dylib (the macOS
#      arm64 signing requirement; the same linker the recipe-dylib path already uses).
#   3. A tiny C harness dlopens the dylib, casts `_recipe` to `double(*)(const double*)`,
#      and calls it with real 16-byte-aligned f64 buffers [a0,a1,b0,b1].
#   4. Assert the returned double == a0*b0 + a1*b1, bit-for-bit (the recipe folds the
#      SAME downward order as transformer-block's tb-dot, so == not epsilon-close).
#
# ABI NOTE (the crux): the Go kernel's `dylib_call` native is `int64 recipe(int64)`
# (the bootstrap-host ABI) and CANNOT pass a float-pointer or receive a double. But the
# form-macho/recipe-dylib WRAP is ABI-agnostic — mo-object-sym exports the raw bytes at
# `_recipe`; the CALLER'S cast fixes the C signature. So the float-pointer signature
# needs no change to the wrap path, only a caller that casts to double(*)(const double*).
# That caller is this C harness — the documented "dumb loader" witness carrier.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for the loader harness; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fmatvec.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# The matvec recipe lives at form/form-stdlib/form-asm-matvec.fk. If this checkout's
# branch predates it, read it from the commit that shipped it.
MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
if [[ ! -f "$MATVEC" ]]; then
    if git -C "$ROOT" cat-file -e 245b0c8f0:form/form-stdlib/form-asm-matvec.fk 2>/dev/null; then
        git -C "$ROOT" show 245b0c8f0:form/form-stdlib/form-asm-matvec.fk > "$work/form-asm-matvec.fk"
        MATVEC="$work/form-asm-matvec.fk"
    else
        echo "FAIL: form-asm-matvec.fk not found in tree or commit 245b0c8f0"; exit 1
    fi
fi

# Form: emit fam-dot2 bytes, wrap as a Mach-O .o exporting _recipe (mo-object-sym), hex.
# `append` is core.fk's recipe (BML dialect, source-compiled in validate); we inline the
# identical recipe here so this witness is self-contained — it does NOT touch fam-dot2's
# bytes. The wrap chain is exactly form_macho_demo.sh / recipe-dylib-band.fk.
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code (fam-dot2))
    (print (str_concat "DOTBYTES " (hxb code)))
    ; _recipe = 95 114 101 99 105 112 101 (the recipe-dylib export name)
    (print (str_concat "MACHO " (hxb (mo-object-sym code (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"

out="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null)"
dotbytes="$(echo "$out" | grep '^DOTBYTES ' | sed 's/^DOTBYTES //')"
hex="$(echo "$out" | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; cd "$FORM" && "$GO" "$work/emit.fk" 2>&1 | head; exit 1; }
echo "fam-dot2 program: $(( ${#dotbytes} / 2 )) bytes (no rustc/clang in this compute)"
echo "  arm64 bytes: $dotbytes"

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

# The dumb loader: dlopen, cast _recipe to double(*)(const double*), call with real f64s.
cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
typedef double (*dot_fn)(const double *);
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen fail: %s\n", dlerror()); return 2; }
    dot_fn dot = (dot_fn)dlsym(h, "recipe");      /* leading _ stripped by dlsym */
    if (!dot) { fprintf(stderr, "dlsym fail: %s\n", dlerror()); return 3; }
    struct { double a0,a1,b0,b1, expect; } c[] = {  /* buf layout a0@0 a1@8 b0@16 b1@24 */
        {2.0, 3.0, 5.0, 7.0, 2.0*5.0 + 3.0*7.0},        /* 31.0 */
        {1.5,-2.0, 4.0, 0.5, 1.5*4.0 + (-2.0)*0.5},     /* 5.0  */
        {0.0, 0.0, 9.0, 9.0, 0.0},                      /* 0.0  */
        {1e8, 1e-8, 1e-8, 1e8, 1e8*1e-8 + 1e-8*1e8},    /* 2.0  */
    };
    int n = sizeof(c)/sizeof(c[0]), all = 1;
    for (int i = 0; i < n; i++) {
        double buf[4] __attribute__((aligned(16)));   /* 16-byte aligned f64s */
        buf[0]=c[i].a0; buf[1]=c[i].a1; buf[2]=c[i].b0; buf[3]=c[i].b1;
        double got = dot(buf);
        int m = (got == c[i].expect); if (!m) all = 0;
        printf("EXEC: [%g,%g,%g,%g] dot=%.17g expected=%.17g %s\n",
               c[i].a0, c[i].a1, c[i].b0, c[i].b1, got, c[i].expect, m ? "MATCH" : "FAIL");
    }
    dlclose(h);
    return all ? 0 : 1;
}
EOF
clang -o "$work/harness" "$work/harness.c" || { echo "FAIL: harness build"; exit 1; }

"$work/harness" "$work/recipe.dylib"; rc=$?
echo
if [[ "$rc" == "0" ]]; then
    echo "WITNESS: the Form-emitted matvec dot RUNS and MATCHES on $(uname -m)."
    echo "  fam-dot2's bytes (form-asm, four-way) -> form-macho .o -> ld -dylib -> dlopen+call."
    echo "  The native result IS the recipe's result, bit-for-bit. Gap B of the inference arc: closed."
else
    echo "WITNESS FAILED: a vector did not match (rc=$rc) — the emitted bytes do not compute the dot."
    exit 1
fi
