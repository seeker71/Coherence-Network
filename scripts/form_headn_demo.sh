#!/usr/bin/env bash
# form_headn_demo.sh — `head N`, the REAL head, built with ZERO clang and direct
# Form -> asm: it reads its count from argv[1] (no longer hardcoded). The new piece
# is atoi — parse the decimal arg to an int — and it adds NO new encoder: a digit
# loop using b.hi (unsigned >, end of digits) + mul/add (register forms already in
# the table). Then the head loop runs on that N. Oracle: the system `head -n N`.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fheadn.XXXXXX")"; trap 'rm -rf "$work"' EXIT

PROG='(fa-image (list
    (fa-sub-x-imm 31 31 16) (fa-ldr 9 1 1)
    (fa-movz 19 0) (fa-movz 20 10)
    (fa-ldrb 8 9 0) (fa-sub 10 8 48) (fa-cmp 10 9) (fa-bcond 8 5)
    (fa-mul 19 19 20) (fa-add-r 19 19 10) (fa-add-x-imm 9 9 1) (fa-b-off -7)
    (fa-movz-x 0 0) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1) (fa-movz-x 16 3) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-cmp-x 0 0) (fa-bcond 13 13)
    (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1) (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-ldrb 8 31 0) (fa-cmp 8 10) (fa-bcond 1 -16)
    (fa-sub 19 19 1) (fa-cmp 19 0) (fa-bcond 12 -19)
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
echo "$hex" | xxd -r -p > "$work/h.o"
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/head" "$work/h.o" 2>/dev/null

seq 1 8 | sed 's/^/line /' > "$work/in"
echo "── head N, the REAL head (count from argv), zero clang ──"
pass=0; total=0
for n in 1 2 3 5 8; do
    total=$((total+1))
    "$work/head" "$n" < "$work/in" > "$work/got"
    head -n "$n" "$work/in" > "$work/want"
    if cmp -s "$work/got" "$work/want"; then pass=$((pass+1)); printf "  ok   head %s  ->  %s lines\n" "$n" "$(wc -l <"$work/got"|tr -d ' ')"
    else printf "  DIFF head %s\n" "$n"; diff "$work/want" "$work/got"; fi
done
echo
if [[ "$pass" -eq "$total" ]]; then
    echo "  $pass/$total — Form \`head N\` matches the system \`head -n N\` byte-for-byte, N parsed from argv."
    echo "  atoi added no new encoder; the same digit loop gives wc/tail their counts next."
else echo "  FAIL: $pass/$total"; exit 1; fi