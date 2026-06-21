#!/usr/bin/env bash
# form_cli_learn_on_session.sh — the SessionEnd trigger that makes tool-use learning CONTINUOUS.
# On session end it runs `form-cli learn` (tap -> featurize -> retrain) DETACHED, so it never blocks
# session teardown and survives it. Guarded so it is safe to wire anywhere:
#   - no-op unless bin/form-cli is built (the GPU/corpus machine) — other clones skip silently;
#   - never overlaps a GPU retrain (a running learn holds a lock; a new trigger skips).
# Activation is per-machine (settings.local.json SessionEnd hook), because the corpus + GPU are local;
# the capability is committed, the trigger is opt-in. Carrier only.
set -u
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COH="$HOME/.coherence-network"
LOCK="$COH/.form-cli-learn.lock"
LOG="$COH/form-cli-learn.log"
mkdir -p "$COH" 2>/dev/null

# guard 1: only where form-cli is built (the corpus/GPU machine); silent no-op elsewhere
[ -x "$ROOT/bin/form-cli" ] || exit 0

# guard 2: never overlap GPU retrains — if the last learn's pid is still alive, skip this trigger.
# (A stale lock pointing at a dead pid fails kill -0, so it is ignored and overwritten below — no
# trap needed, which keeps this safe on macOS bash 3.2 where $BASHPID does not exist.)
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  exit 0
fi

# launch the one-motion learn DETACHED: never blocks teardown, survives it; record its pid for guard 2
nohup bash "$ROOT/scripts/form_cli_learn.sh" >>"$LOG" 2>&1 &
echo "$!" > "$LOCK"
disown 2>/dev/null || true
exit 0
