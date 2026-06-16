#!/usr/bin/env bash
# form_byte_filter_demo.sh — a shell command, lowered to native asm from a Form recipe.
#
# hati-os-byte-filter-emit.fk emits the C source of a stdin->stdout byte filter; the
# per-byte transform IS the command (data, not code). clang (an allowed host carrier
# under host-kernel.form) makes it a native binary; the system command is the oracle.
# We prove the Form-lowered native binary's output equals the system command's,
# byte-for-byte, on real input. This is the north star for composting the shell: not
# "tokenize in Form to avoid grep" but "the shell commands have source — build them as
# Form recipes and lower them to native asm."
#
# Usage: form_byte_filter_demo.sh ["input string"]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null
command -v "$CLANG" >/dev/null || { echo "no clang — the C toolchain is the lowering carrier"; exit 1; }
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT

INPUT="${1:-Hello, World! 123 ABCxyz}"
pass=0; total=0

echo "── shell commands, lowered to native asm from Form recipes ──"
echo "   Form emits the C · clang lowers it · the system command is the oracle"
echo "   input: [$INPUT]"
echo

run_one() { # label  name  transform-recipe  system-cmd...
    local label="$1" name="$2" tr="$3"; shift 3
    # Form emits the whole C program for this filter; the kernel is only the mouth.
    { cat "$STD/hati-os-byte-filter-emit.fk"; echo "(print (bf-filter-c \"$name\" $tr))"; } > "$work/$name.fk"
    "$GO" "$work/$name.fk" 2>/dev/null | sed '/^null$/d' | head -1 > "$work/$name.c"
    if ! "$CLANG" -O2 -o "$work/$name" "$work/$name.c" 2>"$work/$name.err"; then
        printf "  ✗ %-12s clang failed: %s\n" "$label" "$(head -1 "$work/$name.err")"; return 1
    fi
    total=$((total+1))
    local got want
    got="$(printf '%s' "$INPUT" | "$work/$name")"
    want="$(printf '%s' "$INPUT" | "$@")"
    if [[ "$got" == "$want" ]]; then
        pass=$((pass+1)); printf "  ✓ %-12s native == [%s]  (%d bytes of Form-emitted C)\n" "$label" "$got" "$(wc -c <"$work/$name.c")"
    else
        printf "  ✗ %-12s native[%s] != system[%s]\n" "$label" "$got" "$want"
    fi
}

run_one "tr A-Z a-z" low   "(bf-lower)" tr 'A-Z' 'a-z'
run_one "tr a-z A-Z" up    "(bf-upper)" tr 'a-z' 'A-Z'
run_one "cat"        catf  "(bf-cat)"   cat
run_one "rot13"      r13   "(bf-rot13)" tr 'A-Za-z' 'N-ZA-Mn-za-m'

echo
echo "  $pass/$total shell commands match their Form-lowered native binary, byte-for-byte"
[[ "$pass" -eq "$total" && "$total" -gt 0 ]]
