#!/usr/bin/env bash
# Clear agent task queue and reset PM so the next pipeline run starts in the right order
# (spec → impl → test → review). Requires API to be running with the DELETE /api/agent/tasks route.
set -e
API_URL="${API_URL:-http://localhost:8000}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$REPO_ROOT/api"

echo "Clearing agent task queue at $API_URL ..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$API_URL/api/agent/tasks?confirm=clear" || true)
if [ "$HTTP_CODE" = "204" ]; then
  echo "Queue cleared (204)."
elif [ "$HTTP_CODE" = "405" ]; then
  echo "ERROR: API returned 405 Method Not Allowed. Restart the API so it loads the DELETE /api/agent/tasks route, then re-run this script."
  exit 1
elif [ "$HTTP_CODE" = "400" ]; then
  echo "ERROR: Clear requires confirm=clear (got 400)."
  exit 1
else
  echo "ERROR: Unexpected response code: $HTTP_CODE"
  exit 1
fi

echo "Resetting project manager and creating spec task for first backlog item ..."
cd "$API_DIR"
.venv/bin/python scripts/project_manager.py --once -v --reset

echo "Done. Run the agent runner to execute the spec task (then PM again for impl, etc.):"
echo "  cd api && .venv/bin/python scripts/agent_runner.py --once -v"
