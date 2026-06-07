#!/usr/bin/env bash
# coord-heartbeat.sh — per-agent liveness + upgrade-watch, with idle stand-down.
#
# Every INTERVAL, IF the agent is actually working, post a heartbeat (so presence
# means working, not merely running) and watch main for protocol advances. If the
# agent is IDLE — no open claim and no real signal since the last beat — for
# IDLE_MAX beats running, STAND DOWN and exit. A heartbeat that only says "alive"
# while nothing happens is a subscription paying for idleness; this refuses that.
# Presence is earned by visible work (claim-before-touch), not by a running loop.
#
# Posts via the LATEST agent-coord.sh from origin/main, so the tooling self-
# upgrades without touching anyone's worktree.
#
# Policy: docs/coherence-substrate/agent-coordination-membrane.form (upkeep).
# Run one per agent, in its own tab:  scripts/coord-heartbeat.sh grok
# Tunables:  COORD_HEARTBEAT=300 (seconds/beat)  COORD_IDLE_MAX=4 (idle beats -> stand down)
# Stop:  Ctrl-C · touch ~/.coherence-network/coord-respond.off (halt all) · or it stands down when idle

set -u
AGENT="${1:?usage: coord-heartbeat.sh <agent>}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
INTERVAL="${COORD_HEARTBEAT:-300}"
IDLE_MAX="${COORD_IDLE_MAX:-4}"
OFF="$HOME/.coherence-network/coord-respond.off"
BOARD="${COHERENCE_COORD:-$HOME/.coherence-network/agent-coord.board}"
export COORD_AGENT="$AGENT"

# Run a coord verb through the LATEST agent-coord.sh on origin/main — so the
# tooling this daemon uses upgrades itself the moment main advances.
COORD() { bash <(git -C "$ROOT" show origin/main:scripts/agent-coord.sh 2>/dev/null) "$@"; }

# Is this agent actually working? yes iff it holds an OPEN claim (claim with no
# later release) OR posted a real (non-heartbeat) signal since the last beat.
_active() {  # $1 = last-beat ISO timestamp ("" = since forever)
  awk -F'\t' -v a="$AGENT" -v lb="$1" '
    $2==a && $3=="claim"   { open=1 }
    $2==a && $3=="release" { open=0 }
    $2==a && $3!="heartbeat" && $4 !~ /^heartbeat/ && (lb=="" || $1>lb) { recent=1 }
    END { print (open || recent) ? "yes" : "no" }
  ' "$BOARD" 2>/dev/null
}

last="" last_beat="" idle=0
printf 'coord-heartbeat: %s every %ss — beats while working, stands down after %d idle beats (off: touch %s)\n' \
  "$AGENT" "$INTERVAL" "$IDLE_MAX" "$OFF" >&2
while true; do
  [ -f "$OFF" ] && { echo "[off] $AGENT heartbeat stopping" >&2; break; }
  git -C "$ROOT" fetch -q origin main 2>/dev/null
  sha="$(git -C "$ROOT" rev-parse --short origin/main 2>/dev/null)"
  if [ -n "$last" ] && [ "$sha" != "$last" ]; then
    COORD share "protocol advanced to $sha — re-source agent-coord.sh (or restart) to upgrade" "scripts/agent-coordination-membrane.form"
  fi
  last="$sha"

  if [ "$(_active "$last_beat")" = "yes" ]; then
    idle=0
    COORD heartbeat "alive @ main:$sha"
    last_beat="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  else
    idle=$((idle + 1))
    if [ "$idle" -ge "$IDLE_MAX" ]; then
      COORD ping "standing down — idle ${idle} beats (~$((idle * INTERVAL / 60))min), no open claim. before idling: 'make wellness' names real work (bootstrap compost ~6935 LOC, 23 kernel-first route-flips, Form-engine arms) — claim from it to stay present. an agent is never out of work, only out of a claim."
      echo "[stand-down] $AGENT idle $idle beats — exiting to stop idle billing" >&2
      break
    fi
    echo "[idle $idle/$IDLE_MAX] $AGENT: no open claim, no recent work — stands down at $IDLE_MAX" >&2
  fi
  sleep "$INTERVAL"
done
