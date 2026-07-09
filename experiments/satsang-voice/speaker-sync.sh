#!/usr/bin/env bash
# speaker-sync.sh — make the voice book shareable across every device. Two lanes, matching how
# the mesh actually works:
#   1. ROSTER over the mesh — one compact offer per person under speaker/profile/<slug>
#      (person|n|updated, well under the 127-char cap) so any device sees who we know.
#   2. DATA as a file — the centroids + per-sample embeddings (profiles.json + samples/*.json,
#      NOT the raw wav clips, which stay local like all raw audio) pushed to the phone over the
#      LAN it shares with this Mac, and rsync'd to any peers. The math travels; the voice does not.
#
# Run as the organ earth.hati.speaker-sync (every ~180s), or once by hand.
set -uo pipefail
CN="$HOME/.coherence-network"
STORE="$CN/speakers"
PROFILES="$STORE/profiles.json"
API="${HATI_MESH:-https://api.coherencycoin.com/api}/hati/mesh"
FROM="hati-organ-macos-77a05bc8f6c24"
ADB="${ADB:-/opt/homebrew/bin/adb}"
SERIAL="${SEMA_PHONE:-192.168.0.8:5555}"
PHONE_DIR="/sdcard/Android/data/com.coherence.sema/files/speakers"
PEERS="$CN/speaker-peers"   # optional: one rsync target per line (device on another network)

[[ -f "$PROFILES" ]] || { echo "[speaker-sync] no profiles yet"; exit 0; }

# 1. roster to the mesh — one compact offer per person
post() { # slug cap
    local slug="$1" cap="${2:0:120}" pf; pf="$(mktemp)"
    python3 -c "import json,sys;json.dump({'from_organ_id':sys.argv[1],'to_organ_id':'hati-suci','protocol':'hati-mesh','interface':'speaker/profile/'+sys.argv[2],'capability':sys.argv[3],'codec':'json','data_type':'event','direction':'presence','status':'offered'}, open(sys.argv[4],'w'))" "$FROM" "$slug" "$cap" "$pf"
    curl -s -m 8 -o /dev/null -w "%{http_code} " -X POST "$API/channels/offer" -H "Content-Type: application/json" --data @"$pf"
    rm -f "$pf"
}
echo -n "[speaker-sync] roster: "
while IFS='|' read -r slug cap; do
    [[ -n "$slug" ]] && post "$slug" "$cap"
done < <(python3 -c "
import json,re
b=json.load(open('$PROFILES'))
for p in b.get('profiles',[]):
    slug=re.sub(r'[^a-z0-9]+','-',p['person'].lower()).strip('-') or 'anon'
    print(f\"{slug}|{p['person']}|{p['n']} samples|{p['updated_at']}\")
")
echo ""

# 2. data to the phone over the LAN (best-effort; only when co-located)
if "$ADB" connect "$SERIAL" >/dev/null 2>&1 && "$ADB" -s "$SERIAL" shell true >/dev/null 2>&1; then
    "$ADB" -s "$SERIAL" shell "mkdir -p $PHONE_DIR" >/dev/null 2>&1
    "$ADB" -s "$SERIAL" push "$PROFILES" "$PHONE_DIR/profiles.json" >/dev/null 2>&1 \
        && echo "[speaker-sync] pushed profiles.json to phone" \
        || echo "[speaker-sync] phone push failed (app files dir may need the app installed)"
else
    echo "[speaker-sync] phone not on this LAN — roster still on the mesh for it to read"
fi

# 3. peers on other networks (internet-routable rsync targets), if any
if [[ -f "$PEERS" ]]; then
    while read -r target; do
        [[ -z "$target" || "$target" == \#* ]] && continue
        rsync -az --include='profiles.json' --include='samples/' --include='samples/*.json' \
              --exclude='*' "$STORE/" "$target" 2>/dev/null \
            && echo "[speaker-sync] synced to $target"
    done < "$PEERS"
fi
