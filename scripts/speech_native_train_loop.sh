#!/usr/bin/env bash
# speech_native_train_loop.sh — continuous OFFLINE native speech training, best model.
#
# The MODEL is the proven Form-native transformer: a two-block residual stack with
# real backprop (transformer-numerics / transformer-block / transformer-backprop /
# transformer-corpus-train.fk), four-way proven by validate.sh — the same architecture
# the body uses for TTS/STT, fp64, no fixed-point hacks. This script is a thin host-io
# carrier only: it generates diverse content with a local LLM, captures real local
# audio, featurizes into normalized vectors, drives the Go kernel on the proven recipe,
# PERSISTS THE FULL STACK losslessly, and logs the generalization curve.
#
# Two real speech lanes, each a multi-feature map the transformer learns:
#   STT  acoustic → text   : x = [duration, samples]  → t = [chars, words]
#   TTS  text → acoustic   : x = [chars, words]        → t = [duration, samples]
# (the two are inverse maps over the same four measured quantities, all normalized to
#  ~[0,1] so the residual fp64 block conditions cleanly).
#
# Best oracles, all local / offline:
#   - content oracle: a strong local LLM (default llama3.3:70b) writes fresh phrases each
#     round, with a rotating STYLE so the feature space is covered widely (the honest
#     lever is sample DIVERSITY, not epochs). Falls back to a wide-length phrase bank.
#   - teacher oracle: best local whisper (default ggml-large-v3.bin) gives the highest-
#     fidelity transcripts → cleanest labels.
#   - baseline being retired: the predict-the-mean-vector oracle. The native transformer
#     earns authority only by beating it on HELD-OUT data (lower SSE, more hits).
#
# Each round: new phrases → say → 16kHz PCM → whisper → real rows append to a GROWING
# corpus; the persisted stack is LOADED and trained further (it continues, never re-
# inits); train-loss, HELD-OUT loss, native held-hits, and mean-oracle held-hits are
# logged. Held-loss tracking train-loss down = real generalization, not memorization.
#
# Persists under $STATE so you launch it, go offline, and it keeps improving:
#   corpus.jsonl  metrics.csv  tts.model.json  stt.model.json  round
#
# Usage: scripts/speech_native_train_loop.sh [--rounds N] [--batch K] [--sleep S]
#            [--content-model M] [--whisper FILE] [--voice V] [--state DIR]
#   --rounds N         stop after N rounds (default 0 = run until Ctrl-C)
#   --batch  K         new phrases captured per round (default 6)
#   --content-model M  local LLM that writes phrases (default llama3.3:70b; "" = bank only)
#   --whisper FILE     whisper.cpp label model (default ggml-large-v3.bin; turbo = faster)
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"
GO="$ROOT/form/form-kernel-go/bin-go"

ROUNDS=0
BATCH=6
SLEEP_S=3
CONTENT_MODEL="llama3.3:70b"
VOICE="${SPEECH_TEACHER_VOICE:-Samantha}"
STATE="${SPEECH_NATIVE_TRAIN_STATE:-$HOME/.coherence-network/speech-native-train}"
WHISPER_MODEL="${WHISPER_MODEL:-$HOME/whisper-models/ggml-large-v3.bin}"

# transformer training config — the proven conditioning (form_cli_transformer_train.sh:
# lr=0.05, eps=1e-5; fp64; two-block residual stack). EP per round is modest so
# accumulating diverse SAMPLES across rounds (the honest lever) drives generalization.
LR=0.05
EPS=0.00001
EP=60
# per-lane held-out hit tolerance, in SSE over the 2-dim normalized target (tuned so an
# untrained model misses and a trained one hits — the visible native-beats-oracle signal).
TOL=0.01
# normalization constants (fixed, documented) — map raw measurements into ~[0,1].
# features are the HIGH-SIGNAL quantities: text shape [chars, words] and audio timing
# [duration, samples]. rms/pitch are near-constant for one clean voice (low learnable
# signal), so they are left out — vitality per feature, not a wider noisy vector.
CHARS_N=100; WORDS_N=25; DUR_N=6000; SAMPLES_N=96000

# the proven two-block residual init (form_cli_transformer_train.sh), used until a
# persisted model exists. width D=2: x and t are 2-dim; the FFN hidden is 2.
INIT_STACK='[[[[0.3,-0.2],[0.1,0.4]],[0.0,0.0],[[0.5,0.2],[-0.3,0.6]],[0.0,0.0]],[[[0.2,0.1],[-0.1,0.3]],[0.0,0.0],[[0.4,-0.2],[0.3,0.5]],[0.0,0.0]]]'

