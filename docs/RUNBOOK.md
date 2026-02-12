# Ops Runbook — Coherence Network

Quick reference for common operational tasks.

## Log Locations

| Path | Purpose |
|------|---------|
| `api/logs/agent_runner.log` | Agent runner: task pickups, completions, errors |
| `api/logs/task_{id}.log` | Full stdout/stderr for each task run |
| `api/logs/telegram.log` | Webhook events, send results |
| `api/logs/project_manager.log` | PM: backlog, phase, task creation |
| `api/logs/overnight_orchestrator.log` | Overnight pipeline orchestrator |
| `api/logs/project_manager_state.json` | PM state (backlog index, phase) |
| `api/logs/project_manager_state_overnight.json` | Overnight pipeline state |
| `api/logs/graph_store.json` | Project graph (spec 019; persisted after index) |

## Index npm packages

To populate the project graph (Sprint 1):

```bash
cd api && .venv/bin/python scripts/index_npm.py --target 5000
# Or limit: --limit 100
```

## Index PyPI packages

To add Python packages to the graph (spec 024):

```bash
cd api && .venv/bin/python scripts/index_pypi.py --target 100
# Or limit: --limit 50
```

Uses same graph_store.json as npm; projects coexist.

## API Restart

```bash
# If running via uvicorn directly
pkill -f "uvicorn app.main"
cd api && uvicorn app.main:app --reload --port 8000

# If running via start_with_telegram
# Stop the script (Ctrl+C), then restart
./scripts/start_with_telegram.sh
```

## Pipeline Recovery

**Pipeline stuck or agent runner died:**

1. Check API: `curl -s http://localhost:8000/api/health`
2. Restart overnight pipeline:
   ```bash
   cd api && ./scripts/run_overnight_pipeline.sh
   ```
3. Or restart components separately:
   ```bash
   cd api
   .venv/bin/python scripts/agent_runner.py --interval 10 -v &
   .venv/bin/python scripts/project_manager.py --interval 15 --hours 8 -v
   ```

**Blocked on needs_decision:**

- Telegram: `/reply {task_id} yes` (or your decision)
- API: `curl -X PATCH http://localhost:8000/api/agent/tasks/{id} -d '{"decision":"yes"}'`

## Check Pipeline Status

```bash
cd api && .venv/bin/python scripts/check_pipeline.py
```

Shows: running task, pending count, recent completed, latest LLM activity.

```bash
# JSON output for scripting
.venv/bin/python scripts/check_pipeline.py --json
```

## Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Liveness |
| `GET /api/ready` | Readiness (k8s) |
| `GET /api/version` | API version |
| `GET /api/agent/tasks/count` | Task counts (total, by_status) |
| `GET /api/agent/pipeline-status` | Pipeline visibility |

## Run Tests

```bash
cd api && .venv/bin/pytest -v
```

## Cleanup Old Task Logs

Task logs accumulate. To remove logs older than 7 days:

```bash
find api/logs -name 'task_*.log' -mtime +7 -delete
```

Or use `api/scripts/cleanup_temp.py` if it supports log cleanup.
