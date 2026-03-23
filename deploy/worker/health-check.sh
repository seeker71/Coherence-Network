#!/bin/bash
# health-check.sh — Check worker health and alert if down
# Can be run from cron or manually.
#
# Usage:
#   ./deploy/worker/health-check.sh          # check and print status
#   ./deploy/worker/health-check.sh --alert  # also send alert via message bus

set -euo pipefail

API="${COHERENCE_API_BASE:-https://api.coherencycoin.com}"
ALERT="${1:-}"

echo "Worker Health Check"
echo "==================="

# 1. Check API health
API_STATUS=$(curl -sf "$API/api/health" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "offline")
echo "API: $API_STATUS"

# 2. Check federation nodes
NODES=$(curl -sf "$API/api/federation/nodes" 2>/dev/null)
if [ -n "$NODES" ]; then
    NODE_COUNT=$(echo "$NODES" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 0)" 2>/dev/null || echo "0")
    echo "Nodes registered: $NODE_COUNT"

    # Check each node's last_seen_at
    echo "$NODES" | python3 -c "
import sys, json
from datetime import datetime, timezone

nodes = json.load(sys.stdin)
if not isinstance(nodes, list):
    sys.exit(0)

now = datetime.now(timezone.utc)
for n in nodes:
    last = n.get('last_seen_at', '')
    hostname = n.get('hostname', '?')
    nid = n.get('node_id', '?')[:12]

    if last:
        try:
            dt = datetime.fromisoformat(last.replace('Z', '+00:00'))
            age_min = (now - dt).total_seconds() / 60
            if age_min < 5:
                status = 'HEALTHY'
            elif age_min < 60:
                status = 'STALE'
            else:
                status = 'DOWN'
            print(f'  {status:8s}  {hostname:30s}  {nid}  ({age_min:.0f}m ago)')
        except:
            print(f'  UNKNOWN   {hostname:30s}  {nid}')
    else:
        print(f'  UNKNOWN   {hostname:30s}  {nid}')
" 2>/dev/null
fi

# 3. Check running tasks
TASKS=$(curl -sf "$API/api/agent/tasks?limit=5" 2>/dev/null)
if [ -n "$TASKS" ]; then
    RUNNING=$(echo "$TASKS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tasks = d.get('tasks', []) if isinstance(d, dict) else d
running = [t for t in tasks if t.get('status') == 'running']
print(len(running))
" 2>/dev/null || echo "?")
    echo "Running tasks: $RUNNING"
fi

# 4. Alert if requested and nodes are down
if [ "$ALERT" = "--alert" ]; then
    # Find down nodes
    DOWN_NODES=$(echo "$NODES" | python3 -c "
import sys, json
from datetime import datetime, timezone
nodes = json.load(sys.stdin)
now = datetime.now(timezone.utc)
down = []
for n in nodes if isinstance(nodes, list) else []:
    last = n.get('last_seen_at', '')
    if last:
        try:
            dt = datetime.fromisoformat(last.replace('Z', '+00:00'))
            if (now - dt).total_seconds() > 3600:
                down.append(n.get('hostname', '?'))
        except:
            pass
print(','.join(down))
" 2>/dev/null || echo "")

    if [ -n "$DOWN_NODES" ]; then
        echo ""
        echo "ALERT: Down nodes: $DOWN_NODES"
        # Send alert via message bus
        curl -sf -X POST "$API/api/federation/broadcast" \
            -H "Content-Type: application/json" \
            -d "{\"from_node\":\"health-check\",\"type\":\"command\",\"text\":\"ALERT: Down nodes: $DOWN_NODES\",\"payload\":{\"command\":\"alert\",\"down_nodes\":\"$DOWN_NODES\"}}" \
            > /dev/null 2>&1 && echo "Alert broadcast sent" || echo "Failed to send alert"
    else
        echo ""
        echo "All nodes healthy."
    fi
fi
