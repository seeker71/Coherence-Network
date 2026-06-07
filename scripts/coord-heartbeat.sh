#!/usr/bin/env bash
# coord-heartbeat.sh — per-agent liveness + upgrade-watch (carrier).
#
# Every INTERVAL: post a heartbeat (so "idle" on the board means quiet, not gone),
# fetch main, and when the protocol/tooling advances, announce it so agents
# re-source / next sessions read the latest. Posts via the LATEST agent-coord.sh
# from origin/main, so the heartbeat tooling self-upgrades without ever touching
# anyone's worktree (no risk to an agent's uncommitted work).
#
# Policy: docs/coherence-substrate/agent-coordination-membrane.form (upkeep).
# Run one per agent, in its own tab:  scripts/coord-heartbeat.sh grok
# Tunable:  COORD_HEARTBEAT=300   (seconds between beats)
# Stop:  Ctrl-C, or  touch ~/.coherence-network/coord-respond.off   (halts daemons)

set -u
AGENT="${1:?usage: coord-heartbeat.sh <agent>}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
INTERVAL="${COORD_HEARTBEAT:-300}"
OFF="$HOME/.coherence-network/coord-respond.off"
export COORD_AGENT="$AGENT"

# Run a coord verb through the LATEST agent-coord.sh on origin/main — so the
# tooling this daemon uses upgrades itself the moment main advances.
COORD() { bash <(git -C "$ROOT" show origin/main:scripts/agent-coord.sh 2>/dev/null) "$@"; }

last=""
printf 'coord-heartbeat: %s every %ss — liveness + upgrade-watch (off: touch %s)\n' "$AGENT" "$INTERVAL" "$OFF" >&2
while true; do
  [ -f "$OFF" ] && { echo "[off] $AGENT heartbeat stopping" >&2; break; }
  git -C "$ROOT" fetch -q origin main 2>/dev/null
  sha="$(git -C "$ROOT" rev-parse --short origin/main 2>/dev/null)"
  if [ -n "$last" ] && [ "$sha" != "$last" ]; then
    COORD share "protocol advanced to $sha — re-source agent-coord.sh (or restart) to upgrade" "scripts/agent-coordination-membrane.form"
  fi
  last="$sha"
  COORD heartbeat "alive @ main:$sha"
  sleep "$INTERVAL"
done
