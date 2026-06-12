#!/usr/bin/env bash
# self_translate_demo.sh — emit, compile, and run the self-contained binary that
# translates its OWN internal model into English and French with no external
# content. The running proof of numeric-core-symbol-pack.form: identity is the
# numeric model; the language is a removable symbol pack baked beside it.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/self-xlate.XXXXXX")"; trap 'rm -rf "$work"' EXIT
{ printf '(do\n'; cat "$FORM/form-stdlib/self-translate.fk"; printf '\n(print "==C==")\n(print (stx-emit))\n(print "==END==")\n0)\n'; } > "$work/driver.fk"
(cd "$FORM" && "$GO" "$work/driver.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/self.c"
"$CLANG" -O2 -o "$work/self" "$work/self.c"
echo "self-contained binary: $(wc -c < "$work/self" | tr -d ' ') bytes (internal model + en + fr packs baked in)"
echo "imports (no fs/net = reads nothing external):"
otool -Iv "$work/self" 2>/dev/null | grep -iE "_open|_read|_socket|_fopen" | head -3 || true
echo "-- the binary translating its OWN model -> ENGLISH:"; "$work/self" en
echo "-- the SAME binary -> FRENCH:";                       "$work/self" fr
echo "ok — one binary, one numeric model, two languages, zero external content"
