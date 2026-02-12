#!/bin/bash
# Ensure an effective pipeline: check prereqs, prompt user for required actions.
# Run this to see what needs attention before/during pipeline operation.
#
# Usage: ./scripts/ensure_effective_pipeline.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$API_DIR")"
cd "$API_DIR"

[ -f .env ] && set -a && source .env && set +a

BASE="${AGENT_API_BASE:-http://localhost:8000}"
PYTHON="${API_DIR}/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

echo "=== Pipeline Effectiveness Check ==="
echo ""

NEED_ACTION=0

# 1. API reachable
if curl -s --max-time 5 "${BASE}/api/health" >/dev/null 2>&1; then
  echo "[OK] API reachable at ${BASE}"
else
  echo "[ACTION] API not reachable. Start it:"
  echo "  cd api && uvicorn app.main:app --reload --port 8000"
  echo "  # or: ./scripts/start_with_telegram.sh"
  NEED_ACTION=1
fi

# 2. Metrics endpoint (needs API restart if 404)
if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${BASE}/api/agent/metrics" 2>/dev/null | grep -q 200; then
  echo "[OK] GET /api/agent/metrics returns 200"
else
  echo "[ACTION] GET /api/agent/metrics returns 404. Restart API to load metrics route."
  NEED_ACTION=1
fi

# 3. Monitor-issues endpoint
if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${BASE}/api/agent/monitor-issues" 2>/dev/null | grep -q 200; then
  echo "[OK] GET /api/agent/monitor-issues returns 200"
else
  echo "[ACTION] GET /api/agent/monitor-issues returns 404. Restart API to load monitor route."
  NEED_ACTION=1
fi

# 3b. Effectiveness endpoint (for measuring pipeline progress)
if curl -s --max-time 5 -o /dev/null -w "%{http_code}" "${BASE}/api/agent/effectiveness" 2>/dev/null | grep -q 200; then
  echo "[OK] GET /api/agent/effectiveness returns 200"
else
  echo "[ACTION] GET /api/agent/effectiveness returns 404. Restart API to load effectiveness route."
  NEED_ACTION=1
fi

# 4. Pipeline version file (written when pipeline starts)
if [ -f logs/pipeline_version.json ]; then
  echo "[OK] pipeline_version.json present (version tracking active)"
else
  echo "[INFO] No pipeline_version.json — pipeline not started with current script, or not yet run."
fi

# 5. Existing pipeline processes
if pgrep -f "project_manager.py" >/dev/null 2>&1; then
  echo "[INFO] Project manager is running (existing pipeline active)"
  if pgrep -f "monitor_pipeline.py" >/dev/null 2>&1; then
    echo "[OK] Monitor is running"
  else
    echo "[ACTION] Monitor not running. Restart pipeline to start monitor."
    NEED_ACTION=1
  fi
  if pgrep -f "agent_runner.py" >/dev/null 2>&1; then
    echo "[OK] Agent runner is running"
    # Require --workers 5 for phase coverage (spec 028)
    runner_line=$(ps aux 2>/dev/null | grep -v grep | grep agent_runner | grep python | head -1)
    if [ -n "$runner_line" ]; then
      if echo "$runner_line" | grep -qE '\--workers [0-9]+'; then
        workers=$(echo "$runner_line" | sed -n 's/.*--workers \([0-9]*\).*/\1/p')
        if [ -n "$workers" ] && [ "$workers" -lt 5 ] 2>/dev/null; then
          echo "[ACTION] agent_runner has workers=$workers (need 5 for phase coverage). Restart pipeline."
          NEED_ACTION=1
        fi
      else
        echo "[ACTION] agent_runner running without --workers (default 1). Restart with: ./scripts/run_overnight_pipeline.sh"
        NEED_ACTION=1
      fi
    fi
  else
    echo "[ACTION] Agent runner not running. Restart pipeline."
    NEED_ACTION=1
  fi
  # Require PM --parallel for phase coverage
  pm_line=$(ps aux 2>/dev/null | grep -v grep | grep project_manager | grep python | head -1)
  if [ -n "$pm_line" ] && ! echo "$pm_line" | grep -q '\--parallel'; then
    echo "[ACTION] Project manager not in --parallel mode. Restart pipeline: ./scripts/run_overnight_pipeline.sh"
    NEED_ACTION=1
  fi
else
  echo "[INFO] No pipeline running. To start:"
  echo "  cd api && ./scripts/run_overnight_pipeline.sh"
fi

# 6. Effectiveness summary (when API reachable)
if curl -s --max-time 5 "${BASE}/api/health" >/dev/null 2>&1; then
  eff=$(curl -s --max-time 5 "${BASE}/api/agent/effectiveness" 2>/dev/null)
  if [ -n "$eff" ] && echo "$eff" | grep -q "goal_proximity"; then
    echo ""
    echo "=== Effectiveness (last 7d) ==="
    echo "$eff" | "$PYTHON" -c "
import json,sys
try:
  d=json.load(sys.stdin)
  t=d.get('throughput',{})
  print('  Throughput:', t.get('completed_7d',0), 'tasks,', t.get('tasks_per_day',0), '/day')
  print('  Success rate:', int((d.get('success_rate',0) or 0)*100), '%')
  i=d.get('issues',{})
  print('  Issues: open=', i.get('open',0), ', resolved_7d=', i.get('resolved_7d',0))
  print('  Goal proximity:', d.get('goal_proximity',0))
  top=d.get('top_issues_by_priority',[])[:3]
  if top:
    print('  Top issues:', [x.get('condition') for x in top])
except Exception:
  pass
" 2>/dev/null || true
  fi
fi

echo ""
if [ "$NEED_ACTION" = "1" ]; then
  echo "=== REQUIRED ACTIONS ==="
  echo "1. Restart API (to load metrics + monitor-issues routes):"
  echo "   pkill -f uvicorn; cd api && uvicorn app.main:app --reload --port 8000"
  echo ""
  echo "2. Restart pipeline (to get workers=5, parallel mode, monitor, version tracking):"
  echo "   Ctrl+C in pipeline terminal, then: cd api && ./scripts/run_overnight_pipeline.sh"
  echo ""
  echo "3. Optional — use watchdog for auto-restart on stale version:"
  echo "   PIPELINE_AUTO_RECOVER=1 ./scripts/run_overnight_pipeline_watchdog.sh"
  exit 1
else
  echo "=== All checks passed. Pipeline should be effective. ==="
  exit 0
fi
