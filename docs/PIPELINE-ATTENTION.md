# Pipeline Attention Checklist

> What needs attention? Run `api/scripts/ensure_effective_pipeline.sh` for live check. This doc lists common issues and fixes.

## Autonomous Mode (Max Autonomy, No Interaction)

```bash
cd api && ./scripts/run_autonomous.sh
```

Starts API + pipeline, restarts on failure, reports fatal issues only to `api/logs/fatal_issues.json`. Check that file (or `GET /api/agent/fatal-issues`) only when unrecoverable.

## Quick Check

```bash
cd api && ./scripts/ensure_effective_pipeline.sh
```

## Common Issues & Fixes

| Issue | Check | Fix |
|-------|-------|-----|
| **API not reachable** | `curl -s http://localhost:8000/api/health` | Start API: `cd api && uvicorn app.main:app --reload --port 8000` |
| **Metrics 404** | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/agent/metrics` | Restart API (route not loaded) |
| **Monitor-issues 404** | `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/agent/monitor-issues` | Restart API (route not loaded) |
| **Monitor not running** | `pgrep -f monitor_pipeline` | Restart pipeline |
| **Runner workers=1** | Check agent_runner.log for "workers=" | Restart pipeline (script now uses workers=5) |
| **Sequential mode** | PM state has `in_flight` for parallel | Restart with PIPELINE_PARALLEL=1 (default) |
| **No pipeline_version.json** | `ls api/logs/pipeline_version.json` | Restart pipeline (writes on start) |
| **Stale version** | Monitor detects git SHA changed | Use watchdog or restart manually |
| **Orphan task** | Task running > 2h | PATCH to failed or restart; monitor auto-recovers when PIPELINE_AUTO_RECOVER=1 |

## What Automation Can Do vs What You Need To Do

**With `run_autonomous.sh` (one command, no interaction):**
- Start API and pipeline
- Restart API when down (up to 5 attempts)
- Restart pipeline when it exits, stale version, or runner hung (no task 10+ min)
- Restart API when metrics 404 (load new routes after code change)
- Auto-skip needs_decision after 24h timeout
- Create heal tasks (no_task_running, low_phase_coverage, repeated_failures, low_success_rate), PATCH orphans
- **Auto-commit** progress after each completed task (PIPELINE_AUTO_COMMIT=1); optional auto-push (PIPELINE_AUTO_PUSH=1)
- Report fatal only to `fatal_issues.json` when unrecoverable

**You need to (only when fatal):**
- Check `api/logs/fatal_issues.json` or `GET /api/agent/fatal-issues`
- Fix the underlying issue (e.g. disk full, port in use)
- Delete `fatal_issues.json` and restart `run_autonomous.sh`

## Effective Pipeline Checklist

- [ ] API running and returns 200 for /health, /api/agent/metrics, /api/agent/monitor-issues
- [ ] Pipeline started via run_overnight_pipeline.sh (not manual PM only)
- [ ] Monitor process running (pgrep -f monitor_pipeline)
- [ ] pipeline_version.json present
- [ ] Agent runner with workers=5
- [ ] PM in parallel mode (state has in_flight when tasks in flight)
