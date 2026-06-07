#!/usr/bin/env bash
# coord-respond.sh — a GUARDED auto-responder for ONE agent (carrier).
#
# Watches the coordination board and, ONLY when a sibling addresses this agent,
# generates a one-line reply via the agent's headless mode and posts it back —
# so the agent answers without a human handing it a turn. The policy and the
# guards are named canonically in docs/coherence-substrate/agent-coordination-
# membrane.form (auto-response). This file only pumps the bytes.
#
# Reactivity without guards burns the subscriptions we set out to spare, so:
#   . fires only on @<agent> / @all          . never on announce/ack/heartbeat
#   . never answers its own voice            . hard reply cap per window
#   . one-line reply or SKIP                 . one-touch off switch halts all
#
# Run one per agent, each in its own tab:
#   scripts/coord-respond.sh grok            # or: cursor | gemini
# Tunables:  COORD_CAP=6  COORD_WINDOW=900   (max replies / seconds)
# Stop:  Ctrl-C, or  touch ~/.coherence-network/coord-respond.off   (halts every responder)

set -u
AGENT="${1:?usage: coord-respond.sh <grok|cursor|gemini>}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
BOARD="${COHERENCE_COORD:-$HOME/.coherence-network/agent-coord.board}"
OFF="$HOME/.coherence-network/coord-respond.off"
RL="$HOME/.coherence-network/.coord-respond-$AGENT.rl"
CAP="${COORD_CAP:-6}"
WINDOW="${COORD_WINDOW:-900}"

# shellcheck source=/dev/null
. "$ROOT/scripts/agent-coord.sh"          # for coord()
export COORD_AGENT="$AGENT"

# Per-agent headless reply generator → prints the reply to stdout, then exits.
_gen() {
  case "$AGENT" in
    grok)   grok -p "$1" 2>/dev/null ;;
    gemini) gemini -p "$1" 2>/dev/null ;;
    cursor) cursor-agent -p --output-format text "$1" 2>/dev/null ;;
    codex)  codex exec "$1" 2>/dev/null | grep -vE 'tokens used|^[0-9,]+$' ;;  # strip exec's usage footer
    *)      printf 'SKIP\n' ;;
  esac
}

# File-based rate limit (survives the tail|while subshell): keep stamps in the
# window, allow only CAP within it.
_rate_ok() {
  local now n; now="$(date +%s)"
  [ -f "$RL" ] && { awk -v n="$now" -v w="$WINDOW" 'n-$1<w' "$RL" >"$RL.t" 2>/dev/null && mv "$RL.t" "$RL"; }
  n="$(wc -l <"$RL" 2>/dev/null || echo 0)"
  [ "${n:-0}" -lt "$CAP" ]
}

mkdir -p "$(dirname "$RL")"; : >"$RL"
printf 'coord-respond: %s listening — only @%s/@all, cap %s/%ss. Stop: Ctrl-C or touch %s\n' \
  "$AGENT" "$AGENT" "$CAP" "$WINDOW" "$OFF" >&2

tail -n 0 -f "$BOARD" | while IFS=$'\t' read -r ts from type msg; do
  [ -f "$OFF" ] && { echo "[off-switch] stopping $AGENT responder" >&2; break; }
  [ "$from" = "$AGENT" ] && continue                                   # never self
  case "$type" in announce|ack|heartbeat|release|done) continue;; esac # never low-value
  case "$msg" in *"@$AGENT"*|*"@all"*|*"@everyone"*) : ;; *) continue;; esac  # only addressed
  _rate_ok || { echo "[rate-cap] $AGENT skipped: $msg" >&2; continue; }
  prompt="You are $AGENT, one member of a sibling-agent coordination channel (siblings: claude, codex, cursor, gemini, human). $from said on the channel: \"${msg//\"/\'}\". If a reply is wanted from you, answer in ONE concise line for the channel. If no reply is warranted, output exactly SKIP. Take no other action."
  reply="$(_gen "$prompt" | tr -d '\r' | grep -v '^[[:space:]]*$' | tail -1)"
  [ -z "$reply" ] && continue
  [ "$reply" = "SKIP" ] && continue
  date +%s >>"$RL"
  coord ping "$reply"
done
