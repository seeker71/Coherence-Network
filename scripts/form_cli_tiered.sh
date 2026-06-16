#!/usr/bin/env bash
# form_cli_tiered.sh — retire the REMOTE oracle on reasoning: local-first, tiered.
#
# The self-guided runner runs a SMALL local model first. If it fails (reaches
# max-steps or returns nothing), escalate to a BIGGER local model. Only if every
# LOCAL tier fails does the runner cross the network to a remote oracle — the
# last resort. Each served tier is ledgered as a membrane crossing
# (form-cli-membrane.fk): local tiers stay air-gap-clean; a remote escalation is
# the one network crossing. The flywheel's measurable lever: remote reliance =
# network crossings, which the bigger local tier drives toward zero.
#
# Composes the self-guiding runner (form_native_run.sh) + the membrane + existing
# routing intent. No new recipe — operationalization of local-first routing.
#
# Usage: form_cli_tiered.sh "<task>" [max-steps] [tier1] [tier2] [remote]
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
TASK="${1:?task}"; MAX="${2:-4}"
TIER1="${3:-ollama run llama3.2:3b}"     # fast, weak — handles the easy ones
TIER2="${4:-ollama run coder}"           # bigger local — catches what tier1 drops
REMOTE="${5:-claude -p}"                 # last resort: the only tier that needs network
[[ -x "$GO" ]] || ( cd "$ROOT/form/form-kernel-go" && go build -o bin-go . ) 2>/dev/null

echo "── tiered local-first runner ──"
echo "  task: $(printf '%s' "$TASK" | head -c 70)"

# a run succeeds when it returns a real final answer (no max-steps cap, non-empty)
served=""; surface=""; answer=""
try_tier() {
    local name="$1" model="$2" sfc="$3"
    printf "  · tier %s (%s) …" "$name" "$model"
    local out; out="$(bash "$ROOT/scripts/form_native_run.sh" "$TASK" "$model" "$MAX" 2>/dev/null)"
    # a real success: non-trivial content, no max-steps cap, no model-availability
    # or runtime error signature (an unavailable/erroring tier must escalate).
    local clean; clean="$(printf '%s' "$out" | sed 's/null[[:space:]]*$//' | tr -d '[:space:]')"
    if [[ ${#clean} -ge 10 ]] \
       && ! printf '%s' "$out" | grep -q "reached max-steps" \
       && ! printf '%s' "$out" | grep -qiE "error: |no such|not found|try pulling|manifest|connection refused|failed to"; then
        echo " served ✓"; served="$name"; surface="$sfc"; answer="$out"; return 0
    fi
    echo " passed"; return 1
}

if   try_tier "1-local-small" "$TIER1" "local-oracle"; then :
elif try_tier "2-local-big"   "$TIER2" "local-oracle"; then :
else
    # every LOCAL tier failed — the remote oracle is the only one left.
    echo "  · tier 3 (remote: $REMOTE) — last resort"
    served="3-remote"; surface="remote-oracle"
    if command -v "${REMOTE%% *}" >/dev/null 2>&1; then
        answer="$(bash "$ROOT/scripts/form_native_run.sh" "$TASK" "$REMOTE" "$MAX" 2>/dev/null)"
    else
        answer="(remote oracle unavailable offline — escalation point recorded)"
    fi
fi

# ── ledger the served tier as a membrane crossing (Form judges the surface) ──
led="$(mktemp)"; trap 'rm -f "$led"' EXIT
{ cat "$STD/core-native.fk"
  cat "$STD/tool-channel.fk" "$STD/choice-receipt.fk" "$STD/form-cli-membrane.fk"
  echo "(let cx (fcm-crossing \"tiered:$served\" \"cap.host.exec\" (fcm-surface-$( [[ "$surface" == remote-oracle ]] && echo remote-oracle || echo local-oracle )) 0 \"tier $served served the task\" \"success\" 80 0))"
  echo '(let rep (fcm-report (list cx)))'
  echo '(print (fcm-surface-needs-network? (fcm-x-surface cx)))'
  echo '(print (fcm-report-airgap-clean? rep))'
} > "$led"
NETC=""; CLEAN=""; i=0
while IFS= read -r v; do v="$(printf '%s' "$v"|tr -d '[:space:]')"; [[ -z "$v" || "$v" == null ]] && continue; case $i in 0) NETC="$v";; 1) CLEAN="$v";; esac; i=$((i+1)); done < <("$GO" "$led" 2>/dev/null)

echo
echo "── result ──"
echo "  served by    tier $served ($surface)"
echo "  network used $([[ "${NETC:-0}" == "1" ]] && echo "YES — remote oracle crossed" || echo "no — stayed offline")"
echo "  air-gap-clean $([[ "${CLEAN:-0}" == "1" ]] && echo "yes" || echo "no")"
printf "  answer: %s\n" "$(printf '%s' "$answer" | tr '\n' ' ' | head -c 160)"
echo
echo "  remote reliance is the flywheel's lever: as the local tiers improve, tier-3"
echo "  crossings (network) go to zero — the remote oracle retires on reasoning too."
