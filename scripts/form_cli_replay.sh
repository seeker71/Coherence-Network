#!/usr/bin/env bash
# form_cli_replay.sh — measure how the native models do against the agent.
#
# For each sample in the corpus, ask a LOCAL model to predict which tools it would
# reach for on that task, then score the prediction against the tools the agent
# actually used — through the Form score recipe (form-cli-score.fk, champion =
# the agent reference, challenger = the native model). Reports native match rate
# vs an always-Bash baseline, so the signal is honest: does the native model
# carry real tool-selection skill, or just guess the most common tool?
#
# The scoring is Form (the kernel computes overlap + match + tally); this shell
# runs the predictor and tallies the report. No remote calls — the model is local.
#
# Usage: form_cli_replay.sh [N] [local-teacher-command] [corpus]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
N="${1:-12}"; TEACHER="${2:-ollama run coder}"
CORPUS="${3:-${FORM_CLI_CORPUS:-$HOME/.coherence-network/form-cli-corpus/corpus.jsonl}}"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null
[[ -f "$CORPUS" ]] || { echo "no corpus at $CORPUS"; exit 1; }

echo "── replay: local teacher ($TEACHER) vs the agent, on $N tasks ──"
KNOWN="Bash Read Write Edit Grep Glob Agent"

# pick N substantive tasks; emit "agent_tools<TAB>task" per line
mapfile_compat() { while IFS= read -r l; do printf '%s\n' "$l"; done; }
PICKS="$(python3 - "$CORPUS" "$N" <<'PY'
import json,sys
path,n=sys.argv[1],int(sys.argv[2])
KNOWN={"Bash","Read","Write","Edit","Grep","Glob","Agent"}
out=[]
for l in open(path):
    try: r=json.loads(l)
    except: continue
    t=r.get("task","").strip()
    if len(t)<28: continue
    tools=[]
    for s in r.get("steps",[]):
        tn=s.get("tool")
        if tn in KNOWN and tn not in tools: tools.append(tn)
    if not tools: continue
    out.append((",".join(tools), t.replace("\n"," ")[:240]))
    if len(out)>=n: break
for a,t in out: print(a+"\t"+t)
PY
)"
[[ -n "$PICKS" ]] || { echo "no substantive tasks found"; exit 1; }

# for each task: ask the model to predict tools, build a Form trial
trials=""; baseline=""; shown=""
i=0
while IFS=$'\t' read -r agent_tools task; do
    [[ -z "$task" ]] && continue
    i=$((i+1))
    prompt="You are a coding agent with these tools: $KNOWN. For the task below, list ONLY the tool names you would use, one per line, most important first, nothing else.
Task: $task"
    pf="$(mktemp)"; printf '%s' "$prompt" > "$pf"
    raw="$($TEACHER < "$pf" 2>/dev/null)"; rm -f "$pf"
    # extract known tool names from the reply, preserving order, unique
    native="$(printf '%s\n' "$raw" | grep -oiE 'Bash|Read|Write|Edit|Grep|Glob|Agent' \
        | awk '{print toupper(substr($0,1,1)) tolower(substr($0,2))}' | awk '!seen[$0]++' | head -8)"
    # to Form lists
    a_form="$(printf '%s' "$agent_tools" | tr ',' '\n' | sed 's/.*/"&"/' | tr '\n' ' ')"
    n_form="$(printf '%s\n' "$native" | sed '/^$/d; s/.*/"&"/' | tr '\n' ' ')"
    [[ -z "${n_form// }" ]] && n_form='""'
    trials="$trials (fcsc-trial (list $a_form) (list $n_form))"
    baseline="$baseline (fcsc-trial (list $a_form) (list \"Bash\"))"
    nt="$(printf '%s' "$native" | tr '\n' ',' | sed 's/,$//')"
    printf "  %2d  agent[%s]  native[%s]\n" "$i" "$agent_tools" "$nt"
done <<< "$PICKS"

# score on the kernel (Form is the judge)
prog="$(mktemp)"
{ cat "$STD/form-cli-score.fk"
  echo "(let trials (list $trials))"
  echo "(let baseline (list $baseline))"
  echo '(print (fcsc-matched trials))'
  echo '(print (fcsc-full-matched trials))'
  echo '(print (fcsc-total trials))'
  echo '(print (fcsc-native-reaches? trials))'
  echo '(print (fcsc-matched baseline))'
} > "$prog"
mapfile_lines="$("$GO" "$prog" 2>/dev/null)"; rm -f "$prog"
M="$(printf '%s\n' "$mapfile_lines" | sed -n '1p')"
F="$(printf '%s\n' "$mapfile_lines" | sed -n '2p')"
T="$(printf '%s\n' "$mapfile_lines" | sed -n '3p')"
R="$(printf '%s\n' "$mapfile_lines" | sed -n '4p')"
B="$(printf '%s\n' "$mapfile_lines" | sed -n '5p')"

echo
echo "── score (Form-judged) ──"
pct(){ [[ "${2:-0}" -gt 0 ]] && echo $(( $1 * 100 / $2 )) || echo 0; }
printf "  native majority-match   %s/%s  (%s%%)\n" "$M" "$T" "$(pct "${M:-0}" "${T:-0}")"
printf "  native full-cover       %s/%s  (%s%%)\n" "$F" "$T" "$(pct "${F:-0}" "${T:-0}")"
printf "  always-Bash baseline    %s/%s  (%s%%)\n" "$B" "$T" "$(pct "${B:-0}" "${T:-0}")"
if [[ "${M:-0}" -gt "${B:-0}" ]]; then
    echo "  → native carries real tool-selection skill above the baseline."
elif [[ "${M:-0}" -eq "${B:-0}" ]]; then
    echo "  → native matches the dumb baseline — no skill above guessing Bash yet."
else
    echo "  → native is below the baseline — the lane is wide open to train."
fi
echo "  native reaches the agent on a majority of tasks: $([[ "${R:-0}" == "1" ]] && echo yes || echo not yet)"
