#!/usr/bin/env bash
# asm_pl_human_demo.sh — an assembly -> programming language -> human language
# translator, shipped as ONE binary + a swappable symbol pack. Emit the binary
# from asm-pl-human.fk (quoteless -> three-way clean), then render the SAME
# numeric program at every level by swapping the pack: assembly, a programming
# language, English, French — and any further tongue is just another pack file.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/aph.XXXXXX")"; trap 'rm -rf "$work"' EXIT

{ printf '(do\n'; cat "$FORM/form-stdlib/asm-pl-human.fk"; printf '\n(print "==C==")\n(print (aph-emit))\n(print "==END==")\n0)\n'; } > "$work/d.fk"
(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/aph.c"
"$CLANG" -O2 -o "$work/aph" "$work/aph.c"
echo "translator emitted from asm-pl-human.fk: $(wc -c < "$work/aph" | tr -d ' ') bytes — ONE numeric program inside"
echo "bundled program: if (n <= 1) then 1 else (n + (n - 1))"

# one pack per level/language: line t = the template for op-tag t ($d = child d)
#   tags: 1 LIT(value) · 2 ARG · 3 ADD · 4 SUB · 5 LE · 6 COND
printf '\n\nARG\n(ADD $1 $2)\n(SUB $1 $2)\n(LE $1 $2)\n(BRZ $1 $2 $3)\n'                           > "$work/asm.pack"
printf '\n\nn\n($1 + $2)\n($1 - $2)\n($1 <= $2)\n($1 ? $2 : $3)\n'                                  > "$work/c.pack"
printf '\n\nthe input n\n$1 plus $2\n$1 minus $2\n$1 is at most $2\nif $1, then $2, otherwise $3\n' > "$work/english.pack"
printf '\n\nle nombre n\n$1 plus $2\n$1 moins $2\n$1 est au plus $2\nsi $1, alors $2, sinon $3\n'   > "$work/french.pack"

echo
echo "the SAME binary, a different pack each line — assembly -> programming language -> human:"
echo "  [assembly] $("$work/aph" "$work/asm.pack")"
echo "  [C lang  ] $("$work/aph" "$work/c.pack")"
echo "  [English ] $("$work/aph" "$work/english.pack")"
echo "  [French  ] $("$work/aph" "$work/french.pack")"
echo
echo "ok — one binary + a symbol pack; the level (asm/PL/human) and the language are both just packs"
