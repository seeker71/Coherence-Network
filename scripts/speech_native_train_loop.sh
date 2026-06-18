#!/usr/bin/env bash
# speech_native_train_loop.sh — continuous OFFLINE native speech training loop.
#
# The LOGIC is Form, four-way proven: affine-train.fk (the SGD descent atom folded
# over a corpus), affine-corpus-fit.fk (native-vs-mean-oracle held-out scoring), and
# oracle-flywheel.fk (oracle-reliance = the queries the native model still misses).
# These are the EXACT recipes proven by validate.sh — the same descent the
# form-native transformer scales to millions of weights via backprop. This script is
# a thin host-IO carrier only: it generates content, captures real local audio,
# featurizes, drives the Go kernel on the proven recipe, persists the model, and logs.
#
# What it trains, on REAL content the body runs through, with LOCAL OFFLINE oracles:
#   - TTS lane: predict utterance duration_ms from text length  (the speaking-rate
#     model every TTS duration-predictor needs). Teacher = macOS `say`.
#   - STT lane: predict transcript word-count from audio duration. Teacher = whisper-cli.
#   Content oracle = local LLM via ollama (fresh varied phrases each round, offline);
#   baseline oracle being retired = the predict-the-mean predictor (acf-* / of-*).
#
# Each round: new phrases -> say -> 16kHz PCM -> whisper-cli -> real (text,audio) rows
# appended to a GROWING corpus; the persisted model (two fixed-point ints, scale 1000)
# is LOADED and trained further (it continues, it does not re-init); held-out loss,
# native-correct, mean-oracle-correct, and oracle-calls are logged. More SAMPLES (not
# epochs) is the honest lever — exactly as oracle-flywheel.fk proves.
#
# Persists under $STATE so you launch it, walk offline, and it keeps learning:
#   corpus.jsonl  metrics.csv  tts.model  stt.model  round
#
# Usage: scripts/speech_native_train_loop.sh [--rounds N] [--batch K] [--sleep S]
#                                            [--ollama MODEL] [--voice V] [--state DIR]
#   --rounds N   stop after N rounds (default 0 = run until Ctrl-C)
#   --batch  K   new phrases captured per round (default 5)
#   --sleep  S   seconds between rounds (default 3)
#   --ollama M   local content-oracle model (default llama3.2:3b; empty = bank only)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"
GO="$ROOT/form/form-kernel-go/bin-go"

ROUNDS=0
BATCH=5
SLEEP_S=3
OLLAMA_MODEL="llama3.2:3b"
VOICE="${SPEECH_TEACHER_VOICE:-Samantha}"
STATE="${SPEECH_NATIVE_TRAIN_STATE:-$HOME/.coherence-network/speech-native-train}"
WHISPER_MODEL="${WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3-turbo.bin}"

# fixed-point training config — the proven conditioning (affine-corpus-fit-band.fk:
# feature-scale features, lr=3, ~40 epochs, scale 1000). EP per round is small so
# accumulating SAMPLES (the honest lever) drives generalization across rounds.
LR=3
EP=24
TTS_FX=50      # chars * 50  -> x lands in the proven ~400..2700 band
TTS_TOL=200    # held-out hit within 200 ms
STT_FY=300     # words * 300 -> y conditions against duration_ms x
STT_TOL=400    # held-out hit within ~1.3 words

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rounds) ROUNDS="$2"; shift 2 ;;
        --batch)  BATCH="$2"; shift 2 ;;
        --sleep)  SLEEP_S="$2"; shift 2 ;;
        --ollama) OLLAMA_MODEL="$2"; shift 2 ;;
        --voice)  VOICE="$2"; shift 2 ;;
        --state)  STATE="$2"; shift 2 ;;
        -h|--help) sed -n '1,40p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "FAIL missing tool: $1" >&2; exit 1; }; }
need say; need afconvert; need sox; need whisper-cli; need jq; need awk
[[ -f "$WHISPER_MODEL" ]] || { echo "FAIL missing whisper model: $WHISPER_MODEL" >&2; exit 1; }
[[ -x "$GO" ]] || { echo "building Go kernel…"; ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) || exit 1; }

