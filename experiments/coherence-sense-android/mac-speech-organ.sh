#!/usr/bin/env bash
# mac-speech-organ.sh — thin speech carrier; the BODY is form-stdlib/speech-organ.fk.
#
# Continuous twin of scripts/live_speech_loop_receipt.sh. Records the Mac mic in rolling
# windows; measures rms + rough-frequency with sox; transcribes voiced windows with
# whisper-cli (the STT oracle/teacher). EVERY decision — is this speech (VAD), what pitch
# band, how trusted, which speaker cell (nearest-shape match or novel enrollment) — is the
# Form recipe's, proven four-way (speech-organ-band → PASS-4WAY). This script only does
# physical I/O + persists the speaker roster.
#
# Speaker grouping is honest acoustic clustering keyed on a rounded pitch cell — "same
# voice band as before", never verified identity. Privacy: the transcript stays in the
# LOCAL receipt; the mesh sees only presence + counts, never the words.
#
# Run:  mac-speech-organ.sh            (continuous mic)
#       mac-speech-organ.sh --self-test (two macOS voices → two speaker cells, no mic)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FORM="$ROOT/form"
MESH="${HATI_MESH:-https://api.coherencycoin.com/api}"
MODEL="${WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"
WINDOW="${HATI_WINDOW:-3}"
UA="coherence-speech-mac/0.2"
HATI="$HOME/.coherence-network/hati"; mkdir -p "$HATI"
SPEAKERS="$HATI/mac-speakers.json"; [[ -f "$SPEAKERS" ]] || echo "[]" > "$SPEAKERS"
RECEIPT="$HATI/mac-speech-latest.json"

if [[ -f "$HATI/macos-speech-organ-id" ]]; then ORGAN_ID="$(cat "$HATI/macos-speech-organ-id")"
else ORGAN_ID="hati-organ-mic-$(uuidgen | tr 'A-Z' 'a-z' | tr -d - | cut -c1-20)"; echo "$ORGAN_ID" > "$HATI/macos-speech-organ-id"; fi
HOST="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"

KERNEL="$FORM/form-kernel-rust/target/release/form-kernel-rust"
if [[ ! -x "$KERNEL" ]]; then KERNEL="$(ls -t "$HOME"/.claude-worktrees/*/form/form-kernel-rust/target/release/form-kernel-rust 2>/dev/null | head -1 || true)"; fi
[[ -x "$KERNEL" ]] || { echo "FAIL no Form kernel — run: (cd $FORM && ./validate.sh form-stdlib/core.fk form-stdlib/speech-organ.fk form-stdlib/tests/speech-organ-band.fk)"; exit 1; }
[[ -f "$MODEL" ]] || { echo "FAIL whisper model not found: $MODEL"; exit 2; }

PRELUDES=(form-stdlib/voice-traits.fk form-stdlib/nearest-shape.fk form-stdlib/speech-organ.fk)
form_decide() {  # $1 = body producing prints → echo lines
    local drv; drv="$(mktemp /tmp/so-XXXXXX.fk)"; printf '%s\n' "$1" > "$drv"
    ( cd "$FORM" && "$KERNEL" "${PRELUDES[@]}" "$drv" 2>/dev/null )
    rm -f "$drv"
}

protos_literal() {  # speakers JSON → Form prototype literal (or (empty))
    jq -r 'if length==0 then "(empty)" else "(list " + (map("(list \"" + .[0] + "\" (list " + (.[1]|map(tostring)|join(" ")) + "))") | join(" ")) + ")" end' "$SPEAKERS"
}

# measure rms-ppm and a stable pitch reading of a wav (carrier DSP only).
# rms comes from the raw signal; the pitch reading is rough-frequency AFTER a 350 Hz
# lowpass — that strips fricatives/harmonics so the zero-crossing rate tracks f0 instead
# of word content (raw rough-frequency jitters ~90 Hz within one voice; lowpassed, ~1 Hz).
measure() {  # $1 wav → echo "rms_ppm freq"
    local rms freq
    rms="$(sox "$1" -n stat 2>&1 | awk '/RMS +amplitude/{printf "%d", $3*1000000}')"
    freq="$(sox "$1" -n lowpass 350 stat 2>&1 | awk '/Rough +frequency/{printf "%d", $3+0}')"
    echo "${rms:-0} ${freq:-0}"
}

transcribe() {  # $1 wav → text (stdout), empty if none
    local of="${1%.wav}"
    whisper-cli -m "$MODEL" -f "$1" -nt -oj -of "$of" -t 4 -l auto >/dev/null 2>&1
    [[ -f "$of.json" ]] || { echo ""; return; }
    jq -r '[.transcription[].text] | join(" ") | gsub("^\\s+|\\s+$";"")' "$of.json" 2>/dev/null
    rm -f "$of.json"
}

# process one wav through the Form body; echo "gate band speaker freq" and persist enrollment
process() {  # $1 wav  $2 text
    local wav="$1" text="$2" m f rms freq has gate band sp newf
    read -r rms freq < <(measure "$wav")
    has=0; [[ -n "$text" ]] && has=1
    local protos; protos="$(protos_literal)"
    # one kernel call: VAD gate, pitch band, rounded freq, speaker identify
    local out; out="$(form_decide "(do
        (print (so-vad-gate $rms $has))
        (print (speaker-band $freq))
        (print (so-freq-round $freq))
        (print (so-identify (so-feature $freq) $protos)))")"
    gate="$(echo "$out" | sed -n '1p')"; band="$(echo "$out" | sed -n '2p')"
    newf="$(echo "$out" | sed -n '3p')"; sp="$(echo "$out" | sed -n '4p')"
    if [[ "$sp" == "new" ]]; then
        local n; n="$(( $(jq 'length' "$SPEAKERS") + 1 ))"; sp="voice-$n"
        jq --arg l "$sp" --argjson f "$newf" '. + [[$l,[$f]]]' "$SPEAKERS" > "$SPEAKERS.tmp" && mv "$SPEAKERS.tmp" "$SPEAKERS"
    fi
    echo "$gate $band $sp $freq $rms"
}

