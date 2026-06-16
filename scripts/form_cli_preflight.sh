#!/usr/bin/env bash
# form_cli_preflight.sh — air-gap readiness check for the form-cli.
#
# Proves the offline self-improvement kit is whole WHILE the network is still
# reachable to fix anything: the Form kernel builds and runs, the surface
# membrane is legible (Form-native), local oracles are present (sovereign,
# offline), the stdlib recipes + specs are on disk, and the agent loop runs
# end-to-end against a LOCAL oracle with no network crossing.
#
# The LOGIC (the surface report) is Form, evaluated on the kernel. This shell is
# a thin carrier: it orchestrates checks and runs the kernel. No body lives here.
# Written for stock macOS bash 3.2 — no mapfile, arrays guarded.
#
# Usage: scripts/form_cli_preflight.sh [smoke-oracle]
#   smoke-oracle defaults to a fast local model just to prove the loop.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO_DIR="$ROOT/form/form-kernel-go"
GO="$GO_DIR/bin-go"
SMOKE_ORACLE="${1:-ollama run llama3.2:3b}"
MENTOR_MODELS="$HOME/mentor-install/.models"
PASS=0; GAP=0
ok(){ printf "  ✓  %s\n" "$1"; PASS=$((PASS+1)); }
gap(){ printf "  ✗  GAP: %s\n" "$1"; GAP=$((GAP+1)); }
note(){ printf "     %s\n" "$1"; }

echo "── form-cli air-gap preflight ──"

# 1. Kernel: build + eval smoke ------------------------------------------------
echo "[1] Form kernel"
if [[ ! -x "$GO" ]] || find "$GO_DIR" -name '*.go' -newer "$GO" -print -quit 2>/dev/null | grep -q .; then
    ( cd "$GO_DIR" && go build -o bin-go . ) 2>/dev/null
fi
if [[ -x "$GO" ]]; then
    smoke="$("$GO" <(echo "(print (add 20 22))") 2>/dev/null | tr -d '[:space:]')"
    case "$smoke" in 42*) ok "kernel builds and evaluates (20+22=42)" ;; *) gap "kernel built but eval smoke failed (got '$smoke')" ;; esac
else
    gap "kernel did not build — need Go toolchain (offline-fine once built)"
fi

# 2. Surface membrane: Form-native report --------------------------------------
echo "[2] Surface membrane (Form-native)"
if [[ -x "$GO" ]]; then
    rep="$(mktemp)"; trap 'rm -f "$rep"' EXIT
    # The kernel walks the Lisp dialect natively (builtins len/add/eq are native);
    # core.fk is the BML maintenance dialect and needs the source-compiler, so it
    # is NOT preluded here — these three Lisp recipes are all the report needs.
    { cat "$ROOT/form/form-stdlib/tool-channel.fk" \
          "$ROOT/form/form-stdlib/choice-receipt.fk" \
          "$ROOT/form/form-stdlib/form-cli-membrane.fk"
      echo '(print (fcm-surface-protocol-count))'
      echo '(print (fcm-surface-native-count))'
      echo '(print (fcm-surface-host-count))'
    } > "$rep"
    S_PROT=""; S_NAT=""; S_HOST=""; i=0
    while IFS= read -r line; do
        line="$(printf '%s' "$line" | tr -d '[:space:]')"
        [[ -z "$line" || "$line" == "null" ]] && continue
        case $i in 0) S_PROT="$line";; 1) S_NAT="$line";; 2) S_HOST="$line";; esac
        i=$((i+1))
    done < <("$GO" "$rep" 2>/dev/null)
    if [[ -n "$S_PROT" ]] && [[ "$S_PROT" -ge 1 ]] 2>/dev/null; then
        ok "membrane reports $S_PROT channels: $S_NAT native-recipe, $S_HOST host-crossing"
        note "host-crossings are where a native recipe is a gap to close"
    else
        gap "membrane report did not evaluate"
    fi
else
    gap "skipped — kernel unavailable"
fi

