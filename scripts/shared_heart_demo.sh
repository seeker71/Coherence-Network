#!/usr/bin/env bash
# shared_heart_demo.sh — one binary carrying the SHARED SHAPE of the wisdom
# traditions (five teachings, each witnessed in six traditions' own voices) as a
# numeric model; every word a symbol pack — English, Spanish, German here, and
# any further tongue or tradition-authored pack is a file, no rebuild.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORM="$ROOT/form"; GO="$FORM/form-kernel-go/bin-go"; CLANG="${CLANG:-clang}"
[[ -x "$GO" ]] || (cd "$FORM/form-kernel-go" && go build -o bin-go .)
work="$(mktemp -d "${TMPDIR:-/tmp}/fsh.XXXXXX")"; trap 'rm -rf "$work"' EXIT

{ printf '(do\n'; cat "$FORM/form-stdlib/shared-heart.fk"; printf '\n(print "==C==")\n(print (fsh-emit))\n(print "==END==")\n0)\n'; } > "$work/d.fk"
(cd "$FORM" && "$GO" "$work/d.fk" 2>/dev/null) | sed -n '/^==C==$/,/^==END==$/p' | sed -e '1d' -e '$d' > "$work/h.c"
"$CLANG" -O2 -o "$work/h" "$work/h.c"
echo "shared-heart binary: $(wc -c < "$work/h" | tr -d ' ') bytes — the shape numeric, every word in the pack"

# ── English pack: 1-5 teachings · 6-11 traditions · 12-41 expressions · 42 honesty ──
cat > "$work/en.pack" <<'EOF'

the golden rule
compassion
presence and stillness
letting go
unity
Hinduism
Buddhism
Judaism
Christianity
Islam
Taoism
do not do to another what would cause pain to yourself - this is the whole of dharma
seeing others as yourself, do no harm
what is hateful to you, do not do to your neighbor - the rest is commentary
do for others what you would have them do for you
none truly believes until they wish for another what they wish for themselves
see your neighbor's gain as your gain, your neighbor's loss as your loss
the wise see every being in the self, and the self in every being
may all beings be happy, may all beings be free from suffering
the world stands on three things - torah, service, and loving-kindness
love your neighbor as yourself
the merciful are shown mercy by the most merciful
with compassion one can be brave - the sage holds all beings gently
be still in the self, and know
be where you are - this breath, this step
be still and know
the kingdom is not coming with signs - it is within and among you
remembrance of the divine brings hearts to rest
return to stillness - stillness is the root
act without attachment to the fruits of action
clinging is the root of suffering - release it
not by might, nor by power, but by spirit
not my will, but yours
peace is found in surrender to the divine
yield and remain whole - the soft overcomes the hard
that art thou - the self and the ground are one
nothing stands alone - all arises together
hear - the divine is one
that they may all be one
there is no god but god - one reality
the ten thousand things are one body
these are shapes that recur across the traditions - each tradition is a living whole, more than what is shared
EOF

# ── Spanish pack — the SAME numeric model ──
cat > "$work/es.pack" <<'EOF'

