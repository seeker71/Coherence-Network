#!/bin/bash
set -euo pipefail

# Stable PATH for launchd/non-interactive shells.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
cd "$API_DIR"

if [ ! -f .env ]; then
  echo "[supervisor] missing .env in $API_DIR" >&2
  exit 1
fi

set -a
source .env
set +a

PORT="${PORT:-18161}"
if [ -z "${TELEGRAM_PERSONAL_BOT_TOKEN:-}" ]; then
  echo "[supervisor] TELEGRAM_PERSONAL_BOT_TOKEN is required" >&2
  exit 1
fi

PY="/opt/homebrew/opt/python@3.11/bin/python3.11"
if [ ! -x "$PY" ]; then
  echo "[supervisor] python runtime not found at $PY" >&2
  exit 1
fi

for required in curl jq lsof; do
  if ! command -v "$required" >/dev/null 2>&1; then
    echo "[supervisor] required command missing: $required" >&2
    exit 1
  fi
done

LOG_DIR="$API_DIR/logs"
mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/personal_api.log"
MONITOR_LOG="$LOG_DIR/assistant_monitor.log"
POLLER_LOG="$LOG_DIR/personal_poller.log"
RUNTIME_ENV="$LOG_DIR/personal_runtime.env"
QUEUE_LOG="$LOG_DIR/assistant_pending_queue.jsonl"
OFFSET_FILE="$LOG_DIR/personal_poller_offset.txt"
STATE_DIR="$LOG_DIR/assistant_monitor_state"
SUPERVISOR_PID_FILE="$LOG_DIR/personal_supervisor.pid"
mkdir -p "$STATE_DIR/pending" "$STATE_DIR/notified"

