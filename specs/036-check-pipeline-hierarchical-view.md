# Spec: Hierarchical view in check_pipeline (goal → PM → tasks → artifacts)

## Purpose

Operators need a single command that shows pipeline health in a clear hierarchy: goal progress first, then orchestration (PM), then task execution, then artifact health. This makes it easy to see "are we on track?" before drilling into running/pending tasks and recent outputs.

## Requirements

- [ ] When run without `--json`, `check_pipeline.py` prints a **hierarchical view**: Goal → PM/Orchestration → Tasks → Artifacts (in that order).
- [ ] **Goal** section: Use `GET /api/agent/status-report` when available (from monitor-written file); show layer_0_goal status and summary (e.g. goal_proximity, throughput, success rate). If status-report is missing, show "Goal: (report not yet generated)" or fetch `GET /api/agent/effectiveness` and show goal_proximity and a one-line summary.
- [ ] **PM / Orchestration** section: Show layer_1_orchestration from status-report when available; else derive from pipeline-status (project_manager state, backlog_index, phase, blocked) and process detection (agent_runner workers, PM --parallel). Same information as current "PROJECT MANAGER" and "PROCESSES" blocks, but labeled as Layer 1.
- [ ] **Tasks** section: Running, pending (with wait times), recent completed (with duration) — current pipeline-status content, labeled as Layer 2 / Tasks.
- [ ] **Artifacts** section: Recent task outputs / artifact health — e.g. recent_completed tasks with output_len and optional one-line output_preview; optionally mention spec/STATUS artifact health if effectiveness or status-report exposes it. At minimum: list recent completed with output size so operator can see "artifacts produced."
- [ ] Add optional flag `--hierarchical` to explicitly enable this view; default human-readable output is hierarchical. Add `--flat` to preserve legacy flat output (Goal/PM/Tasks/Artifacts order still allowed but sections not strictly layered).
- [ ] With `--json`, when hierarchical view is requested (default or `--hierarchical`), include in the JSON a top-level key `hierarchical` (or merge layer_0_goal, layer_1_orchestration, layer_2_execution, layer_3_attention from status-report when available) so script consumers get the same structure.

## API Contract (if applicable)

No new API. Uses existing:

- `GET /api/agent/status-report` — hierarchical report (layer_0_goal … layer_3_attention) when monitor has written it.
- `GET /api/agent/pipeline-status` — running, pending, recent_completed, project_manager, attention, etc.
- `GET /api/agent/effectiveness` — goal_proximity, throughput, success_rate (fallback when status-report missing).

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
