#!/usr/bin/env bash
# form_cli_judge.sh — measure the REASONING lane: how well a native model's answer
# covers the agent's, as graded by a local oracle judge.
#
# Tool selection is a set problem the native model already wins. Reasoning is the
# hard lane: the native answer must cover the SUBSTANCE of the agent's, which
# set-overlap can't measure. So for each task a LOCAL model gives a one-shot
# answer, a LOCAL oracle judges how well it covers the agent's captured answer
# (0..100), and the Form judge recipe (form-cli-judge.fk) tallies — pass-rate at a
# threshold + grade distribution. The judge is the carrier; the tally is Form.
#
# Usage: form_cli_judge.sh [N] [native-model] [judge-model] [threshold] [corpus]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
N="${1:-5}"; NATIVE="${2:-ollama run coder}"; JUDGE="${3:-ollama run coder}"; THR="${4:-60}"
CORPUS="${5:-${FORM_CLI_CORPUS:-$HOME/.coherence-network/form-cli-corpus/corpus.jsonl}}"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null
[[ -f "$CORPUS" ]] || { echo "no corpus at $CORPUS"; exit 1; }

echo "── reasoning lane: native ($NATIVE) judged ($JUDGE) vs the agent, $N tasks ──"

# pick N substantive tasks: emit task<TAB>agent_answer
PICKS="$(python3 - "$CORPUS" "$N" <<'PY'
import json,sys
path,n=sys.argv[1],int(sys.argv[2])
out=[]
for l in open(path):
    try: r=json.loads(l)
    except: continue
    t=r.get("task","").strip(); a=r.get("answer","").strip()
    if len(t)<40 or len(a)<120: continue       # substantive task AND a real answer
    out.append(t.replace("\n"," ")[:300]+"\t"+a.replace("\n"," ")[:1400])
    if len(out)>=n: break
print("\n".join(out))
PY
)"
[[ -n "$PICKS" ]] || { echo "no substantive (task,answer) pairs found"; exit 1; }

scores=""; i=0
while IFS=$'\t' read -r task agent; do
    [[ -z "$task" ]] && continue
    i=$((i+1))
    # 1. native one-shot answer
    pf="$(mktemp)"; printf 'Task: %s\nGive a concise, concrete answer or approach (a few sentences).' "$task" > "$pf"
    native_ans="$($NATIVE < "$pf" 2>/dev/null | tr '\n' ' ' | head -c 1200)"; rm -f "$pf"
    # 2. local oracle judges coverage of the agent's reference, 0..100
    jf="$(mktemp)"
    printf 'You are grading. REFERENCE answer:\n%s\n\nCANDIDATE answer:\n%s\n\nHow well does the CANDIDATE cover the substance of the REFERENCE? Reply with ONLY an integer 0-100.' "$agent" "$native_ans" > "$jf"
    raw="$($JUDGE < "$jf" 2>/dev/null)"; rm -f "$jf"
    score="$(printf '%s' "$raw" | grep -oE '[0-9]+' | head -1)"; score="${score:-0}"
    [[ "$score" -gt 100 ]] && score=100
    scores="$scores $score"
    printf "  %2d  judge=%3s  task: %s\n" "$i" "$score" "$(printf '%s' "$task" | head -c 56)"
done <<< "$PICKS"

# tally on the kernel (Form is the judge of the scores)
sform="$(printf '%s' "$scores" | sed 's/^ *//; s/  */ /g')"
prog="$(mktemp)"
{ cat "$STD/form-cli-judge.fk"
  echo "(let scores (list $sform))"
  echo "(print (fcj-passed scores $THR))"
  echo "(print (fcj-total scores))"
  echo "(print (fcj-sum scores))"
  echo "(print (fcj-count-grade scores (fcj-grade-poor)))"
  echo "(print (fcj-count-grade scores (fcj-grade-weak)))"
  echo "(print (fcj-count-grade scores (fcj-grade-partial)))"
  echo "(print (fcj-count-grade scores (fcj-grade-strong)))"
  echo "(print (fcj-native-reaches? scores $THR))"
} > "$prog"
o="$("$GO" "$prog" 2>/dev/null)"; rm -f "$prog"
P=$(sed -n '1p' <<<"$o"); T=$(sed -n '2p' <<<"$o"); S=$(sed -n '3p' <<<"$o")
G0=$(sed -n '4p' <<<"$o"); G1=$(sed -n '5p' <<<"$o"); G2=$(sed -n '6p' <<<"$o"); G3=$(sed -n '7p' <<<"$o"); R=$(sed -n '8p' <<<"$o")
pct(){ [[ "${2:-0}" -gt 0 ]] && echo $(( $1 * 100 / $2 )) || echo 0; }
avg(){ [[ "${2:-0}" -gt 0 ]] && echo $(( $1 / $2 )) || echo 0; }

echo
echo "── reasoning-lane score (Form-tallied) ──"
printf "  native pass (>=%s)    %s/%s  (%s%%)\n" "$THR" "$P" "$T" "$(pct "${P:-0}" "${T:-0}")"
printf "  average judge score  %s/100\n" "$(avg "${S:-0}" "${T:-0}")"
printf "  grades   poor %s · weak %s · partial %s · strong %s\n" "${G0:-0}" "${G1:-0}" "${G2:-0}" "${G3:-0}"
echo "  native reaches the lane (majority pass): $([[ "${R:-0}" == "1" ]] && echo yes || echo 'NOT YET — the open frontier')"
echo "  (tool-selection lane is already won natively; reasoning is the hard road.)"
