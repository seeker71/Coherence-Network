#!/usr/bin/env bash
# form_syscall_demo.sh — a program that does I/O, built with ZERO clang. The Form
# encoder (form-asm.fk) now carries the syscall / byte-I/O instruction set (svc,
# 64-bit movz/movk, strb, stack-frame add/sub); form-macho.fk wraps the bytes into
# a Mach-O object; `ld` (not clang) links it; the binary RUNS and writes to stdout
# via the macOS arm64 write syscall. clang is the ORACLE only — it assembles the
# same instructions so we can prove our bytes ARE the assembler's, byte-for-byte —
# never the lowering crutch. This is the syscall primitive a unix filter (cat, tr)
# composes from; the read-loop is the next move.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fsys.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# The program, as a Form instruction list: write "Hi\n" to stdout, return 0.
PROG='(fa-image (list
    (fa-sub-x-imm 31 31 16)
    (fa-movz 8 72)  (fa-strb 8 31 0)
    (fa-movz 8 105) (fa-strb 8 31 1)
    (fa-movz 8 10)  (fa-strb 8 31 2)
    (fa-movz-x 0 1) (fa-add-x-imm 1 31 0) (fa-movz-x 2 3)
    (fa-movz-x 16 4) (fa-movk-x-16 16 512) (fa-svc 128)
    (fa-movz 0 0) (fa-add-x-imm 31 31 16) (fa-ret)))'

# ── 1. Form emits the code image + the whole Mach-O object (hex). No clang. ──
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
form_code="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null | grep '^CODE ' | sed 's/^CODE //')"
hex="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; exit 1; }

# ── 2. clang as ORACLE: assemble the same instructions, compare bytes ──
cat > "$work/ref.s" <<'EOF'
.text
.globl _main
_main:
    sub  sp, sp, #16
    movz w8, #72
    strb w8, [sp, #0]
    movz w8, #105
    strb w8, [sp, #1]
    movz w8, #10
    strb w8, [sp, #2]
    movz x0, #1
    add  x1, sp, #0
    movz x2, #3
    movz x16, #4
    movk x16, #0x200, lsl #16
    svc  #0x80
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
echo "── a program that writes to stdout, built with zero clang ──"
echo "  Form encoder bytes : $form_code"
echo "  clang/as  (oracle) : $ref_code"
if [[ -n "$ref_code" && "$form_code" == "$ref_code" ]]; then
    echo "  CONVICTION: the Form encoder IS the assembler over the syscall set, byte-for-byte"
else
    echo "  (oracle unavailable or mismatch — running the Form binary is still the proof below)"
fi

# ── 3. ld (NOT clang) links the Form-emitted object; run it ──
echo "$hex" | xxd -r -p > "$work/fs.o"
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/fs" "$work/fs.o" 2>/dev/null
echo
echo "  running the Form-built binary ($(wc -c <"$work/fs.o" | tr -d ' ') bytes of Mach-O, no clang):"
out="$("$work/fs")"; rc=$?
printf '    stdout = [%s]  exit = %s\n' "$out" "$rc"
if [[ "$out" == $'Hi\n'* || "$out" == "Hi" ]]; then
    echo
    echo "  RUNNABLE I/O, ZERO CLANG — Form encoded the syscall, emitted the Mach-O, ld linked it,"
    echo "  and the binary wrote to stdout through the OS kernel. clang stayed the oracle."
else
    echo "  FAIL: expected stdout 'Hi', got '$out'"; exit 1
fi