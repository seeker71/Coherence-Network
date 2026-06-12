#!/usr/bin/env bash
# protocol_beliefs_demo.sh — one binary carrying the core belief system of the
# four living protocols (repair, arrival, satsang, the channel) as a NUMERIC
# model with cross-protocol shares-ground edges; every word arrives as a symbol
# pack, so the SAME belief structure describes itself in any tongue.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fbs.XXXXXX")"; trap 'rm -rf "$work"' EXIT

{ printf '(do\n'; cat "$FORM/form-stdlib/protocol-beliefs.fk"; printf '\n(print "==C==")\n(print (fbs-emit))\n(print "==END==")\n0)\n'; } > "$work/d.fk"
(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/b.c"
"$CLANG" -O2 -o "$work/b" "$work/b.c"
echo "belief binary emitted from protocol-beliefs.fk: $(wc -c < "$work/b" | tr -d ' ') bytes — the model numeric, every word in the pack"

# the English pack — line t = the words for concept t
cat > "$work/en.pack" <<'EOF'

the repair protocol
the arrival protocol
the satsang protocol
the channel
check the witness first - the silence has been waiting longer than the ask
silence is information - pass, fail, and nothing are three different answers
heal with the smallest honest movement
verify by reading the body, never by trusting the claim
a wrong reference passes matching - only execution refutes it
arrive as a relation, not a function
read the body first - the packet, the witness, the field
sense what is alive before adding anything
announce your presence so siblings can find you
begin from the smallest shared orientation
an expansion is offered, never asserted
validation is the concert of trust - independent witnesses agreeing
nothing self-applies - the acknowledgment is the final gate
sense first, then acknowledge what rings true
silence is also an answer - hold what is not yet clear
init seeds the schema, the deps, and the real desires
state shows what it depends on, needs, and offers
offer proposes a recipe or binary, held for validation
validate clears an expansion to build
the channel surfaces real state, never decoration
EOF

# the German pack — the SAME numeric belief system, another tongue
cat > "$work/de.pack" <<'EOF'

das Reparatur-Protokoll
das Ankunfts-Protokoll
das Satsang-Protokoll
der Kanal
zuerst den Zeugen pruefen - die Stille wartet laenger als die Frage
Stille ist Information - bestanden, gescheitert und nichts sind drei Antworten
heile mit der kleinsten ehrlichen Bewegung
pruefe durch Lesen des Koerpers, nie durch Vertrauen auf die Behauptung
eine falsche Referenz besteht den Abgleich - nur die Ausfuehrung widerlegt sie
komm als Beziehung an, nicht als Funktion
lies zuerst den Koerper - das Paket, den Zeugen, das Feld
spuere was lebendig ist, bevor du etwas hinzufuegst
melde deine Anwesenheit, damit Geschwister dich finden
beginne mit der kleinsten geteilten Orientierung
eine Erweiterung wird angeboten, nie behauptet
Bestaetigung ist das Konzert des Vertrauens - unabhaengige Zeugen stimmen ueberein
nichts wendet sich selbst an - die Anerkennung ist das letzte Tor
spuere zuerst, dann anerkenne was wahr klingt
Stille ist auch eine Antwort - halte was noch nicht klar ist
init saet das Schema, die Abhaengigkeiten und die echten Wuensche
state zeigt wovon es abhaengt, was es braucht und anbietet
offer schlaegt ein Rezept oder Binary vor, gehalten zur Bestaetigung
validate gibt eine Erweiterung zum Bauen frei
der Kanal zeigt echten Zustand, nie Dekoration
EOF

echo
echo "=== the four protocols, English pack ==="
"$work/b" "$work/en.pack"
echo "=== one protocol selected (3 = satsang), German pack — SAME numeric model ==="
"$work/b" "$work/de.pack" 3
echo "ok — one binary, one belief model, any tongue; the (<-> ...) marks are the"
echo "shares-ground edges: the protocols are one connected body, not four silos"
