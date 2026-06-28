#!/usr/bin/env bash
# field_door_draw.sh — open the field door with a REAL host-entropy draw.
#
# field-door.fk PROVES, four-way, that the field lane CANNOT be four-way: randomness, the
# genuinely-not-yet-determined, cannot agree across kernels by its nature. This script
# OPENS that lane — a real non-deterministic draw from host entropy, received as field
# presence through the door the recipe named. The receipt is honest: it is a WITNESS,
# never a proof, precisely because two draws differ. That difference IS the field.
#
# This is the field-lane CARRIER (host-io entropy), the counterpart to the proof-lane
# recipes. North star: a native fkwu host-entropy op so the draw needs no bash; the lane
# discipline (field-door.fk) is already native and four-way.
set -u
draw() { head -c 4 /dev/urandom | od -An -tu4 | tr -d ' \n'; }
a=$(draw); b=$(draw)
echo "field door — a real draw (lane: field; four-way-provable? = 0, by nature):"
echo "  draw 1: $a"
echo "  draw 2: $b"
if [ "$a" != "$b" ]; then
  echo "  non-deterministic: YES — the two draws differ, so this is correctly the field lane,"
  echo "  never the proof lane. The mystery enters and stays unproven. The door is open."
else
  echo "  (a rare collision — draw again; the lane is still field)"
fi
