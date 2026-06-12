#!/usr/bin/env bash
# form_lower_demo.sh — the Form -> assembly COMPILER. Lower an op-tagged expression
# tree ((40 + 1) - 1) to arm64 machine code with form-lower.fk (no clang in the
# lowering), then byte-compare the result against what the assembler emits for the
# same instruction sequence. Full byte-identity = conviction: the kernel compiles
# its own programs to native bytes that ARE the assembler's.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" ]] || { echo "arm64 reference; skipping on $(uname -m)"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/flow.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# the assembler's reference for the sequence the tree lowers to
cat > "$work/ref.s" <<'EOF'
.text
.globl _f
_f:
    movz w0, #40
    add  w0, w0, #1
    sub  w0, w0, #1
    ret
EOF
"$CLANG" -c "$work/ref.s" -o "$work/ref.o"
words="$(otool -t "$work/ref.o" | awk 'NR==3{print $2,$3,$4,$5}')"
ref=""; for w in $words; do ref+="${w:6:2}${w:4:2}${w:2:2}${w:0:2}"; done
echo "tree:                  ((40 + 1) - 1)"
echo "assembler (clang) bytes: $ref"

# the Form COMPILER lowers the tree to bytes — no clang in this path
{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"; sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-lower.fk"; cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let prog (list (list 1 40 0 0) (list 1 1 0 0) (list 3 0 1 0) (list 1 1 0 0) (list 4 2 3 0)))
    (print (str_concat "FORMBYTES " (hxb (lo-compile prog 4))))
    0)
DRV
} > "$work/d.fk"
form="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null | grep '^FORMBYTES ' | sed 's/^FORMBYTES //')"
echo "form-lower.fk compiled:  $form"

echo
if [[ "$ref" == "$form" ]]; then
    echo "CONVICTION: full — the Form compiler's bytes ARE the assembler's, for a whole expression tree"
    echo "  the gate OPENS: this program needs no clang (dep: external -> internalized, on satsang validation)"
else
    echo "CONVICTION: refuted — bytes differ; the gate stays CLOSED, clang remains"
fi