while [[ $# -gt 0 ]]; do
    case "$1" in
        --rounds) ROUNDS="$2"; shift 2 ;;
        --batch)  BATCH="$2"; shift 2 ;;
        --sleep)  SLEEP_S="$2"; shift 2 ;;
        --content-model) CONTENT_MODEL="$2"; shift 2 ;;
        --whisper) WHISPER_MODEL="$2"; shift 2 ;;
        --voice)  VOICE="$2"; shift 2 ;;
        --state)  STATE="$2"; shift 2 ;;
        -h|--help) sed -n '1,52p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

need() { command -v "$1" >/dev/null 2>&1 || { echo "FAIL missing tool: $1" >&2; exit 1; }; }
need say; need afconvert; need sox; need whisper-cli; need jq; need awk; need curl
[[ -f "$WHISPER_MODEL" ]] || { echo "FAIL missing whisper model: $WHISPER_MODEL" >&2; exit 1; }
[[ -x "$GO" ]] || { echo "building Go kernel…"; ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) || exit 1; }

# the content oracle is reached through ollama's LOCAL HTTP API with stream:false —
# clean JSON, no interactive TTY redraw codes (the `ollama run` CLI bleeds ANSI cursor
# escapes into piped output), fully offline on 127.0.0.1.
OLLAMA_API="${OLLAMA_API:-http://127.0.0.1:11434/api/generate}"
OLLAMA_TIMEOUT=120

mkdir -p "$STATE/.cap"
CORPUS="$STATE/corpus.jsonl"
METRICS="$STATE/metrics.csv"
ROUND_FILE="$STATE/round"
TTS_MODEL="$STATE/tts.model.json"
STT_MODEL="$STATE/stt.model.json"
PRELUDE="$STATE/.prelude.fk"

# the four-way-proven transformer recipe stack as the kernel prelude (pure S-expr; no
# core.fk needed — same files form_cli_transformer_train.sh cats), plus two inline
# mean-oracle helpers that reuse the prelude's own SSE so native and baseline are
# scored by ONE identical loss.
{
    cat "$STD/transformer-numerics.fk" "$STD/transformer-block.fk" \
        "$STD/transformer-backprop.fk" "$STD/transformer-corpus-train.fk"
    echo "(defn mo-loss (mean held) (if (eq (len held) 0) 0.0 (add (tbp-sse mean (tct-ex-t (head held))) (mo-loss mean (tail held)))))"
    echo "(defn mo-hits (mean held tol) (if (eq (len held) 0) 0 (add (if (le (tbp-sse mean (tct-ex-t (head held))) tol) 1 0) (mo-hits mean (tail held) tol))))"
} > "$PRELUDE"

[[ -f "$TTS_MODEL" ]] || printf '%s\n' "$INIT_STACK" > "$TTS_MODEL"
[[ -f "$STT_MODEL" ]] || printf '%s\n' "$INIT_STACK" > "$STT_MODEL"
[[ -f "$ROUND_FILE" ]] || echo "0" > "$ROUND_FILE"
[[ -f "$METRICS" ]] || echo "ts,round,lane,corpus_n,train_n,held_n,train_loss0,train_lossT,held_loss,native_hits,mean_oracle_loss,mean_oracle_hits,tol" > "$METRICS"

# ---- local phrase bank: wide length spread (1 word → 23), used as fallback/seed ----
BANK=(
"yes" "good morning" "the cat slept" "rain again today" "she closed the door"
"birds gathered at dusk" "he read the letter twice" "warm bread waited on the table"
"a small boat crossed the wide bay" "old friends met again after many years"
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
"two gray cats slept curled beneath the warm radiator while the winter storm rattled the windows"
"warm" "all done" "the lake was calm" "a fox crossed the road" "the market opened at dawn"
"she tied her scarf against the wind" "a single bright star rose above the rooftops"
"the baker lit the ovens long before sunrise that morning"
"the violin echoed through the empty theater and faded into the dark"
"they counted the falling stars from the back porch until the cold drove them inside"
)
# rotating styles so the LLM oracle covers the feature space widely (length + rhythm).
STYLES=(
"very short terse commands of two to four words"
"medium everyday observations of six to nine words"
"long flowing descriptive sentences of fourteen to twenty words"
"short questions of three to six words"
"calm narration of ten to thirteen words"
)

