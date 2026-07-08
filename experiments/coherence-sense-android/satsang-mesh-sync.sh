#!/usr/bin/env bash
# satsang-mesh-sync.sh — the mesh receiver for satsang recordings. Runs on the Mac (a mesh
# device), and every tick: finds any FINALIZED recording on the phone, pulls it, transcribes
# it with whisper, stores audio+txt+srt in the shared satsang folder, and fans it out to any
# other mesh devices listed in the peers file. The phone keeps its own copy (>=3 days,
# indefinite — never deleted here), so this replicates rather than moves.
#
# The mesh membrane has no blob store (file endpoints 404), so transmission is peer-to-peer:
# this device pulls over the LAN it already shares with the phone, then rsyncs to peers.
#
#   Peers (other devices): one rsync target per line in
#     ~/.coherence-network/satsang-peers      e.g.  urs@urs-windows-desktop:/Users/Urs/Satsang/
#   Empty by default — today only this Mac receives; add a line per device as it joins.
set -uo pipefail

ADB="${ADB:-/opt/homebrew/bin/adb}"
SERIAL="${SEMA_PHONE:-192.168.0.8:5555}"
MODEL="${WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"
REMOTE_DIR="/sdcard/Android/data/com.coherence.sema/files/satsang"
SHARED="${SATSANG_DIR:-$HOME/Documents/Coherence-private/satsang}"
STATE="$HOME/.coherence-network/satsang/pulled"
PEERS="$HOME/.coherence-network/satsang-peers"
mkdir -p "$SHARED" "$(dirname "$STATE")"
touch "$STATE"

log() { echo "[satsang-sync $(date -u +%H:%M:%S)] $*"; }

"$ADB" connect "$SERIAL" >/dev/null 2>&1 || true

# List recordings on the phone with their sizes (name<TAB>bytes).
listing="$("$ADB" -s "$SERIAL" shell "ls -l $REMOTE_DIR/*.m4a 2>/dev/null" | tr -d '\r' | awk '{print $NF"\t"$5}')"
[[ -n "$listing" ]] || { log "no recordings on phone"; exit 0; }

while IFS=$'\t' read -r remote bytes; do
    [[ -n "$remote" ]] || continue
    base="$(basename "$remote")"
    grep -qxF "$base" "$STATE" && continue          # already pulled

    # finalization guard: size must be stable (not still recording).
    sleep 4
    bytes2="$("$ADB" -s "$SERIAL" shell "ls -l $remote 2>/dev/null" | tr -d '\r' | awk '{print $5}')"
    if [[ "$bytes" != "$bytes2" || -z "$bytes2" || "$bytes2" == "0" ]]; then
        log "$base still recording (or empty) — skip this tick"
        continue
    fi

    log "pulling $base ($bytes2 bytes)"
    audio="$SHARED/$base"
    "$ADB" -s "$SERIAL" pull "$remote" "$audio" >/dev/null 2>&1 || { log "pull failed $base"; continue; }

    stem="${audio%.*}"; wav="$stem.16k.wav"
    if command -v whisper-cli >/dev/null && command -v ffmpeg >/dev/null && [[ -f "$MODEL" ]]; then
        ffmpeg -y -i "$audio" -ar 16000 -ac 1 -c:a pcm_s16le "$wav" >/dev/null 2>&1 \
            && whisper-cli -m "$MODEL" -f "$wav" -l auto -otxt -osrt -of "$stem" -t 4 >/dev/null 2>&1 \
            && log "transcribed -> $(basename "$stem").txt"
        rm -f "$wav"
    else
        log "whisper/ffmpeg/model missing — audio stored, transcript pending"
    fi

    # fan out to other mesh devices (peer-to-peer; empty peers = this Mac only today).
    if [[ -s "$PEERS" ]]; then
        while IFS= read -r peer; do
            [[ -z "$peer" || "$peer" == \#* ]] && continue
            rsync -az "$stem".* "$peer" >/dev/null 2>&1 && log "fanned out to $peer" || log "peer unreachable: $peer"
        done < "$PEERS"
    fi

    echo "$base" >> "$STATE"
    log "done $base -> $SHARED (phone keeps its copy >=3 days)"
done <<< "$listing"
