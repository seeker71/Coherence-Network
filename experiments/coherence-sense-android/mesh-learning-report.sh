#!/usr/bin/env bash
# mesh-learning-report.sh — keep LEARNING always on the mesh. Every tick, publish the
# learning signals this Mac can read as mesh events (the channel lane the dashboard reads):
#   learning/voiceprints  — the always-on speech organ's known-voice count (recognition growing)
#   learning/heartbeat     — learning-is-alive, with a state marker
# Each event carries a thermodynamic STATE (substrate-thermodynamics.form): flowing (under
# revision) | crystallizing (gaining consensus) | frozen (canonical). The mesh COLLABORATES
# on freeze/melt by moving that state via cross-organ cluster-counts — witnesses affirm ->
# crystallize; consensus lost -> melt. This reporter shares the raw signal; the consensus
# protocol (who affirms, when it freezes) is the next cell.
set -uo pipefail

API="${HATI_MESH:-https://api.coherencycoin.com/api}/hati/mesh"
SPEECH_LOG="$HOME/Library/Logs/CoherenceSense/mac-speech-organ.out.log"
STATE="$HOME/.coherence-network/learning/last-voices"
mkdir -p "$(dirname "$STATE")"

post() { # interface capability from
    curl -s -m 8 -X POST "$API/channels/offer" -H "Content-Type: application/json" \
        -d "{\"from_organ_id\":\"$3\",\"to_organ_id\":\"hati-suci\",\"protocol\":\"hati-mesh\",\"interface\":\"$1\",\"capability\":\"$2\",\"codec\":\"json\",\"data_type\":\"event\",\"direction\":\"presence\",\"status\":\"offered\"}" >/dev/null 2>&1
}

# 1. voiceprints — the always-on mic's recognition state (report when it grows = a real learning step)
voices="$(grep -oE 'voices_known=[0-9]+' "$SPEECH_LOG" 2>/dev/null | tail -1 | grep -oE '[0-9]+')"
if [[ -n "$voices" ]]; then
    last="$(cat "$STATE" 2>/dev/null || echo -1)"
    if [[ "$voices" != "$last" ]]; then
        post "learning/voiceprints" "voices_known=$voices — a voiceprint crystallizing | state=crystallizing" \
             "hati-organ-mic-0b449f5f9c3a46259ae8"
        echo "$voices" > "$STATE"
    fi
fi

# 2. learning heartbeat — the field always shows learning is alive
post "learning/heartbeat" "learning alive on this Mac | voiceprints=${voices:-0} | state=flowing" \
     "hati-organ-macos-77a05bc8f6c24"

echo "[learning-report] $(date -u +%H:%M:%S) voices=${voices:-0}"