# 3. Local oracles: sovereign, offline -----------------------------------------
echo "[3] Local oracles (offline)"
FAST=""; CODER=""; N_LOCAL=0; LOCAL_LIST=""
if command -v ollama >/dev/null 2>&1; then
    while IFS= read -r m; do
        [[ -z "$m" ]] && continue
        N_LOCAL=$((N_LOCAL+1)); LOCAL_LIST="$LOCAL_LIST $m"
        case "$m" in *3b*|*3.2*) FAST="$m";; esac
        case "$m" in *coder*) CODER="$m";; esac
    done < <(ollama list 2>/dev/null | awk 'NR>1 && $1 !~ /:cloud/ {print $1}')
    if [[ "$N_LOCAL" -gt 0 ]]; then
        ok "ollama: $N_LOCAL local model(s) —$LOCAL_LIST"
        [[ -z "$FAST" ]] && FAST="$(printf '%s' "$LOCAL_LIST" | awk '{print $1}')"
    else
        gap "ollama present but no local models pulled"
    fi
else
    gap "ollama not on PATH"
fi
N_GGUF=0; CODER_GGUF=""
if [[ -d "$MENTOR_MODELS" ]]; then
    while IFS= read -r g; do
        [[ -z "$g" ]] && continue
        N_GGUF=$((N_GGUF+1))
        case "$g" in *coder*) CODER_GGUF="$g";; esac
    done < <(find "$MENTOR_MODELS" -maxdepth 1 -iname '*.gguf' 2>/dev/null)
    [[ "$N_GGUF" -gt 0 ]] && ok "coder GGUF on disk: $N_GGUF file(s) in mentor-install/.models"
fi
if [[ -n "$CODER" ]]; then
    note "coder oracle ready in ollama: $CODER"
elif [[ -n "$CODER_GGUF" ]]; then
    note "coder oracle stageable (no internet needed): ollama create coder -f <(echo \"FROM $CODER_GGUF\")"
fi

# 4. Recipes + specs on disk ---------------------------------------------------
echo "[4] Body on disk (recipes + specs)"
FK=$(find "$ROOT/form/form-stdlib" -name '*.fk' 2>/dev/null | grep -c . | tr -d ' ')
SPECS=$(find "$ROOT/specs" -name '*.md' 2>/dev/null | grep -c . | tr -d ' ')
[[ "$FK" -gt 0 ]] && ok "$FK Form stdlib recipes present" || gap "no Form recipes found"
[[ "$SPECS" -gt 0 ]] && ok "$SPECS specs present (idea→form-spec source)" || gap "no specs found"

# 5. Offline loop smoke: agent loop on a LOCAL oracle, no network ---------------
echo "[5] Offline agent loop (local oracle: $SMOKE_ORACLE)"
loop_out="$(bash "$ROOT/scripts/form_native_run.sh" \
    "Use the bash tool to run: echo PREFLIGHT-OK. Then report the output as your final answer." \
    "$SMOKE_ORACLE" 3 2>/dev/null)"
if printf '%s' "$loop_out" | grep -q "PREFLIGHT-OK"; then
    ok "agent loop ran end-to-end against a local oracle (no network)"
else
    gap "offline loop smoke did not complete (oracle '$SMOKE_ORACLE' reachable?)"
fi

# 6. Readiness receipt ---------------------------------------------------------
echo "── receipt ──"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
VERDICT="READY"; [[ "$GAP" -gt 0 ]] && VERDICT="GAPS:$GAP"
printf "  when      %s\n  checks    %d passed, %d gap(s)\n  fast      %s\n  coder     %s\n  verdict   %s\n" \
    "$STAMP" "$PASS" "$GAP" "${FAST:-none}" "${CODER:-unstaged}" "$VERDICT"
if [[ "$GAP" -eq 0 ]]; then
    echo "  the kit is whole — you can lose the network and keep improving."
else
    echo "  close the gaps above before the network goes dark."
fi
[[ "$GAP" -eq 0 ]]
