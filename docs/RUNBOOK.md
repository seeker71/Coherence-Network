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
| `api/logs/monitor_issues.json` | Monitor issues (check via GET /api/agent/monitor-issues) |
| `api/logs/monitor_resolutions.jsonl` | Resolution events for effectiveness measurement |
| `api/logs/commit_progress.log` | Auto-commit log (when PIPELINE_AUTO_COMMIT=1) |
| `api/logs/monitor.log` | Monitor script log (hierarchical STATUS lines each check) |
| `api/logs/pipeline_status_report.json` | Hierarchical status (machine readable): Layer 0–3, going_well, needs_attention |
| `api/logs/pipeline_status_report.txt` | Same report in human-readable text |
| `api/logs/pipeline_version.json` | Git SHA at pipeline start (version check) |
| `api/logs/graph_store.json` | Project graph (spec 019; persisted after index) |
| `api/logs/fatal_issues.json` | Fatal pipeline issues (unrecoverable; check via GET /api/agent/fatal-issues or report_fatal.py) |

Application log files (e.g. agent_runner.log, project_manager.log) use rotation: 5 MiB per file, 3 backups (spec 013). Task logs (`task_*.log`) are ephemeral; cleanup via find or `cleanup_temp.py`.

## API Restart

Stop and start the API (port 8000). Process cleanup when needed:

```bash
# Stop any uvicorn process on app.main
pkill -f "uvicorn app.main"

# Start API (from api/)
cd api && uvicorn app.main:app --reload --port 8000
```

Optional: run API with Telegram webhook support:

```bash
cd api && ./scripts/start_with_telegram.sh
```

## Pipeline Recovery

When the pipeline is stuck or the agent runner died:

1. **Effectiveness check:** `cd api && ./scripts/ensure_effective_pipeline.sh`
2. **Restart API** if health/metrics/monitor-issues fail: `pkill -f uvicorn; cd api && uvicorn app.main:app --reload --port 8000`
3. **Restart overnight pipeline:** `cd api && ./scripts/run_overnight_pipeline.sh` (uses watchdog by default for auto-restart on stale_version, api_unreachable; pass `--no-watchdog` to run once)
4. **Or restart components separately:**
   ```bash
   cd api
   .venv/bin/python scripts/agent_runner.py --interval 10 -v &
   .venv/bin/python scripts/project_manager.py --interval 15 --hours 8 -v
   ```

**Monitor: "agent_runner and PM processes not seen"**

- **Check logs:** `tail -50 api/logs/agent_runner.log`, `tail -50 api/logs/project_manager.log`, `tail -30 api/logs/monitor.log`. If monitor wrote `api/logs/restart_requested.json` (e.g. stale_version), the watchdog would have restarted the pipeline if it was running; otherwise restart manually.
- **Restart pipeline:** `cd api && ./scripts/run_overnight_pipeline.sh` (starts API if needed, then agent_runner + monitor + PM). Optional: `rm api/logs/restart_requested.json` before starting for a clean run.

**Unblock needs_decision:**

- Telegram: `/reply {task_id} yes` (or your decision)
- API: `curl -X PATCH http://localhost:8000/api/agent/tasks/{id} -H "Content-Type: application/json" -d '{"decision":"yes"}'`

## Connection stalled / API unreachable

If scripts or tests fail with **Connection stalled**, **ReadTimeout**, or **ConnectError** (e.g. when API is not running):

1. **Start the API:** `cd api && uvicorn app.main:app --reload --port 8000`
2. **Verify:** `curl -s http://localhost:8000/api/health` should return 200.
3. **CI/tests:** Project manager and agent runner do an upfront health check and exit quickly when API is unreachable; ensure API is started before running `--once` or pipeline tests. See docs/GLOSSARY.md (Connection stalled).

**Auto-recovery:** With PIPELINE_AUTO_RECOVER=1, the monitor writes `restart_requested.json` on api_unreachable. The watchdog (run_overnight_pipeline_watchdog.sh) restarts the API when it sees this. For full automation including API restart, use `run_autonomous.sh`.

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

## Full Automation (Single Command)

One command: API + pipeline + watchdog. Restarts on stale_version and api_unreachable.

```bash
cd api && ./scripts/run_overnight_pipeline.sh
```

- Starts API if not running
- Watchdog restarts pipeline on stale code or API down
- Auto-commit, auto-fix, auto-recover
- Pass `--no-watchdog` to run once without restarts

## Autonomous Pipeline (Max Autonomy)

Same as above but with a top-level monitor loop and needs_decision timeout:

```bash
cd api && ./scripts/run_autonomous.sh
```

- Auto-fix and auto-recover enabled
- **Auto-commit** (PIPELINE_AUTO_COMMIT=1): After each completed spec/impl/test/review task, runs `git add -A && git commit` with message `[pipeline] {type} {id}: ...`. Set PIPELINE_AUTO_COMMIT=0 to disable.
- **Auto-push** (PIPELINE_AUTO_PUSH=0 by default): Set to 1 to run `git push` after commit. Use with caution.
- needs_decision timeout: 24h (auto-skip blocked tasks)
- Fatal issues: `api/logs/fatal_issues.json` or `GET /api/agent/fatal-issues`
- Check fatal only when unrecoverable: `cd api && .venv/bin/python scripts/report_fatal.py`

## Pipeline Effectiveness Check

**Before or during pipeline runs, verify everything is working:**

```bash
cd api && ./scripts/ensure_effective_pipeline.sh
```

This checks: API reachable, metrics endpoint, monitor-issues endpoint, effectiveness endpoint, version tracking, monitor/runner processes. Reports effectiveness summary (throughput, success rate, issues, goal proximity) and required actions if anything needs attention.

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
| `GET /api/agent/tasks` | List tasks |
| `GET /api/agent/tasks/count` | Task counts (total, by_status) |
| `GET /api/agent/pipeline-status` | Pipeline visibility (running, pending, running_by_phase) |
| `GET /api/agent/metrics` | Task metrics (success rate, duration) |
| `GET /api/agent/monitor-issues` | Monitor issues (check/react/improve) |

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

## See also

- [AGENTS.md](../AGENTS.md) — Commands, agent API, pipeline scripts
- [PIPELINE-MONITORING-AUTOMATED.md](PIPELINE-MONITORING-AUTOMATED.md) — Monitor rules, auto-recovery, thresholds
- [013 Logging Audit](../specs/013-logging-audit.md) — Log rotation; RUNBOOK log list stays in sync
