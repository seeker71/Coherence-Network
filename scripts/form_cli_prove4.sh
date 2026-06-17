#!/usr/bin/env bash
# form_cli_prove4.sh — promote a closed recipe to a FOUR-WAY-proven stdlib cell.
#
# close validates a draft on the Go kernel only. This is the integrity gate: it
# moves the draft into the stdlib, auto-generates a verdict-1 band (the assertion),
# registers it in the fourth-arm manifest (NEWLINE-SAFE — a row that lands mid-line
# is invisible to fkwu), runs validate.sh, and only succeeds if the band crosses the
# 4th kernel (fkwu) FOUR-WAY with 0 divergent. A recipe the self-closer "loads" must
# have crossed fkwu, never passed on Go alone.
#
# Usage: form_cli_prove4.sh <id> <assert-expr> <expected> <dep-basenames>
#   dep-basenames: space-separated stdlib files the recipe needs (e.g. "form-asm.fk")
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; MAN="$ROOT/form/fourth-arm-bands.txt"
ID="${1:?id}"; ASSERT="${2:?assert}"; EXPECT="${3:?expected}"; DEPS="${4:-}"
DRAFT="$STD/drafts/$ID.fk"; RECIPE="$STD/$ID.fk"; BAND="$STD/tests/$ID-band.fk"
[ -f "$DRAFT" ] || { echo "prove4: no draft at $DRAFT"; exit 2; }

# 1. promote the draft to a real stdlib recipe (wrapped, headered)
{ printf '; %s.fk — self-closed by form-cli close-next (local oracle), proven four-way.\n' "$ID"
  printf '; preludes: %s\n(do ' "${DEPS:-form-stdlib/core.fk}"
  cat "$DRAFT"
  printf ' 0)\n'
} > "$RECIPE"

# 2. auto-generate the verdict-1 band (the assertion, four-way checkable)
deppaths=""; for d in $DEPS; do deppaths="$deppaths form-stdlib/$d"; done
{ printf '; preludes:%s form-stdlib/%s.fk\n' "$deppaths" "$ID"
  printf '; %s-band — self-closed recipe %s, proven four-way incl. fkwu.\n' "$ID" "$ID"
  printf '(do (if (eq %s %s) 1 0))\n' "$ASSERT" "$EXPECT"
} > "$BAND"

# 3. register in the manifest — NEWLINE-SAFE (the gotcha: a mid-line row is invisible)
emitter="fkc"; case "$ASSERT$(cat "$DRAFT")" in *'"'*) emitter="fks";; esac
grep -qx "$ID $emitter 1" "$MAN" || {
    [ -s "$MAN" ] && [ -n "$(tail -c1 "$MAN")" ] && printf '\n' >> "$MAN"
    printf '%s %s 1\n' "$ID" "$emitter" >> "$MAN"
}

# 4. run validate.sh and REQUIRE the fourth arm (fkwu) four-way, 0 divergent
out="$(cd "$ROOT/form" && ./validate.sh $deppaths "form-stdlib/$ID.fk" "form-stdlib/tests/$ID-band.fk" 2>&1)"
echo "$out" | grep -E '→|fourth arm|divergent' | sed 's/^/    /'
if echo "$out" | grep -q 'fourth arm: 1 band(s) four-way' && echo "$out" | grep -q '0 divergent'; then
    echo "  ✓ $ID PROVEN four-way (incl. fkwu) — loaded as a native stdlib cell"
    exit 0
else
    echo "  ✗ $ID did NOT cross the 4th kernel — NOT loaded (Go-only is not native)"
    exit 1
fi