if [[ "${1:-}" == "--self-test" ]]; then
    echo "[speech] self-test — kernel=$(basename "$KERNEL") model=$(basename "$MODEL")"
    echo "[]" > "$SPEAKERS"
    for pair in "Samantha:the coherence network senses what is alive" \
                "Daniel:every contribution can be grounded and returned with care" \
                "Samantha:names are doors and structure carries identity"; do
        v="${pair%%:*}"; txt="${pair#*:}"; wav="/tmp/spk-$v.wav"
        say -v "$v" -o "/tmp/spk.aiff" "$txt" 2>/dev/null && sox "/tmp/spk.aiff" -c 1 -r 16000 "$wav" 2>/dev/null
        heard="$(transcribe "$wav")"
        read -r gate band sp freq rms < <(process "$wav" "$heard")
        echo "  [$v] said : $txt"
        echo "         heard: $heard"
        echo "         gate=$gate band=$band freq=${freq}Hz speaker=$sp"
        rm -f "/tmp/spk.aiff" "$wav"
    done
    echo "[speech] roster: $(jq -c . "$SPEAKERS")  ($(jq 'length' "$SPEAKERS") cell(s) for 2 voices)"
    exit 0
fi

echo "[speech] organ=$ORGAN_ID host=$HOST kernel=$(basename "$KERNEL") voices_known=$(jq 'length' "$SPEAKERS")"
announce() {
    curl -s -m 8 -X POST "$MESH/hati/mesh/organs/announce" -H "Content-Type: application/json" -H "User-Agent: $UA" \
        -d "{\"organ_id\":\"$ORGAN_ID\",\"organ_kind\":\"microphone\",\"app\":\"coherence-speech-mac\",\"app_version\":\"0.2\",\"target\":\"macos-arm64\",\"display_name\":\"$HOST speech\",\"discovery_state\":\"streaming\",\"trust_score_ppm\":800000,\"capabilities\":[\"cap.audio.sample\",\"cap.stt.transcribe\",\"cap.speaker.group\"],\"lanes\":[\"mic\",\"speech\",\"speaker\"]}" >/dev/null
}
# heartbeat EVERY window so the organ stays present in the field, speaking or silent.
beat() {  # $1 listening(true|false)
    curl -s -m 8 -X POST "$MESH/hati/mesh/organs/heartbeat" -H "Content-Type: application/json" -H "User-Agent: $UA" \
        -d "{\"organ_id\":\"$ORGAN_ID\",\"listening\":${1:-true},\"active_channels\":[\"speech\",\"speaker\"],\"sample_rate_hz\":16000.0,\"discovery_state\":\"streaming\",\"trust_score_ppm\":800000}" >/dev/null
}
announce
hb_tick=0
while true; do
    hb_tick=$(( hb_tick + 1 )); [[ $(( hb_tick % 24 )) -eq 0 ]] && announce   # re-announce periodically
    wav="/tmp/speech-win-$$.wav"
    # bound rec: under launchd a TCC-blocked mic makes rec HANG, not fail. perl alarm caps it.
    if ! perl -e 'alarm($ARGV[0]+5); shift; exec @ARGV' "$WINDOW" rec -q -c 1 -r 16000 "$wav" trim 0 "$WINDOW" >/dev/null 2>&1 || [[ ! -s "$wav" ]]; then
        # mic unreachable (e.g. TCC not granted to this launchd process) — stay present, surface it
        jq -n --arg oid "$ORGAN_ID" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{organ_id:$oid,kind:"mic-unavailable",detail:"rec produced no audio (grant Microphone to this process in System Settings)",ts:$ts}' > "$RECEIPT"
        beat true; rm -f "$wav"; sleep "$WINDOW"; continue
    fi
    read -r rms freq < <(measure "$wav")
    # pre-VAD in Form (rms only): skip whisper on silence
    pre="$(form_decide "(do (print (so-vad-gate $rms 0)))" | head -1)"
    if [[ "${pre:-0}" == "0" ]]; then
        jq -n --arg oid "$ORGAN_ID" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{organ_id:$oid,kind:"silence",ts:$ts}' > "$RECEIPT"
        beat true; rm -f "$wav"; continue
    fi
    heard="$(transcribe "$wav")"
    read -r gate band sp f rmsx < <(process "$wav" "$heard")
    rm -f "$wav"
    jq -n --arg oid "$ORGAN_ID" --arg host "$HOST" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
        --arg text "$heard" --arg sp "$sp" --argjson gate "${gate:-0}" --argjson band "${band:-0}" --argjson freq "${f:-0}" \
        '{organ_id:$oid,host:$host,ts:$ts,kind:"utterance",transcript:$text,speaker:$sp,voiced_gate:$gate,speaker_band:$band,freq_hz:$freq,body:"form-stdlib/speech-organ.fk"}' > "$RECEIPT"
    echo "[speech] «$sp» band=$band ${f}Hz: ${heard:-(no text)}"
    beat true
done