# portable bounded-run for the content oracle: macOS ships no GNU `timeout`.
# gtimeout (brew coreutils) or timeout if present; else run unguarded (local daemon).
OLLAMA_TIMEOUT=60
if command -v gtimeout >/dev/null 2>&1; then TO=(gtimeout "$OLLAMA_TIMEOUT")
elif command -v timeout >/dev/null 2>&1; then TO=(timeout "$OLLAMA_TIMEOUT")
else TO=(); fi

mkdir -p "$STATE/.cap"
CORPUS="$STATE/corpus.jsonl"
METRICS="$STATE/metrics.csv"
TTS_MODEL="$STATE/tts.model"
STT_MODEL="$STATE/stt.model"
ROUND_FILE="$STATE/round"
PRELUDE="$STATE/.prelude.fk"

# the four-way-proven recipe stack as the kernel prelude. abs is core.fk's only
# borrow; core.fk is BML surface (needs the source-compiler), so we provide the
# one S-expr def directly and cat the proven S-expr recipes — the form_cli_*.sh pattern.
{
    echo "(defn abs (n) (if (lt n 0) (sub 0 n) n))"
    cat "$STD/affine-train.fk" "$STD/affine-corpus-fit.fk" "$STD/oracle-flywheel.fk"
} > "$PRELUDE"

[[ -f "$TTS_MODEL" ]] || echo "0 0" > "$TTS_MODEL"
[[ -f "$STT_MODEL" ]] || echo "0 0" > "$STT_MODEL"
[[ -f "$ROUND_FILE" ]] || echo "0" > "$ROUND_FILE"
[[ -f "$METRICS" ]] || echo "ts,round,lane,corpus_n,train_n,held_n,loss0,lossT,held_loss,native_correct,oracle_correct,oracle_calls,w,b" > "$METRICS"

# ---- local phrase bank (offline fallback / seed when ollama is slow or absent) ----
# Deliberately WIDE length spread (2 words → 20+). Variance is what lets the native
# slope model beat the predict-the-mean oracle: the mean misses the short and long
# extremes, the learned chars→duration line catches them. Uniform lengths would make
# "predict the mean" trivially win and hide the learning.
BANK=(
"yes"
"good morning"
"the cat slept"
"rain again today"
"she closed the door"
"birds gathered at dusk"
"he read the letter twice"
"warm bread waited on the table"
"a small boat crossed the wide bay"
"old friends met again after many years"
"the train arrived late on a cold snowy night"
"she planted rows of tomatoes along the garden fence"
"the orchestra tuned quietly before the very first song began"
"they shared a long slow meal and told stories until midnight"
"the mountain path grew steep and stony as the gray clouds gathered overhead"
"he fixed the old bicycle in the cold garage while the radio played softly"
"a gentle evening wind carried the sharp clean scent of pine across the valley"
"she sketched the busy harbor from the high cliff as the morning fog slowly lifted"
"the children laughed and chased each other through the bright red and gold autumn leaves"
"the lantern swayed above the wooden door and threw long shadows across the quiet snowy yard"
"the kettle whistled sharply as the heavy snow kept falling past the small frosted kitchen window"
"two gray cats slept curled beneath the warm radiator while the winter storm rattled the old windows all night"
"the river froze slowly along its quiet shaded edge and the whole valley grew still under the pale afternoon light"
"warm"
"all done"
"the lake was calm"
"a fox crossed the road"
"the market opened at dawn"
"she tied her scarf against the wind"
"a single bright star rose above the rooftops"
"the baker lit the ovens long before sunrise that morning"
"horses grazed in the misty lower field as the sun climbed slowly"
"the violin echoed through the empty theater and faded into the dark"
"they counted the falling stars from the back porch until the cold drove them inside"
"a small paper boat sailed down the rushing gutter and vanished beneath the iron grate"
)

