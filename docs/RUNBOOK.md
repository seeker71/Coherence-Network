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
- **Restart pipeline:** From repo root: `cd api && ./scripts/run_overnight_pipeline.sh` (starts API if needed, then agent_runner + monitor + PM). Ensure API is up first: `curl -s http://localhost:8000/api/health`; if not, start API in another terminal: `cd api && uvicorn app.main:app --reload --port 8000`. Optional: `rm api/logs/restart_requested.json` before starting for a clean run.

**Unblock needs_decision:**

- Telegram: `/reply {task_id} yes` (or your decision)
- API: `curl -X PATCH http://localhost:8000/api/agent/tasks/{id} -H "Content-Type: application/json" -d '{"decision":"yes"}'`

## n8n Security and HITL Operations

Use this when workflow runs involve n8n-powered automation.

Security floor:
- v1 deployments must be `>=1.123.17`
- v2 deployments must be `>=2.5.2`

Deploy gate check (from `api/`):

```bash
.venv/bin/python scripts/validate_pr_to_public.py --branch codex/<thread-name> --wait-public --n8n-version "${N8N_VERSION}"
```

Expected behavior:
1. If n8n is below minimum, result is `blocked_n8n_version` and deploy should not proceed.
2. If n8n is at/above minimum, gate result depends on normal PR/public checks.

HITL contract:
1. Mark destructive or external-impacting actions as approval-required.
2. Verify a blocked action remains blocked until explicit approval event is recorded.
3. If approvals fail to trigger, treat as a deploy blocker and roll back workflow changes enabling direct execution.

## Self-Improvement Thinking Loop

When running plan/implement/verify cycles, enforce this thinking contract before coding:

1. **Intent first**: state what is being optimized (trust, clarity, reuse), not only "finish task".
2. **System-level lens**: describe behavior change in runtime/API/user flow, not only file edits.
3. **Option thinking**: evaluate 2-3 approaches, select one, and record tradeoff rationale.
4. **Failure anticipation**: write "how this degrades in 2 weeks" and define guardrails/alerts.
5. **Proof of meaning**: show operator/user impact, not only passing tests/commands.

Execution hook:

```bash
cd api && .venv/bin/python scripts/run_self_improve_cycle.py --base-url http://127.0.0.1:8000
```

Required cycle evidence:

- plan output contains intent/system/options/failure/meaning sections.
- execution result references concrete production-facing deltas (API/UI/runtime), not just patch lists.
- review stage rejects outputs missing user/operator impact proof.

## Code Quality Drift Guidance (Non-Blocking)

Use this as directional guidance so the system improves over time while features continue shipping.

Daily check:

```bash
curl -s http://localhost:8000/api/automation/usage/daily-summary?window_hours=24\&top_n=5 | jq '.quality_awareness'
```

What to look for:

1. `summary.severity`, `risk_score`, and `regression` trend.
2. Hotspots (`very_large_module`, `long_function`, `layer_violation`, `runtime_placeholder`) that keep growing.
3. Guidance + recommended tasks that improve trust/clarity/reuse without freezing delivery.

Expected operating behavior:

- Treat quality-awareness output as planning input and routing guidance, not as a strict blocker.
- Prefer extracting logic into focused modules before adding more branches into oversized files.
- Capture one proof-of-meaning statement in each self-improvement cycle showing user/operator benefit.

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

## Production Postgres Operations (Railway)

Use this flow for any direct production DB work (assessment or cleanup).

Safety contract:
- Always run read-only checks first.
- Never use Railway internal DB host from local shell (`postgres.railway.internal` is not reachable locally).
- For local execution, resolve the public proxy URL from Railway fallback variable.
- Use dry-run before any delete and record row counts before/after.

### 1) Resolve a reachable production DB URL

```bash
cd /path/to/Coherence-Network
railway run printenv DATABASE_URL_RAILWAY_FALLBACK
```

This returns the public Railway Postgres proxy URL (`*.proxy.rlwy.net`), suitable for local scripts.

### 2) Run read-only assessment

```bash
python3 - <<'PY'
import json, subprocess
from sqlalchemy import create_engine, text
url = subprocess.check_output(
    ['bash','-lc','cd /path/to/Coherence-Network && railway run printenv DATABASE_URL_RAILWAY_FALLBACK'],
    text=True
).strip()
engine = create_engine(url, pool_pre_ping=True)
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE'
        ORDER BY table_name
    """)).fetchall()
print("table_count=", len(rows))
PY
```

For existing snapshots, see:
- `docs/system_audit/production_db_table_assessment_2026-03-05.json`
- `docs/system_audit/production_db_quality_profile_2026-03-05.json`
- `docs/system_audit/production_db_cleanup_candidates_2026-03-05.json`

### 3) Clean `agent_tasks` safely

