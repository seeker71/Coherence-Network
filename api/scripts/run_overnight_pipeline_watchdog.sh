#!/bin/bash
# Watchdog: run overnight pipeline, restart when monitor requests (stale version, etc).
# Use when PIPELINE_AUTO_RECOVER=1 and you want automatic restart on detected issues.
#
# Usage: ./scripts/run_overnight_pipeline_watchdog.sh [--hours 8]
# Prereq: API running. Set PIPELINE_AUTO_RECOVER=1 for monitor to write restart_requested.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$API_DIR")"
RESTART_FILE="$API_DIR/logs/restart_requested.json"
cd "$API_DIR"

[ -f .env ] && set -a && source .env && set +a

export PIPELINE_AUTO_RECOVER="${PIPELINE_AUTO_RECOVER:-1}"
echo "Watchdog: PIPELINE_AUTO_RECOVER=$PIPELINE_AUTO_RECOVER"
echo "Monitor will write $RESTART_FILE when restart needed (e.g. stale version)"
echo ""

while true; do
  echo "--- Starting pipeline $(date '+%Y-%m-%d %H:%M:%S') ---"
  "$SCRIPT_DIR/run_overnight_pipeline.sh" "$@" &
  PIPELINE_PID=$!

  # Wait for pipeline to exit, or check restart_requested every 90s
  RESTART_NEEDED=0
  while kill -0 $PIPELINE_PID 2>/dev/null; do
    sleep 90
    if [ -f "$RESTART_FILE" ]; then
      echo ""
      echo "--- Restart requested $(date '+%Y-%m-%d %H:%M:%S') ---"
      cat "$RESTART_FILE" 2>/dev/null || true
      rm -f "$RESTART_FILE"
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
