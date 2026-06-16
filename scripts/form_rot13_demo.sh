#!/usr/bin/env bash
# form_rot13_demo.sh — `rot13`, built with ZERO clang and direct Form -> asm, and
# the proof the encoder-as-table pays off: rot13 added NO new encoder recipe. Its
# branchless two-range rotation is sub/add/cmp/csel — instructions already in the
# table; rot13 is purely a longer data-row list. This RETIRES the C-emit byte-filter
# lane: its last unique reach was an arbitrary transform, now lifted to native asm.
#
# Oracle #1 (clang) assembles the same instructions to check the bytes; oracle #2
# is the ARM/LLVM encoding spec. The behavioral oracle is the system rot13
# (`tr A-Za-z N-ZA-Mn-za-m`) — and rot13 is its own inverse, so rot13∘rot13 = id.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/frot.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# `rot13` as a Form instruction list: cat loop + branchless two-range rotate-by-13.
PROG='(fa-image (list
    (fa-sub-x-imm 31 31 16)
    (fa-movz-x 0 0) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 3) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-cmp-x 0 0) (fa-bcond 13 26)
    (fa-ldrb 8 31 0)
    (fa-sub 9 8 65) (fa-add 10 9 13) (fa-sub 11 10 26) (fa-cmp 10 26) (fa-csel 10 11 10 2) (fa-add 10 10 65)
    (fa-sub 12 8 97) (fa-add 13 12 13) (fa-sub 14 13 26) (fa-cmp 13 26) (fa-csel 13 14 13 2) (fa-add 13 13 97)
    (fa-cmp 9 25) (fa-csel 8 10 8 9)
    (fa-cmp 12 25) (fa-csel 8 13 8 9)
    (fa-strb 8 31 0)
    (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-b-off -32)
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
echo "$hex" | xxd -r -p > "$work/r.o"
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/rot13" "$work/r.o" 2>/dev/null

IN='Hello, ROT13! Mixed CASE 123.'
got="$(printf '%s' "$IN" | "$work/rot13")"
want="$(printf '%s' "$IN" | tr 'A-Za-z' 'N-ZA-Mn-za-m')"
roundtrip="$(printf '%s' "$IN" | "$work/rot13" | "$work/rot13")"
echo "── rot13, built with zero clang and direct Form -> asm (no new encoder) ──"
echo "  in              : $IN"
echo "  Form-rot13 ($(wc -c <"$work/r.o" | tr -d ' ') byte Mach-O): $got"
echo "  system rot13    : $want"
echo "  round-trip (∘)  : $roundtrip"
if [[ "$got" == "$want" && "$roundtrip" == "$IN" ]]; then
    echo
    echo "  IT ROTATES — matches system rot13 byte-for-byte, and rot13∘rot13 = identity."
    echo "  A real shell command on Form's own bytes, added as DATA ROWS — no new encoder."
    echo "  The C-emit filter lane retires: every common filter now runs zero-clang."
else
    echo "  FAIL: Form-rot13 [$got] / round-trip [$roundtrip] vs system [$want]"; exit 1
fi