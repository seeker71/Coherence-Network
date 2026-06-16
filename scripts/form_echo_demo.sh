#!/usr/bin/env bash
# form_echo_demo.sh — `echo $1`, built with ZERO clang and direct Form -> asm, and
# the proof the lane can READ ARGV. At _main, x1 = argv (char**); argv[1] is the
# pointer at [x1, #8]. echo loads it (ldr — the one new instruction this adds),
# writes each byte until NUL, then a newline. This is the primitive every
# argument-taking tool needs: head N, tr SET1 SET2, cat FILE all start here.
# Oracle: the system `echo`.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fecho.XXXXXX")"; trap 'rm -rf "$work"' EXIT

PROG='(fa-image (list
    (fa-sub-x-imm 31 31 16) (fa-ldr 9 1 1)
    (fa-ldrb 8 9 0) (fa-cmp 8 0) (fa-bcond 0 9)
    (fa-movz-x 0 1) (fa-add-x-imm 1 9 0) (fa-movz-x 2 1)
    (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-add-x-imm 9 9 1) (fa-b-off -10)
    (fa-movz 8 10) (fa-strb 8 31 0)
    (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
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
echo "$hex" | xxd -r -p > "$work/e.o"
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/echo" "$work/e.o" 2>/dev/null

echo "── echo \$1, built with zero clang and direct Form -> asm (reads argv) ──"
pass=0; total=0
for arg in "hello world" "café ☃ 123" "" "a-single-token"; do
    total=$((total+1))
    got="$("$work/echo" "$arg")"
    want="$(echo "$arg")"
    if [[ "$got" == "$want" ]]; then pass=$((pass+1)); printf "  ok   echo [%s] -> [%s]\n" "$arg" "$got"
    else printf "  DIFF echo [%s]  form=[%s] system=[%s]\n" "$arg" "$got" "$want"; fi
done
echo
if [[ "$pass" -eq "$total" ]]; then
    echo "  IT ECHOES — Form-echo matches the system \`echo\` for argv[1], byte-for-byte."
    echo "  The lane reads argv now: ldr [x1,#8]. head N / tr SET1 SET2 / cat FILE build on this."
else
    echo "  FAIL: $pass/$total matched"; exit 1
fi