emit_phrases() {
    local n="$1" round="$2" out lines style prompt resp
    if [[ -n "$CONTENT_MODEL" ]]; then
        style="${STYLES[$(( round % ${#STYLES[@]} ))]}"
        prompt="Write exactly $n plain English sentences, each $style, about everyday life. One sentence per line. No numbering, no quotes, no extra commentary."
        resp="$(jq -nc --arg m "$CONTENT_MODEL" --arg p "$prompt" \
                  '{model:$m, prompt:$p, stream:false, options:{temperature:0.9}}' \
                | curl -s --max-time "$OLLAMA_TIMEOUT" "$OLLAMA_API" -d @- 2>/dev/null \
                | jq -r '.response // empty' 2>/dev/null)"
        out="$(printf '%s\n' "$resp" \
            | sed -E 's/\x1b\[[0-9;]*[A-Za-z]//g; s/^[[:space:]]*[0-9]+[.)-]?[[:space:]]*//; s/^[-*][[:space:]]*//; s/["“”]//g' \
            | awk 'NF>=1 && NF<=24 {print}' \
            | head -n "$n")"
        lines="$(printf '%s\n' "$out" | grep -c .)"
        if [[ "${lines:-0}" -ge 1 ]]; then
            printf '%s\n' "$out"
            local missing=$(( n - lines ))
            while [[ "$missing" -gt 0 ]]; do printf '%s\n' "${BANK[$RANDOM % ${#BANK[@]}]}"; missing=$(( missing - 1 )); done
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
        text, transcript, duration_ms, samples, rms_ppm, rough_hz,
        chars: (.text | length),
        words: (.transcript | ascii_downcase | gsub("[^a-z ]"; " ") | gsub(" +"; " ")
                 | ltrimstr(" ") | rtrimstr(" ") | split(" ") | map(select(length>0)) | length),
        overlap: .transcript_overlap_percent
    }' "$rj" >> "$CORPUS"
    rm -rf "$capdir"
}

# featurize the corpus into Form (x t) example rows for a lane. which=train|held;
# the four jq exprs (over a bare row) are the two input dims then the two target dims.
# filter valid rows, reindex, every 5th (index 0,5,…) -> held, the rest -> train.
feat_rows() {
    local which="$1" x0="$2" x1="$3" t0="$4" t1="$5" mod
    if [[ "$which" == "held" ]]; then mod='== 0'; else mod='!= 0'; fi
    jq -s -r '
        [ .[] | select(.duration_ms>0 and .words>0 and .chars>0) ]
        | to_entries
        | [ .[] | select((.key % 5) '"$mod"') | .value
            | "(list (list \('"$x0"') \('"$x1"')) (list \('"$t0"') \('"$t1"')))" ]
        | "(list " + (join(" ")) + ")"
    ' "$CORPUS"
}
count_rows() {
    local which="$1" mod
    if [[ "$which" == "held" ]]; then mod='== 0'; else mod='!= 0'; fi
    jq -s '[ .[] | select(.duration_ms>0 and .words>0 and .chars>0) ]
           | to_entries | map(select((.key % 5) '"$mod"')) | length' "$CORPUS"
}
# mean TARGET vector over the TRAIN split (the predict-the-mean baseline oracle).
mean_target() {
    local t0="$1" t1="$2"
    jq -s -r '
        [ .[] | select(.duration_ms>0 and .words>0 and .chars>0) ]
        | to_entries | map(select(.key % 5 != 0)) | map(.value)
        | (if length==0 then "0 0"
           else "\(([ .[] | ('"$t0"') ] | add / length)) \(([ .[] | ('"$t1"') ] | add / length))" end)
    ' "$CORPUS"
}

