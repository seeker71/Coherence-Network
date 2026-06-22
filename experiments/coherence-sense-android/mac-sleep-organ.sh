#!/usr/bin/env bash
# mac-sleep-organ.sh — thin bedside SLEEP carrier; the BODY is the Form recipes
#   form-stdlib/wav-sense.fk        (energy envelope 0..9 from a 16-bit WAV)
#   form-stdlib/signal-derivative.fk(oscillation count across a window)
#   form-stdlib/sleep-sense.fk      (ss-snore? : 1 if a window is loud AND periodic)
#   form-stdlib/sleep-night.fk      (fold a night's 0/1 stream into a morning readout)
#
# Sibling of mac-speech-organ.sh. Records the Mac mic in rolling 30s windows through the night;
# for each window the Form kernel computes the energy envelope (wav-envelope-file) and decides
# snore? (ss-snore?). The carrier only does physical I/O + persistence — EVERY decision is the
# recipe's, proven four-way at validate.sh. At wake it folds the night's 0/1 verdicts with
# sleep-night into a plain-words readout.txt.
#
# PRIVACY: audio + per-window verdicts stay on THIS Mac. WAVs are held a couple of days so the
# floors can be re-tuned, then composted. Only presence/counts may reach the mesh, never the audio.
#
# HONEST LANE: ss-snore? reads "loud AND periodic" — the signature of breathing-shaped sound, not a
# verified snore. The floors (energy 3, oscillation 3) are first-night defaults, untuned against real
# audio; a quiet room reads 0 and a loud oscillating breath reads 1 (verified on real WAVs before the run).
#
# Run:  mac-sleep-organ.sh                 capture until SLEEP_STOP_HOUR (default 08:00), then write readout
#       mac-sleep-organ.sh --readout DIR   just (re)build the readout from DIR/windows.csv
#       mac-sleep-organ.sh --dry N         record+sense N short windows now, no overnight loop (calibration)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FORM="$ROOT/form"
MESH="${HATI_MESH:-https://api.coherencycoin.com/api}"
UA="coherence-sleep-mac/0.1"

DATE="${SLEEP_DATE:-$(date +%Y-%m-%d)}"
DIR="${SLEEP_DIR:-$HOME/sleep-$DATE}"
WAVDIR="$DIR/wav"
CSV="$DIR/windows.csv"
READOUT="$DIR/readout.txt"

WINDOW="${SLEEP_WINDOW:-30}"        # seconds of audio per window
STEP="${SLEEP_STEP:-2}"             # envelope byte step (must be EVEN — 2 = full resolution)
EFLOOR="${SLEEP_EFLOOR:-3}"         # energy floor   (untuned first-night default)
AFLOOR="${SLEEP_AFLOOR:-3}"         # oscillation floor
STOP_HOUR="${SLEEP_STOP_HOUR:-8}"   # auto-stop at this local hour
MIC_NAME="${SLEEP_MIC_NAME:-MacBook Pro Microphone}"

# --- pinned Go kernel: a private copy so a later validate.sh rebuild can't disturb a running night ---
KERNEL="${SLEEP_KERNEL:-$DIR/kernel-go}"
PRELUDES=(form-stdlib/signal-derivative.fk form-stdlib/sleep-sense.fk form-stdlib/wav-sense.fk)
NIGHT_PRELUDE=(form-stdlib/sleep-night.fk)

mkdir -p "$WAVDIR"

ensure_kernel() {
    if [[ ! -x "$KERNEL" ]]; then
        local src="$FORM/form-kernel-go/bin-go"
        [[ -x "$src" ]] || { echo "FAIL no Go kernel at $src — build with: (cd $FORM && ./validate.sh form-stdlib/core.fk form-stdlib/signal-derivative.fk form-stdlib/sleep-sense.fk form-stdlib/tests/sleep-sense-band.fk)"; exit 1; }
        cp "$src" "$KERNEL"
    fi
}

