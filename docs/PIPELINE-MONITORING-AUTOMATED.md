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
| `runner_pm_not_seen` | high | PROCESSES: agent_runner not seen, PM not seen — pipeline processes down |
| `output_empty` | high | Completed task has 0 chars output (capture failure or silent crash) |
| `orphan_running` | medium | Single running task > 2h |
| `needs_decision` | medium | PM blocked on human decision |
| `api_unreachable` | high | pipeline-status request fails |
| `metrics_unavailable` | low | GET /api/agent/metrics returns 404 |
| `phase_6_7_not_worked` | medium | Backlog (006) has not reached Phase 6 — Phase 6/7 product-critical items not being worked; verify backlog maps to PLAN phases |
| `architecture_maintainability_drift` | high/medium | Maintainability audit reports blocking drift or baseline regression (architecture complexity/layer health) |
| `runtime_placeholder_debt` | high | Runtime mock/fake/stub placeholder findings increased beyond baseline |

**Backlog alignment (spec 007):** GET /api/agent/effectiveness returns `plan_progress.backlog_alignment` with `phase_6_7_status` and `phase_6_7_not_worked`. The monitor flags when Phase 6/7 items are not being worked so progress toward PLAN.md goals is visible.

## Fallback Recovery (PIPELINE_AUTO_RECOVER=1)

| Issue | Fallback Action |
|-------|-----------------|
| `stale_version` | Write restart_requested.json → watchdog restarts pipeline |
| `runner_pm_not_seen` | Write restart_requested.json → watchdog restarts pipeline |
| `orphan_running` | PATCH task to failed (unblock pipeline) |
| `no_task_running` | Create heal task (when auto-fix also enabled) |
| `repeated_failures` | Create heal task (when auto-fix also enabled) |
| `architecture_maintainability_drift` | Create high-ROI heal task (when auto-fix also enabled) |
| `runtime_placeholder_debt` | Create placeholder cleanup heal task (when auto-fix also enabled) |

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

## CI/CD Gate Auto-Heal (Main Deploy Path)

To reduce Railway skipped deploys caused by failed required checks on `main`, CI includes:

- Workflow: `.github/workflows/auto-heal-deploy-gates.yml`
- Script: `api/scripts/auto_heal_deploy_gates.py`

Behavior:
1. Trigger when `Test`, `Thread Gates`, or `Change Contract` finishes on `main` with non-success conclusion.
2. Detect failing required contexts from branch protection.
3. Rerun failed GitHub Actions jobs for those required contexts.
4. Re-check status until reruns finish with success (or fail/timeout); upload `auto_heal_report.json`.
5. Guard against recursion with one-attempt trigger (`run_attempt == 1`) and per-SHA concurrency.

`Change Contract` review thresholds are configurable to avoid blocking velocity when no reviewer is available:
- `CHANGE_CONTRACT_MIN_APPROVALS` (repo variable, default `0`)
- `CHANGE_CONTRACT_MIN_UNIQUE_APPROVERS` (repo variable, default `0`)
Raise these values when collective review coverage is strong enough to enforce stricter payout/ack gates.

To avoid race conditions right after merge, `Change Contract` now re-validates for up to 5 minutes when the only failure reason is `Commit checks are not green on main`.

## Public Deploy Drift Monitor (Main + Schedule)

To detect production drift even when CI checks are green:

- Workflow: `.github/workflows/public-deploy-contract.yml`
- Script: `api/scripts/validate_public_deploy_contract.py`
- Trigger:
  - Push to `main`
  - Every 30 minutes (`cron`)
  - Manual run (`workflow_dispatch`)

Contract checks:
1. Railway `/api/health` responds `200`.
2. Railway `/api/gates/main-head` responds `200` and returns SHA equal to GitHub `main` head.
3. Vercel `/gates` page responds `200`.
4. Vercel `/api/health-proxy` responds `200`, reports `api.status=ok`, and `web.updated_at` equals GitHub `main` head.
5. Railway value-lineage E2E transaction passes:
   - `POST /api/value-lineage/links`
   - `POST /api/value-lineage/links/{id}/usage-events`
   - `GET /api/value-lineage/links/{id}/valuation`
   - `POST /api/value-lineage/links/{id}/payout-preview`
   - invariants validated (`measured_value_total`, payout weights/amounts).