emit_phrases() {
    local n="$1" out lines
    if [[ -n "$OLLAMA_MODEL" ]] && command -v ollama >/dev/null 2>&1; then
        out="$(printf '%s\n' "Write exactly $n short plain English sentences about everyday life, 5 to 10 words each, one sentence per line, no numbering, no quotes." \
            | ${TO[@]+"${TO[@]}"} ollama run "$OLLAMA_MODEL" 2>/dev/null \
            | sed -E 's/^[[:space:]]*[0-9]+[.)-]?[[:space:]]*//; s/^[-*][[:space:]]*//; s/["“”]//g' \
            | awk 'NF>=4 && NF<=14 {print}' \
            | head -n "$n")"
        lines="$(printf '%s\n' "$out" | grep -c .)"
        if [[ "${lines:-0}" -ge 1 ]]; then
            printf '%s\n' "$out"
            # top up from bank if the oracle returned fewer than asked
            local missing=$(( n - lines ))
            while [[ "$missing" -gt 0 ]]; do
                printf '%s\n' "${BANK[$RANDOM % ${#BANK[@]}]}"
                missing=$(( missing - 1 ))
            done
            return
        fi
    fi
    local i
    for ((i=0; i<n; i++)); do printf '%s\n' "${BANK[$RANDOM % ${#BANK[@]}]}"; done
}

# capture one phrase into a real receipt and append a row to the growing corpus.
capture_phrase() {
    local phrase="$1"
    local capdir="$STATE/.cap/$(date -u +%Y%m%dT%H%M%S)-$RANDOM"
    SPEECH_TEACHER_OUT="$capdir" WHISPER_MODEL="$WHISPER_MODEL" SPEECH_TEACHER_VOICE="$VOICE" \
        "$ROOT/scripts/speech_teacher_receipt.sh" "$phrase" >/dev/null 2>&1 || return 1
    local rj="$capdir/speech-teacher-receipt.json"
    [[ -s "$rj" ]] || return 1
    jq -c '{
        text, transcript,
        duration_ms, samples, rms_ppm, rough_hz,
        chars: (.text | length),
        words: (.transcript | ascii_downcase | gsub("[^a-z ]"; " ") | gsub(" +"; " ")
                 | ltrimstr(" ") | rtrimstr(" ") | split(" ") | map(select(length > 0)) | length),
        overlap: .transcript_overlap_percent,
        audio_sha: .audio_sha256
    }' "$rj" >> "$CORPUS"
    rm -rf "$capdir"
}

# featurize the whole corpus for a lane into Form (x y) train/held lists.
# args: which(train|held) xexpr yexpr  (bare jq exprs over a row). filter valid
# rows, reindex, every 5th (index 0,5,10,…) -> held-out, the rest -> train.
form_rows() {
    local which="$1" xexpr="$2" yexpr="$3"
    local mod
    if [[ "$which" == "held" ]]; then mod='== 0'; else mod='!= 0'; fi
    jq -s -r '
        [ .[] | select(.duration_ms > 0 and .words > 0 and .chars > 0) ]
        | to_entries
        | [ .[] | select((.key % 5) '"$mod"') | .value
            | "(list \('"$xexpr"') \('"$yexpr"'))" ]
        | "(list " + (join(" ")) + ")"
    ' "$CORPUS"
}

# count valid rows in the train or held split (same filter→reindex→split basis).
count_rows() {
    local which="$1" mod
    if [[ "$which" == "held" ]]; then mod='== 0'; else mod='!= 0'; fi
    jq -s '[ .[] | select(.duration_ms>0 and .words>0 and .chars>0) ]
           | to_entries | map(select((.key % 5) '"$mod"')) | length' "$CORPUS"
}