From `api/`:

```bash
# Targeted cleanup (default): pending + test
.venv/bin/python scripts/cleanup_pending_agent_test_tasks.py \
  --use-railway-fallback-url \
  --dry-run

# Full table cleanup (guarded)
.venv/bin/python scripts/cleanup_pending_agent_test_tasks.py \
  --use-railway-fallback-url \
  --all \
  --batch-size 5000 \
  --dry-run

.venv/bin/python scripts/cleanup_pending_agent_test_tasks.py \
  --use-railway-fallback-url \
  --all \
  --batch-size 5000 \
  --confirm-delete-all DELETE_ALL_AGENT_TASKS
```

### 4) High-volume telemetry cleanup policy

Before deleting telemetry, review table size and date range first, then enforce retention windows (for example 30-90 days depending on operator needs). Candidate high-volume tables:
- `runtime_events`
- `telemetry_external_tool_usage_events`
- `telemetry_friction_events`
- `telemetry_task_metrics`

Prefer deleting only old rows by timestamp, not full-table truncation.

## System Audit (Cost/Value)

Use these when deciding what to fix next (lowest-cost, highest-value first):

```bash
# Runtime truth: mounted routes vs web expectations and unmounted agent routes
cd api && .venv/bin/python scripts/audit_runtime_surface.py

# Failure concentration: which task types/signals are dragging success rate
cd api && .venv/bin/python scripts/analyze_pipeline_failures.py
```

Save artifacts under `docs/system_audit/` and update `docs/SYSTEM-QUESTION-LEDGER.md` each cycle.

## Awareness Questions (Cost + Improvement)

Ask these once per daily operations review. Treat any "no" as a priority improvement signal: record owner, next command, and target date, then track trend each cycle.

### Hosted worker failure reporting

1. Were at least 75% of hosted worker failures recorded with `task_id`, `tool`, `model`, and provider fields in friction events?
2. Is every open hosted worker failure linked to an explicit `unblock_condition` and owner?
3. Did we reduce failure recurrence cost (energy loss + cost of delay) versus the prior check window?

### Task-provider visibility

1. Are at least 75% of recent tracked runs showing both `provider` and `billing_provider` alongside `task_id`?
2. Can an operator answer "which task used which provider" from `/agent` or `/tasks` without querying raw logs?
3. Are untracked completed/failed tasks trending down week-over-week?

### Recovery and learning capture

1. Are at least 75% of recoverable tool failures either `resolved` or mapped to a concrete `resolution_action`?
2. For each unresolved failure cluster, is there a documented next command and owner?
3. Did we add at least one prevention action (prompt guard, route policy, or monitor) for each repeated failure pattern?

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

## Validate Changed Specs

