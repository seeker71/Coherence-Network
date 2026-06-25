#!/usr/bin/env bash
# form_cli_self_review.sh — the self-review flywheel, driven through form-cli.
#
# An explicit local teacher model answers; an INTERNAL judge and the ORACLE (Claude via
# the CLI by default — proof the body can be reviewed by, and learn from, its
# strongest oracle) both score the SAME answer against the reference; the Form
# convergence metric (form-cli-review-gap.fk) measures how close the internal review
# is to the oracle's. This script is a training/review lane, not `form-cli ask`.
# While the gap is wide the oracle is the authority; when a
# majority of reviews agree within tolerance the internal review has REACHED the
# oracle and the remote reviewer can retire. The judges are carriers; the
# convergence tally is Form (four-way proven).
#
# Every oracle review is captured (form_cli_capture.sh) so the internal judge can be
# trained toward it — "learn from the oracle until your own review is as good."
#
# Usage: form_cli_self_review.sh [N] [native] [internal-judge] [oracle-judge] [tol] [corpus]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STD="$ROOT/form/form-stdlib"; GO="$ROOT/form/form-kernel-go/bin-go"
N="${1:-2}"; NATIVE="${2:-ollama run coder}"; INNER="${3:-ollama run llama3.2:3b}"
ORACLE="${4:-claude -p}"; TOL="${5:-15}"
CORPUS="${6:-${FORM_CLI_CORPUS:-$HOME/.coherence-network/form-cli-corpus/corpus.jsonl}}"
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null
[[ -f "$CORPUS" ]] || { echo "no corpus at $CORPUS"; exit 1; }

echo "── self-review: native ($NATIVE) reviewed by INNER ($INNER) vs ORACLE ($ORACLE) ──"

PICKS="$(python3 - "$CORPUS" "$N" <<'PY'
import json,sys
path,n=sys.argv[1],int(sys.argv[2])
out=[]
for l in open(path):
    try: r=json.loads(l)
    except: continue
    t=r.get("task","").strip(); a=r.get("answer","").strip()
    if len(t)<40 or len(a)<120: continue
    out.append(t.replace("\n"," ")[:280]+"\t"+a.replace("\n"," ")[:1200])
    if len(out)>=n: break
print("\n".join(out))
PY
)"
[[ -n "$PICKS" ]] || { echo "no substantive (task,answer) pairs"; exit 1; }

score_of(){ printf '%s' "$1" | grep -oE '[0-9]+' | head -1; }
judge_prompt(){ printf 'You are grading. REFERENCE answer:\n%s\n\nCANDIDATE answer:\n%s\n\nHow well does the CANDIDATE cover the substance of the REFERENCE? Reply with ONLY an integer 0-100.' "$1" "$2"; }

INNER_SCORES=""; ORACLE_SCORES=""; i=0
while IFS=$'\t' read -r task agent; do
    [[ -z "$task" ]] && continue
    i=$((i+1))
    # 1. the body answers from its own model (once)
    af="$(mktemp)"; printf 'Task: %s\nGive a concise, concrete answer or approach (a few sentences).' "$task" > "$af"
    ans="$($NATIVE < "$af" 2>/dev/null | tr '\n' ' ' | head -c 1200)"; rm -f "$af"
    # 2. INTERNAL review (a local judge)
    jf="$(mktemp)"; judge_prompt "$agent" "$ans" > "$jf"
    is="$(score_of "$($INNER < "$jf" 2>/dev/null)")"; is="${is:-0}"; [[ "$is" -gt 100 ]] && is=100
    # 3. ORACLE review (the agent CLI on its subscription login) — the SAME answer.
    # env -u ANTHROPIC_API_KEY: subscription-only, a stray key can't silently meter.
    os="$(score_of "$(env -u ANTHROPIC_API_KEY $ORACLE < "$jf" 2>/dev/null)")"; os="${os:-0}"; [[ "$os" -gt 100 ]] && os=100
    rm -f "$jf"
    INNER_SCORES="$INNER_SCORES $is"; ORACLE_SCORES="$ORACLE_SCORES $os"
    printf "  %2d  inner=%3s  oracle=%3s  gap=%3s  task: %s\n" "$i" "$is" "$os" "$(( is>os ? is-os : os-is ))" "$(printf '%s' "$task" | head -c 48)"
    # 4. capture the oracle's review so the inner judge can learn toward it
    if [[ -x "$ROOT/scripts/form_cli_capture.sh" ]]; then
        bash "$ROOT/scripts/form_cli_capture.sh" --gap \
            "review answer for: $task" "internal judge scored $is; learn the oracle's eye" \
            "oracle($ORACLE) scored this answer $os/100" "success" "$(printf '%s' "$ORACLE" | awk '{print $1}')" >/dev/null 2>&1
    fi
done <<< "$PICKS"

# 5. the convergence metric is Form (form-cli-review-gap.fk, four-way)
inl="$(printf '%s' "$INNER_SCORES" | sed 's/^ *//; s/  */ /g')"
orl="$(printf '%s' "$ORACLE_SCORES" | sed 's/^ *//; s/  */ /g')"
prog="$(mktemp)"
{ cat "$STD/form-cli-review-gap.fk"
  echo "(let ins (list $inl))"
  echo "(let ors (list $orl))"
  echo "(print (frg-total-gap ins ors))"
  echo "(print (frg-worst-gap ins ors))"
  echo "(print (frg-agree-count ins ors $TOL))"
  echo "(print (len ins))"
  echo "(print (frg-converged? ins ors $TOL))"
} > "$prog"
o="$("$GO" "$prog" 2>/dev/null)"; rm -f "$prog"
TG=$(sed -n '1p' <<<"$o"); WG=$(sed -n '2p' <<<"$o"); AG=$(sed -n '3p' <<<"$o"); TT=$(sed -n '4p' <<<"$o"); CV=$(sed -n '5p' <<<"$o")
avg(){ [[ "${2:-0}" -gt 0 ]] && echo $(( $1 / $2 )) || echo 0; }

echo
echo "── convergence of internal review toward the oracle (Form-tallied) ──"
printf "  reviews            %s\n" "${TT:-0}"
printf "  agree within %-3s   %s/%s\n" "$TOL" "${AG:-0}" "${TT:-0}"
printf "  average gap        %s/100\n" "$(avg "${TG:-0}" "${TT:-0}")"
printf "  worst gap          %s/100\n" "${WG:-0}"
if [[ "${CV:-0}" == "1" ]]; then
    echo "  CONVERGED — the internal review reached the oracle's; the remote reviewer can retire."
else
    echo "  NOT YET — the internal review is still learning the oracle's eye (the frontier; captured to train it)."
fi
