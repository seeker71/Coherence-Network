#!/usr/bin/env bash
# form_cli_guided.sh — the trained native model makes the live model better.
#
# The flywheel's payoff, operationalized: the corpus-trained tool predictor
# (form-cli-predict.fk) knows the local coder omits Bash. So for each task it
# computes the likely tool set and INJECTS it as a hint into the local model's
# prompt. We compare the local model's tool selection UNGUIDED vs GUIDED, scored
# by the kernel (form-cli-score.fk) against what the agent actually used.
#
# Composes two already-proven recipes — no new logic. The predictor (Form)
# guides; the scorer (Form) judges; this shell wires them to the local model.
#
# Usage: form_cli_guided.sh [N] [model] [corpus]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
N="${1:-6}"; MODEL="${2:-ollama run coder}"
CORPUS="${3:-${FORM_CLI_CORPUS:-$HOME/.coherence-network/form-cli-corpus/corpus.jsonl}}"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null
[[ -f "$CORPUS" ]] || { echo "no corpus at $CORPUS"; exit 1; }
KNOWN="Bash Read Write Edit Grep Glob Agent"

echo "── guided vs unguided: the predictor guides $MODEL, on $N tasks ──"

# the learned model (base-rates + Agent boosts), as Form lets we reuse per task
MODEL_FK='(let base (list (fcp-base-pair "Bash" 93) (fcp-base-pair "Edit" 56) (fcp-base-pair "Read" 54) (fcp-base-pair "Write" 47) (fcp-base-pair "Agent" 9)))
(let boosts (list (fcp-boost-pair "parallel" "Agent") (fcp-boost-pair "explore" "Agent") (fcp-boost-pair "spawn" "Agent") (fcp-boost-pair "audit" "Agent") (fcp-boost-pair "sweep" "Agent") (fcp-boost-pair "review" "Agent")))'

PICKS="$(python3 - "$CORPUS" "$N" <<'PY'
import json,sys,re
path,n=sys.argv[1],int(sys.argv[2])
KNOWN={"Bash","Read","Write","Edit","Grep","Glob","Agent"}
out=[]
for l in open(path):
    try: r=json.loads(l)
    except: continue
    t=r.get("task","").strip()
    tools=[]
    for s in r.get("steps",[]):
        tn=s.get("tool")
        if tn in KNOWN and tn not in tools: tools.append(tn)
    if len(t)<28 or not tools: continue
    kw=list(dict.fromkeys(re.findall(r"[a-z]{4,}", t.lower())))[:12]
    out.append("\t".join([",".join(tools), " ".join(kw), t.replace("\n"," ")[:200]]))
    if len(out)>=n: break
print("\n".join(out))
PY
)"
[[ -n "$PICKS" ]] || { echo "no tasks"; exit 1; }

parse(){ printf '%s\n' "$1" | grep -oiE 'Bash|Read|Write|Edit|Grep|Glob|Agent' \
    | awk '{print toupper(substr($0,1,1)) tolower(substr($0,2))}' | awk '!seen[$0]++'; }
flist(){ local o="(list"; for x in $1; do o="$o \"$x\""; done; echo "$o)"; }

u_trials=""; g_trials=""; i=0
while IFS=$'\t' read -r agent_tools kw task; do
    [[ -z "$task" ]] && continue
    i=$((i+1))
    # predictor's likely tools for this task (Form: form-cli-predict)
    pp="$(mktemp)"
    { cat "$STD/form-cli-predict.fk"; echo "$MODEL_FK"
      echo "(let kw $(flist "$kw"))"
      for t in $KNOWN; do echo "(print (fcp-predicted? base boosts kw \"$t\" 40 50))"; done
    } > "$pp"
    mapfile_pred=""; j=0; pred=""
    while IFS= read -r v; do j=$((j+1)); tool=$(echo $KNOWN | cut -d' ' -f$j); [[ "$(echo "$v"|tr -d '[:space:]')" == "1" ]] && pred="$pred $tool"; done < <("$GO" "$pp" 2>/dev/null | head -7)
    rm -f "$pp"; pred="$(echo $pred)"

    # unguided + guided local-model tool predictions
    uf="$(mktemp)"; printf 'You are a coding agent with tools: %s. For the task, list ONLY the tool names you would use, one per line.\nTask: %s' "$KNOWN" "$task" > "$uf"
    u_native="$(parse "$($MODEL < "$uf" 2>/dev/null)")"; rm -f "$uf"
    gf="$(mktemp)"; printf 'You are a coding agent with tools: %s. Based on similar past tasks you will LIKELY need: %s. For the task, list ONLY the tool names you would use, one per line.\nTask: %s' "$KNOWN" "$pred" "$task" > "$gf"
    g_native="$(parse "$($MODEL < "$gf" 2>/dev/null)")"; rm -f "$gf"

    a_form="$(flist "$(echo $agent_tools | tr ',' ' ')")"
    u_form="$(flist "$(echo $u_native)")"; [[ "$u_form" == "(list)" ]] && u_form='(list "")'
    g_form="$(flist "$(echo $g_native)")"; [[ "$g_form" == "(list)" ]] && g_form='(list "")'
    u_trials="$u_trials (fcsc-trial $a_form $u_form)"
    g_trials="$g_trials (fcsc-trial $a_form $g_form)"
    printf "  %2d  agent[%s]  hint[%s]\n      unguided[%s]  guided[%s]\n" "$i" "$agent_tools" "$(echo $pred|tr ' ' ',')" "$(echo $u_native|tr '\n' ',')" "$(echo $g_native|tr '\n' ',')"
done <<< "$PICKS"

# score both arms (Form judges)
sp="$(mktemp)"
{ cat "$STD/form-cli-score.fk"
  echo "(let U (list $u_trials))"; echo "(let G (list $g_trials))"
  echo '(print (fcsc-matched U))'; echo '(print (fcsc-full-matched U))'; echo '(print (fcsc-total U))'
  echo '(print (fcsc-matched G))'; echo '(print (fcsc-full-matched G))'
} > "$sp"
o="$("$GO" "$sp" 2>/dev/null)"; rm -f "$sp"
UM=$(sed -n '1p'<<<"$o"); UF=$(sed -n '2p'<<<"$o"); T=$(sed -n '3p'<<<"$o"); GM=$(sed -n '4p'<<<"$o"); GF=$(sed -n '5p'<<<"$o")
pct(){ [[ "${2:-0}" -gt 0 ]] && echo $(( $1*100/$2 )) || echo 0; }

echo
echo "── score (Form-judged) ──"
printf "  UNGUIDED  majority %s/%s (%s%%)   full-cover %s/%s (%s%%)\n" "$UM" "$T" "$(pct "${UM:-0}" "${T:-0}")" "$UF" "$T" "$(pct "${UF:-0}" "${T:-0}")"
printf "  GUIDED    majority %s/%s (%s%%)   full-cover %s/%s (%s%%)\n" "$GM" "$T" "$(pct "${GM:-0}" "${T:-0}")" "$GF" "$T" "$(pct "${GF:-0}" "${T:-0}")"
if [[ "${GF:-0}" -gt "${UF:-0}" ]]; then
    echo "  → the predictor's guidance IMPROVED the live model's tool selection."
    echo "    the trained native model made the local model better — the flywheel turns."
elif [[ "${GF:-0}" -eq "${UF:-0}" ]]; then
    echo "  → guidance held even with unguided on this sample (model already covered)."
else
    echo "  → guidance did not help on this sample — worth a larger run."
fi
