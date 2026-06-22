#!/usr/bin/env bash
# mesh_command_receiver.sh — the DEVICE side of cloud->device dispatch.
#
# The gap (Urs, 2026-06-22): the cloud cell can DISPATCH to a device — it POSTs a
# message onto the federation node-message bus (already live, Postgres-durable) —
# but it cannot make a session on the device ACT. Capture only happens when a live
# local instance runs the prompt. THIS is that live local instance: it polls this
# node's inbox, and for a trusted, directed `command` message it wakes a real local
# `claude -p`, captures the output, and posts the capture back to the dispatcher.
#
# Carrier-last: the DECISION (act | refuse | ignore) is the four-way-proven recipe
# form/form-stdlib/mesh-command.fk (mc-route). This script holds NO policy — it
# gathers three facts (is-command, for-me, trusted), asks the recipe, and on "act"
# RECOGNIZES the dispatch as its own lineage's (a signature over a public channel),
# confirms it's listening, runs the live instance, and returns the capture.
#
# The bus is a public, open channel — a message can arrive wearing any name. The
# signature is how this device recognizes a dispatch as really from its own cloud
# instance and not a stranger in its name (the same "never act on an unverified
# name" the body keeps elsewhere; the membrane recognizing self, not a fortress).
# It listens by default; to let it rest, rm the listening flag.
#
#   mesh_command_receiver.sh --once            # one poll cycle (heartbeat/cron hook)
#   mesh_command_receiver.sh --loop [secs]     # poll forever every N secs (default 60)
#   mesh_command_receiver.sh --dispatch <to> <text>   # local proof: send a signed command
#
# Config (env, all optional):
#   MR_NODE_ID        this device's node id on the bus           (default sema-macos)
#   MR_API_BASE       federation API base                        (default https://api.coherencycoin.com)
#   MR_TRUSTED        comma list of lineage dispatcher node ids  (default claude-sema-cloud)
#   MR_KEY_FILE       lineage signing key (mode 600)             (default ~/.coherence-network/mesh-lineage.key)
#   MR_LISTEN_FILE    listening flag; absent = rest, no run      (default ~/.coherence-network/mesh-receiver.listening)
#   MR_DEFAULT_MODE   claude permission mode when unset by msg   (default default)
#   MR_LOG            audit ledger                               (default ~/.coherence-network/mesh-receiver.log)
#   MR_TIMEOUT        seconds a single dispatched run may take   (default 900)
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

ROOT="${MR_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
NODE_ID="${MR_NODE_ID:-sema-macos}"
API_BASE="${MR_API_BASE:-https://api.coherencycoin.com}"
TRUSTED="${MR_TRUSTED:-claude-sema-cloud}"
KEY_FILE="${MR_KEY_FILE:-$HOME/.coherence-network/mesh-lineage.key}"
LISTEN_FILE="${MR_LISTEN_FILE:-$HOME/.coherence-network/mesh-receiver.listening}"
DEFAULT_MODE="${MR_DEFAULT_MODE:-default}"
LOG="${MR_LOG:-$HOME/.coherence-network/mesh-receiver.log}"
TIMEOUT="${MR_TIMEOUT:-900}"
CLAUDE="$HOME/.local/bin/claude"
KERNEL="$ROOT/form/form-kernel-go/bin-go"
RECIPE="$ROOT/form/form-stdlib/mesh-command.fk"
SEEN="$HOME/.coherence-network/mesh-receiver.seen"   # handled message ids (idempotency)
ALLOWED_MODES="default acceptEdits bypassPermissions plan"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }

# portable bounded run — macOS ships no `timeout`; prefer it / gtimeout, else perl alarm.
run_bounded() {  # secs cmd...
  local secs="$1"; shift
  if command -v timeout >/dev/null 2>&1; then timeout "$secs" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then gtimeout "$secs" "$@"
  else perl -e 'my $s=shift; eval { local $SIG{ALRM}=sub{die"to\n"}; alarm $s; exec @ARGV }; exit 124' "$secs" "$@"
  fi
}

# the body's decision over the three facts — the carrier asks, never decides.
mc_route() {  # is_cmd for_me trusted -> act|refuse|ignore
  [ -x "$KERNEL" ] || { printf 'ignore'; return; }
  local df out; df="$(mktemp)"
  printf '(do (print (mc-route %s %s %s)))\n' "$1" "$2" "$3" > "$df"
  # the kernel prints the route then a trailing `null` (the do-block value) — strip it.
  out="$("$KERNEL" "$RECIPE" "$df" 2>/dev/null | sed '/^null$/d' | tail -1 | tr -dc 'a-z')"
  rm -f "$df"
  case "$out" in act|refuse|ignore) printf '%s' "$out";; *) printf 'ignore';; esac
}

