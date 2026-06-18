#!/usr/bin/env bash
# form_cli_roadmap.sh — list the floor->north-star steps and the next one to build.
#
# The steps and the queries (total / open / next) are roadmap.fk on the kernel
# (four-way); this carrier formats AND reconciles each rung's claimed status
# against the manifest. roadmap.fk stays pure Form data + query logic; reading
# form/fourth-arm-bands.txt is host-io, so it lives here, not in the recipe. Each
# rung carries a `band` stem (the fourth-arm-bands.txt row that PROVES it); the
# carrier checks the stem's presence in the manifest and surfaces any drift
# between the recipe's claim and the manifest reality, so the recipe's status can
# never silently lie. A rung whose band is "-" (the axiom floor or a multi-band
# phase) is reported as recipe-asserted, not manifest-reconciled.
#
# For an OPEN step that is a closable recipe gap, the printed spec is what you
# hand to form_cli_close_gap.sh — a LOCAL oracle drafts the recipe, the LOCAL
# kernel validates it. No remote LLM, fully offline.
#
# Usage: form_cli_roadmap.sh            # the whole tower, done + open, next named
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
MANIFEST="$ROOT/form/fourth-arm-bands.txt"
[ -x "$GO" ] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null

# manifest_has STEM -> 0 if a band row `<STEM> <emitter> <verdict>` is present.
# host-io: the recipe names the stem, the carrier reads the manifest floor.
manifest_has() {
  awk -v s="$1" '$1==s {found=1; exit} END {exit found?0:1}' "$MANIFEST"
}

prog="$(mktemp)"
{ cat "$STD/roadmap.fk"
  echo '(defn rm-emit (rows) (if (eq (len rows) 0) 0 (do (print (rm-id (head rows))) (print (rm-phase (head rows))) (print (rm-status (head rows))) (print (rm-band (head rows))) (print (rm-title (head rows))) (rm-emit (tail rows)))))'
  echo '(rm-emit (rm-seed))'
  echo '(print "===")'
  echo '(print (rm-open-count (rm-seed)))'
  echo '(print (rm-id (rm-next-open (rm-seed))))'
  echo '(print (rm-title (rm-next-open (rm-seed))))'
  echo '(print (rm-spec (rm-next-open (rm-seed))))'
} > "$prog"
out="$("$GO" "$prog" 2>/dev/null | sed '/^null$/d')"; rm -f "$prog"

echo "── floor → north-star (roadmap.fk on the kernel, status reconciled vs manifest) ──"
# steps: 5 lines each (id, phase, status, band, title) until the === marker.
# the carrier reconciles each rung's claimed status against form/fourth-arm-bands.txt:
#   band present in manifest  -> proven   (drift flagged if recipe claims open)
#   band absent from manifest -> unproven (drift flagged if recipe claims done)
#   band "-"                  -> recipe-asserted (axiom floor / multi-band phase)
drift=0
while IFS= read -r id && IFS= read -r phase && IFS= read -r status \
      && IFS= read -r band && IFS= read -r title; do
  [ "$id" = "===" ] && break
  mark='○'; [ "$status" = "done" ] && mark='✓'
  note=""
  if [ "$band" = "-" ]; then
    note="  (recipe-asserted)"
  elif manifest_has "$band"; then
    if [ "$status" != "done" ]; then
      note="  ⚠ DRIFT: band '$band' is in the manifest but recipe says open"
      drift=$((drift+1))
    else
      note="  (proven: band '$band')"
    fi
  else
    if [ "$status" = "done" ]; then
      note="  ⚠ DRIFT: recipe says done but band '$band' is NOT in the manifest"
      drift=$((drift+1))
    else
      note="  (gap: band '$band' not yet in manifest)"
    fi
  fi
  printf "  %s  [%s] %-12s %s%s\n" "$mark" "$phase" "$id" "$title" "$note"
done <<EOF
$out
EOF

# tail block after === : open-count, next id, next title, next spec
tailblock="$(printf '%s\n' "$out" | awk '/^===$/{b=1;next} b{print}')"
open="$(printf '%s\n' "$tailblock" | sed -n '1p')"
nid="$(printf '%s\n' "$tailblock" | sed -n '2p')"
ntitle="$(printf '%s\n' "$tailblock" | sed -n '3p')"
nspec="$(printf '%s\n' "$tailblock" | sed -n '4p')"

printf "\n  open: %s   next to build: %s — %s\n" "$open" "$nid" "$ntitle"
printf "  spec: %s\n" "$nspec"
printf "  build it offline:  form-cli close \"%s\" \"<recipe-spec>\" \"<assert>\" \"<expected>\" \"ollama run coder\"\n" "$nid"

if [ "$drift" -gt 0 ]; then
  printf "\n  ⚠ %d rung(s) drift from the manifest — reconcile roadmap.fk status with form/fourth-arm-bands.txt.\n" "$drift"
fi