cleanup() {
  set +e
  [ -n "${POLLER_PID:-}" ] && kill "$POLLER_PID" 2>/dev/null || true
  [ -n "${MONITOR_PID:-}" ] && kill "$MONITOR_PID" 2>/dev/null || true
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "$$" > "$SUPERVISOR_PID_FILE"

# Free port if stale process exists.
for p in $(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
  kill "$p" 2>/dev/null || true
done
sleep 1

# Start API.
: > "$API_LOG"
"$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >> "$API_LOG" 2>&1 &
API_PID=$!
echo "[supervisor] API pid=$API_PID port=$PORT"

for i in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    echo "[supervisor] API healthy"
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "[supervisor] API exited early" >&2
    tail -n 120 "$API_LOG" >&2 || true
    exit 1
  fi
  sleep 1
  if [ "$i" -eq 90 ]; then
    echo "[supervisor] API failed to become healthy" >&2
    tail -n 120 "$API_LOG" >&2 || true
    exit 1
  fi
done

# Switch bot to long-poll mode (no public webhook/tunnel required).
DELETE_RESP="$(curl -s "https://api.telegram.org/bot${TELEGRAM_PERSONAL_BOT_TOKEN}/deleteWebhook?drop_pending_updates=false")"
if [ "$(printf "%s" "$DELETE_RESP" | jq -r '.ok')" != "true" ]; then
  echo "[supervisor] deleteWebhook failed: $DELETE_RESP" >&2
fi
printf "%s\n" "$DELETE_RESP" | jq -r '.' > "$LOG_DIR/personal_delete_webhook.json"

# Poller loop.
: > "$POLLER_LOG"
(
  offset="0"
  if [ -f "$OFFSET_FILE" ]; then
    offset="$(cat "$OFFSET_FILE" | tr -cd '0-9')"
    [ -z "$offset" ] && offset="0"
  fi
  echo "[$(date -u +%FT%TZ)] poller_start offset=$offset" >> "$POLLER_LOG"

  while true; do
    resp="$(curl -s --max-time 70 "https://api.telegram.org/bot${TELEGRAM_PERSONAL_BOT_TOKEN}/getUpdates?timeout=60&offset=${offset}")"
    ok="$(printf "%s" "$resp" | jq -r '.ok // false')"
    if [ "$ok" != "true" ]; then
      echo "[$(date -u +%FT%TZ)] getUpdates_failed $(printf "%s" "$resp" | tr '\n' ' ' | head -c 300)" >> "$POLLER_LOG"
      sleep 2
      continue
    fi

    while IFS= read -r upd; do
      [ -z "$upd" ] && continue
      update_id="$(printf "%s" "$upd" | jq -r '.update_id')"
      curl -s -X POST "http://127.0.0.1:${PORT}/api/assistant/telegram/webhook" \
        -H "Content-Type: application/json" \
        -d "$upd" >/dev/null || true
      offset="$((update_id + 1))"
      printf "%s" "$offset" > "$OFFSET_FILE"
      echo "[$(date -u +%FT%TZ)] update_processed id=$update_id next_offset=$offset" >> "$POLLER_LOG"
    done < <(printf "%s" "$resp" | jq -c '.result[]?')
  done
) &
POLLER_PID=$!

# Monitor loop (queue + completion callbacks).
: > "$MONITOR_LOG"
(
  send_msg() {
    local chat_id="$1"
    local text="$2"
    if [ -z "${chat_id}" ] || [ -z "${TELEGRAM_PERSONAL_BOT_TOKEN:-}" ]; then
      return 0
    fi
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_PERSONAL_BOT_TOKEN}/sendMessage" \
      -H "Content-Type: application/json" \
      -d "$(jq -n --arg c "$chat_id" --arg t "$text" '{chat_id:$c,text:$t}')" >/dev/null || true
  }

  while true; do
    TASK_IDS="$(curl -fsS "http://127.0.0.1:${PORT}/api/agent/tasks?limit=100" | jq -r '.tasks[].id' || true)"
    if [ -n "$TASK_IDS" ]; then
      while IFS= read -r task_id; do
        [ -z "$task_id" ] && continue
        TASK_JSON="$(curl -fsS "http://127.0.0.1:${PORT}/api/agent/tasks/${task_id}" || true)"
        [ -z "$TASK_JSON" ] && continue

        SOURCE="$(printf "%s" "$TASK_JSON" | jq -r '.context.source // ""')"
        [ "$SOURCE" != "telegram_personal_assistant" ] && continue

        STATUS="$(printf "%s" "$TASK_JSON" | jq -r '.status // "unknown"')"
        CHAT_ID="$(printf "%s" "$TASK_JSON" | jq -r '.context.telegram_chat_id // ""')"
        DIRECTION="$(printf "%s" "$TASK_JSON" | jq -r '.direction // ""' | head -c 220)"
        UPDATED_AT="$(printf "%s" "$TASK_JSON" | jq -r '.updated_at // .created_at // ""')"

        if [ "$STATUS" = "pending" ] && [ ! -f "$STATE_DIR/pending/$task_id" ]; then
          printf '%s\n' "$(printf "%s" "$TASK_JSON" | jq -c '{id,status,direction,created_at,updated_at,context:{telegram_chat_id:(.context.telegram_chat_id // ""),telegram_user_id:(.context.telegram_user_id // "")}}')" >> "$QUEUE_LOG"
          touch "$STATE_DIR/pending/$task_id"
          echo "[$(date -u +%FT%TZ)] queued $task_id" >> "$MONITOR_LOG"
        fi

        if { [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; } && [ ! -f "$STATE_DIR/notified/$task_id" ]; then
          OUTPUT="$(printf "%s" "$TASK_JSON" | jq -r '.output // ""' | tr -d '\r' | head -c 2500)"
          MSG="Task ${task_id} is ${STATUS}\nUpdated: ${UPDATED_AT}\nRequest: ${DIRECTION}"
          if [ -n "$OUTPUT" ]; then
            MSG="${MSG}\n\nOutput:\n${OUTPUT}"
          fi
          send_msg "$CHAT_ID" "$MSG"
          touch "$STATE_DIR/notified/$task_id"
          echo "[$(date -u +%FT%TZ)] notified $task_id status=$STATUS" >> "$MONITOR_LOG"
        fi
      done <<< "$TASK_IDS"
    fi
    sleep 5
  done
) &
MONITOR_PID=$!

{
  printf "MODE=polling\n"
  printf "API_PORT=%s\n" "$PORT"
  printf "API_PID=%s\n" "$API_PID"
  printf "POLLER_PID=%s\n" "$POLLER_PID"
  printf "MONITOR_PID=%s\n" "$MONITOR_PID"
  printf "OFFSET_FILE=%s\n" "$OFFSET_FILE"
  printf "QUEUE_LOG=%s\n" "$QUEUE_LOG"
  printf "EXEC_TOKEN_FILE=%s\n" "$LOG_DIR/assistant_execute_token.txt"
} > "$RUNTIME_ENV"

cat "$RUNTIME_ENV"

while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "[supervisor] API process exited" >&2
    tail -n 120 "$API_LOG" >&2 || true
    exit 1
  fi
  if ! kill -0 "$POLLER_PID" 2>/dev/null; then
    echo "[supervisor] Poller process exited" >&2
    tail -n 120 "$POLLER_LOG" >&2 || true
    exit 1
  fi
  if ! kill -0 "$MONITOR_PID" 2>/dev/null; then
    echo "[supervisor] Monitor process exited" >&2
    tail -n 120 "$MONITOR_LOG" >&2 || true
    exit 1
  fi
  sleep 3
done
