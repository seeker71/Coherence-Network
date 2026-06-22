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
# FORM is the dir the kernel loads recipes from (expects form-stdlib/*.fk under it). Override with
# SLEEP_FORM to point at a durable copy — so a morning re-analysis survives the worktree being cleaned.
FORM="${SLEEP_FORM:-$ROOT/form}"
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
# Form-native classifier chain (analysis -> features -> nearest-shape recognition), all four-way proven
CLASSIFY_PRELUDES=(form-stdlib/signal-derivative.fk form-stdlib/sleep-sense.fk form-stdlib/feature-vector.fk form-stdlib/nearest-shape.fk form-stdlib/sleep-classify.fk form-stdlib/wav-sense.fk)
REPORT_PRELUDE=(form-stdlib/sleep-report.fk)
SLEEP_CLASSES='"silent" "quiet-breath" "snore" "steady-noise" "loud-event" "sleep-talk"'
# the LOCAL oracle: whisper settles the one identity the envelope can't (snore vs speech). local-only.
WHISPER_MODEL="${SLEEP_WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"

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

# classify one wav through the Form-native classifier -> echo "label strength needs_oracle"
classify_wav() {  # $1 wav
    local drv; drv="$(mktemp /tmp/sleepc-XXXXXX.fk)"
    cat > "$drv" <<EOF
(do (let e (wav-envelope-file "$1" $STEP))
    (print (sc-classify e)) (print (sc-strength e)) (print (sc-needs-oracle? e)))
EOF
    local out; out="$( cd "$FORM" && "$KERNEL" "${CLASSIFY_PRELUDES[@]}" "$drv" 2>/dev/null )"
    rm -f "$drv"
    echo "$(sed -n '1p' <<<"$out") $(sed -n '2p' <<<"$out") $(sed -n '3p' <<<"$out")"
}

# the LOCAL oracle: does this window carry coherent SPEECH? whisper-cli, transcript stays local.
# returns the transcript on stdout when it reads as speech, empty otherwise. honest lane: whisper can
# hallucinate on non-speech, so this is "whisper heard words here", the ground-truth lane the Form
# classifier learns from (self-grounding-classifier.fk), not a final verdict.
oracle_speech() {  # $1 wav -> transcript (only if it reads as speech)
    [[ -x "$(command -v whisper-cli)" && -f "$WHISPER_MODEL" ]] || { echo ""; return; }
    local of; of="$(mktemp /tmp/sleepw-XXXXXX)"
    whisper-cli -m "$WHISPER_MODEL" -f "$1" -nt -oj -of "$of" -t 4 -l auto >/dev/null 2>&1
    local txt=""
    [[ -f "$of.json" ]] && txt="$(jq -r '[.transcription[].text] | join(" ")' "$of.json" 2>/dev/null | tr 'A-Z' 'a-z')"
    rm -f "$of.json" "$of"
    # strip whisper's non-speech markers + punctuation; speech = at least two word-runs survive
    local clean; clean="$(echo "$txt" | sed -E 's/\[[^]]*\]//g; s/\([^)]*\)//g; s/[^a-z ]//g' | tr -s ' ')"
    local words; words="$(echo "$clean" | wc -w | tr -d ' ')"
    if [[ "${words:-0}" -ge 2 ]]; then echo "$(echo "$clean" | tr -s ' ')"; else echo ""; fi
}

# fold classified.csv into a Form-native per-class readout (sleep-report)
build_classified_readout() {  # $1 dir
    local dir="$1"
    local ccsv="$dir/classified.csv" out="$dir/readout-classified.txt"
    [[ -f "$ccsv" ]] || { echo "no classified.csv in $dir"; return 1; }
    ensure_kernel
    # label stream (col 3), quoted, for the Form report
    local labels; labels="$(awk -F, 'NR>1{printf "\"%s\" ",$3}' "$ccsv")"
    local oracle_used; oracle_used="$(awk -F, 'NR>1 && $5=="yes"{n++} END{print n+0}' "$ccsv")"
    local first last; first="$(awk -F, 'NR==2{print $2}' "$ccsv")"; last="$(awk -F, 'END{print $2}' "$ccsv")"
    local drv; drv="$(mktemp /tmp/sleepr-XXXXXX.fk)"
    cat > "$drv" <<EOF