hmac() {  # text -> hex HMAC-SHA256 over "<NODE_ID>\n<text>" with the lineage key
  local key; key="$(cat "$KEY_FILE" 2>/dev/null)"
  [ -n "$key" ] || { printf ''; return; }
  printf '%s\n%s' "$NODE_ID" "$1" | openssl dgst -sha256 -hmac "$key" -hex 2>/dev/null | sed 's/^.*= *//'
}

is_lineage() { case ",$TRUSTED," in *",$1,"*) return 0;; *) return 1;; esac; }

# post a pre-built message body to the bus, retrying — the bus is the channel home
# for a capture, and a strained edge drops POSTs; swallowing that loses the payoff
# silently. Returns 0 on HTTP 2xx, non-zero after all tries.
post_body() {  # json_body
  local code i
  for i in 1 2 3 4; do
    code="$(curl -sS --max-time 25 -o /dev/null -w '%{http_code}' -X POST \
            "$API_BASE/api/federation/nodes/$NODE_ID/messages" \
            -H 'content-type: application/json' -d "$1" 2>/dev/null)"
    case "$code" in 2*) return 0;; esac
    sleep $(( i * 3 ))
  done
  return 1
}

post_msg() {  # to_node type text payload_json
  post_body "$(jq -nc --arg fn "$NODE_ID" --arg tn "$2" --arg ty "$3" --arg tx "$4" --argjson pl "${5:-{}}" \
              '{from_node:$fn,to_node:$tn,type:$ty,text:$tx,payload:$pl}')"
}

# --- act on one message: run a live local claude -p, capture, return it ---
act_on() {  # msg_id from_node text payload_json
  local mid="$1" frm="$2" text="$3" pl="$4"
  local sig want mode cwd capto out rc start ms
  sig="$(printf '%s' "$pl" | jq -r '.sig // empty')"
  want="$(hmac "$text")"
  if [ -z "$want" ] || [ "$sig" != "$want" ]; then
    log "UNKNOWN $mid from=$frm signature unrecognized (have=${sig:0:12}.. want=${want:0:12}..) — set aside"
    post_msg "$frm" command-result "set aside: signature not from this lineage" \
      "$(jq -nc --arg r "$mid" '{in_reply_to:$r, ok:false, reason:"unrecognized-signature"}')"
    return
  fi
  if [ ! -f "$LISTEN_FILE" ]; then
    log "REST  $mid from=$frm recognized but resting (touch $LISTEN_FILE to listen)"
    post_msg "$frm" command-result "resting: receiver is not listening right now" \
      "$(jq -nc --arg r "$mid" '{in_reply_to:$r, ok:false, reason:"resting"}')"
    return
  fi
  mode="$(printf '%s' "$pl" | jq -r '.permission_mode // empty')"; [ -n "$mode" ] || mode="$DEFAULT_MODE"
  case " $ALLOWED_MODES " in *" $mode "*) :;; *) mode="$DEFAULT_MODE";; esac
  cwd="$(printf '%s' "$pl" | jq -r '.cwd // empty')"; [ -d "$cwd" ] || cwd="$ROOT"
  capto="$(printf '%s' "$pl" | jq -r '.capture_to // empty')"; [ -n "$capto" ] || capto="$frm"

  log "ACT   $mid from=$frm mode=$mode cwd=$cwd -> waking live local claude"
  start="$(date +%s)"
  out="$(cd "$cwd" && run_bounded "$TIMEOUT" "$CLAUDE" -p "$text" --permission-mode "$mode" 2>&1)"; rc=$?
  ms=$(( ($(date +%s) - start) * 1000 ))
  # capture is durable LOCALLY first — even if the bus is down, the work isn't lost.
  local capdir="$HOME/.coherence-network/mesh-captures"; mkdir -p "$capdir"
  printf '%s' "$out" > "$capdir/$mid.txt"
  log "DONE  $mid rc=$rc ms=$ms chars=${#out} -> $capdir/$mid.txt"
  # build the full send-home envelope and persist it as resendable BEFORE trying the bus.
  local body
  body="$(jq -nc --arg fn "$NODE_ID" --arg tn "$capto" --arg tx "${out:0:1500}" \
            --arg r "$mid" --argjson ok "$([ $rc -eq 0 ] && echo true || echo false)" \
            --argjson ms "$ms" --arg full "$out" \
            '{from_node:$fn,to_node:$tn,type:"command-result",text:$tx,
              payload:{in_reply_to:$r, ok:$ok, ms:$ms, capture:$full}}')"
  printf '%s' "$body" > "$capdir/$mid.unsent.json"
  if post_body "$body"; then
    rm -f "$capdir/$mid.unsent.json"; log "SENT  $mid capture -> $capto"
  else
    log "UNSENT $mid capture held at $capdir/$mid.unsent.json (bus unreachable; --resend)"
  fi
}

