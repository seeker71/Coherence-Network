#!/usr/bin/env bash
# agent-coord.sh — the carrier for agent-coordination-membrane.form.
#
# Pure transport: append a signal to, or tail, a shared append-only board so
# sibling agents (Claude, Codex, Cursor, Grok, Gemini) and the human coordinate
# in one live field. The signal vocabulary — announce / claim / release / ping /
# block / unblock / ack / done — and what each means live in the canonical shape:
#   docs/coherence-substrate/agent-coordination-membrane.form
# This file only moves the bytes. The git-side view (worktrees, dirty state,
# file-level collisions) is scripts/agent_status.py — intent here, body there.
#
# Usage (per terminal):
#   export COORD_AGENT=grok           # claude | codex | cursor | grok | gemini | human
#   source scripts/agent-coord.sh
#   coord announce "$(pwd)"           # join the field, name your worktree
#   coord claim   "form/ kernel files"
#   coord ping    "rebased on main, kernel band green"
#   coord block   "need the cursor UI branch merged first"
#   coord release "form/ kernel files"
#   coord watch                       # live stream from all siblings (Ctrl-C to leave)
#   coord log 50                      # last 50 signals
#
# The board is liquid (ephemeral, gitignored, this machine). Durable task
# ownership stays in `coh tasks` + git branches + PRs.

COHERENCE_COORD="${COHERENCE_COORD:-$HOME/.coherence-network/agent-coord.board}"

_coord_fmt() {
  # tab-delimited: ISO-ts \t agent \t type \t message  →  HH:MM:SS agent type msg
  while IFS=$'\t' read -r ts agent type msg; do
    printf '  %s  %-7s %-9s %s\n' "${ts:11:8}" "$agent" "$type" "$msg"
  done
}

coord() {
  local type="$1"; shift 2>/dev/null || true
  local agent="${COORD_AGENT:-$(whoami)}"
  mkdir -p "$(dirname "$COHERENCE_COORD")"; touch "$COHERENCE_COORD" 2>/dev/null
  case "$type" in
    watch) tail -n 40 -f "$COHERENCE_COORD" | _coord_fmt; return;;
    log)   tail -n "${1:-30}" "$COHERENCE_COORD" | _coord_fmt; return;;
    announce|claim|release|ping|block|unblock|ack|done) : ;;
    *) echo "usage: coord <announce|claim|release|ping|block|unblock|ack|done|watch|log> [message]"; return 1;;
  esac
  local msg; msg="$(printf '%s' "$*" | tr '\t\n' '  ')"
  printf '%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$agent" "$type" "$msg" >> "$COHERENCE_COORD"
  printf '  → [%s] %s %s\n' "$agent" "$type" "$msg"
}
