#!/usr/bin/env bash
# form_cli_agent.sh — thin WITNESS: the kernel runs the TIERED agent loop (form-native-run.fk).
#
# Body is Form: fnr-run-tiered drives the read/edit/bash/search/glob loop LOCAL-FIRST and escalates
# each unusable step to the REMOTE frontier oracle (claude -p), reading recent session memory in and
# persisting this run out (logs now, substrate later) — for cross-turn memory AND training. This
# carrier only marshals args and invokes the kernel; no logic here (the form_native_run.sh pattern).
#
# Usage: form_cli_agent.sh "<task>"   (env: LOCAL=coder REMOTE="claude -p" MAX=6)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GO="$ROOT/form/form-kernel-go/bin-go"; STD="$ROOT/form/form-stdlib"
[[ -x "$GO" ]] || (cd "$ROOT/form/form-kernel-go" && go build -o bin-go .)
LOCAL="${LOCAL:-coder}"; REMOTE="${REMOTE:-claude -p}"; MAX="${MAX:-6}"
TASK="$*"
[[ -n "$TASK" ]] || { echo "usage: form-cli do \"<task>\"" >&2; exit 2; }
mkdir -p "$HOME/.coherence-network"
esc(){ printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
{ cat "$STD/form-native-run.fk"
  echo "(print (fnr-run-tiered \"$(esc "$TASK")\" \"ollama run $LOCAL\" \"$(esc "$REMOTE")\" $MAX))"
} > "$work/agent.fk"
"$GO" "$work/agent.fk" 2>/dev/null | sed '/^null$/d'
