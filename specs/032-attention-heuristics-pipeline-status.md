# Spec: Attention Heuristics in Pipeline-Status

## Purpose

Surface pipeline health signals so operators and automation can detect stuck runs, repeated failures, and low success rate without inspecting logs. The `GET /api/agent/pipeline-status` response includes an `attention` object whose flags drive alerts, Telegram summaries, and optional auto-fix (see spec 027).

## Requirements

- [x] `GET /api/agent/pipeline-status` returns an `attention` object with boolean flags and a `flags` list (spec 002, 027).
- [x] **Stuck:** `attention.stuck` is true when there are pending tasks, no running task, and the longest pending wait time exceeds a threshold (default 10 minutes).
- [x] **Repeated failures:** `attention.repeated_failures` is true when the three most recently completed tasks (by completion order) are all failed.
- [x] **Low success rate:** `attention.low_success_rate` is true when metrics over the rolling window (e.g. 7 days) have at least 10 tasks and success rate &lt; 80%.
- [ ] Heuristic thresholds (stuck minutes, consecutive failure count, success-rate window and minimum sample) are configurable (env or config) with documented defaults.
- [ ] `check_pipeline.py --attention` prints attention flags in human-readable form (spec 027).

## API Contract (if applicable)

### `GET /api/agent/pipeline-status`

Existing response; `attention` object is required:

**Response 200** — `attention` shape:

```json
{
  "attention": {
    "stuck": false,
    "repeated_failures": false,
    "low_success_rate": false,
    "flags": []
  }
}
```

- `stuck`: true if pipeline appears stuck (pending with no progress beyond threshold).
- `repeated_failures`: true if last N completed tasks are all failed (N = 3 by default).
- `low_success_rate`: true if windowed success rate is below threshold when sample size is sufficient.
- `flags`: list of string names of raised conditions (e.g. `["stuck"]`, `["repeated_failures", "low_success_rate"]`), empty when none.

## Data Model (if applicable)

Attention is computed at read time from in-memory task store and (for low_success_rate) from `metrics_service.get_aggregates()`. No new persisted model; thresholds may be read from env (e.g. `PIPELINE_ATTENTION_STUCK_MINUTES`, `PIPELINE_ATTENTION_CONSECUTIVE_FAILURES`, `PIPELINE_ATTENTION_MIN_TASKS`, `PIPELINE_ATTENTION_SUCCESS_RATE_MIN`).

## Heuristic Definitions

| Flag | Condition | Default |
|------|-----------|--------|
| **stuck** | `pending.size > 0` and `running.size == 0` and `max(pending.wait_seconds) > STUCK_THRESHOLD_SECONDS` | 600 (10 min) |
| **repeated_failures** | Among most recent completed tasks (by `updated_at` or completion order), the first N are all status `failed` | N = 3 |
| **low_success_rate** | `metrics_service.get_aggregates()` (rolling 7d): `total >= MIN_TASKS` and `rate < SUCCESS_RATE_MIN` | MIN_TASKS=10, rate&lt;0.8 |

When metrics are unavailable (e.g. no metrics_service), `low_success_rate` remains false; do not raise.

## Files to Create/Modify

- `api/app/services/agent_service.py` — `get_pipeline_status()`: compute attention from store + optional metrics; use configurable thresholds when added.
- `api/app/routers/agent.py` — no change if response shape already includes `attention`.
- `api/scripts/check_pipeline.py` — add `--attention` flag to print attention flags (when implemented).
- `api/tests/test_agent.py` — tests: pipeline-status includes `attention` with all keys; optional tests for stuck true when pending > 10 min no running, repeated_failures when last 3 failed, low_success_rate when metrics indicate.

## Acceptance Tests

- `GET /api/agent/pipeline-status` response includes `attention` with keys `stuck`, `repeated_failures`, `low_success_rate`, `flags` (existing tests in test_agent.py).
- When there are pending tasks, no running task, and longest wait > 10 min: `attention.stuck` is true and `"stuck"` in `attention.flags`.
- When the three most recently completed tasks are all failed: `attention.repeated_failures` is true and `"repeated_failures"` in `attention.flags`.
- When metrics exist with total ≥ 10 and rate &lt; 0.8: `attention.low_success_rate` is true and `"low_success_rate"` in `attention.flags`.
- When metrics are missing or empty: `attention.low_success_rate` is false (no exception).

## Out of Scope

- Auto-fix actions (create heal task, restart) — spec 027 Phase 4.
- Per-phase repeated-failure detection (e.g. “3 failed impl in a row”) — possible future refinement.
- Persisting attention history or alerting channels other than existing status/Telegram.

## Decision Gates (if any)

- Adding new env vars for thresholds: document in RUNBOOK/AGENTS.md; default-only change does not require gate.
- Changing the definition of “repeated failures” (e.g. same phase, or N ≠ 3) — human approval.

## See also

- [002 Agent Orchestration API](002-agent-orchestration-api.md) — pipeline-status response shape.
- [027 Fully Automated Pipeline](027-fully-automated-pipeline.md) — Phase 3 monitor attention, Phase 4 auto-fix.
- [007 Meta-pipeline backlog](007-meta-pipeline-backlog.md) — item 4: attention heuristics.
- [PIPELINE-ATTENTION](../docs/PIPELINE-ATTENTION.md) — operational checklist.
