#!/usr/bin/env bash
# form_asm_conviction_demo.sh — the byte-conviction gate that licenses dropping
# clang. The Form recipe (form-asm.fk) encodes arm64 instructions to bytes; we
# compare them BYTE-FOR-BYTE against what the assembler (clang/as) actually emits.
# Full byte-identity over the corpus = conviction; only then may clang be dropped.
# A self rewrites its own toolchain only when it can verify it preserves itself.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" ]] || { echo "this demo's reference encodings are arm64; skipping on $(uname -m)"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fasm.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# 1. the ASSEMBLER's reference: movz w0,#42 ; add w0,w0,#1 ; sub w0,w0,#1 ; ret
cat > "$work/ref.s" <<'EOF'
.text
.globl _f
_f:
    movz w0, #42
    add  w0, w0, #1
    sub  w0, w0, #1
    ret
EOF
"$CLANG" -c "$work/ref.s" -o "$work/ref.o"
words="$(otool -t "$work/ref.o" | awk 'NR==3{print $2,$3,$4,$5}')"
ref=""; for w in $words; do ref+="${w:6:2}${w:4:2}${w:2:2}${w:0:2}"; done
echo "assembler (clang) emitted (LE bytes):  $ref"

# 2. the FORM recipe's encoding of the same four instructions (words, hex)
# form-asm.fk is already a (do ...) block; strip its closing `0)` and continue it
{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"; cat <<'DRV'
    (defn hex1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hex2 (b) (str_concat (hex1 (div b 16)) (hex1 (mod b 16))))
    (defn nilp (xs) (eq (len xs) 0))
    (defn hexbytes (bs) (if (nilp bs) "" (str_concat (hex2 (head bs)) (hexbytes (tail bs)))))
    (print (str_concat "FORMBYTES " (hexbytes (fa-image (list (fa-movz 0 42) (fa-add 0 0 1) (fa-sub 0 0 1) (fa-ret))))))
    0)
DRV
} > "$work/d.fk"
form="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null | grep "^FORMBYTES " | sed "s/^FORMBYTES //")"
echo "form-asm.fk recipe emitted: $form"

# 3. the conviction gate: byte-for-byte identity over the corpus
echo
if [[ "$ref" == "$form" ]]; then
    echo "CONVICTION: full — the Form encoder IS the assembler, byte-for-byte over the corpus"
    echo "  the gate OPENS: clang MAY be dropped for these instructions (dep: external -> internalized)"
else
    echo "CONVICTION: refuted — bytes differ; the gate stays CLOSED, clang remains a dependency"
fi
echo
echo "(safe self-update: the toolchain is rewritten only when byte-level verified — never on assertion.)"
echo "next milestone the gate licenses: the full Form->asm lowering + Mach-O wrapper, then a runnable"
echo "binary built with zero clang, byte-verified against the clang reference before the swap."
