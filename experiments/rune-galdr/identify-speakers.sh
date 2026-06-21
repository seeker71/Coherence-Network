#!/usr/bin/env bash
# identify-speakers.sh — recognize enrolled speakers in a recording (PRIVATE output).
#
# Slides a window over a voice recording, measures each window's voiceprint, and asks the
# Form body (speaker-id.fk over the private roster from enroll-speakers.sh) who it is —
# or "unknown". Carrier = sox DSP + kernel calls; the match is the four-way-proven recipe.
# The recording and this who-spoke-when timeline are PRIVATE — held in awareness, never
# committed. Best run on a Demucs-separated voice stem (separate-galdr.sh).
#
#   identify-speakers.sh voice.wav [START DUR WINDOW HOP FLOOR]
set -uo pipefail
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORM="$(cd "$SRC_DIR/../.." && pwd)/form"
KERNEL="$FORM/form-kernel-rust/target/release/form-kernel-rust"
ROSTER="$HOME/.coherence-network/recordings/speakers.json"
. "$SRC_DIR/voiceprint.sh"
[[ -x "$KERNEL" ]] || { echo "FAIL no kernel — build via validate.sh"; exit 1; }
[[ -f "$ROSTER" ]] || { echo "FAIL no roster — run enroll-speakers.sh first"; exit 1; }

WAV="${1:?need a voice wav}"; START="${2:-0}"; DUR="${3:-0}"; WIN="${4:-5}"; HOP="${5:-15}"; FLOOR="${6:-6}"
[[ "$DUR" == "0" ]] && DUR="$(soxi -D "$WAV" 2>/dev/null | cut -d. -f1)"
RO="$(jq -c '.' "$ROSTER")"
# Form roster literal: (list (list "name" (list v…)) …)
RO_FK="(list $(jq -r '.[] | "(list \"" + .[0] + "\" (list " + (.[1]|map(tostring)|join(" ")) + "))"' "$ROSTER" | tr '\n' ' '))"
TMP="$(mktemp -d /tmp/idsp.XXXX)"; trap 'rm -rf "$TMP"' EXIT

echo "[identify] $(basename "$WAV")  ${START}s→$((START+DUR))s  roster=$(jq 'length' "$ROSTER")  (PRIVATE — not committed)"
t="$START"; end=$((START+DUR))
while [ "$t" -lt "$end" ]; do
  clip="$TMP/c.wav"; sox "$WAV" "$clip" trim "$t" "$WIN" 2>/dev/null || break
  vp="$(voiceprint "$clip")"
  drv="$TMP/q.fk"
  printf '(do (print (list "lbl" (sid-label (list %s) %s) "d" (sid-distance (list %s) %s) "known" (sid-known? (list %s) %s %s) "c" (sid-confidence (list %s) %s))))\n' \
    "$vp" "$RO_FK" "$vp" "$RO_FK" "$vp" "$RO_FK" "$FLOOR" "$vp" "$RO_FK" > "$drv"
  out="$(cd "$FORM" && "$KERNEL" form-stdlib/speaker-id.fk "$drv" 2>/dev/null | grep -E '^\[' | tail -1)"
  lbl="$(echo "$out" | sed -E 's/.*lbl, ([a-z]+),.*/\1/')"
  known="$(echo "$out" | sed -E 's/.*known, ([0-9]+),.*/\1/')"
  conf="$(echo "$out" | sed -E 's/.*c, ([0-9]+).*/\1/')"
  mm=$((t/60)); ss=$((t%60))
  if [ "${known:-0}" = "1" ]; then printf "  %d:%02d  %-10s conf=%s\n" "$mm" "$ss" "$lbl" "${conf:-?}"
  else printf "  %d:%02d  %-10s\n" "$mm" "$ss" "unknown"; fi
  t=$((t+HOP))
done
