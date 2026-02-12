#!/bin/bash
# Autonomous pipeline: starts API + pipeline, restarts on failure, reports fatal issues only.
# Maximize autonomy, minimize user interaction. Run once; no further interaction needed.
#
# Usage: ./scripts/run_autonomous.sh
# Fatal issues written to api/logs/fatal_issues.json (check only when unrecoverable).

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$API_DIR")"
LOG_DIR="$API_DIR/logs"
FATAL_FILE="$LOG_DIR/fatal_issues.json"
API_LOG="$LOG_DIR/autonomous_api.log"
mkdir -p "$LOG_DIR"
cd "$API_DIR"

[ -f .env ] && set -a && source .env && set +a

PORT="${PORT:-8000}"
# Autonomous mode: we start the API, so point everything at it
export AGENT_API_BASE="http://127.0.0.1:$PORT"
BASE="$AGENT_API_BASE"
PYTHON="${API_DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"
export PIPELINE_AUTO_FIX_ENABLED="${PIPELINE_AUTO_FIX_ENABLED:-1}"
export PIPELINE_AUTO_RECOVER="${PIPELINE_AUTO_RECOVER:-1}"
export PIPELINE_AUTONOMOUS="${PIPELINE_AUTONOMOUS:-1}"
export PIPELINE_AUTO_COMMIT="${PIPELINE_AUTO_COMMIT:-1}"
export PIPELINE_AUTO_PUSH="${PIPELINE_AUTO_PUSH:-0}"
export PIPELINE_NEEDS_DECISION_TIMEOUT_HOURS="${PIPELINE_NEEDS_DECISION_TIMEOUT_HOURS:-24}"

_api_alive() { curl -s --max-time 5 "${BASE}/api/health" >/dev/null 2>&1; }
_write_fatal() {
  local reason="$1"
  local detail="${2:-}"
  echo "{\"at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\", \"reason\": \"$reason\", \"detail\": \"$detail\", \"recovery_attempted\": true}" > "$FATAL_FILE"
  echo "FATAL: $reason — see $FATAL_FILE"
}

_start_api() {
  pkill -f "uvicorn app.main" 2>/dev/null || true
  sleep 2
  $PYTHON -m uvicorn app.main:app --port "$PORT" --host 127.0.0.1 >> "$API_LOG" 2>&1 &
  echo $!
}

echo "=== Autonomous Pipeline ==="
echo "API: $BASE | Auto-fix: on | Auto-recover: on | Auto-commit: ${PIPELINE_AUTO_COMMIT:-0} | Auto-push: ${PIPELINE_AUTO_PUSH:-0}"
echo "Fatal issues: $FATAL_FILE"
echo ""

# Start or reuse API
API_PID=""
if _api_alive; then
  echo "[OK] API already running"
else
  echo "Starting API..."
  API_PID=$(_start_api)
  for i in $(seq 1 30); do
    sleep 1
    if _api_alive; then echo "  API ready."; API_PID=""; break; fi
    [ $i -eq 30 ] && { _write_fatal "api_start_failed" "API did not become healthy in 30s"; exit 1; }
  done
fi

# Start pipeline watchdog (runs pipeline, restarts on stale version or exit)
echo "Starting pipeline watchdog (autonomous mode, needs_decision timeout=${PIPELINE_NEEDS_DECISION_TIMEOUT_HOURS}h)..."
"$SCRIPT_DIR/run_overnight_pipeline_watchdog.sh" --hours=0 &
WATCHDOG_PID=$!
echo "  Watchdog PID: $WATCHDOG_PID"
echo ""
echo "Running. Ctrl+C to stop. Fatal issues only in $FATAL_FILE"
echo ""

# Monitor loop: restart API if down, restart watchdog if died, report fatal on repeated failure
API_RESTART_COUNT=0
WATCHDOG_RESTART_COUNT=0
MAX_API_RESTARTS=5
MAX_WATCHDOG_RESTARTS=10

while true; do
  sleep 120

  # Check API
  if ! _api_alive; then
    echo "[$(date '+%H:%M:%S')] API down, restarting..."
    pkill -f "uvicorn app.main" 2>/dev/null || true
    sleep 2
    API_PID=$(_start_api)
    for i in $(seq 1 20); do
      sleep 1
      if _api_alive; then
        echo "  API restarted."
        API_RESTART_COUNT=0
        break
      fi
    done
    if ! _api_alive; then
      API_RESTART_COUNT=$((API_RESTART_COUNT + 1))
      if [ "$API_RESTART_COUNT" -ge "$MAX_API_RESTARTS" ]; then
        _write_fatal "api_restart_failed" "API failed to start after $MAX_API_RESTARTS attempts"
        exit 1
      fi
    fi
  fi

  # Check watchdog (pipeline)
  if ! kill -0 $WATCHDOG_PID 2>/dev/null; then
    echo "[$(date '+%H:%M:%S')] Pipeline watchdog exited, restarting..."
    WATCHDOG_RESTART_COUNT=$((WATCHDOG_RESTART_COUNT + 1))
    if [ "$WATCHDOG_RESTART_COUNT" -ge "$MAX_WATCHDOG_RESTARTS" ]; then
      _write_fatal "pipeline_restart_failed" "Watchdog exited $MAX_WATCHDOG_RESTARTS times"
      exit 1
    fi
    "$SCRIPT_DIR/run_overnight_pipeline_watchdog.sh" --hours=0 &
    WATCHDOG_PID=$!
    sleep 5
  fi
done