# re-post any locally-held captures the bus dropped earlier (strained-edge recovery).
resend() {
  local capdir="$HOME/.coherence-network/mesh-captures" f mid n=0
  for f in "$capdir"/*.unsent.json; do
    [ -e "$f" ] || { log "RESEND none held"; return; }
    mid="$(basename "$f" .unsent.json)"
    if post_body "$(cat "$f")"; then rm -f "$f"; log "RESENT $mid"; n=$((n+1)); else log "RESEND-FAIL $mid"; fi
  done
  log "RESEND delivered=$n"
}

cycle() {
  local resp rows mid frm to ty text pl is_cmd for_me trust route
  resp="$(curl -sS --max-time 20 "$API_BASE/api/federation/nodes/$NODE_ID/messages?unread_only=true&limit=20" 2>/dev/null)"
  [ -n "$resp" ] || { log "POLL  no response from bus"; return; }
  rows="$(printf '%s' "$resp" | jq -c '.messages[]?' 2>/dev/null)"
  [ -n "$rows" ] || return
  while IFS= read -r m; do
    [ -n "$m" ] || continue
    mid="$(printf '%s' "$m" | jq -r '.id')"
    grep -qxF "$mid" "$SEEN" 2>/dev/null && continue
    echo "$mid" >> "$SEEN"
    frm="$(printf '%s' "$m" | jq -r '.from_node')"
    to="$(printf '%s' "$m" | jq -r '.to_node // empty')"
    ty="$(printf '%s' "$m" | jq -r '.type')"
    text="$(printf '%s' "$m" | jq -r '.text')"
    pl="$(printf '%s' "$m" | jq -c '.payload // {}')"
    is_cmd=$([ "$ty" = "command" ] && echo 1 || echo 0)
    for_me=$([ "$to" = "$NODE_ID" ] && echo 1 || echo 0)
    trust=$(is_lineage "$frm" && echo 1 || echo 0)
    route="$(mc_route "$is_cmd" "$for_me" "$trust")"
    case "$route" in
      act)    act_on "$mid" "$frm" "$text" "$pl" ;;
      refuse) log "REFUSE $mid from=$frm directed command from a node outside the lineage — set aside" ;;
      ignore) : ;;
    esac
  done <<< "$rows"
}

# --- local proof helper: dispatch a signed command to a node (acts as the cloud cell) ---
# The sig binds to the TARGET node (the receiver verifies with its own NODE_ID), so the
# HMAC is over "<to>\n<text>" with the lineage key — the key itself never crosses the wire.
dispatch() {  # to_node text [from_node] [permission_mode]
  local to="$1" text="$2" from="${3:-claude-sema-cloud}" mode="${4:-default}"
  local key sig
  key="$(cat "$KEY_FILE" 2>/dev/null)"
  [ -n "$key" ] || { echo "no lineage key at $KEY_FILE" >&2; return 1; }
  sig="$(printf '%s\n%s' "$to" "$text" | openssl dgst -sha256 -hmac "$key" -hex 2>/dev/null | sed 's/^.*= *//')"
  curl -sS --max-time 20 -X POST "$API_BASE/api/federation/nodes/$from/messages" \
    -H 'content-type: application/json' \
    -d "$(jq -nc --arg fn "$from" --arg tn "$to" --arg tx "$text" --arg sig "$sig" --arg cap "$from" --arg md "$mode" \
          '{from_node:$fn,to_node:$tn,type:"command",text:$tx,payload:{sig:$sig,capture_to:$cap,permission_mode:$md}}')" \
    | jq -c '{id, to:.to_node, type}' 2>/dev/null
}

touch "$SEEN" 2>/dev/null || true
case "${1:---once}" in
  --once)     resend; cycle ;;
  --loop)     while true; do resend; cycle; sleep "${2:-60}"; done ;;
  --resend)   resend ;;
  --dispatch) shift; dispatch "$@" ;;
  *) echo "usage: $0 [--once | --loop [secs] | --resend | --dispatch <to> <text> [from] [mode]]" >&2; exit 2 ;;
esac