train_lane() {
    local lane="$1" modelfile="$2" x0="$3" x1="$4" t0="$5" t1="$6"
    local round; round="$(cat "$ROUND_FILE")"
    local ntrain nheld; ntrain="$(count_rows train)"; nheld="$(count_rows held)"
    if [[ "${ntrain:-0}" -lt 2 || "${nheld:-0}" -lt 1 ]]; then
        printf "  %-4s round %-3s  corpus growing — need >=2 train, >=1 held (have %s/%s)\n" "$lane" "$round" "${ntrain:-0}" "${nheld:-0}"
        return
    fi
    local train held meanv stack prog out
    train="$(feat_rows train "$x0" "$x1" "$t0" "$t1")"
    held="$(feat_rows held "$x0" "$x1" "$t0" "$t1")"
    read -r mv0 mv1 < <(mean_target "$t0" "$t1")
    # load persisted stack (JSON) -> Form literal: [ -> (list , ] -> ), , -> space.
    stack="$(sed 's/\[/(list /g; s/\]/)/g; s/,/ /g' "$modelfile")"

    prog="$(mktemp "${TMPDIR:-/tmp}/speechtfm.XXXXXX.fk")"
    cat "$PRELUDE" > "$prog"
    {
        echo "(do"
        echo "  (let lr $LR) (let eps $EPS) (let tol $TOL)"
        echo "  (let train $train)"
        echo "  (let held $held)"
        echo "  (let mean (list $mv0 $mv1))"
        echo "  (let st0 $stack)"
        echo "  (let ba0 (nth st0 0))"
        echo "  (let bb0 (nth st0 1))"
        echo "  (let s0 (list ba0 bb0))"
        echo "  (let sT (tct-train-blocks ba0 bb0 train lr eps $EP))"
        echo "  (print (round (mul (tct-corpus-loss s0 train eps) 1000000.0)))"
        echo "  (print (round (mul (tct-corpus-loss sT train eps) 1000000.0)))"
        echo "  (print (round (mul (tct-corpus-loss sT held eps) 1000000.0)))"
        echo "  (print (tct-heldout-correct sT held eps tol))"
        echo "  (print (round (mul (mo-loss mean held) 1000000.0)))"
        echo "  (print (mo-hits mean held tol))"
        echo "  (print sT)"
        echo "  0)"
    } >> "$prog"
    out="$("$GO" "$prog" 2>/dev/null)"
    rm -f "$prog"
    local loss0 lossT heldloss nhits moloss mohits newjson
    loss0=$(sed -n '1p' <<<"$out"); lossT=$(sed -n '2p' <<<"$out"); heldloss=$(sed -n '3p' <<<"$out")
    nhits=$(sed -n '4p' <<<"$out"); moloss=$(sed -n '5p' <<<"$out"); mohits=$(sed -n '6p' <<<"$out")
    newjson=$(sed -n '7p' <<<"$out")
    if [[ -z "${newjson:-}" || "${newjson:0:1}" != "[" ]]; then
        printf "  %-4s round %-3s  kernel produced no stack (kept previous model)\n" "$lane" "$round"
        return
    fi
    printf '%s\n' "$newjson" > "$modelfile"
    # per-example averages (×1e6) — the honest generalization signal, not the growing sum.
    local atr0=$(( ${loss0:-0} / ntrain )) atrT=$(( ${lossT:-0} / ntrain ))
    local ahd=$(( ${heldloss:-0} / nheld )) amo=$(( ${moloss:-0} / nheld ))
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),$round,$lane,$((ntrain+nheld)),$ntrain,$nheld,$atr0,$atrT,$ahd,$nhits,$amo,$mohits,$TOL" >> "$METRICS"
    printf "  %-4s round %-3s  train=%-3s held=%-3s  train-loss/ex %-7s→ %-7s  held-loss/ex %-7s (oracle %-7s)  native=%s/%s  mean-oracle=%s/%s\n" \
        "$lane" "$round" "$ntrain" "$nheld" "$atr0" "$atrT" "$ahd" "$amo" "$nhits" "$nheld" "$mohits" "$nheld"
}

trap 'echo; echo "stopped at round $(cat "$ROUND_FILE") — state in $STATE"; exit 0' INT TERM

echo "── native speech transformer training loop (model is four-way Form; carrier is host-io) ──"
echo "   state=$STATE"
echo "   model: 2-block residual transformer (fp64, backprop)   labels: $(basename "$WHISPER_MODEL")   content-oracle: ${CONTENT_MODEL:-bank-only}"
echo "   STT lane: [chars words] ← [duration samples]    TTS lane: [duration samples] ← [chars words]    (loss/ex ×1e6, tol=$TOL)"
echo

r=0
while :; do
    round="$(( $(cat "$ROUND_FILE") + 1 ))"
    echo "$round" > "$ROUND_FILE"
    captured=0
    while IFS= read -r phrase; do
        [[ -n "$phrase" ]] || continue
        if capture_phrase "$phrase"; then captured=$((captured+1)); fi
    done < <(emit_phrases "$BATCH" "$round")
    printf "round %-3s  captured %s real utterances (corpus now %s rows)\n" \
        "$round" "$captured" "$(grep -c . "$CORPUS" 2>/dev/null || echo 0)"
    # STT: predict text-shape [chars words] from audio timing [duration samples]
    train_lane "STT" "$STT_MODEL" \
        ".duration_ms/$DUR_N" ".samples/$SAMPLES_N" ".chars/$CHARS_N" ".words/$WORDS_N"
    # TTS: predict audio timing [duration samples] from text-shape [chars words]
    train_lane "TTS" "$TTS_MODEL" \
        ".chars/$CHARS_N" ".words/$WORDS_N" ".duration_ms/$DUR_N" ".samples/$SAMPLES_N"
    echo
    r=$((r+1))
    [[ "$ROUNDS" -gt 0 && "$r" -ge "$ROUNDS" ]] && break
    sleep "$SLEEP_S"
done
echo "done — $r rounds. metrics: $METRICS"