(do (let xs (list ${labels:-}))
    (let classes (list $SLEEP_CLASSES))
    (print (sr-total xs))
    (print (sr-dominant xs classes))
    (print (sr-count xs "silent")) (print (sr-count xs "quiet-breath"))
    (print (sr-count xs "snore"))  (print (sr-count xs "steady-noise"))
    (print (sr-count xs "loud-event")) (print (sr-count xs "sleep-talk"))
    (print (sr-episodes xs "snore")) (print (sr-longest xs "snore")) (print (sr-fraction xs "snore")))
EOF
    local r; r="$( cd "$FORM" && "$KERNEL" "${REPORT_PRELUDE[@]}" "$drv" 2>/dev/null )"; rm -f "$drv"
    local tot dom n_sil n_qb n_sn n_st n_le n_tk sn_ep sn_lg sn_pc
    tot="$(sed -n '1p' <<<"$r")"; dom="$(sed -n '2p' <<<"$r")"
    n_sil="$(sed -n '3p' <<<"$r")"; n_qb="$(sed -n '4p' <<<"$r")"; n_sn="$(sed -n '5p' <<<"$r")"
    n_st="$(sed -n '6p' <<<"$r")"; n_le="$(sed -n '7p' <<<"$r")"; n_tk="$(sed -n '8p' <<<"$r")"
    sn_ep="$(sed -n '9p' <<<"$r")"; sn_lg="$(sed -n '10p' <<<"$r")"; sn_pc="$(sed -n '11p' <<<"$r")"
    {
        echo "Sleep sensing — night of $DATE  (Form-native classification)"
        echo "================================================================"
        echo
        echo "Captured $first  →  $last  ·  ${tot:-0} windows of ${WINDOW}s"
        echo "The night was mostly: ${dom:-—}"
        echo
        echo "What each window's sound looked like (named in Form, four-way proven):"
        printf "   %-14s %s\n" "silent"       "${n_sil:-0}"
        printf "   %-14s %s\n" "quiet-breath" "${n_qb:-0}"
        printf "   %-14s %s   (loud + periodic)\n" "snore" "${n_sn:-0}"
        printf "   %-14s %s   (loud but flat — a fan/AC, not a snore)\n" "steady-noise" "${n_st:-0}"
        printf "   %-14s %s   (a brief loud spike)\n" "loud-event" "${n_le:-0}"
        printf "   %-14s %s   (whisper heard words — likely speech, not a snore)\n" "sleep-talk" "${n_tk:-0}"
        echo
        echo "Snore detail: ${n_sn:-0} windows · ${sn_pc:-0}% of the night · ${sn_ep:-0} episode(s) · longest run ${sn_lg:-0} window(s)"
        echo
        echo "How this was decided"
        echo "--------------------"
        echo "• Each window's energy envelope → a 3-bin fingerprint [loud osc peak] → nearest interned"
        echo "  prototype (Form recipe sleep-classify, proven four-way on Go/Rust/TS/fkwu). Earned"
        echo "  confidence, not asserted — the body's own recognition."
        echo "• The ONE thing the envelope can't settle — snore vs speech, both 'loud + periodic' — was"
        echo "  handed to the LOCAL oracle (whisper, on-device): ${oracle_used:-0} window(s) escalated;"
        echo "  where it heard coherent words the window became 'sleep-talk', else the Form label stood."
        echo "• Honest lane: this names envelope SHAPE, not verified identity; whisper can hallucinate on"
        echo "  non-speech. Nothing left this Mac — no audio, no transcript, no per-window data."
        echo
        echo "(body: sleep-classify.fk + sleep-report.fk, composing feature-vector + nearest-shape; oracle: local whisper)"
    } > "$out"
    echo "$out"
}

# ---- modes -------------------------------------------------------------------
if [[ "${1:-}" == "--readout" ]]; then
    build_readout "${2:-$DIR}"; exit 0
fi

# --classify DIR : re-read the kept WAVs through the Form-native classifier; escalate only the windows
# whose acoustic identity the envelope can't settle (snore/loud-event) to the LOCAL whisper oracle.
if [[ "${1:-}" == "--classify" ]]; then
    cdir="${2:-$DIR}"; ensure_kernel
    ccsv="$cdir/classified.csv"
    echo "idx,ts,label,strength,oracle_used,wav" > "$ccsv"
    i=0; esc=0
    for w in "$cdir"/wav/win-*.wav; do
        [[ -f "$w" ]] || continue
        i=$((i+1))
        read -r label strength needs < <(classify_wav "$w")
        used="no"
        if [[ "${needs:-0}" == "1" ]]; then
            esc=$((esc+1)); used="yes"
            heard="$(oracle_speech "$w")"
            [[ -n "$heard" ]] && label="sleep-talk"
        fi
        ts="$(stat -f '%Sm' -t '%Y-%m-%dT%H:%M:%S' "$w" 2>/dev/null)"
        echo "$i,$ts,${label:-unknown},${strength:-0},$used,$(basename "$w")" >> "$ccsv"
        printf "\r[sleep] classified %d windows (%d escalated to oracle)   " "$i" "$esc" >&2
    done
    echo >&2
    build_classified_readout "$cdir"
    exit 0
