#!/bin/bash
# Watchdog: run overnight pipeline, restart when monitor requests (stale version, api_unreachable).
# Starts API if not running (full automation in one command).
#
# Usage: ./scripts/run_overnight_pipeline_watchdog.sh [--hours 8]
# Set PIPELINE_AUTO_RECOVER=1 for monitor to write restart_requested.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$API_DIR")"
RESTART_FILE="$API_DIR/logs/restart_requested.json"
PYTHON="${API_DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"
cd "$API_DIR"

[ -f .env ] && set -a && source .env && set +a

export PIPELINE_AUTO_RECOVER="${PIPELINE_AUTO_RECOVER:-1}"
PORT="${PORT:-8000}"
BASE="${AGENT_API_BASE:-http://127.0.0.1:$PORT}"

_api_alive() { curl -s --max-time 5 "${BASE}/api/health" >/dev/null 2>&1; }
_start_api() {
  pkill -f "uvicorn app.main" 2>/dev/null || true
  sleep 2
  $PYTHON -m uvicorn app.main:app --port "$PORT" --host 127.0.0.1 >> "$API_DIR/logs/autonomous_api.log" 2>&1 &
}

echo "Watchdog: PIPELINE_AUTO_RECOVER=$PIPELINE_AUTO_RECOVER"
echo "Monitor will write $RESTART_FILE when restart needed (e.g. stale version, api_unreachable)"
if ! _api_alive; then
  echo "API not running — starting API on port $PORT..."
  export AGENT_API_BASE="http://127.0.0.1:$PORT"
  BASE="$AGENT_API_BASE"
  _start_api
  for i in $(seq 1 30); do
    sleep 1
    if _api_alive; then echo "  API ready."; break; fi
    [ $i -eq 30 ] && { echo "  API failed to start. Start manually: cd api && uvicorn app.main:app --port $PORT"; exit 1; }
  done
else
  echo "API OK at $BASE"
fi
echo ""

while true; do
  echo "--- Starting pipeline $(date '+%Y-%m-%d %H:%M:%S') ---"
  "$SCRIPT_DIR/run_overnight_pipeline.sh" --no-watchdog "$@" &
  PIPELINE_PID=$!

  # Wait for pipeline to exit, or check restart_requested every 90s
  RESTART_NEEDED=0
  while kill -0 $PIPELINE_PID 2>/dev/null; do
    sleep 90
    if [ -f "$RESTART_FILE" ]; then
      echo ""
      echo "--- Restart requested $(date '+%Y-%m-%d %H:%M:%S') ---"
      cat "$RESTART_FILE" 2>/dev/null || true
      REASON=$($PYTHON -c "import json; d=json.load(open('$RESTART_FILE')); print(d.get('reason',''))" 2>/dev/null || true)
      rm -f "$RESTART_FILE"
      # When api_unreachable or effectiveness_404, restart API (stale routes need fresh API process)
      if [ "$REASON" = "api_unreachable" ] || [ "$REASON" = "effectiveness_404" ]; then
        echo "API unreachable — attempting API restart..."
        pkill -f "uvicorn app.main" 2>/dev/null || true
        sleep 2
        PORT="${PORT:-8000}"
        $PYTHON -m uvicorn app.main:app --port "$PORT" --host 127.0.0.1 >> "$API_DIR/logs/autonomous_api.log" 2>&1 &
        sleep 5
        if curl -s --max-time 5 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
          echo "  API restarted."
        else
          echo "  API restart may have failed (check logs)."
        fi
      fi
      echo "Stopping pipeline (PID $PIPELINE_PID)..."
      kill $PIPELINE_PID 2>/dev/null || true
      wait $PIPELINE_PID 2>/dev/null || true
      sleep 3
      RESTART_NEEDED=1
      break
    fi
  done

  # If pipeline exited without restart requested
  if [ "$RESTART_NEEDED" = "0" ]; then
    wait $PIPELINE_PID 2>/dev/null || true
    # In autonomous mode, always restart (maximize autonomy)
    if [ "${PIPELINE_AUTONOMOUS:-0}" = "1" ]; then
      echo "Pipeline exited. Autonomous mode: restarting in 10s..."
      sleep 10
    else
      echo "Pipeline exited. Watchdog stopping."
      exit 0
    fi
  else
    echo "Restarting pipeline in 5s..."
    sleep 5
  fi
done
