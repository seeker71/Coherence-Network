#!/usr/bin/env bash
# form_macho_demo.sh — a RUNNABLE native binary built with ZERO clang. The Form
# recipes compile a program tree to machine code (form-lower.fk) and wrap it in a
# valid Mach-O object (form-macho.fk); `ld` (not clang) links the object; the
# binary RUNS and its exit code IS the program's value. clang's compiler and
# assembler are gone — only Form, ld (the linker), and ld's ad-hoc signature (the
# macOS arm64 signing requirement) remain, each a named carrier, not a compiler.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping on $(uname -m)/$(uname -s)"; exit 0; }
command -v ld >/dev/null || { echo "need ld (the linker); skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fmacho.XXXXXX")"; trap 'rm -rf "$work"' EXIT

# Form: compile the tree ((40 + 1) - 1) -> code, wrap -> Mach-O .o bytes (hex). No clang.
{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-lower.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let prog (list (list 1 40 0 0) (list 1 1 0 0) (list 3 0 1 0) (list 1 1 0 0) (list 4 2 3 0)))
    (print (str_concat "MACHO " (hxb (mo-object (lo-compile prog 4)))))
    0)
DRV
} > "$work/d.fk"
hex="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: Form emitted no object"; exit 1; }
echo "$hex" | xxd -r -p > "$work/fm.o"
echo "Form-emitted Mach-O object: $(wc -c < "$work/fm.o" | tr -d ' ') bytes (no clang)"
file "$work/fm.o" | sed 's/^[^:]*: /  /'

# ld (NOT clang) links the object into a runnable binary
SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/fm" "$work/fm.o" 2>/dev/null
echo
echo "running the binary the Form recipes built (program: ((40 + 1) - 1) = 40):"
"$work/fm"; rc=$?
echo "  exit code = $rc"
if [[ "$rc" == "40" ]]; then
    echo
    echo "RUNNABLE, ZERO CLANG — Form compiled the code, emitted the Mach-O object, ld linked it,"
    echo "and the binary ran returning the program's value. clang's compiler + assembler: dropped."
else
    echo "FAIL: expected exit 40, got $rc"; exit 1
fi
