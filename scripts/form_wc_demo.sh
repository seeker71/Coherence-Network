#!/usr/bin/env bash
# form_wc_demo.sh — `wc -l`, built with ZERO clang and direct Form -> asm. It closes
# the read-number / print-number symmetry: head atoi'd a count IN; wc counts
# newlines and itoa's the count OUT. itoa adds NO new encoder — udiv/mul/sub/mov
# register forms already in the table. The output format is read FROM the real BSD
# `wc -l` (count right-justified in an 8-char space-padded field + newline, 9 bytes),
# not invented — the recipe fills 8 spaces, writes the digits backward into the
# field's right edge, and writes all 9 bytes at once. Oracle: /usr/bin/wc -l.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fwc.XXXXXX")"; trap 'rm -rf "$work"' EXIT

PROG='(fa-image (list
    (fa-sub-x-imm 31 31 32) (fa-movz 19 0)
    (fa-movz-x 0 0) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1) (fa-movz-x 16 3) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-cmp-x 0 0) (fa-bcond 13 6)
    (fa-ldrb 8 31 0) (fa-cmp 8 10) (fa-bcond 1 -10) (fa-add 19 19 1) (fa-b-off -12)
    (fa-add-x-imm 10 31 8) (fa-movz 8 32)
    (fa-strb 8 10 0) (fa-strb 8 10 1) (fa-strb 8 10 2) (fa-strb 8 10 3)
    (fa-strb 8 10 4) (fa-strb 8 10 5) (fa-strb 8 10 6) (fa-strb 8 10 7)
    (fa-movz 8 10) (fa-strb 8 10 8)
    (fa-add-x-imm 9 10 8) (fa-movz 20 10)
    (fa-udiv 11 19 20) (fa-mul 12 11 20) (fa-sub-r 13 19 12) (fa-add 13 13 48)
    (fa-sub-x-imm 9 9 1) (fa-strb 13 9 0) (fa-mov 19 11) (fa-cmp 19 0) (fa-bcond 1 -8)
    (fa-movz-x 0 1) (fa-add-x-imm 1 10 0) (fa-movz-x 2 9) (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-movz 0 0) (fa-add-x-imm 31 31 32) (fa-ret)))'

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
echo "$hex" | xxd -r -p > "$work/wc.o"
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/wc" "$work/wc.o" 2>/dev/null

echo "── wc -l, zero clang, vs the real /usr/bin/wc -l (byte-for-byte incl. the padding) ──"
pass=0; total=0
for n in 0 1 7 42 123 1234; do
    if [ "$n" = 0 ]; then printf 'no trailing newline' > "$work/in"; else yes 2>/dev/null | head -n "$n" > "$work/in"; fi
    "$work/wc"   < "$work/in" > "$work/got"
    /usr/bin/wc -l < "$work/in" > "$work/want"
    total=$((total+1))
    if cmp -s "$work/got" "$work/want"; then pass=$((pass+1)); printf "  ok   %-5s -> [%s]\n" "$n" "$(tr '\n' '/' <"$work/got")"
    else printf "  DIFF %-5s form[%s] bsd[%s]\n" "$n" "$(od -An -c <"$work/got"|tr -s ' ')" "$(od -An -c <"$work/want"|tr -s ' ')"; fi
done
echo
if [[ "$pass" -eq "$total" ]]; then
    echo "  $pass/$total — Form \`wc -l\` matches /usr/bin/wc -l byte-for-byte, padding and all."
    echo "  itoa out + atoi in (head N) closes the number-in/number-out symmetry, zero new encoder."
else echo "  FAIL: $pass/$total"; exit 1; fi