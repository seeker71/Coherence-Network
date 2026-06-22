#!/usr/bin/env bash
# kernel_memory_witness.sh — a host guardian (carrier tissue, not Form logic).
#
# The Form kernels (Go / Rust / TS / fkwu) run UNBOUNDED by design: a four-way
# proof walk is meant to use the host's full stack and heap. macOS does not
# enforce RLIMIT_AS (`ulimit -v` is silently ignored), so a single
# non-terminating band can balloon ONE kernel process to ~100 GB and OOM the
# whole machine — the JetsamEvent cascade (vm-compressor-space-shortage ->
# hundreds of system daemons jettisoned) that froze this Mac twice on
# 2026-06-21. The Rust arm is the catastrophic shape: where Go/TS/fkwu hit a
# stack wall and die alone, Rust allocates on the heap and runs to ~100 GB.
#
# This witness watches ONLY the kernel processes (by command substring — never
# claude / MCP / other node) and SIGKILLs any one that crosses a generous
# ceiling, so a runaway dies alone instead of taking the Mac down. Every catch
# is named (log + notification + mesh) so the non-terminating band becomes a
# visible, huntable event rather than a silent crash.
#
# It is a NET, not the fix. The durable fix is the kernel self-limiting and the
# non-terminating recipe healed at the source. This only guarantees the machine
# survives long enough to hunt that band safely. The cost of a false-positive
# kill (a legit >ceiling band shows as a failed leg, an agent investigates) is
# far smaller than the cost the net prevents (the whole machine going down).
set -uo pipefail

CAP_GB="${FORM_KERNEL_MEM_CAP_GB:-16}"          # legit bands use <2 GB; 100 GB killed the Mac
INTERVAL="${FORM_KERNEL_WITNESS_INTERVAL:-2}"   # one ps+awk every INTERVAL s — negligible
CAP_KB=$(( CAP_GB * 1024 * 1024 ))
LOG="${FORM_KERNEL_WITNESS_LOG:-$HOME/Library/Logs/CoherenceSense/kernel-memory-witness.log}"
COORD="${FORM_KERNEL_WITNESS_COORD:-/Users/ursmuff/source/Coherence-Network/scripts/agent-coord.sh}"

# Match only Form kernel processes. These substrings never appear in the claude
# CLI, the MCP node servers, or any other host process.
PATTERN='form-kernel-rust|form-kernel-ts|form-kernel-go|/bin-go( |$)|(^|/)fkwu'

mkdir -p "$(dirname "$LOG")"
log() { printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" >> "$LOG"; }

log "kernel-memory-witness up — cap=${CAP_GB}GB interval=${INTERVAL}s"

while true; do
  # awk does the cheap numeric filter; the per-pid command lookup (and any kill)
  # only happens for the RARE process already over the ceiling. ps RSS is in KB.
  while read -r pid rss; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    cmd="$(ps -p "$pid" -o command= 2>/dev/null)" || continue
    [[ -n "$cmd" ]] || continue
    case "$cmd" in *kernel_memory_witness*) continue ;; esac   # never ourselves
    printf '%s' "$cmd" | grep -Eq "$PATTERN" || continue
    gb=$(( rss / 1024 / 1024 ))
    log "RUNAWAY KILL pid=$pid rss=${gb}GB (cap=${CAP_GB}GB) cmd=${cmd:0:180}"
    if kill -9 "$pid" 2>/dev/null; then
      log "  killed $pid"
    else
      log "  kill failed $pid (already gone?)"
    fi
    osascript -e "display notification \"Killed a runaway Form kernel at ${gb}GB before it could OOM the Mac. A band is non-terminating — hunt it.\" with title \"Coherence — kernel memory witness\" sound name \"Basso\"" 2>/dev/null || true
    # publish the catch onto the mesh so it is witnessable, not only local
    [[ -f "$COORD" ]] && COORD_AGENT=kernel-witness bash "$COORD" share \
      "killed a runaway Form kernel at ${gb}GB (cap ${CAP_GB}GB) — a band is non-terminating; hunt it" \
      >/dev/null 2>&1 || true
  done < <(ps -axo pid=,rss= | awk -v cap="$CAP_KB" '$2+0 > cap {print $1, $2}')
  sleep "$INTERVAL"
done
