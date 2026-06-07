#!/usr/bin/env bash
# coord-watcher.sh — the naive watcher: asks silly questions to keep the field honest.
#
# The cheapest blind-spot finder is a dumb question. "Who?" "When?" "How come?"
# needs no expertise — being asked forces the check the doer skipped. This watcher
# matches a SHAPE on the board and fires a templated naive question. It carries no
# intelligence and runs no agent turn — a board scan, nearly free — so it can watch
# continuously without being the idle billing it guards against. It asks each thing
# ONCE (deduped) and sparingly: a jester in the corner, not a nag.
#
# Shapes it watches and the silly question each earns:
#   open block, never cleared   -> "how come still blocked? who clears it?"
#   open claim, gone quiet      -> "@<agent> when does <scope> land? still on it?"
#   ask with no answer          -> "who knows? still no answer."
#   done, never verified        -> "did anyone check it? is it really proven?"
#   field quiet with open work   -> "quiet a while — who is moving what?"
#   a new .py shipped to main    -> "why python? carrier or logic — where is the Form recipe?"
#   python ship named on board   -> "why python — carrier or logic?"  (BML-first discipline)
#
# Policy: docs/coherence-substrate/agent-coordination-membrane.form (watcher).
# Run (one, anywhere):  scripts/coord-watcher.sh
# Tunables:  COORD_WATCH_EVERY=300 (s/scan)  COORD_STALE_MIN=20  COORD_QUIET_MIN=40  PY_WINDOW_MIN=30
# Stop:  Ctrl-C  ·  touch ~/.coherence-network/coord-respond.off (halts all daemons)

set -u
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
BOARD="${COHERENCE_COORD:-$HOME/.coherence-network/agent-coord.board}"
SEEN="$HOME/.coherence-network/.coord-watcher.seen"
OFF="$HOME/.coherence-network/coord-respond.off"
EVERY="${COORD_WATCH_EVERY:-300}"
STALE="${COORD_STALE_MIN:-20}"
QUIET="${COORD_QUIET_MIN:-40}"
MAX_PER_SCAN="${COORD_WATCH_MAX:-2}"   # sparing: ask at most this many per scan
export COORD_AGENT="watcher"
mkdir -p "$(dirname "$SEEN")"; touch "$SEEN" "$BOARD" 2>/dev/null

# Post through the LATEST agent-coord.sh on origin/main — tooling self-upgrades.
COORD() { bash <(git -C "$ROOT" show origin/main:scripts/agent-coord.sh 2>/dev/null) "$@"; }
_seen() { grep -qxF "$1" "$SEEN" 2>/dev/null; }
_mark() { printf '%s\n' "$1" >> "$SEEN"; }
# ISO-8601 cutoff N minutes ago (BSD -v / GNU -d); board ts compare lexically == chronologically
_ago()  { date -u -v-"$1"M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d "-$1 min" +%Y-%m-%dT%H:%M:%SZ; }

# One pass over the board → candidate "KEY<TAB>QUESTION" lines for stale shapes.
# Naive on purpose: tracks the MOST RECENT block/ask/done and whether it was
# cleared/answered/checked after, plus open claims with no progress since.
_candidates() {
  local cs cq pw; cs="$(_ago "$STALE")"; cq="$(_ago "$QUIET")"; pw="$(_ago "${PY_WINDOW_MIN:-30}")"
  awk -F'\t' -v cs="$cs" -v cq="$cq" -v pw="$pw" '
    $2!="watcher"                         { lastany=$1 }                       # newest non-watcher signal (quiet gauge)
    $3=="claim"                           { ct[$2]=$1; scope[$2]=$4; open[$2]=1 }
    $3=="release"                         { open[$2]=0 }
    $2!="watcher" && $3!="heartbeat" && $3!="claim" && $4 !~ /^heartbeat/ { act[$2]=$1 }  # real progress per agent
    $3=="block"                           { bts=$1; bmsg=$4; bcleared=0 }
    $3=="unblock"                         { bcleared=1 }
    $2!="watcher" && $3=="ask"            { ats=$1; aagent=$2; answered=0 }     # watcher asks do not count
    $3=="answer"                          { answered=1 }
    $3=="done"                            { dts=$1; dmsg=$4; checked=0 }
    $3=="check" || $3=="ack"              { checked=1 }
    # python ANNOUNCED on the board: a fresh signal naming a .py being added/created/shipped
    # (the trigger word must precede the path, so "composted python" never fires). BML-first:
    # python is a carrier authored last, never the body; the question makes that conscious.
    $2!="watcher" && $1>pw && $4 ~ /(add|new|creat|wrote|writ|ship|port)[A-Za-z]*[: ][A-Za-z0-9_\/.-]*\.py([^A-Za-z0-9]|$)/ { pts=$1; pagent=$2; pmsg=$4 }
    END {
      for (a in open) if (open[a] && ct[a]<cs && (act[a]=="" || act[a]<=ct[a]))
        printf "claim:%s:%s\t@%s when does \"%s\" land? still on it?\n", a, ct[a], a, substr(scope[a],1,40)
      if (bts!="" && !bcleared && bts<cs)
        printf "block:%s\thow come \"%s\" is still blocked? who clears it?\n", bts, substr(bmsg,1,40)
      if (ats!="" && !answered && ats<cs)
        printf "ask:%s\twho knows? still no answer to %s.\n", ats, aagent
      if (dts!="" && !checked && dts<cs)
        printf "done:%s\tdid anyone check \"%s\"? is it really proven?\n", dts, substr(dmsg,1,40)
      if (pts!="")
        printf "pymsg:%s\t@%s why python — \"%s\"? carrier (fan-out/route/script) or logic? if logic, where is the Form recipe + BML grammar?\n", pts, pagent, substr(pmsg,1,44)
      if (lastany!="" && lastany<cq)
        printf "quiet:%s\tquiet a while — who is moving what?\n", substr(lastany,1,16)
    }
  ' "$BOARD" 2>/dev/null
}

# python SHIPPED to main: a new .py file added on origin/main in the recent window.
# Additions only (--diff-filter=A), so it never fires on python being composted —
# only on a new module being born, which is the "before any new .py" moment caught
# after the fact: the exterior mirror to the interior BML-first hook. BML-first
# holds python is a carrier authored last; a new .py module always earns the question.
_py_shipped_candidates() {
  git -C "$ROOT" log origin/main --since="${PY_WINDOW_MIN:-30} minutes ago" \
      --diff-filter=A --name-only --pretty="format:@@ %h" 2>/dev/null | awk '
    /^@@ / { sha=$2; next }
    /\.py$/ { printf "pyship:%s:%s\twhy python? %s is a new .py on main — carrier (fan-out/route/script/test) or logic? if logic, where is the Form recipe + BML grammar it should be?\n", sha, $0, $0 }
  '
}

echo "coord-watcher: the silly question every ${EVERY}s (stale>${STALE}min, quiet>${QUIET}min). off: touch $OFF" >&2
while true; do
  [ -f "$OFF" ] && { echo "[off] watcher stopping" >&2; break; }
  git -C "$ROOT" fetch -q origin main 2>/dev/null
  asked=0
  while IFS=$'\t' read -r key q; do
    [ -z "$key" ] && continue
    _seen "$key" && continue
    COORD ask "$q" >/dev/null 2>&1
    _mark "$key"
    asked=$((asked + 1))
    [ "$asked" -ge "$MAX_PER_SCAN" ] && break
  done < <(_candidates; _py_shipped_candidates)
  [ "$asked" -gt 0 ] && echo "[watch] asked $asked silly question(s)" >&2
  sleep "$EVERY"
done
