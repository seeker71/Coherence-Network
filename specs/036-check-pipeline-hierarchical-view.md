# Spec: Hierarchical view in check_pipeline (goal → PM → tasks → artifacts)

## Purpose

Operators need a single command that shows pipeline health in a clear hierarchy: goal progress first, then orchestration (PM), then task execution, then artifact health. This makes it easy to see "are we on track?" before drilling into running/pending tasks and recent outputs.

## Requirements

- [x] When run without `--json`, `check_pipeline.py` prints a **hierarchical view**: Goal → PM/Orchestration → Tasks → Artifacts (in that order).
- [x] **Goal** section: Use `GET /api/agent/status-report` when available (from monitor-written file); show layer_0_goal status and summary (e.g. goal_proximity, throughput, success rate). If status-report is missing, show "Goal: (report not yet generated)" or fetch `GET /api/agent/effectiveness` and show goal_proximity and a one-line summary.
- [x] **PM / Orchestration** section: Show layer_1_orchestration from status-report when available; else derive from pipeline-status (project_manager state, backlog_index, phase, blocked) and process detection (agent_runner workers, PM --parallel). Same information as current "PROJECT MANAGER" and "PROCESSES" blocks, but labeled as Layer 1.
- [x] **Tasks** section: Running, pending (with wait times), recent completed (with duration) — current pipeline-status content, labeled as Layer 2 / Tasks.
- [x] **Artifacts** section: Recent task outputs / artifact health — e.g. recent_completed tasks with output_len and optional one-line output_preview; optionally mention spec/STATUS artifact health if effectiveness or status-report exposes it. At minimum: list recent completed with output size so operator can see "artifacts produced."
- [x] Add optional flag `--hierarchical` to explicitly enable this view; default human-readable output is hierarchical. Add `--flat` to preserve legacy flat output (Goal/PM/Tasks/Artifacts order still allowed but sections not strictly layered).
- [x] With `--json`, when hierarchical view is requested (default or `--hierarchical`), include in the JSON a top-level key `hierarchical` (or merge layer_0_goal, layer_1_orchestration, layer_2_execution, layer_3_attention from status-report when available) so script consumers get the same structure.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 007, 026, 032

## Task Card

```yaml
goal: Operators need a single command that shows pipeline health in a clear hierarchy: goal progress first, then orchestration (PM), then task execution, then artifact health.
files_allowed:
  - api/scripts/check_pipeline.py
done_when:
  - When run without `--json`, `check_pipeline.py` prints a hierarchical view: Goal → PM/Orchestration → Tasks → Artifact...
  - Goal section: Use `GET /api/agent/status-report` when available (from monitor-written file); show layer_0_goal status...
  - PM / Orchestration section: Show layer_1_orchestration from status-report when available; else derive from pipeline-s...
  - Tasks section: Running, pending (with wait times), recent completed (with duration) — current pipeline-status content...
  - Artifacts section: Recent task outputs / artifact health — e.g. recent_completed tasks with output_len and optional o...
commands:
  - python3 -m pytest api/tests/test_check_pipeline_hierarchical.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

No new API. Uses existing:

- `GET /api/agent/status-report` — hierarchical report (layer_0_goal … layer_3_attention) when monitor has written it.
- `GET /api/agent/pipeline-status` — running, pending, recent_completed, project_manager, attention, etc.
- `GET /api/agent/effectiveness` — goal_proximity, throughput, success_rate (fallback when status-report missing).


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

N/A. Script aggregates existing API responses and prints (or emits JSON) in hierarchical order.

## Files to Create/Modify

- `api/scripts/check_pipeline.py` — add hierarchical view: fetch status-report (and optionally effectiveness), merge with pipeline-status; print Goal → PM → Tasks → Artifacts; add `--hierarchical` / `--flat`; extend `--json` to include hierarchical structure when available.

## Acceptance Tests

- Run `python scripts/check_pipeline.py` (no `--json`): output shows four sections in order — Goal, PM/Orchestration, Tasks, Artifacts.
- Run with `--json`: response includes hierarchical data (e.g. from status-report or built from pipeline-status + effectiveness).
- Run with `--flat`: output is legacy flat format (no requirement to change section order for `--flat` beyond preserving previous behavior).
- When status-report file is missing and API is up: Goal section shows fallback from effectiveness or "report not yet generated"; Tasks and Artifacts still from pipeline-status.

## Out of Scope

- Changing `GET /api/agent/status-report` or `GET /api/agent/pipeline-status` contracts.
- Modifying `monitor_pipeline.py` (monitor continues to write status-report as today).
- New API endpoints or new files beyond the single script change.

## See also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — item 5.
- [PIPELINE-EFFICIENCY-PLAN.md](../docs/PIPELINE-EFFICIENCY-PLAN.md) — §4.3 Hierarchical view, §7 Phase 3.
- [032-attention-heuristics-pipeline-status.md](032-attention-heuristics-pipeline-status.md) — attention flags.
- [026-pipeline-observability-and-auto-review.md](026-pipeline-observability-and-auto-review.md) — goal status and dashboard.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add distributed locking for multi-worker pipelines.


## Verification

```bash
python3 -m pytest api/tests/test_check_pipeline_hierarchical.py -x -v
```
