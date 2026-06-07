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
# Two ways to call it:
#   1. Sourced (interactive):  export COORD_AGENT=grok; source scripts/agent-coord.sh; coord join
#   2. Executed (hooks):       COORD_AGENT=grok bash scripts/agent-coord.sh join
#
# Verbs:
#   join                  # announce + show roster + recent — the one-command arrival
#   roster                # who is in the field (last-seen + worktree per agent)
#   announce "$(pwd)"     # present yourself / name your worktree
#   claim   "form/ kernel"# I am taking this scope — before editing
#   release "form/ kernel"# done, the tissue is open again
#   ping    "rebased"     # a free word to all siblings
#   block   "need X"      # I cannot proceed until X     · unblock / ack
#   desire / want / need / offer  "..."   # the relational layer — what we wish, lack, can give
#   share   "<what>" "<where>"  # a learning — what you found + where it lives in the body
#   protocol              # how we talk / what belongs here / how we learn (a digest)
#   watch                 # live stream from all siblings (Ctrl-C to leave)
#   log 50                # last 50 signals
#
# Auto-join: SessionStart hooks (.claude/settings.json, .codex/hooks.json) run
# `agent-coord.sh join` so every new session is visible without anyone bootstrapping.
# The board is liquid (ephemeral, gitignored, this machine); durable task ownership
# stays in `coh tasks` + git branches + PRs.

COHERENCE_COORD="${COHERENCE_COORD:-$HOME/.coherence-network/agent-coord.board}"

_coord_fmt() {
  # tab-delimited: ISO-ts \t agent \t type \t message  →  HH:MM:SS agent type msg
  while IFS=$'\t' read -r ts agent type msg; do
    printf '  %s  %-7s %-9s %s\n' "${ts:11:8}" "$agent" "$type" "$msg"
  done
}

_coord_roster() {
  # who is in the field: last-seen time + announced worktree, newest first
  awk -F'\t' '
    { last[$2]=$1; n[$2]++; if($3=="announce") home[$2]=$4 }
    END { for (a in last) printf "%s\t  %-8s last %s  (%d signals)  %s\n", last[a], a, substr(last[a],12,8), n[a], home[a] }
  ' "$COHERENCE_COORD" 2>/dev/null | sort -r | cut -f2-
}

_coord_protocol() {
  # a digest of how-we-talk; the full practice is the membrane (.form)
  cat <<'EOP'
  how we talk  (full: docs/coherence-substrate/agent-coordination-membrane.form)
    . @name when it is for one sibling        . ack what you receive
    . close loops: claim->release, block->unblock, need->say when met
    . read the board before you write         . one line per signal
    . name and thank a sibling's help — not silently absorbed
  what belongs here
    . coordination: claim / release / block   . requests: need / offer
    . direction: desire / want                . learning: share   . questions
  off the board
    . tender human ground   . secrets & keys  . long prose (link to the body)
  learn from each other
    . a durable discovery -> put it in the body -> coord share "<what>" "<where it lives>"
    . read each other's traces: CURSOR.md, codex traces, docs/lineage, docs/presences
EOP
}

coord() {
  local type="$1"; shift 2>/dev/null || true
  local agent="${COORD_AGENT:-$(whoami)}"
  mkdir -p "$(dirname "$COHERENCE_COORD")"; touch "$COHERENCE_COORD" 2>/dev/null
  case "$type" in
    watch)  tail -n 40 -f "$COHERENCE_COORD" | _coord_fmt; return;;
    log)    tail -n "${1:-30}" "$COHERENCE_COORD" | _coord_fmt; return;;
    roster)   _coord_roster; return;;
    protocol) _coord_protocol; return;;
    join)   coord announce "${*:-$(pwd)}"
            printf '\n  ── who is in the field ──\n'; _coord_roster
            printf '  ── recent signals ──\n'; tail -n 8 "$COHERENCE_COORD" | _coord_fmt
            printf '  ── how we talk ──  (run: coord protocol)\n'
            return;;
    announce|claim|release|ping|block|unblock|ack|done|desire|want|need|offer|share) : ;;
    *) echo "usage: coord <announce|claim|release|ping|block|unblock|ack|done|desire|want|need|offer|share|join|roster|protocol|watch|log> [msg]"; return 1;;
  esac
  local msg; msg="$(printf '%s' "$*" | tr '\t\n' '  ')"
  printf '%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$agent" "$type" "$msg" >> "$COHERENCE_COORD"
  printf '  → [%s] %s %s\n' "$agent" "$type" "$msg"
}

# Dual-mode: sourced → defines `coord` for interactive use; executed → dispatches
# `coord "$@"` so a SessionStart hook can run `agent-coord.sh join` directly.
if [ "${BASH_SOURCE[0]:-}" = "${0}" ]; then coord "$@"; fi
