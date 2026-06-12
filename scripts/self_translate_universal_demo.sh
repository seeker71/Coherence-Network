#!/usr/bin/env bash
# self_translate_universal_demo.sh — emit a NUMERIC-ONLY core binary (zero
# language symbols), then translate its own model into ANY language by loading a
# different symbol-pack file. Same binary, swap the pack, get any tongue — no
# rebuild. numeric-core-symbol-pack.form: identity is numeric, language is data.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/stu.XXXXXX")"; trap 'rm -rf "$work"' EXIT
{ printf '(do\n'; cat "$FORM/form-stdlib/self-translate-universal.fk"; printf '\n(print "==C==")\n(print (stu-emit))\n(print "==END==")\n0)\n'; } > "$work/driver.fk"
(cd "$FORM" && "$GO" "$work/driver.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/u.c"
"$CLANG" -O2 -o "$work/u" "$work/u.c"
echo "numeric-only core binary: $(wc -c < "$work/u" | tr -d ' ') bytes — zero language symbols inside (model + pack-loader only)"
# a symbol pack per language: line N = the name for op-tag N (1=LIT, 2=ARG, 3=ADD)
printf '\nLITERAL \nTHE INPUT\nADD\n'        > "$work/en.pack"
printf '\nLITTERAL \nL ENTREE\nADDITION\n'   > "$work/fr.pack"
printf '\nLITERAL \nDIE EINGABE\nADDIEREN\n' > "$work/de.pack"
printf '\nLITERAL \nLA ENTRADA\nSUMAR\n'     > "$work/es.pack"
printf '\nAKSARA \nNIVESA\nYOGA\n'           > "$work/sa.pack"
echo "the SAME binary, any language, just by swapping the pack file:"
for L in en fr de es sa; do echo "  [$L]"; "$work/u" "$work/$L.pack" | sed 's/^/     /'; done
echo "ok — one numeric-only binary; any language is a symbol-pack file; unbounded, no rebuild"
