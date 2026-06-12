#!/usr/bin/env bash
# form_fib_demo.sh — TRUE RECURSION, zero clang. The Form compiler lowers
# fib(n) = if n <= 1 then 1 else fib(n-1) + fib(n-2) — a self-CALLing function
# with a stack frame, callee-saved registers, and bl (branch-with-link) — wraps it
# in a Mach-O object (form-macho.fk), ld links it, and the binary runs on
# n = argc: the exit codes ARE the Fibonacci sequence (1, 2, 3, 5, 8).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/ffib.XXXXXX")"; trap 'rm -rf "$work"' EXIT

{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-lower.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let prog (list (list 1 1 0 0) (list 2 0 0 0) (list 5 1 0 0) (list 4 1 0 0)
                    (list 7 3 0 0) (list 1 2 0 0) (list 4 1 5 0) (list 7 6 0 0)
                    (list 3 4 7 0) (list 6 2 0 8)))
    (print (str_concat "MACHO " (hxb (mo-object (lo-rec-fn prog 9)))))
    0)
DRV
} > "$work/d.fk"
hex="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: no object emitted"; exit 1; }
echo "$hex" | xxd -r -p > "$work/f.o"
echo "program: fib(n) = if (n <= 1) then 1 else fib(n-1) + fib(n-2)   [n = argc]"
echo "Form-emitted object: $(wc -c < "$work/f.o" | tr -d ' ') bytes — frame, callee-saved regs, bl; zero clang"

SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/f" "$work/f.o" 2>/dev/null

echo
echo "one self-calling binary — the exit codes ARE the Fibonacci sequence:"
"$work/f";         r1=$?; echo "  fib(1) -> $r1"
"$work/f" a;       r2=$?; echo "  fib(2) -> $r2"
"$work/f" a b;     r3=$?; echo "  fib(3) -> $r3"
"$work/f" a b c;   r4=$?; echo "  fib(4) -> $r4"
"$work/f" a b c d; r5=$?; echo "  fib(5) -> $r5"
if [[ "$r1$r2$r3$r4$r5" == "12358" ]]; then
    echo
    echo "TRUE RECURSION, ZERO CLANG — the Form compiler emits a self-CALLing function"
    echo "(stack frame, callee-saved w19/w20, branch-with-link) and the binary computes"
    echo "Fibonacci by calling itself. The expression compiler became a function compiler."
else
    echo "FAIL: expected 1 2 3 5 8, got $r1 $r2 $r3 $r4 $r5"; exit 1
fi