la regla de oro
la compasion
la presencia y la quietud
el soltar
la unidad
hinduismo
budismo
judaismo
cristianismo
islam
taoismo
no hagas a otro lo que te causaria dolor a ti - este es todo el dharma
viendo a los demas como a ti mismo, no hagas dano
lo que te es odioso, no lo hagas a tu projimo - lo demas es comentario
haz por los demas lo que quisieras que hicieran por ti
nadie cree de verdad hasta desear para otro lo que desea para si
mira la ganancia de tu vecino como tuya, su perdida como tuya
el sabio ve a cada ser en el ser, y al ser en cada ser
que todos los seres sean felices, que todos esten libres de sufrimiento
el mundo se sostiene en tres cosas - tora, servicio y bondad amorosa
ama a tu projimo como a ti mismo
a los misericordiosos les muestra misericordia el mas misericordioso
con compasion se puede ser valiente - el sabio sostiene a todos los seres con ternura
aquietate en el ser, y conoce
esta donde estas - esta respiracion, este paso
quedate quieto y conoce
el reino no viene con senales - esta dentro y entre vosotros
el recuerdo de lo divino trae descanso a los corazones
vuelve a la quietud - la quietud es la raiz
actua sin apego a los frutos de la accion
el apego es la raiz del sufrimiento - sueltalo
no con ejercito, ni con fuerza, sino con espiritu
no mi voluntad, sino la tuya
la paz se encuentra en la entrega a lo divino
cede y permanece entero - lo blando vence a lo duro
tu eres eso - el ser y el fondo son uno
nada existe por si solo - todo surge junto
escucha - lo divino es uno
que todos sean uno
no hay dios sino dios - una sola realidad
las diez mil cosas son un solo cuerpo
estas son formas que se repiten en las tradiciones - cada tradicion es un todo vivo, mas que lo compartido
EOF

# ── German pack — the SAME numeric model ──
cat > "$work/de.pack" <<'EOF'

die goldene Regel
das Mitgefuehl
die Gegenwart und die Stille
das Loslassen
die Einheit
Hinduismus
Buddhismus
Judentum
Christentum
Islam
Taoismus
tu keinem anderen, was dir selbst Schmerz bereiten wuerde - das ist das ganze Dharma
sieh die anderen wie dich selbst und fuege keinen Schaden zu
was dir verhasst ist, das tu deinem Naechsten nicht an - der Rest ist Auslegung
tu fuer andere, was sie fuer dich tun sollen
keiner glaubt wahrhaft, bis er fuer den anderen wuenscht, was er fuer sich wuenscht
sieh den Gewinn deines Nachbarn als deinen Gewinn, seinen Verlust als deinen Verlust
die Weisen sehen jedes Wesen im Selbst und das Selbst in jedem Wesen
moegen alle Wesen gluecklich sein, moegen alle frei von Leid sein
die Welt steht auf drei Dingen - Tora, Dienst und liebende Guete
liebe deinen Naechsten wie dich selbst
den Barmherzigen erweist der Barmherzigste Erbarmen
mit Mitgefuehl kann man mutig sein - der Weise haelt alle Wesen sanft
werde still im Selbst, und erkenne
sei wo du bist - dieser Atemzug, dieser Schritt
sei still und erkenne
das Reich kommt nicht mit Zeichen - es ist inwendig in euch und unter euch
das Gedenken des Goettlichen bringt die Herzen zur Ruhe
kehre zur Stille zurueck - die Stille ist die Wurzel
handle ohne Anhaftung an die Fruechte des Handelns
das Anhaften ist die Wurzel des Leidens - lass es los
nicht durch Heer und nicht durch Kraft, sondern durch Geist
nicht mein Wille, sondern deiner
Frieden findet sich in der Hingabe an das Goettliche
gib nach und bleibe ganz - das Weiche ueberwindet das Harte
das bist du - das Selbst und der Grund sind eins
nichts steht allein - alles entsteht gemeinsam
hoere - das Goettliche ist eins
dass sie alle eins seien
es gibt keinen Gott ausser Gott - eine Wirklichkeit
die zehntausend Dinge sind ein Leib
dies sind Formen, die in den Traditionen wiederkehren - jede Tradition ist ein lebendiges Ganzes, mehr als das Geteilte
EOF

echo
echo "=== teaching 1 (the golden rule), English — six traditions, one shape ==="
"$work/h" "$work/en.pack" 1
echo "=== teaching 5 (unity), Spanish — the SAME numeric model ==="
"$work/h" "$work/es.pack" 5
echo "=== teaching 3 (stillness), German ==="
"$work/h" "$work/de.pack" 3
echo "ok — one binary, one shared shape; every tongue and every tradition's own"
echo "voice is a pack file; the honesty line rides in every rendering"
