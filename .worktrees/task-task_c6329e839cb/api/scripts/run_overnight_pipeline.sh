#!/bin/bash
# Run the full overnight pipeline: project manager + agent runner.
# Stops overnight_orchestrator first (it conflicts with project manager).
#
# By default, uses the watchdog for full automation (restarts on stale_version, api_unreachable).
# Pass --no-watchdog to run once without watchdog.
#
# Prereq: API must be running, or use watchdog (starts API if down).
#
# Usage: ./scripts/run_overnight_pipeline.sh [--hours 8] [--backlog PATH] [--cursor] [--no-watchdog]
#   --hours 8      Run for 8 hours (default)
#   --backlog      Backlog file (default: specs/006-overnight-backlog.md)
#   --cursor       Use Cursor CLI (agent) instead of Claude Code for tasks
#   --no-watchdog  Run without watchdog (no auto-restart; use when invoked by watchdog)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$API_DIR")"
cd "$API_DIR"

[ -f .env ] && set -a && source .env && set +a

# Default: use watchdog for full automation (restarts on stale, api_unreachable). Pass --no-watchdog to skip.
USE_WATCHDOG=1
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "--no-watchdog" ]; then
    USE_WATCHDOG=0
  else
    ARGS+=("$arg")
  fi
done
if [ "$USE_WATCHDOG" = "1" ]; then
  echo "Full automation: using watchdog (auto-restart on stale_version, api_unreachable)"
  exec "$SCRIPT_DIR/run_overnight_pipeline_watchdog.sh" "${ARGS[@]}"
fi

# Meta-pipeline: interleave 20% meta items (EXECUTION-PLAN). Set PIPELINE_META_RATIO=0 to disable.
export PIPELINE_META_BACKLOG="${PIPELINE_META_BACKLOG:-${PROJECT_ROOT}/specs/007-meta-pipeline-backlog.md}"
export PIPELINE_META_RATIO="${PIPELINE_META_RATIO:-0.2}"

# Full automation: auto-fix, auto-recover, auto-commit default on for overnight.
# Set to 0 in .env to disable.
export PIPELINE_AUTO_FIX_ENABLED="${PIPELINE_AUTO_FIX_ENABLED:-1}"
export PIPELINE_AUTO_RECOVER="${PIPELINE_AUTO_RECOVER:-1}"
export PIPELINE_AUTO_COMMIT="${PIPELINE_AUTO_COMMIT:-1}"
export PIPELINE_AUTO_PUSH="${PIPELINE_AUTO_PUSH:-0}"

PYTHON="${API_DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"
BASE="${AGENT_API_BASE:-http://localhost:8000}"
HOURS=8
BACKLOG="${PROJECT_ROOT}/specs/006-overnight-backlog.md"
CURSOR_ARG=""
for arg in "${ARGS[@]}"; do
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

# 2. Write pipeline version (for monitor to detect stale code, restart if needed)
mkdir -p logs 2>/dev/null || true
GIT_SHA=""
[ -d "$PROJECT_ROOT/.git" ] && GIT_SHA=$(git -C "$PROJECT_ROOT" rev-parse HEAD 2>/dev/null) || true
echo "{\"git_sha\": \"${GIT_SHA:-unknown}\", \"started_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > logs/pipeline_version.json

# 3. Check API
if ! curl -s --max-time 5 "${BASE}/api/health" >/dev/null 2>&1; then
  echo "API not reachable at ${BASE}. Start it first:"
  echo "  ./scripts/start_with_telegram.sh"
  exit 1
fi
echo "API OK"
if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${BASE}/api/agent/pipeline-status" | grep -q 404; then
  echo "WARNING: pipeline-status returns 404. Restart API for full visibility: ./scripts/start_with_telegram.sh"
fi

# 3. Start agent runner in background (workers=5: spec, impl, test, review + buffer)
WORKERS="${AGENT_RUNNER_WORKERS:-5}"
echo "Starting agent runner (workers=$WORKERS)..."
$PYTHON scripts/agent_runner.py --interval 10 --workers "$WORKERS" --verbose >> logs/agent_runner.log 2>&1 &
RUNNER_PID=$!
echo "  Agent runner PID: $RUNNER_PID"

# 3b. Start monitor (version check, phase coverage, issues, fallback recovery)
MONITOR_INTERVAL="${PIPELINE_MONITOR_INTERVAL:-60}"
AUTOFIX=""; [ "$PIPELINE_AUTO_FIX_ENABLED" = "1" ] && AUTOFIX="--auto-fix"
AUTORECOV=""; [ "$PIPELINE_AUTO_RECOVER" = "1" ] && AUTORECOV="--auto-recover"
echo "Starting pipeline monitor (interval=${MONITOR_INTERVAL}s)..."
$PYTHON scripts/monitor_pipeline.py --interval "$MONITOR_INTERVAL" $AUTOFIX $AUTORECOV >> logs/monitor.log 2>&1 &
MONITOR_PID=$!
echo "  Monitor PID: $MONITOR_PID"

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

# 5. Start project manager (foreground; Ctrl+C stops all)
cleanup() {
  echo ""
  echo "Stopping..."
  kill $STATUS_PID 2>/dev/null || true
  kill $MONITOR_PID 2>/dev/null || true
  kill $RUNNER_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "Starting project manager (hours=$HOURS, backlog=$BACKLOG)..."
echo "  Auto-commit: ${PIPELINE_AUTO_COMMIT:-0} | Auto-push: ${PIPELINE_AUTO_PUSH:-0}"
echo "  Pipeline status every 60s. Press Ctrl+C to stop"
echo ""
echo "--- Pipeline Status $(date '+%Y-%m-%d %H:%M:%S') ---"
$PYTHON scripts/check_pipeline.py 2>/dev/null || echo "  (API unreachable)"
echo ""
PM_ARGS="--interval 15 --hours $HOURS --verbose --backlog $BACKLOG --state-file api/logs/project_manager_state_overnight.json --reset $CURSOR_ARG"
# Parallel mode: spec/impl/test/review in flight, 2+ specs buffered (spec 028). Default on.
[ "${PIPELINE_PARALLEL:-1}" = "1" ] && PM_ARGS="$PM_ARGS --parallel"
$PYTHON scripts/project_manager.py $PM_ARGS
