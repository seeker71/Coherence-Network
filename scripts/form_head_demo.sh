#!/usr/bin/env bash
# form_head_demo.sh — `head -3`, built with ZERO clang and direct Form -> asm. head
# is the cat loop plus a line COUNTER held in a callee-saved register (w19, preserved
# across the read/write syscalls): each newline written decrements it; at zero, exit.
# No new encoder — just cmp/sub data rows and two new branch CONDITIONS (b.ne, b.gt).
# N is fixed at 3 (argv-parsed N is the next step). Oracle: the system `head -n 3`.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fhead.XXXXXX")"; trap 'rm -rf "$work"' EXIT

PROG='(fa-image (list
    (fa-sub-x-imm 31 31 16) (fa-movz 19 3)
    (fa-movz-x 0 0) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 3) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-cmp-x 0 0) (fa-bcond 13 13)
    (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 1)
    (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
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

printf 'line one\nline two\nline three\nline four\nline five\n' > "$work/in.txt"
"$work/head" < "$work/in.txt" > "$work/got.txt"
head -n 3 "$work/in.txt" > "$work/want.txt"
echo "── head -3, built with zero clang and direct Form -> asm (no new encoder) ──"
echo "  input: 5 lines; Form-head ($(wc -c <"$work/h.o" | tr -d ' ') byte Mach-O) emits:"
sed 's/^/    | /' "$work/got.txt"
if cmp -s "$work/got.txt" "$work/want.txt"; then
    echo
    echo "  IT HEADS — matches the system \`head -n 3\` byte-for-byte. A real shell command on"
    echo "  Form's own bytes: a callee-saved line counter, decremented per newline, b.ne/b.gt."
else
    echo "  FAIL: Form-head != system head"; diff "$work/want.txt" "$work/got.txt"; exit 1
fi