# sense one wav → echo "verdict mean activity env" (env is space-joined, [] stripped)
sense_wav() {  # $1 wav
    local drv; drv="$(mktemp /tmp/sleep-XXXXXX.fk)"
    cat > "$drv" <<EOF
(do (let e (wav-envelope-file "$1" $STEP))
    (print (ss-snore? e $EFLOOR $AFLOOR))
    (print (ss-mean e))
    (print (sd-activity e))
    (print e))
EOF
    local out; out="$( cd "$FORM" && "$KERNEL" "${PRELUDES[@]}" "$drv" 2>/dev/null )"
    rm -f "$drv"
    local v m a e
    v="$(sed -n '1p' <<<"$out")"; m="$(sed -n '2p' <<<"$out")"
    a="$(sed -n '3p' <<<"$out")"; e="$(sed -n '4p' <<<"$out" | tr -d '[]' | tr ',' ' ')"
    echo "${v:-x} ${m:-0} ${a:-0} ${e:- }"
}

measure_rms() {  # $1 wav → rms in parts-per-million (carrier DSP, re-tuning aid only)
    sox "$1" -n stat 2>&1 | awk '/RMS +amplitude/{printf "%d", $3*1000000}'
}

resolve_mic() {  # echo avfoundation audio index for MIC_NAME, fallback 1
    local idx
    idx="$(ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 \
        | sed -n '/audio devices/,$p' | grep -F "$MIC_NAME" | grep -oE '\[[0-9]+\]' | head -1 | tr -d '[]')"
    echo "${idx:-1}"
}

record_window() {  # $1 out.wav  $2 secs  $3 mic_index → 0 ok / nonzero on fail
    rm -f "$1"
    # bound the recorder: a TCC-blocked mic makes ffmpeg HANG under launchd, not fail. perl alarm caps it.
    perl -e 'alarm($ARGV[0]+8); shift; exec @ARGV' "$2" \
        ffmpeg -hide_banner -loglevel error -f avfoundation -i ":$3" -t "$2" -ac 1 -ar 16000 -y "$1" >/dev/null 2>&1
    [[ -s "$1" ]]
}

# fold windows.csv into a plain-words readout. Gaps (verdict x) are excluded, never counted as quiet.
build_readout() {  # $1 dir
    local dir="$1"                                    # assign first; a same-line csv="$dir/..." would
    local csv="$dir/windows.csv" out="$dir/readout.txt"  # expand $dir before local sets it (set -u trap)
    [[ -f "$csv" ]] || { echo "no windows.csv in $dir"; return 1; }
    ensure_kernel
    # 0/1 stream (verdict column 3), excluding gaps; + gap count + first/last timestamps
    local stream gaps total_rows first last
    stream="$(awk -F, 'NR>1 && ($3==0||$3==1){printf "%s ",$3}' "$csv")"
    gaps="$(awk -F, 'NR>1 && $3=="x"{n++} END{print n+0}' "$csv")"
    total_rows="$(awk -F, 'NR>1{n++} END{print n+0}' "$csv")"
    first="$(awk -F, 'NR==2{print $2}' "$csv")"
    last="$(awk -F, 'END{print $2}' "$csv")"
    local drv; drv="$(mktemp /tmp/sleep-night-XXXXXX.fk)"
    cat > "$drv" <<EOF
(do (let xs (list ${stream:-}))
    (print (sn-total xs))
    (print (sn-snores xs))
    (print (sn-longest xs))
    (print (sn-episodes xs))
    (print (sn-fraction xs)))
EOF
    local r; r="$( cd "$FORM" && "$KERNEL" "${NIGHT_PRELUDE[@]}" "$drv" 2>/dev/null )"
    rm -f "$drv"
    local n snores longest eps pct
    n="$(sed -n '1p' <<<"$r")"; snores="$(sed -n '2p' <<<"$r")"
    longest="$(sed -n '3p' <<<"$r")"; eps="$(sed -n '4p' <<<"$r")"; pct="$(sed -n '5p' <<<"$r")"
    n="${n:-0}"; snores="${snores:-0}"; longest="${longest:-0}"; eps="${eps:-0}"; pct="${pct:-0}"

    local sensed_min=$(( n * WINDOW / 60 ))
    local longest_min=$(( longest * WINDOW / 60 ))
    {
        echo "Sleep sensing — night of $DATE"
        echo "================================================"
        echo
        echo "Captured $first  →  $last"
        echo "$n windows of ${WINDOW}s carried real audio (~${sensed_min} min sensed)."
        [[ "$gaps" -gt 0 ]] && echo "$gaps window(s) recorded no audio (system asleep or mic blocked) — excluded, not counted as quiet."
        echo
        echo "Breathing-shaped (loud + periodic) sound was sensed in $snores of $n windows — ${pct}% of the sensed night."
        echo "That clustered into $eps episode(s); the longest unbroken stretch ran $longest window(s) (~${longest_min} min)."
        echo
        echo "How to read this"
        echo "----------------"
        echo "• This reads \"loud AND periodic\" — the signature of breathing/snoring, NOT a verified snore."
        echo "  A steady loud sound (a fan) is rejected; a quiet room reads nothing."
        echo "• Floors were first-night defaults (energy ${EFLOOR} / oscillation ${AFLOOR}), untuned against your real audio."
        echo "  Before the run: a quiet room read 0, a loud oscillating breath read 1 (verified on real WAVs)."
        echo "  The kept WAVs let these floors be re-tuned over the next couple of days."
        echo "• Each window is ${WINDOW}s, so the percentages are coarse — a single noisy moment can light one window."
        echo "• Audio + verdicts never left this Mac. WAVs live in $WAVDIR; held ~2 days for re-tuning, then composted."
        echo
        echo "(body: form-stdlib/{wav-sense,signal-derivative,sleep-sense,sleep-night}.fk — four-way proven recipes)"
    } > "$out"
    echo "$out"
}

