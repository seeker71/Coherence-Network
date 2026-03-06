#!/usr/bin/env bash
# Run Claude locally on one real impl task: discover via public API (highest-ROI gap),
# create task on local API with executor=claude, then run agent once.
# Prereqs: Claude Code CLI in PATH; local API at LOCAL_API_URL with AGENT_AUTO_EXECUTE=0.
set -e
PUBLIC_API_URL="${PUBLIC_API_URL:-https://coherence-network-production.up.railway.app}"
LOCAL_API_URL="${LOCAL_API_URL:-http://127.0.0.1:8000}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_DIR="$REPO_ROOT/api"

if ! command -v claude &>/dev/null; then
  echo "Claude CLI not found in PATH. Install from https://claude.com/docs/claude-code and retry."
  exit 1
fi

# Optional: pin a spec and skip discovery (local API mode validation)
if [ -n "${SPEC_ID:-}" ]; then
  TITLE="${SPEC_TITLE:-Implement spec $SPEC_ID}"
  PAYLOAD=$(python3 -c "
import json
spec_id = '''$SPEC_ID'''.strip()
title = '''$TITLE'''.strip() or spec_id
direction = (
    f'Implement spec {spec_id} ({title}) from spec file. '
    'Follow the spec verification contract, add/update tests for behavior, and run local validation. '
    'Do not modify tests only to force pass.'
)
context = {'executor': 'claude', 'source': 'spec_implementation_gap', 'spec_id': spec_id, 'spec_title': title}
print(json.dumps({'direction': direction, 'task_type': 'impl', 'context': context}))
" 2>/dev/null)
  echo "Using pinned spec_id=$SPEC_ID (skip discovery)."
else
echo "Discovering highest-ROI gap from public API..."
# Prefer specs without implementation (in_progress), then ideas without spec (none)
SPEC_RESP=$(curl -s -L "$PUBLIC_API_URL/api/spec-registry/cards?state=in_progress&sort=roi_desc&limit=1")
ITEMS=$(echo "$SPEC_RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    items = d.get('items') or d.get('data') or []
    print(json.dumps(items[:1]))
except Exception:
    print('[]')
" 2>/dev/null || echo "[]")

if [ -z "$ITEMS" ] || [ "$ITEMS" = "[]" ]; then
  IDEA_RESP=$(curl -s -L "$PUBLIC_API_URL/api/ideas/cards?state=none&sort=roi_desc&limit=1")
  ITEMS=$(echo "$IDEA_RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    items = d.get('items') or d.get('data') or []
    print(json.dumps(items[:1]))
except Exception:
    print('[]')
" 2>/dev/null || echo "[]")
fi

# Build direction and context from first item (spec or idea card)
PAYLOAD=$(echo "$ITEMS" | python3 -c "
import sys, json
items = json.load(sys.stdin)
if not items:
    print('')
    sys.exit(0)
item = items[0]
spec_id = (item.get('spec_id') or '').strip()
title = (item.get('title') or '').strip() or spec_id or 'Untitled'
idea_id = (item.get('idea_id') or '').strip()
if not spec_id and not idea_id:
    print('')
    sys.exit(0)
if spec_id:
    direction = (
        f'Implement spec {spec_id} ({title}) from spec file. '
        'Follow the spec verification contract, add/update tests for behavior, and run local validation. '
        'Do not modify tests only to force pass.'
    )
    context = {'executor': 'claude', 'source': 'spec_implementation_gap', 'spec_id': spec_id, 'spec_title': title}
else:
    direction = (
        f'Create a spec for idea {idea_id} ({title}) and implement it. '
        'Follow the spec template and verification contract. Do not modify tests only to force pass.'
    )
    context = {'executor': 'claude', 'source': 'idea_without_spec', 'idea_id': idea_id, 'title': title}
out = json.dumps({'direction': direction, 'task_type': 'impl', 'context': context})
print(out)
" 2>/dev/null)

if [ -z "$PAYLOAD" ] || [ "$PAYLOAD" = "{}" ]; then
  echo "No gap found from public API (no in_progress specs and no ideas without spec). Try different PUBLIC_API_URL or filters."
  exit 0
fi
fi

echo "Creating task on local API..."
TASK_RESP=$(curl -s -X POST "$LOCAL_API_URL/api/agent/tasks" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")
TASK_ID=$(echo "$TASK_RESP" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('id') or '')
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$TASK_ID" ]; then
  echo "Failed to create task. Response: $TASK_RESP"
  exit 1
fi
echo "Created task id: $TASK_ID"

echo "Running agent runner once (AGENT_TASK_ID=$TASK_ID, no task timeout)..."
cd "$API_DIR"
AGENT_TASK_ID="$TASK_ID" AGENT_AUTO_GENERATE_IDLE_TASKS=0 AGENT_TASK_TIMEOUT=0 .venv/bin/python scripts/agent_runner.py --once --workers 1 --interval 1
