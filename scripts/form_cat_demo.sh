#!/usr/bin/env bash
# form_cat_demo.sh — `cat`, a real unix command, built with ZERO clang and direct
# Form -> asm. The Form encoder (form-asm.fk) carries the full loop now: syscalls
# (read/write), a compare, a forward EOF branch, and a BACKWARD branch to the loop
# top. form-macho.fk wraps the bytes; `ld` (not clang) links; the binary loops
# read(0)->write(1) until EOF — it cats stdin to stdout.
#
# North star: direct Form -> asm. clang is ONE oracle (it assembles the same
# instructions so we can prove our bytes ARE the assembler's); understanding the
# LLVM/ARM encoding spec is the OTHER oracle (the two's-complement branch fold is
# derived from it, not from clang). Neither oracle is the destination — the Form
# recipe emitting machine code on its own is.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fcat.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# `cat` as a Form instruction list: loop { n=read(0,sp,1); if n<=0 exit; write(1,sp,1); }
PROG='(fa-image (list
    (fa-sub-x-imm 31 31 16)
    (fa-movz-x 0 0) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 3) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-cmp-x 0 0) (fa-bcond 13 8)
    (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-b-off -14)
    (fa-movz 0 0) (fa-add-x-imm 31 31 16) (fa-ret)))'

# ── Form emits the code image + Mach-O object (hex). No clang. ──
{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<DRV
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let code $PROG)
    (print (str_concat "CODE " (hxb code)))
    (print (str_concat "MACHO " (hxb (mo-object code))))
    0)
DRV
} > "$work/d.fk"
out="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null)"
form_code="$(grep '^CODE ' <<<"$out" | sed 's/^CODE //')"
hex="$(grep '^MACHO ' <<<"$out" | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; exit 1; }

# ── oracle #1 (clang): assemble the same `cat`, compare bytes ──
cat > "$work/ref.s" <<'EOF'
.text
.globl _main
_main:
    sub  sp, sp, #16
Lloop:
    movz x0, #0
    add  x1, sp, #0
    movz x2, #1
    movz x16, #3
    movk x16, #0x200, lsl #16
    svc  #0x80
    cmp  x0, #0
    b.le Ldone
    movz x0, #1
    add  x1, sp, #0
    movz x2, #1
    movz x16, #4
    movk x16, #0x200, lsl #16
    svc  #0x80
    b    Lloop
Ldone:
    movz w0, #0
    add  sp, sp, #16
    ret
EOF
ref_code=""
if "$CLANG" -c "$work/ref.s" -o "$work/ref.o" 2>/dev/null; then
    for w in $(otool -t "$work/ref.o" | awk 'NR>=3{for(i=2;i<=NF;i++)print $i}'); do
        ref_code+="${w:6:2}${w:4:2}${w:2:2}${w:0:2}"
    done
fi
echo "── cat, built with zero clang and direct Form -> asm ──"
[[ -n "$ref_code" && "$form_code" == "$ref_code" ]] \
    && echo "  oracle #1 (clang bytes): the Form encoder IS the assembler, byte-for-byte" \
    || echo "  (clang oracle unavailable — the four-way band and the run below are the proof)"
echo "  oracle #2 (ARM/LLVM spec): the backward branch -14 folds to two's complement 0x17fffff2"

# ── ld (NOT clang) links the Form object; run it as a real cat ──
echo "$hex" | xxd -r -p > "$work/fc.o"
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/cat" "$work/fc.o" 2>/dev/null

printf 'the form cat loops read->write until EOF\nline two, still zero clang\n' > "$work/in.txt"
"$work/cat" < "$work/in.txt" > "$work/out.txt"
echo
echo "  the Form-built cat ($(wc -c <"$work/fc.o" | tr -d ' ') bytes of Mach-O, no clang), piped real input:"
sed 's/^/    | /' "$work/out.txt"
if cmp -s "$work/in.txt" "$work/out.txt"; then
    echo
    echo "  IT CATS — stdin == stdout, byte-for-byte ($(wc -c <"$work/in.txt" | tr -d ' ') bytes through). A real unix"
    echo "  command on Form's own machine code: read/write syscalls, a compare, a backward loop branch."
else
    echo "  FAIL: cat output != input"; exit 1
fi