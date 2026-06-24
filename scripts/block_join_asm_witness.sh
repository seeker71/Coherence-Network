#!/usr/bin/env bash
# block_join_asm_witness.sh — gap D₃ execution witness: fam-dot2 RUNS on REAL loaded weights
# from the block-join mini-GGUF fixture and MATCHES the Form join dot (bj-dot-row-n n=2).
#
# Composes gap B (form_asm_matvec_witness.sh) with gap D (block-join loaded weights).
# Skips on non-arm64-macOS hosts (same as gap B).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS witness; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld; skipping"; exit 0; }
command -v clang >/dev/null || { echo "need clang for harness; skipping"; exit 0; }

work="$(mktemp -d "${TMPDIR:-/tmp}/bjasm.XXXXXX")"; trap 'rm -rf "$work"' EXIT

SNIP="form-stdlib/tests/block-join-asm-witness-snippet.fk"
raw="$(cd "$FORM" && ./validate.sh form-stdlib/core.fk form-stdlib/format-arith.fk form-stdlib/f16-decode.fk \
    form-stdlib/gguf-read.fk form-stdlib/q6k-dequant.fk form-stdlib/weight-load.fk \
    form-stdlib/transformer-block.fk form-stdlib/block-join.fk "$SNIP" 2>&1)"
parsed="$(python3 - "$raw" <<'PY'
import re, sys
out = sys.argv[1]
m = re.search(r'witness-snippet\.fk\s*→\s*([^\n]+)\n((?:-?\d[\d.]*\n)+)', out)
if not m:
    sys.exit(1)
nums = [m.group(1).strip()] + re.findall(r'^(-?\d[\d.]*)', m.group(2), re.M)
print("\n".join(nums[:5]))
PY
)" || { echo "FAIL: Form join dot parse"; echo "$raw" | tail -8; exit 1; }
w0="$(echo "$parsed" | sed -n '1p')"
w1="$(echo "$parsed" | sed -n '2p')"
x0="$(echo "$parsed" | sed -n '3p')"
x1="$(echo "$parsed" | sed -n '4p')"
expect="$(echo "$parsed" | sed -n '5p')"
echo "loaded w=[$w0,$w1] x=[$x0,$x1] bj-dot-row-n n=2 -> $expect"

MATVEC="$FORM/form-stdlib/form-asm-matvec.fk"
{ echo "(do"
  echo '    (defn append (xs ys) (if (nil? xs) ys (cons (head xs) (append (tail xs) ys))))'
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$MATVEC"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (print (str_concat "MACHO " (hxb (mo-object-sym (fam-dot2) (list 95 114 101 99 105 112 101)))))
    0)
DRV
} > "$work/emit.fk"
hex="$(cd "$FORM" && "$GO" "$work/emit.fk" 2>/dev/null | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: no Mach-O"; exit 1; }
echo "$hex" | xxd -r -p > "$work/recipe.o"
SDK="$(xcrun --sdk macosx --show-sdk-path 2>/dev/null)"
ld -dylib -arch arm64 -platform_version macos 11.0 11.0 \
   -o "$work/recipe.dylib" "$work/recipe.o" -lSystem -L"$SDK/usr/lib" -syslibroot "$SDK" 2>/dev/null \
   || { echo "FAIL: ld -dylib"; exit 1; }

cat > "$work/harness.c" <<'EOF'
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
typedef double (*dot_fn)(const double *);
int main(int argc, char **argv) {
    void *h = dlopen(argv[1], RTLD_NOW);
    if (!h) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 2; }
    dot_fn dot = (dot_fn)dlsym(h, "recipe");
    if (!dot) { fprintf(stderr, "dlsym: %s\n", dlerror()); return 3; }
    double buf[4] __attribute__((aligned(16)));
    buf[0] = atof(argv[2]); buf[1] = atof(argv[3]);
    buf[2] = atof(argv[4]); buf[3] = atof(argv[5]);
    double got = dot(buf);
    printf("%.17g\n", got);
    return 0;
}
EOF
clang -o "$work/harness" "$work/harness.c" || exit 1
got="$("$work/harness" "$work/recipe.dylib" "$w0" "$w1" "$x0" "$x1")"
echo "fam-dot2 EXEC on loaded weights -> $got"

python3 - "$got" "$expect" <<'PY'
import sys
g, e = float(sys.argv[1]), float(sys.argv[2])
if g == e:
    print("WITNESS: fam-dot2 on loaded llama3.2:3b Q6_K weights MATCHES bj-dot-row-n n=2, bit-for-bit.")
    sys.exit(0)
print(f"WITNESS FAILED: got={g!r} expect={e!r}")
sys.exit(1)
PY