Before implementation work on changed specs:

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
```

This fails fast when specs are missing verification, risk/assumption, or known-gap follow-up sections.

## Local Web Validation In Worktrees

Use one command from the repo root:

```bash
./scripts/verify_worktree_local_web.sh
```

What it does:
- Validates route readiness for currently running API/web services on thread-aware ports.
- By default, it does not start services.
- Start services on demand with `THREAD_RUNTIME_START_SERVERS=1` or `--start`.
- Records and allocates thread-aware ports so multiple linked worktrees can run independently.
- Verifies key API routes and key human web pages return success and do not contain common runtime-error markers.
- Shuts down only the services it started for this invocation.

Port override example:

```bash
THREAD_RUNTIME_API_BASE_PORT=18100 THREAD_RUNTIME_WEB_BASE_PORT=3110 ./scripts/verify_worktree_local_web.sh
THREAD_RUNTIME_START_SERVERS=1 ./scripts/verify_worktree_local_web.sh
```

## Worktree PR Failure Guard

Run before commit/push to prevent common PR check failures and track failures as artifacts:

```bash
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
```

Track open PR check failures (requires `GITHUB_TOKEN` or `GH_TOKEN`):

```bash
python3 scripts/worktree_pr_guard.py --mode remote --branch "$(git rev-parse --abbrev-ref HEAD)"
```

Both modes write JSON reports to:
- `docs/system_audit/pr_check_failures/`

Remote/all mode also evaluates deployment freshness using latest `Public Deploy Contract` run on `main`; when that run is failed or older than the freshness window, the guard returns blocking status.

## Start-Gate Waivers (Time-Bounded)

Use waivers only for temporary, non-critical unblock cases while a root-cause fix is in-flight.

- File: `config/start_gate_main_workflow_waivers.json`
- Required fields per waiver:
  - `workflow`
  - `owner`
  - `reason`
  - `expires_at` (ISO8601 UTC)
- Optional scope:
  - `run_url_contains` (recommended to target a single failed run)

Blocking workflow failures must have owner mappings in `config/start_gate_workflow_owners.json`.  
The monitor writes enriched GitHub Actions health to `api/logs/github_actions_health.json`, including owner mapping gaps and waiver expiry windows.

If a check fails, the report includes:
- failing step/check name
- output tail
- suggested local remediation command

### PR Failure Triage Automation

Run dedicated PR failure triage across open `codex/*` PRs:

```bash
python3 scripts/pr_check_failure_triage.py --repo seeker71/Coherence-Network --base main --head-prefix codex/ --fail-on-detected
```

Auto-rerun failed GitHub Actions jobs and fail only if still blocked after retry window:

```bash
python3 scripts/pr_check_failure_triage.py \
  --repo seeker71/Coherence-Network \
  --base main \
  --head-prefix codex/ \
  --rerun-failed-actions \
  --rerun-settle-seconds 180 \
  --poll-seconds 20 \
  --fail-on-detected
```

Scheduled automation runs in:
- `.github/workflows/pr-check-failure-triage.yml`

Reference:
- `docs/PR-CHECK-FAILURE-TRIAGE.md`

## Worktree Start Gate

Before starting a new task, enforce worktree-only + clean-state:

```bash
make start-gate
```

What it blocks:
- dirty current worktree
- dirty primary workspace
- failing latest `main` CI state
- failing checks on open `codex/*` PRs
- running in a non-linked worktree

This gate fails when:
- work is started in the primary repo workspace instead of a linked worktree,
- current worktree has uncommitted local changes,
- primary workspace still has leftover local changes from unfinished tasks.

SQLite working-copy policy:
- `data/coherence.db` and `api/data/coherence.db` are operational working copies used for local validation, hydration, and runtime-state inspection.
- They are not normal source changes for continuity or commit-evidence guards.
- Default action on dirty DB files is to restore them before commit: `git restore data/coherence.db api/data/coherence.db`.
- Only commit DB changes when the task intentionally updates a checked-in fixture/snapshot and the commit evidence explains why seed/config changes are not sufficient.

For the full one-page startup flow, use:
- `docs/WORKTREE-QUICKSTART.md`

## Telemetry Migration To DB

Migrate local telemetry files (`automation_usage_snapshots.json`, `friction_events.jsonl`) into DB-backed telemetry tables:

```bash
cd api && python scripts/migrate_local_telemetry_to_db.py --json
```

After `parity_ok=true`, remove outdated local telemetry files:

```bash
cd api && python scripts/migrate_local_telemetry_to_db.py --purge-local --yes --json
```

## Cleanup Old Task Logs

Task logs accumulate. To remove logs older than 7 days:

```bash
find api/logs -name 'task_*.log' -mtime +7 -delete
```

Or use `api/scripts/cleanup_temp.py` if it supports log cleanup.

## Idea Tracking — Every Idea Gets Recorded

**Rule: When a new idea comes up in any conversation, session, or PR — it MUST be recorded in the system as an actual idea before the session ends.**

Ideas are the atomic unit of the Coherence Network. If an idea isn't in the system, it doesn't exist for tracking, attribution, or value lineage.

### How to record an idea

```bash
# Via CLI
coh share

# Via API
curl -s https://api.coherencycoin.com/api/ideas -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "id": "kebab-case-id",
    "name": "Human-readable name",
    "description": "What this idea does and why it matters",
    "potential_value": 50,
    "estimated_cost": 5,
    "confidence": 0.5,
    "manifestation_status": "none",
    "parent_idea_id": "parent-id-if-applicable"
  }'
```

### When to update an idea

- **When implementation starts:** PATCH `manifestation_status` → `"partial"`
- **When implementation ships:** PATCH `manifestation_status` → `"validated"`, set `actual_value` and `actual_cost`
- **When a sub-idea is created:** Set `parent_idea_id` on the child to link the hierarchy

### Checklist (end of every session)

1. Were any new ideas discussed? → Record them via `POST /api/ideas`
2. Were any existing ideas implemented? → Update status via `PATCH /api/ideas/{id}`
3. Do new ideas have parent relationships? → Set `parent_idea_id`
4. Are all ideas discoverable via `coh ideas`? → Verify

### API key requirement

Read operations (GET) work without a key. Write operations (POST, PATCH) require `X-API-Key` header on the production API. For local dev, no key is needed.

## See also

- [AGENTS.md](../AGENTS.md) — Commands, agent API, pipeline scripts
- [PIPELINE-MONITORING-AUTOMATED.md](PIPELINE-MONITORING-AUTOMATED.md) — Monitor rules, auto-recovery, thresholds
- [013 Logging Audit](../specs/013-logging-audit.md) — Log rotation; RUNBOOK log list stays in sync
- [CODEX-THREAD-PROCESS.md](CODEX-THREAD-PROCESS.md) — Required phase gates for parallel Codex threads