# ---- modes -------------------------------------------------------------------
if [[ "${1:-}" == "--readout" ]]; then
    build_readout "${2:-$DIR}"; exit 0
fi

ensure_kernel
MIC="$(resolve_mic)"

if [[ "${1:-}" == "--dry" ]]; then
    N="${2:-3}"; SECS=6
    echo "[sleep] DRY: mic=:$MIC kernel=$(basename "$KERNEL") floors=${EFLOOR}/${AFLOOR} — $N windows of ${SECS}s"
    for i in $(seq 1 "$N"); do
        w="/tmp/sleep-dry-$i.wav"
        if record_window "$w" "$SECS" "$MIC"; then
            read -r v m a env < <(sense_wav "$w")
            printf "  win %d  snore?=%s  mean=%s  activity=%s  env=[%s]  rms=%sppm\n" "$i" "$v" "$m" "$a" "$env" "$(measure_rms "$w")"
        else
            printf "  win %d  NO AUDIO (mic blocked? grant Microphone permission)\n" "$i"
        fi
        rm -f "$w"
    done
    exit 0
fi

# ---- overnight capture -------------------------------------------------------
STOP_EPOCH="$(date -v"${STOP_HOUR}"H -v0M -v0S +%s)"
[[ "$STOP_EPOCH" -le "$(date +%s)" ]] && STOP_EPOCH=$(( STOP_EPOCH + 86400 ))  # already past → tomorrow

[[ -f "$CSV" ]] || echo "idx,ts,verdict,mean,activity,env,rms_ppm" > "$CSV"
echo "[sleep] organ live — dir=$DIR mic=:$MIC window=${WINDOW}s floors=${EFLOOR}/${AFLOOR} stop=$(date -r "$STOP_EPOCH" '+%H:%M')"

idx="$(awk -F, 'END{print (NR>1?NR-1:0)}' "$CSV")"   # resume-safe
while [[ "$(date +%s)" -lt "$STOP_EPOCH" ]]; do
    [[ -f "$DIR/STOP" ]] && { echo "[sleep] STOP sentinel — ending early"; break; }
    idx=$(( idx + 1 ))
    ts="$(date '+%Y-%m-%dT%H:%M:%S')"
    w="$WAVDIR/win-$(printf '%05d' "$idx").wav"
    if record_window "$w" "$WINDOW" "$MIC"; then
        read -r v m a env < <(sense_wav "$w")
        rms="$(measure_rms "$w")"
        echo "$idx,$ts,$v,$m,$a,$env,${rms:-0}" >> "$CSV"
    else
        rm -f "$w"
        echo "$idx,$ts,x,0,0,,0" >> "$CSV"   # gap: no audio this window
    fi
done

echo "[sleep] capture done at $(date '+%H:%M') — building readout"
build_readout "$DIR"
echo "[sleep] readout → $READOUT"
# non-intrusive morning alert (banner only, never audio) so the readout is seen at wake
SUMMARY="$(awk '/Breathing-shaped/{print; exit}' "$READOUT" 2>/dev/null)"
osascript -e "display notification \"${SUMMARY:-readout ready}\" with title \"Sleep readout — $DATE\" subtitle \"$READOUT\"" >/dev/null 2>&1 || true