train_lane() {
    local lane="$1" modelfile="$2" xexpr="$3" yexpr="$4" tol="$5"
    local round; round="$(cat "$ROUND_FILE")"
    local w b; read -r w b < "$modelfile"
    local train held ntrain nheld prog out
    train="$(form_rows train "$xexpr" "$yexpr")"
    held="$(form_rows held "$xexpr" "$yexpr")"
    ntrain="$(count_rows train)"
    nheld="$(count_rows held)"
    if [[ "${ntrain:-0}" -lt 1 || "${nheld:-0}" -lt 1 ]]; then
        printf "  %-4s round %-3s  corpus growing — need >=1 train and >=1 held row (have %s/%s)\n" "$lane" "$round" "${ntrain:-0}" "${nheld:-0}"
        return
    fi
    prog="$(mktemp "${TMPDIR:-/tmp}/speechtrain.XXXXXX.fk")"
    cat "$PRELUDE" > "$prog"
    {
        echo "(do"
        echo "  (let s0 (list $w $b))"
        echo "  (let train $train)"
        echo "  (let held $held)"
        echo "  (let sT (aff-train s0 train $LR $EP))"
        echo "  (let mean (acf-mean-y train))"
        echo "  (print (aff-w sT))"
        echo "  (print (aff-b sT))"
        echo "  (print (aff-corpus-loss s0 train))"
        echo "  (print (aff-corpus-loss sT train))"
        echo "  (print (aff-corpus-loss sT held))"
        echo "  (print (acf-native-correct sT held $tol))"
        echo "  (print (acf-oracle-correct mean held $tol))"
        echo "  (print (of-oracle-calls sT held $tol))"
        echo "  0)"
    } >> "$prog"
    out="$("$GO" "$prog" 2>/dev/null | grep -E '^-?[0-9]+$')"
    rm -f "$prog"
    local nw nb loss0 lossT heldloss nc oc ocalls
    nw=$(sed -n '1p' <<<"$out"); nb=$(sed -n '2p' <<<"$out")
    loss0=$(sed -n '3p' <<<"$out"); lossT=$(sed -n '4p' <<<"$out"); heldloss=$(sed -n '5p' <<<"$out")
    nc=$(sed -n '6p' <<<"$out"); oc=$(sed -n '7p' <<<"$out"); ocalls=$(sed -n '8p' <<<"$out")
    if [[ -z "${nw:-}" ]]; then
        printf "  %-4s round %-3s  kernel produced no result (skipped)\n" "$lane" "$round"
        return
    fi
    echo "$nw $nb" > "$modelfile"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),$round,$lane,$((ntrain+nheld)),$ntrain,$nheld,$loss0,$lossT,$heldloss,$nc,$oc,$ocalls,$nw,$nb" >> "$METRICS"
    printf "  %-4s round %-3s  train=%-3s held=%-3s  loss %-8s→ %-8s  held-loss=%-8s  native=%s/%s  mean-oracle=%s/%s  oracle-calls=%s  w=%s b=%s\n" \
        "$lane" "$round" "$ntrain" "$nheld" "$loss0" "$lossT" "$heldloss" "$nc" "$nheld" "$oc" "$nheld" "$ocalls" "$nw" "$nb"
}

trap 'echo; echo "stopped at round $(cat "$ROUND_FILE") — state in $STATE"; exit 0' INT TERM

echo "── native speech training loop (logic is four-way Form; carrier is host-io) ──"
echo "   state=$STATE  model=$(basename "$WHISPER_MODEL")  oracle=${OLLAMA_MODEL:-bank-only}  batch=$BATCH"
echo "   TTS lane: duration_ms  from  chars*$TTS_FX   |   STT lane: words*$STT_FY  from  duration_ms"
echo

r=0
while :; do
    round="$(( $(cat "$ROUND_FILE") + 1 ))"
    echo "$round" > "$ROUND_FILE"
    captured=0
    while IFS= read -r phrase; do
        [[ -n "$phrase" ]] || continue
        if capture_phrase "$phrase"; then captured=$((captured+1)); fi
    done < <(emit_phrases "$BATCH")
    printf "round %-3s  captured %s real utterances (corpus now %s rows)\n" \
        "$round" "$captured" "$(grep -c . "$CORPUS" 2>/dev/null || echo 0)"
    #              lane  model        x (feature)        y (target)        tol
    train_lane "TTS" "$TTS_MODEL" '.chars*'"$TTS_FX"  '.duration_ms'      "$TTS_TOL"
    train_lane "STT" "$STT_MODEL" '.duration_ms'      '.words*'"$STT_FY"  "$STT_TOL"
    echo
    r=$((r+1))
    [[ "$ROUNDS" -gt 0 && "$r" -ge "$ROUNDS" ]] && break
    sleep "$SLEEP_S"
done

echo "done — $r rounds. metrics: $METRICS"