fi

# --breathing [DIR] [lo-idx] [hi-idx] : recover RESPIRATORY RATE by autocorrelating a fine (0.5s) energy
# envelope across a block of windows. Breathing is a slow envelope oscillation; the autocorrelation peak
# is its period. Honest gate: low confidence = the rhythm is below the mic's noise floor, not absent.
if [[ "${1:-}" == "--breathing" ]]; then
    bdir="${2:-$DIR}"; blo="${3:-1}"; bhi="${4:-100000}"; ensure_kernel
    NWIN=60; FINE_STEP=2; SPM=120; BLO=4; BHI=16   # 0.5s samples; band 2-8s = 7.5-30 br/min
    # fine-envelope-per-window recipe (raw mean amplitude, NWIN samples), composing wav-sense
    finedrv() { cat <<EOF
(do (defn we-wr (bs s e st) (do (let sp (sub e s)) (if (le sp 0) 0 (div (wav-abs-sum bs s e st 0) (div sp st)))))
    (defn we-wi (bs n i nw st) (do (let w (mul (div (div (sub n 44) nw) 2) 2)) (we-wr bs (add 44 (mul i w)) (add 44 (mul (add i 1) w)) st)))
    (defn we-fl (bs n nw i st) (if (eq i nw) (empty) (cons (we-wi bs n i nw st) (we-fl bs n nw (add i 1) st))))
    (defn we-fine (p nw st) (do (let bs (read_file_bytes p)) (we-fl bs (len bs) nw 0 st)))
    (print (we-fine "$1" $NWIN $FINE_STEP)))
EOF
    }
    echo "[breath] building 0.5s envelope across windows $blo..$bhi ..." >&2
    acc=""; nwins=0
    for w in "$bdir"/wav/win-*.wav; do
        idx=$(basename "$w" .wav | sed 's/win-0*//'); [[ -z "$idx" ]] && idx=0
        [[ "$idx" -ge "$blo" && "$idx" -le "$bhi" ]] || continue
        finedrv "$w" > /tmp/bf-$$.fk
        vals="$( cd "$FORM" && "$KERNEL" form-stdlib/wav-sense.fk /tmp/bf-$$.fk 2>/dev/null | grep -E '^\[' | tr -d '[]' | tr ',' ' ')"
        acc="$acc $vals"; nwins=$((nwins+1))
    done
    rm -f /tmp/bf-$$.fk
    cat > /tmp/br-$$.fk <<EOF
(do (let xs (list $acc))
    (print (br-rate xs $BLO $BHI $SPM)) (print (br-confidence xs $BLO $BHI)) (print (br-peak-lag xs $BLO $BHI)))
EOF
    out="$( cd "$FORM" && "$KERNEL" form-stdlib/breath-rhythm.fk /tmp/br-$$.fk 2>/dev/null )"; rm -f /tmp/br-$$.fk
    rate="$(sed -n 1p <<<"$out")"; conf="$(sed -n 2p <<<"$out")"; lag="$(sed -n 3p <<<"$out")"
    echo
    echo "Respiratory rhythm — $nwins windows (~$((nwins/2)) min of audio)"
    echo "  estimated rate : ${rate:-0} breaths/min   (autocorrelation period = ${lag:-0} × 0.5s)"
    echo "  confidence     : ${conf:-0}/100"
    if [[ "${conf:-0}" -lt 30 ]]; then
        echo "  VERDICT: no reliable breathing rhythm — the periodicity is below the mic's noise floor."
        echo "           This is a SENSOR-PLACEMENT limit, not the analysis: validated to recover a known"
        echo "           rate at confidence ~80 when signal is present. Put the mic near the head (pillow/"
        echo "           nightstand) or use a phone on the mattress (chest motion) to feed it real signal."
    else
        echo "  VERDICT: rhythm detected — breathing held ~${rate} breaths/min over this block."
    fi
    exit 0
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
