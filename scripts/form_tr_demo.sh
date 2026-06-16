#!/usr/bin/env bash
# form_tr_demo.sh — `tr A-Z a-z`, a real unix command, built with ZERO clang and
# direct Form -> asm. tr is the zero-clang cat plus a BRANCHLESS per-byte transform:
# ldrb the byte, compute (unsigned)(c-65)<=25 ? c+32 : c with cmp + csel, strb it
# back, then write. form-macho.fk wraps the bytes; `ld` (not clang) links; the
# binary lowercases stdin -> stdout through the OS read/write syscalls.
#
# This is the move that RETIRES the clang filter lane (#3256): the shell commands
# now run on Form's own machine code. clang is ONE oracle (it assembles the same
# instructions so we can prove our bytes ARE the assembler's) and the ARM/LLVM
# encoding spec is the OTHER; the destination is the Form recipe emitting code.
# The system `tr A-Z a-z` is the behavioral oracle: same output, byte-for-byte.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/ftr.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# `tr A-Z a-z` as a Form instruction list: cat loop + branchless lowercase transform.
PROG='(fa-image (list
    (fa-sub-x-imm 31 31 16)
    (fa-movz-x 0 0) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 3) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-cmp-x 0 0) (fa-bcond 13 14)
    (fa-ldrb 8 31 0) (fa-sub 9 8 65) (fa-add 10 8 32) (fa-cmp 9 25) (fa-csel 8 10 8 9) (fa-strb 8 31 0)
    (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-b-off -20)
    (fa-movz 0 0) (fa-add-x-imm 31 31 16) (fa-ret)))'

{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<DRV
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (print (str_concat "MACHO " (hxb (mo-object $PROG))))
    0)
DRV
} > "$work/d.fk"
hex="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; exit 1; }

echo "$hex" | xxd -r -p > "$work/ft.o"
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/tr" "$work/ft.o" 2>/dev/null

IN='Hello, ZERO-Clang TR! Mixed CASE 123.'
got="$(printf '%s' "$IN" | "$work/tr")"
want="$(printf '%s' "$IN" | tr 'A-Z' 'a-z')"
echo "── tr A-Z a-z, built with zero clang and direct Form -> asm ──"
echo "  in            : $IN"
echo "  Form-tr (no clang, $(wc -c <"$work/ft.o" | tr -d ' ') byte Mach-O): $got"
echo "  system tr     : $want"
if [[ "$got" == "$want" ]]; then
    echo
    echo "  IT LOWERCASES — the Form-built tr matches the system \`tr A-Z a-z\` byte-for-byte."
    echo "  A real shell command on Form's own machine code: read/write syscalls, a backward loop,"
    echo "  and a branchless transform (ldrb + cmp + csel). The clang filter lane retires."
else
    echo "  FAIL: Form-tr [$got] != system tr [$want]"; exit 1
fi