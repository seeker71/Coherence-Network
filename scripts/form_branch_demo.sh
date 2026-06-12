#!/usr/bin/env bash
# form_branch_demo.sh — the FULL asm-pl-human program, compiled by Form and run on
# RUNTIME input with ZERO clang. The same tree the translator renders as asm / C /
# English / French — if (n <= 1) then 1 else (n + (n - 1)) — is lowered with
# comparison, conditional branch, and register selection (form-lower.fk), wrapped
# in a Mach-O object (form-macho.fk), linked by `ld`, and run with n = argc: one
# binary, different inputs, both branches witnessed live.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
[[ "$(uname -m)" == "arm64" && "$(uname -s)" == "Darwin" ]] || { echo "arm64 macOS demo; skipping"; exit 0; }
work="$(mktemp -d "${TMPDIR:-/tmp}/fbr.XXXXXX")"; trap 'rm -rf "$work"' EXIT

{ sed '$ d' "$FORM/form-stdlib/form-asm.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-lower.fk"
  sed '1,/^(do$/d;$ d' "$FORM/form-stdlib/form-macho.fk"
  cat <<'DRV'
    (defn hx1 (n) (nth (list "0" "1" "2" "3" "4" "5" "6" "7" "8" "9" "a" "b" "c" "d" "e" "f") n))
    (defn hx2 (b) (str_concat (hx1 (div b 16)) (hx1 (mod b 16))))
    (defn hxb (bs) (if (eq (len bs) 0) "" (str_concat (hx2 (head bs)) (hxb (tail bs)))))
    (let prog (list (list 1 1 0 0) (list 2 0 0 0) (list 5 1 0 0)
                    (list 4 1 0 0) (list 3 1 3 0) (list 6 2 0 4)))
    (print (str_concat "MACHO " (hxb (mo-object (lo-compile-fn prog 5)))))
    0)
DRV
} > "$work/d.fk"
hex="$(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null | grep '^MACHO ' | sed 's/^MACHO //')"
[[ -n "$hex" ]] || { echo "FAIL: no object emitted"; exit 1; }
echo "$hex" | xxd -r -p > "$work/f.o"
echo "program: if (n <= 1) then 1 else (n + (n - 1))   [n = argc]"
echo "Form-emitted object: $(wc -c < "$work/f.o" | tr -d ' ') bytes — comparison, branches, register ops, zero clang"

SDK="$(xcrun --show-sdk-path 2>/dev/null)"
ld -arch arm64 -platform_version macos 13.0 13.0 -L"$SDK/usr/lib" -lSystem -o "$work/f" "$work/f.o" 2>/dev/null

echo
echo "one binary, runtime input — both branches live:"
"$work/f";          rc=$?; echo "  n=1 (no args)  -> exit $rc   (then-branch: 1)"
"$work/f" a;        rc2=$?; echo "  n=2 (1 arg)    -> exit $rc2   (else: 2+1)"
"$work/f" a b c d;  rc5=$?; echo "  n=5 (4 args)   -> exit $rc5   (else: 5+4)"
if [[ "$rc" == 1 && "$rc2" == 3 && "$rc5" == 9 ]]; then
    echo
    echo "BOTH BRANCHES RUN — the full asm-pl-human program (the tree the translator renders"
    echo "as asm/C/English/French) now COMPILES and EXECUTES on runtime input, zero clang."
else
    echo "FAIL: expected 1/3/9, got $rc/$rc2/$rc5"; exit 1
fi
