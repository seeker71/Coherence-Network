#!/bin/bash
# Smoke test: verify API and pipeline endpoints. Run with API running.
# Usage: ./scripts/smoke_test.sh [BASE_URL]
# Default BASE_URL: http://localhost:8000

set -e
BASE="${1:-http://localhost:8000}"

echo "Smoke test: $BASE"
curl -s -o /dev/null -w "%{http_code}" "$BASE/api/health" | grep -q 200 || { echo "FAIL: /api/health"; exit 1; }
echo "  /api/health OK"
curl -s -o /dev/null -w "%{http_code}" "$BASE/api/agent/pipeline-status" | grep -qE "200|404" || { echo "FAIL: /api/agent/pipeline-status"; exit 1; }
echo "  /api/agent/pipeline-status OK"
TASK=$(curl -s -X POST "$BASE/api/agent/tasks" -H "Content-Type: application/json" \
  -d '{"direction":"smoke","task_type":"impl","context":{"command_override":"echo smoke-ok"}}' | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
[ -n "$TASK" ] || { echo "FAIL: create task"; exit 1; }
echo "  Created task $TASK"
echo "Smoke test PASSED"
