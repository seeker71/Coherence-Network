#!/usr/bin/env bash
# live-room.sh — a LIVE room transcriber + Brazilian-Portuguese translator, served to any phone on the wifi.
#
# The Mac listens, segments speech, labels who is speaking (pitch cluster), transcribes (whisper, any
# language auto-detected), and translates each turn to Brazilian Portuguese (local ollama — sovereign, no
# rented mind). Each turn is appended to live-room/turns.json; a clean web page polls it and renders the
# conversation the way a person reads it (translation prominent, original underneath). Built so the
# Brazilian-only member at Hati Suci can FOLLOW a room she otherwise can't.
#
# Carrier-only I/O: whisper is the STT oracle, ollama the translation oracle, the page is static (the
# heavy fusion/decision recipes — VAD, speaker-id — are the Form body). Everything stays on this Mac.
#
# Run:  live-room.sh --serve     start the web page (prints the phone URL); keep it running
#       live-room.sh             the capture+transcribe+translate loop (run alongside --serve)
#       live-room.sh --demo      process a few say-generated voices into turns.json (test the display)
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIR="${LIVE_DIR:-$HOME/.coherence-network/live-room}"; mkdir -p "$DIR"
TURNS="$DIR/turns.json"; [[ -f "$TURNS" ]] || echo "[]" > "$TURNS"
PORT="${LIVE_PORT:-8755}"
WIN="${LIVE_WINDOW:-5}"
MODEL_W="${WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"
MODEL_T="${TRANSLATE_MODEL:-llama3.2:3b}"
MIC="${LIVE_MIC:-1}"
COLORS=("#378ADD" "#1D9E75" "#D85A30" "#7F77DD" "#BA7517" "#D4537E")

cp "$SCRIPT_DIR/live-room.html" "$DIR/index.html" 2>/dev/null || true

# --- speaker diarization by pitch cluster (coarse v1; upgrades to speaker-aam voiceprints later) ---
roster="$DIR/speakers.tsv"; [[ -f "$roster" ]] || : > "$roster"   # lines: pitch<TAB>label<TAB>color
diarize() {  # $1 pitch_hz -> "label\tcolor"
    local p="$1" best="" bestd=9999 bl bc
    while IFS=$'\t' read -r rp rl rc; do
        [[ -z "$rp" ]] && continue
        local d=$(( p>rp ? p-rp : rp-p )); if [[ $d -lt $bestd ]]; then bestd=$d; best="$rl"; bc="$rc"; fi
    done < "$roster"
    if [[ -n "$best" && $bestd -le 18 ]]; then echo -e "$best\t$bc"; return; fi
    local n; n=$(( $(wc -l < "$roster") + 1 )); local label="Voz $n"; local color="${COLORS[$(( (n-1) % ${#COLORS[@]} ))]}"
    printf "%s\t%s\t%s\n" "$p" "$label" "$color" >> "$roster"; echo -e "$label\t$color"
}

transcribe() {  # $1 wav -> text (one line; empty if silence)
    local of="${1%.wav}"
    whisper-cli -m "$MODEL_W" -f "$1" -nt -oj -of "$of" -l auto -t 4 >/dev/null 2>&1
    [[ -f "$of.json" ]] || { echo ""; return; }
    jq -r '[.transcription[].text] | join(" ") | gsub("^[\\s]+|[\\s]+$";"")' "$of.json" 2>/dev/null | grep -vE '^\s*\[.*\]\s*$'
    rm -f "$of.json"
}

translate_pt() {  # $1 text -> Brazilian Portuguese (local ollama HTTP API; clean .response, honest pending marker)
    local prompt out
    prompt="Translate the following into natural Brazilian Portuguese. Output ONLY the translation — no quotes, no notes, no English: $1"
    out=$(curl -s --max-time 40 http://localhost:11434/api/generate \
            -d "$(jq -nc --arg m "$MODEL_T" --arg p "$prompt" '{model:$m, prompt:$p, stream:false, options:{temperature:0.2}}')" \
          | jq -r '.response // empty' | tr '\n' ' ' | sed 's/  */ /g; s/^[[:space:]]*//; s/[[:space:]]*$//; s/^"//; s/"$//')
    if [[ -z "$out" || "$out" == *Metal* || "$out" == *MTLCompiler* ]]; then echo "⏳ tradução local aguardando (Metal)"; else echo "$out"; fi
}

append_turn() {  # $1 label  $2 color  $3 original  $4 pt
    local ts; ts="$(date '+%H:%M')"
    jq --arg s "$1" --arg c "$2" --arg o "$3" --arg p "$4" --arg t "$ts" \
       '. + [{speaker:$s, color:$c, original:$o, pt:$p, time:$t}]' "$TURNS" > "$TURNS.tmp" && mv "$TURNS.tmp" "$TURNS"
}

process_wav() {  # $1 wav
    local text; text="$(transcribe "$1")"
    [[ -z "$text" || "$text" == "[BLANK_AUDIO]" ]] && return
    local pitch; pitch="$(sox "$1" -n lowpass 350 stat 2>&1 | awk '/Rough +frequency/{printf "%d",$3+0}')"
    local label color; IFS=$'\t' read -r label color < <(diarize "${pitch:-150}")
    append_turn "$label" "$color" "$text" "$(translate_pt "$text")"
    echo "[live] «$label» ${pitch}Hz: $text"
}

# ---- modes ----
if [[ "${1:-}" == "--serve" ]]; then
    IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1)"
    echo "[live] serving on  http://$IP:$PORT/   (open this on her phone, same wifi)"
    echo "[live] turns → $TURNS   ·  run '$0' in another shell to start listening"
    cd "$DIR" && exec python3 -m http.server "$PORT" --bind 0.0.0.0
fi

if [[ "${1:-}" == "--demo" ]]; then
    echo "[]" > "$TURNS"; : > "$roster"
    declare -a LINES=("Samantha|Let's land in the body first, one slow breath together."
                      "Daniel|A lot came up for me this week and I want to bring it here."
                      "Samantha|Thank you, we are holding it with you, you are not alone.")
    for pair in "${LINES[@]}"; do
        v="${pair%%|*}"; txt="${pair#*|}"; w="/tmp/lr-$v.wav"
        say -v "$v" -o /tmp/lr.aiff "$txt" 2>/dev/null && sox /tmp/lr.aiff -r 16000 -c 1 "$w" 2>/dev/null
        process_wav "$w"; rm -f /tmp/lr.aiff "$w"
    done
    echo "[live] demo turns:"; jq -r '.[] | "  «\(.speaker)» \(.original)  →  \(.pt)"' "$TURNS"
    exit 0
fi

# ---- live capture loop ----
echo "[live] listening (mic :$MIC, ${WIN}s windows). turns → $TURNS. Ctrl-C to stop."
i=0
while true; do
    [[ -f "$DIR/STOP" ]] && { echo "[live] STOP"; break; }
    w="/tmp/live-win-$$.wav"
    perl -e 'alarm($ARGV[0]+5); shift; exec @ARGV' "$WIN" \
        ffmpeg -hide_banner -loglevel error -f avfoundation -i ":$MIC" -t "$WIN" -ac 1 -ar 16000 -y "$w" >/dev/null 2>&1 || { sleep 1; continue; }
    # cheap silence gate: skip near-silent windows
    rms=$(sox "$w" -n stat 2>&1 | awk '/RMS +amplitude/{printf "%d",$3*1e6}')
    [[ "${rms:-0}" -gt 1500 ]] && process_wav "$w"
    rm -f "$w"
done