Note: if `/api/gates/main-head` is unavailable due missing GitHub auth in public runtime (401/403/502),
the contract records a warning (`railway_gates_main_head_unavailable`) but still requires all other checks,
including value-lineage E2E, to pass.

If contract fails:
- Workflow uploads `public_deploy_contract_report.json`.
- Workflow opens or updates issue: `Public deployment contract failing on main`.
- If Railway secrets are configured (`RAILWAY_TOKEN`, `RAILWAY_PROJECT_ID`, `RAILWAY_ENVIRONMENT`, `RAILWAY_SERVICE`), workflow triggers `railway redeploy` and re-validates for up to 20 minutes before deciding pass/fail.

Machine and human access:
- Machine API: `GET /api/gates/public-deploy-contract`
- Human UI: `/gates` page, section **Public Deploy Contract**
- CI artifact: `public_deploy_contract_report.json`

## External Tool Drift Monitor (Twice Weekly)

To track newly added external tools and keep upgrade cadence:

- Workflow: `.github/workflows/external-tools-audit.yml`
- Script: `scripts/audit_external_tools.py`
- Registry: `docs/system_audit/external_tools_registry.json`
- Trigger:
  - Tuesdays + Fridays (`cron`)
  - Manual run (`workflow_dispatch`)

Behavior:
1. Discover external GitHub Actions, workflow CLI tools, and dependency ecosystems.
2. Compare discovered set against tracked registry.
3. Upload `external_tools_audit_report.json`.
4. Open/update issue `External tools registry drift detected` if new tools appear.
5. Close the issue automatically once registry is updated and audit passes.

Dependency update cadence:
- Dependabot config in `.github/dependabot.yml` runs daily for:
  - GitHub Actions
  - Python (`/api`)
  - npm (`/web`)

## Workflow Reference Guard (Per PR/Push)

To prevent gate regressions caused by broken workflow script paths or missing requirements files:

- Script: `scripts/validate_workflow_references.py`
- Enforced in CI workflow: `.github/workflows/test.yml`
- Contract:
  - Any static `python ...`, `bash ...`, `./...`, and `pip install -r ...` reference in workflow `run:` blocks must resolve to an existing file (repo root or `api/` root).
  - Missing references fail `Test` before merge.

## Provider Readiness Contract (Every 6 Hours)

To ensure provider configuration is continuously validated and failures are surfaced automatically:

- Workflow: `.github/workflows/provider-readiness-contract.yml`
- Script: `api/scripts/check_provider_readiness.py`
- API endpoint: `GET /api/automation/usage/readiness`
- Trigger:
  - Every 6 hours (`cron`)
  - Manual (`workflow_dispatch`)

Contract behavior:
1. Collect provider usage/readiness snapshots.
2. Evaluate required providers from `AUTOMATION_REQUIRED_PROVIDERS` (repo variable, comma-separated).
3. Fail when any required provider is not configured or not healthy.
4. Upload `provider_readiness_report.json` artifact.
5. Open/update issue `Provider readiness contract failing` when blocking issues exist; close it when healthy.

Required provider defaults:
- `coherence-internal`
- `github`
- `openai`
- `railway`
- `vercel`

Machine and human access:
- Machine API: `GET /api/automation/usage/readiness`
- Human UI: `/automation` page, section **Provider Readiness**

## Maintainability Architecture Monitor (Twice Weekly + PR Gate)

To keep architecture and placeholder debt from drifting:

- Scheduled workflow: `.github/workflows/maintainability-architecture-audit.yml`
  - Runs Mondays + Thursdays
  - Executes `api/scripts/run_maintainability_audit.py`
  - Fails on baseline regressions or blocking architecture drift
  - Opens/updates issue `Maintainability architecture drift detected`
- Baseline file: `docs/system_audit/maintainability_baseline.json`
  - PRs fail if maintainability metrics regress beyond baseline (`thread-gates.yml`)
- Runtime monitor integration:
  - Writes audit report to `api/logs/maintainability_audit.json`
  - Raises monitor conditions:
    - `architecture_maintainability_drift`
    - `runtime_placeholder_debt`
  - When auto-fix is enabled, monitor creates a high-ROI heal task once per new condition.
