#!/bin/bash
# Run the full overnight pipeline: project manager + agent runner.
# Stops overnight_orchestrator first (it conflicts with project manager).
#
# Prereq: API must be running (./scripts/start_with_telegram.sh in another terminal)
#
# Usage: ./scripts/run_overnight_pipeline.sh [--hours 8] [--backlog PATH] [--cursor]
#   --hours 8   Run for 8 hours (default)
#   --backlog   Backlog file (default: specs/006-overnight-backlog.md)
#   --cursor    Use Cursor CLI (agent) instead of Claude Code for tasks

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$API_DIR")"
cd "$API_DIR"

[ -f .env ] && set -a && source .env && set +a

PYTHON="${API_DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"
BASE="${AGENT_API_BASE:-http://localhost:8000}"
HOURS=8
BACKLOG="${PROJECT_ROOT}/specs/006-overnight-backlog.md"
CURSOR_ARG=""
for arg in "$@"; do
  case "$arg" in
    --hours=*) HOURS="${arg#--hours=}" ;;
    --backlog=*) BACKLOG="${arg#--backlog=}" ;;
    --cursor) CURSOR_ARG="--cursor" ;;
    --claude) CURSOR_ARG="--claude" ;;
  esac
done
# Use cursor when AGENT_EXECUTOR_DEFAULT=cursor (from .env) unless --claude passed
if [ -z "$CURSOR_ARG" ] && [ "${AGENT_EXECUTOR_DEFAULT:-}" = "cursor" ]; then
  CURSOR_ARG="--cursor"
fi

# 1. Stop overnight_orchestrator (conflicts with project manager)
if pkill -f "overnight_orchestrator" 2>/dev/null; then
  echo "Stopped overnight_orchestrator (use project_manager for full pipeline)"
  sleep 1
fi

# 2. Check API
if ! curl -s --max-time 5 "${BASE}/api/health" >/dev/null 2>&1; then
  echo "API not reachable at ${BASE}. Start it first:"
  echo "  ./scripts/start_with_telegram.sh"
  exit 1
fi
echo "API OK"
if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${BASE}/api/agent/pipeline-status" | grep -q 404; then
  echo "WARNING: pipeline-status returns 404. Restart API for full visibility: ./scripts/start_with_telegram.sh"
fi

# 3. Start agent runner in background
echo "Starting agent runner..."
$PYTHON scripts/agent_runner.py --interval 10 --verbose >> logs/agent_runner.log 2>&1 &
RUNNER_PID=$!
echo "  Agent runner PID: $RUNNER_PID"

# 4. Start pipeline status loop in background (prints every 60s)
status_loop() {
  while true; do
    sleep 60
    echo ""
    echo "--- Pipeline Status $(date '+%Y-%m-%d %H:%M:%S') ---"
    $PYTHON scripts/check_pipeline.py 2>/dev/null || echo "  (API unreachable)"
    echo ""
  done
}
status_loop &
STATUS_PID=$!

# 5. Start project manager (foreground; Ctrl+C stops both)
cleanup() {
  echo ""
  echo "Stopping..."
  kill $STATUS_PID 2>/dev/null || true
  kill $RUNNER_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "Starting project manager (hours=$HOURS, backlog=$BACKLOG)..."
echo "  Pipeline status every 60s. Press Ctrl+C to stop"
echo ""
echo "--- Pipeline Status $(date '+%Y-%m-%d %H:%M:%S') ---"
$PYTHON scripts/check_pipeline.py 2>/dev/null || echo "  (API unreachable)"
echo ""
$PYTHON scripts/project_manager.py --interval 15 --hours "$HOURS" --verbose \
  --backlog "$BACKLOG" --state-file api/logs/project_manager_state_overnight.json --reset $CURSOR_ARG
