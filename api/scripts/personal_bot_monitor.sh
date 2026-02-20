#!/bin/bash
set -euo pipefail

# One-shot watchdog for the personal assistant bot service.
# Intended to run under launchd StartInterval.

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
REPO_DIR="$(dirname "$API_DIR")"
LOG_DIR="$API_DIR/logs"
mkdir -p "$LOG_DIR"

ENV_FILE="$API_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

PORT="${PORT:-18161}"
BOT_LABEL="com.coherence.personal-assistant.polling"
BOT_TARGET="gui/$(id -u)/${BOT_LABEL}"
BOT_SERVICE_SCRIPT="$SCRIPT_DIR/personal_bot_service.sh"

MONITOR_LOG="$LOG_DIR/personal_bot_monitor.log"
LOCK_DIR="$LOG_DIR/personal_bot_monitor.lock"
RUNTIME_ENV="$LOG_DIR/personal_runtime.env"
INCIDENT_ROOT="$LOG_DIR/personal_monitor_incidents"
COOLDOWN_FILE="$LOG_DIR/personal_bot_monitor_escalation.ts"
COOLDOWN_SEC="${PERSONAL_BOT_MONITOR_ESCALATE_COOLDOWN_SEC:-1800}"

mkdir -p "$INCIDENT_ROOT"

log() {
  printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*" >> "$MONITOR_LOG"
}

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "skip: lock held"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

service_running() {
  local tmp state pid
  tmp="$(mktemp)"
  if ! launchctl print "$BOT_TARGET" >"$tmp" 2>/dev/null; then
    rm -f "$tmp"
    return 1
  fi
  state="$(awk -F'= ' '/^[[:space:]]*state = /{print $2; exit}' "$tmp" | tr -d '[:space:]')"
  pid="$(awk -F'= ' '/^[[:space:]]*pid = /{print $2; exit}' "$tmp" | tr -d '[:space:]')"
  rm -f "$tmp"
  if [ "$state" != "running" ]; then
    return 1
  fi
  if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
    return 1
  fi
  kill -0 "$pid" 2>/dev/null
}

api_healthy() {
  curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1
}

runtime_processes_ok() {
  if [ ! -f "$RUNTIME_ENV" ]; then
    return 1
  fi
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  for key in API_PID POLLER_PID MONITOR_PID; do
    pid="${!key:-}"
    if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
      return 1
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      return 1
    fi
  done
  return 0
}

can_escalate_now() {
  local now last
  now="$(date +%s)"
  if [ ! -f "$COOLDOWN_FILE" ]; then
    return 0
  fi
  last="$(tr -cd '0-9' < "$COOLDOWN_FILE")"
  if [ -z "$last" ]; then
    return 0
  fi
  if [ "$((now - last))" -ge "$COOLDOWN_SEC" ]; then
    return 0
  fi
  return 1
}

write_incident_bundle() {
  local incident_dir="$1"
  mkdir -p "$incident_dir"

  {
    echo "timestamp_utc=$(date -u +%FT%TZ)"
    echo "bot_target=${BOT_TARGET}"
    echo "port=${PORT}"
  } > "$incident_dir/summary.env"

  launchctl print "$BOT_TARGET" > "$incident_dir/launchctl_print.txt" 2>&1 || true
  ps aux | rg -i 'start_personal_polling|uvicorn app.main:app|personal_bot_monitor' > "$incident_dir/processes.txt" || true
  curl -fsS "http://127.0.0.1:${PORT}/api/health" > "$incident_dir/api_health.json" 2>&1 || true
  [ -f "$RUNTIME_ENV" ] && cp "$RUNTIME_ENV" "$incident_dir/personal_runtime.env" || true
  [ -f "$LOG_DIR/personal_supervisor_polling.out" ] && tail -n 200 "$LOG_DIR/personal_supervisor_polling.out" > "$incident_dir/personal_supervisor_polling.out.tail" || true
  [ -f "$LOG_DIR/personal_supervisor_polling.err" ] && tail -n 200 "$LOG_DIR/personal_supervisor_polling.err" > "$incident_dir/personal_supervisor_polling.err.tail" || true
  [ -f "$LOG_DIR/personal_poller.log" ] && tail -n 200 "$LOG_DIR/personal_poller.log" > "$incident_dir/personal_poller.log.tail" || true
  [ -f "$LOG_DIR/assistant_monitor.log" ] && tail -n 200 "$LOG_DIR/assistant_monitor.log" > "$incident_dir/assistant_monitor.log.tail" || true
}

spawn_codex_diagnostics() {
  local incident_dir="$1"
  local prompt_file codex_log last_message_file

  if ! command -v codex >/dev/null 2>&1; then
    log "escalation: codex binary missing; incident=$incident_dir"
    return 1
  fi

  prompt_file="$incident_dir/codex_prompt.txt"
  codex_log="$incident_dir/codex_exec.jsonl"
  last_message_file="$incident_dir/codex_last_message.txt"

  cat > "$prompt_file" <<EOF
Personal assistant Telegram bot monitor escalation.

Incident directory: $incident_dir
Repository: $REPO_DIR

Goal:
1) Diagnose why service '${BOT_LABEL}' is not healthy.
2) Apply a fix.
3) Bring the bot back up.
4) Verify:
   - /Users/ursmuff/.claude-worktrees/Coherence-Network/telegram-personal-assistant/api/scripts/personal_bot_service.sh status
   - curl -fsS http://127.0.0.1:${PORT}/api/health
5) Write a concise diagnostics+fix report to:
   $incident_dir/diagnostics_report.md

Use the incident artifacts in this folder first.
EOF

  nohup codex exec \
    --dangerously-bypass-approvals-and-sandbox \
    -C "$REPO_DIR" \
    --json \
    --output-last-message "$last_message_file" \
    - < "$prompt_file" > "$codex_log" 2>&1 &
  local codex_pid=$!
  echo "$codex_pid" > "$incident_dir/codex_pid"
  log "escalation: started codex exec pid=$codex_pid incident=$incident_dir"
  return 0
}

healthy_now() {
  service_running && api_healthy && runtime_processes_ok
}

log "check: begin"
if healthy_now; then
  log "check: healthy"
  exit 0
fi

log "check: unhealthy -> attempting restart"
if [ -x "$BOT_SERVICE_SCRIPT" ]; then
  "$BOT_SERVICE_SCRIPT" restart >> "$MONITOR_LOG" 2>&1 || true
else
  log "restart: missing service script $BOT_SERVICE_SCRIPT"
fi
sleep 10

if healthy_now; then
  log "recovery: successful after restart"
  exit 0
fi

incident_ts="$(date -u +%Y%m%dT%H%M%SZ)"
incident_dir="$INCIDENT_ROOT/$incident_ts"
write_incident_bundle "$incident_dir"
log "recovery: failed incident=$incident_dir"

if can_escalate_now; then
  if spawn_codex_diagnostics "$incident_dir"; then
    date +%s > "$COOLDOWN_FILE"
  fi
else
  log "escalation: skipped due cooldown (${COOLDOWN_SEC}s)"
fi

exit 0
