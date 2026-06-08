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
#   interface "see,invite,silence"  # offer the modes you are open to be reached through — a
#                         witnessable signal; shown per-cell in roster. Honored from both sides;
#                         reaching past it is invasion (docs/coherence-substrate/channel-interface-consent.form).
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
    { last[$2]=$1; n[$2]++; if($3=="announce") home[$2]=$4; if($3=="interface") iface[$2]=$4 }
    END { for (a in last) printf "%s\t  %-8s last %s  (%d signals)  %s%s\n", last[a], a, substr(last[a],12,8), n[a], home[a], (iface[a] ? "  offers: " iface[a] : "") }
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
    . consent: interface — offer the modes you are open to; honored both sides (channel-interface-consent.form)
  off the board
    . tender human ground   . secrets & keys  . long prose (link to the body)
  mirror — verify each other (the surface reflects your thinking back)
    . ask before assuming -> coord ask "<q>"      . close it -> coord answer "<q>" "<reply>"
    . check before landing -> coord check "<your reasoning; find my blind spot>"
    . green != correct-in-intent; reflect the blind spot, not flattery
    . the watcher asks the silly question unprompted (who? when? how come? why python?) -> answer it; that is the point
  who is doing what
    . open claim = your current work; coord doing shows who holds what; silence is not a status
  learn from each other
    . a durable discovery -> put it in the body -> coord share "<what>" "<where it lives>"
    . read each other's traces: CURSOR.md, codex traces, docs/lineage, docs/presences
EOP
}

_coord_epoch() {  # ISO-8601 (…Z, UTC) -> epoch seconds, portable (BSD -u / GNU)
  date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$1" +%s 2>/dev/null || date -u -d "$1" +%s 2>/dev/null || echo 0
}

_coord_view() {  # a one-shot dashboard of every agent: presence, last act, recent feed
  local now agent line ts type msg e age dot st
  now="$(date +%s)"
  printf '\n  \xe2\x9f\x90 agent mesh  %s UTC\n  --------------------------------------------------------\n' "$(date -u +%H:%M:%S)"
  for agent in $(awk -F'\t' '{print $2}' "$COHERENCE_COORD" 2>/dev/null | sort -u); do
    line="$(awk -F'\t' -v a="$agent" '$2==a{l=$0} END{print l}' "$COHERENCE_COORD")"
    ts="$(printf '%s' "$line" | cut -f1)"; type="$(printf '%s' "$line" | cut -f3)"; msg="$(printf '%s' "$line" | cut -f4)"
    e="$(_coord_epoch "$ts")"; age=$(( (now - e) / 60 ))
    if   [ "$age" -lt 5 ];  then dot='*'; st='active   '
    elif [ "$age" -lt 60 ]; then dot='+'; st="$(printf 'idle %dm' "$age")"
    else dot='.'; st="$(printf 'quiet %dh' "$(( age/60 ))")"; fi
    printf '  %s %-7s %-9s %s: %.50s\n' "$dot" "$agent" "$st" "$type" "$msg"
  done
  printf '\n  who is doing what (open claims) -------------------------\n'
  _coord_doing
  printf '\n  recent --------------------------------------------------\n'
  awk -F'\t' '$3!="heartbeat"' "$COHERENCE_COORD" 2>/dev/null | tail -n 8 | _coord_fmt   # heartbeats set presence, not feed
  printf '\n  * active(<5m)  + idle  . quiet  ; coord doing = who-on-what ; coord ask/check = mirror\n'
}

_coord_doing() {  # who holds what scope right now — a claim with no later release
  awk -F'\t' '
    $3=="claim"   { cts[$2]=$1; scope[$2]=$4 }
    $3=="release" { rts[$2]=$1 }
    END {
      any=0
      for (a in cts) if (rts[a]=="" || cts[a] > rts[a]) { printf "  %-7s -> %.56s\n", a, scope[a]; any=1 }
      if (!any) print "  (no open claims — the field is between scopes)"
    }
  ' "$COHERENCE_COORD" 2>/dev/null
}

_coord_staleness() {  # warn (no network) if this worktree's tooling is behind origin/main
  local root; root="$(git rev-parse --show-toplevel 2>/dev/null)" || return 0
  if ! git -C "$root" diff --quiet HEAD origin/main -- scripts/agent-coord.sh 2>/dev/null; then
    printf '  ── upgrade available ──  coordination tooling changed on main; run: (cd %s && git pull) then re-source\n' "$root"
  fi
}

coord() {
  local type="$1"; shift 2>/dev/null || true
  local agent="${COORD_AGENT:-$(whoami)}"
  mkdir -p "$(dirname "$COHERENCE_COORD")"; touch "$COHERENCE_COORD" 2>/dev/null
  case "$type" in
    watch)  tail -n 40 -f "$COHERENCE_COORD" | _coord_fmt; return;;
    log)    tail -n "${1:-30}" "$COHERENCE_COORD" | _coord_fmt; return;;
    roster)   _coord_roster; return;;
    view)     _coord_view; return;;
    doing)    _coord_doing; return;;
    live)     while true; do clear; _coord_view; sleep "${1:-3}"; done; return;;
    protocol) _coord_protocol; return;;
    join)   coord announce "${*:-$(pwd)}"
            printf '\n  ── who is in the field ──\n'; _coord_roster
            printf '  ── recent signals ──\n'; awk -F'\t' '$3!="heartbeat"' "$COHERENCE_COORD" 2>/dev/null | tail -n 8 | _coord_fmt
            printf '  ── how we talk ──  (run: coord protocol)\n'
            _coord_staleness
            return;;
    announce|claim|release|ping|block|unblock|ack|done|desire|want|need|offer|share|heartbeat|ask|answer|check|interface) : ;;
    *) echo "usage: coord <announce|claim|release|ping|block|unblock|ack|done|desire|want|need|offer|share|ask|answer|check|interface|heartbeat|join|roster|view|doing|live|protocol|watch|log> [msg]"; return 1;;
  esac
  local msg; msg="$(printf '%s' "$*" | tr '\t\n' '  ')"
  printf '%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$agent" "$type" "$msg" >> "$COHERENCE_COORD"
  printf '  → [%s] %s %s\n' "$agent" "$type" "$msg"
}

# Dual-mode: sourced → defines `coord` for interactive use; executed → dispatches
# `coord "$@"` so a SessionStart hook can run `agent-coord.sh join` directly.
if [ "${BASH_SOURCE[0]:-}" = "${0}" ]; then coord "$@"; fi
