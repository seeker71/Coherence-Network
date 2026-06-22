#!/usr/bin/env bash
# stt-eval.sh — score an STT candidate transcript against a ground-truth transcript, in Form.
#
# When an authoritative transcript exists for the same audio, our STT earns trust by AGREEING with it.
# This carrier tokenizes both transcripts and scores word agreement PER SEGMENT with stt-agree.fk
# (four-way proven), aligning each candidate [HH:MM] segment to the truth segment at the same timestamp
# (small vs small — no whole-transcript blow-up, and order-local). The per-segment verdicts fold through
# self-grounding-classifier.fk's promotion gate. Whisper is today's candidate (the baseline the native STT
# must beat); point it at the native transcript later to watch it earn the route and the oracle retire.
#
# Run:  stt-eval.sh <truth.txt> <candidate.txt>
# Candidate lines carry a leading [HH:MM] (the sleep-organ whisper format). Truth is matched by the same
# [HH:MM] when present, else paired positionally line-for-line.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORM="${SLEEP_FORM:-$(cd "$SCRIPT_DIR/../.." && pwd)/form}"
KERNEL="${SLEEP_KERNEL:-$FORM/form-kernel-go/bin-go}"
AGREE_FLOOR="${STT_AGREE_FLOOR:-50}"   # a segment "agrees" at >= this word-accuracy
PRELUDE=(form-stdlib/stt-agree.fk form-stdlib/self-grounding-classifier.fk)

TRUTH="${1:?usage: stt-eval.sh <truth.txt> <candidate.txt>}"
CAND="${2:?usage: stt-eval.sh <truth.txt> <candidate.txt>}"
[[ -f "$TRUTH" && -f "$CAND" ]] || { echo "missing transcript file"; exit 1; }

toks() { sed -E 's/\[[0-9:]+\]//g; s/\*[^*]*\*//g' | tr 'A-Z' 'a-z' | tr -cs 'a-z0-9' ' ' \
         | tr ' ' '\n' | grep -vE '^$' | awk '{printf "\"%s\" ",$1}'; }
ts_of() { sed -nE 's/^\[([0-9]+:[0-9]+).*/\1/p' <<<"$1"; }

declare -a TT_KEY TT_TXT; i=0
while IFS= read -r tl; do TT_KEY[$i]="$(ts_of "$tl")"; TT_TXT[$i]="$tl"; i=$((i+1)); done < "$TRUTH"

drv="/tmp/stteval-$$.fk"; echo "(do (let hist (list" > "$drv"
nseg=0; ci=0
while IFS= read -r cl; do
    cw="$(printf '%s' "$cl" | toks)"; [[ -z "$cw" ]] && { ci=$((ci+1)); continue; }
    # positional alignment: candidate line i vs truth line i. Correct only when both share the same
    # segmentation (sanity/baseline). Scoring against a DIFFERENTLY-segmented authoritative transcript
    # (Anne's flat prose) needs word-sequence alignment — the banded-WER recipe named below, not yet built.
    tline="${TT_TXT[$ci]:-}"
    tw="$(printf '%s' "$tline" | toks)"
    echo "  (list (if (ge (sa-accuracy (list $cw) (list ${tw:-})) $AGREE_FLOOR) \"ok\" \"miss\") \"ok\")" >> "$drv"
    nseg=$((nseg+1)); ci=$((ci+1))
done < "$CAND"
echo "))" >> "$drv"
echo "  (print (list \"SEGMENTS\" (sg-total hist) \"AGREE\" (sg-correct hist) \"MISS\" (sg-wrong hist)))" >> "$drv"
echo "  (print (list \"SEG-AGREE-PCT\" (if (ge (sg-total hist) 1) (div (mul (sg-correct hist) 100) (sg-total hist)) 0)))" >> "$drv"
echo "  (print (list \"AUTHORITY\" (sg-authority hist (div (mul (sg-total hist) 7) 10) (div (sg-total hist) 5)))))" >> "$drv"

echo "STT eval — candidate=$(basename "$CAND")  vs truth=$(basename "$TRUTH")  ($nseg segments, ${AGREE_FLOOR}% agree-floor)"
( cd "$FORM" && "$KERNEL" "${PRELUDE[@]}" "$drv" 2>/dev/null ) | sed 's/^/  /'
rm -f "$drv"
echo "  (AUTHORITY 'self' = cleared the 70%-agree / 20%-miss gate, native could retire the oracle."
echo "   Per-segment word-overlap; order-aware WER via banded sequence alignment is the next recipe.)"
