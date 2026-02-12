# Automated Pipeline Monitoring — Check, React, Improve

> Monitor detects issues, persists them, and exposes them via API. Agents and humans can check, react, and improve.

## Flow

1. **Monitor script** (`api/scripts/monitor_pipeline.py`) runs every 60s (overnight pipeline) or on demand.
2. It checks: pipeline version (git SHA) vs current; `GET /api/agent/pipeline-status`; `GET /api/agent/metrics`.
3. Issues are written to `api/logs/monitor_issues.json`; **all issues are reported**.
4. **Check**: `GET /api/agent/monitor-issues` returns the current issues (machine-readable).
5. **React**: When `PIPELINE_AUTO_FIX_ENABLED=1`, monitor creates heal tasks. When `PIPELINE_AUTO_RECOVER=1`, fallback actions run.
6. **Improve**: Use `suggested_action` per issue; iterate on prompts, thresholds, or detection rules.

## Version Check & Restart

- Pipeline writes `api/logs/pipeline_version.json` on start (git SHA, started_at).
- Monitor compares current git SHA to stored value. If different → **stale_version** issue.
- When `PIPELINE_AUTO_RECOVER=1` and stale_version: monitor writes `api/logs/restart_requested.json`.
- Use **run_overnight_pipeline_watchdog.sh** to auto-restart when restart_requested is set.

## Hierarchical Status Report (Machine + Human Readable)

The monitor writes a hierarchical status report each check:

- **`api/logs/pipeline_status_report.json`** — Machine parseable. Structure:
  - `layer_0_goal` — Throughput, success rate, goal proximity
  - `layer_1_orchestration` — PM, runner, monitor
  - `layer_2_execution` — API, metrics
  - `layer_3_attention` — Issues, resolved_since_last
  - `overall.going_well` — Explicit list of what is OK
  - `overall.needs_attention` — Explicit list of what needs action

- **`api/logs/pipeline_status_report.txt`** — Human readable, same hierarchy.

- **`api/logs/monitor.log`** — Each check logs `STATUS OK|ATTENTION` with layer summary; `GOING_WELL` and `NEEDS_ATTENTION` lists for quick scan.

**API:** `GET /api/agent/status-report` returns the JSON report.

## Issue Prioritization & Resolution Tracking

- **Priority**: Each issue has `priority` (1=high, 2=medium, 3=low). Issues are sorted by priority for addressing order.
- **Resolution tracking**: When a condition clears (e.g. metrics_unavailable after API restart), the monitor records it in `api/logs/monitor_resolutions.jsonl`.
- **Effectiveness measurement**: `GET /api/agent/effectiveness` returns throughput, success rate, issues open/resolved, progress by phase, and goal proximity (0–1).

## How to Check (API)

```bash
# Current monitor issues (empty when healthy; sorted by priority)
curl -s http://127.0.0.1:8000/api/agent/monitor-issues | python3 -m json.tool

# Pipeline effectiveness (throughput, issues, goal proximity)
curl -s http://127.0.0.1:8000/api/agent/effectiveness | python3 -m json.tool

# Or read file directly
cat api/logs/monitor_issues.json
```

Pipeline status now includes `running_by_phase`: counts of running+pending per task_type (spec, impl, test, review) for parallel visibility.

Response shape:

```json
{
  "issues": [
    {
      "id": "abc12345",
      "condition": "repeated_failures",
      "severity": "high",
      "message": "3+ consecutive failed tasks (same phase)",
      "suggested_action": "Review task logs; consider heal task or model/prompt change",
      "created_at": "2026-02-12T12:00:00Z",
      "resolved_at": null
    }
  ],
  "last_check": "2026-02-12T12:05:00Z",
  "history": []
}
```

## Detection Rules

| Condition | Severity | Trigger |
|-----------|----------|---------|
| `stale_version` | high | Pipeline running old code (git SHA changed) — restart to pick up latest |
| `no_task_running` | high | Pending 3+ min, no running — analyze why, debug, fix, restart |
| `low_phase_coverage` | medium | Pending exist but &lt;2 running — ensure parallel mode, workers 5 |
| `repeated_failures` | high | 3+ consecutive failed (same phase) |
| `low_success_rate` | medium | 7d success rate < 80% (10+ tasks) |
| `orphan_running` | medium | Single running task > 2h |
| `needs_decision` | medium | PM blocked on human decision |
| `api_unreachable` | high | pipeline-status request fails |
| `metrics_unavailable` | low | GET /api/agent/metrics returns 404 |

## Fallback Recovery (PIPELINE_AUTO_RECOVER=1)

| Issue | Fallback Action |
|-------|-----------------|
| `stale_version` | Write restart_requested.json → watchdog restarts pipeline |
| `orphan_running` | PATCH task to failed (unblock pipeline) |
| `no_task_running` | Create heal task (when auto-fix also enabled) |
| `repeated_failures` | Create heal task (when auto-fix also enabled) |

## How to React (Agent)

1. **Periodically** (e.g. at session start): `GET /api/agent/monitor-issues`.
2. **If `issues` non-empty**: For each issue, follow `suggested_action`:
   - `no_task_running`: Full debug guide in suggested_action. Heal task may already exist (auto-fix). Restart pipeline to continue.
   - `needs_decision`: Use `/reply` or PATCH task with decision.
   - `orphan_running`: PATCH task to failed, or restart pipeline.
   - `api_unreachable`: Restart API; check AGENT_API_BASE.
   - `low_success_rate`: Review metrics; consider prompt/model A/B test.
3. **After action**: Re-check monitor-issues; if still present, escalate or refine approach.

## How to Improve

- **Thresholds**: Edit `monitor_pipeline.py` (`STUCK_THRESHOLD_SEC`, `ORPHAN_RUNNING_SEC`, `LOW_SUCCESS_RATE`).
- **New rules**: Add detection blocks in `_run_check` and `_add_issue`.
- **Auto-fix**: Extend auto-fix for `needs_decision` (e.g. create review task) or `low_success_rate` (e.g. log to file for analysis).
- **Measure effectiveness**: Use `GET /api/agent/effectiveness` to track throughput, issue resolution, and goal proximity. Improve pipeline and agents based on metrics.

## Run Manually

```bash
cd api
python scripts/monitor_pipeline.py --once
python scripts/monitor_pipeline.py --interval 60 --auto-fix --auto-recover --verbose
```

## Wiring (Overnight Pipeline)

`run_overnight_pipeline.sh` starts the monitor with `--interval 60`. If `PIPELINE_AUTO_FIX_ENABLED=1`, adds `--auto-fix`. If `PIPELINE_AUTO_RECOVER=1`, adds `--auto-recover`. Monitor logs to `api/logs/monitor.log`.

## Watchdog (Auto-Restart on Stale Version)

For automatic restart when monitor detects stale version:

```bash
export PIPELINE_AUTO_RECOVER=1
./scripts/run_overnight_pipeline_watchdog.sh --hours 8
```

The watchdog runs the pipeline in a loop; every 90s it checks `api/logs/restart_requested.json`. When present (e.g. from stale_version), it stops the pipeline and restarts it.
