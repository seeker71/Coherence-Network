# Spec: 026 Phase 1 — Persist Task Metrics; GET /api/agent/metrics

*Parent: [026-pipeline-observability-and-auto-review.md](026-pipeline-observability-and-auto-review.md). Format: [TEMPLATE.md](TEMPLATE.md).*

## Purpose

Implement the core metrics slice of spec 026: persist one metric record per completed or failed agent task, and expose aggregates via `GET /api/agent/metrics` so the pipeline can be measured and improved (success rate, execution time, breakdowns by task_type and model).

## Requirements

- [ ] **Persist on completion** — When a task reaches status `completed` or `failed`, append one task metric record (task_id, task_type, model, duration_seconds, status, created_at). Call from agent_runner (or from PATCH /api/agent/tasks when status is set to completed/failed).
- [ ] **Metrics store** — Persist records in a single append-only store (e.g. JSONL at `api/logs/metrics.jsonl`). One JSON object per line.
- [ ] **GET /api/agent/metrics** — Returns 200 with aggregates over a rolling window (e.g. 7 days): success_rate (completed, failed, total, rate), execution_time (p50_seconds, p95_seconds), by_task_type, by_model. Empty or zeroed structure when no metrics exist.
- [ ] **No persistence on other statuses** — Do not record metrics for pending, running, or needs_decision.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 002, 007

## Task Card

```yaml
goal: Implement the core metrics slice of spec 026: persist one metric record per completed or failed agent task, and expose aggregates via `GET /api/agent/metrics` so the pipeline can be measured and improved (success rate, execution time, breakdowns by task_type and model).
files_allowed:
  - api/app/services/metrics_service.py
  - api/app/routers/agent.py
  - api/scripts/agent_runner.py
  - api/app/models/metrics.py
done_when:
  - Persist on completion — When a task reaches status `completed` or `failed`, append one task metric record (task_id, t...
  - Metrics store — Persist records in a single append-only store (e.g. JSONL at `api/logs/metrics.jsonl`). One JSON obje...
  - GET /api/agent/metrics — Returns 200 with aggregates over a rolling window (e.g. 7 days): success_rate (completed, fa...
  - No persistence on other statuses — Do not record metrics for pending, running, or needs_decision.
commands:
  - python3 -m pytest api/tests/test_agent_task_persistence.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

### `GET /api/agent/metrics`

**Request** — None (no path or query parameters).

**Response 200**
```json
{
  "success_rate": { "completed": 80, "failed": 5, "total": 85, "rate": 0.94 },
  "execution_time": { "p50_seconds": 45, "p95_seconds": 120 },
  "by_task_type": {
    "spec": { "count": 10, "completed": 9, "failed": 1, "success_rate": 0.9 },
    "impl": { "count": 75, "completed": 71, "failed": 4, "success_rate": 0.95 }
  },
  "by_model": {
    "cursor/auto": { "count": 60, "avg_duration": 52.0 },
    "ollama/glm-4.7-flash:latest": { "count": 25, "avg_duration": 38.0 }
  }
}
```

When no metrics exist (or window is empty), return the same shape with zeros/empty objects (e.g. `"total": 0`, `"rate": 0.0`, `"by_task_type": {}`, `"by_model": {}`).

**Response 4xx/5xx** — Not required for Phase 1; endpoint may return 200 with empty structure on read/aggregation errors if desired.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

**Stored record (one line of JSONL):**
```yaml
TaskMetricRecord:
  task_id: string
  task_type: string
  model: string
  duration_seconds: number
  status: "completed" | "failed"
  created_at: string   # ISO 8601 UTC
```

**Aggregates (in-memory / API response):** success_rate (completed, failed, total, rate), execution_time (p50_seconds, p95_seconds), by_task_type (per type: count, completed, failed, success_rate), by_model (per model: count, avg_duration).

## Files to Create/Modify

- `api/app/services/metrics_service.py` — Persist one record (e.g. `record_task(...)`), load records, aggregate over rolling window; expose `get_aggregates()`.
- `api/app/routers/agent.py` — Add or ensure `GET /api/agent/metrics` calls metrics service and returns aggregate dict.
- `api/scripts/agent_runner.py` — On task completion or failure, call metrics service to persist task_id, task_type, model, duration_seconds, status (and optionally wire PATCH handler to persist when status → completed/failed).
- `api/app/models/metrics.py` — Optional; Pydantic models for metrics response if desired. Otherwise plain dict is acceptable for Phase 1.

## Acceptance Tests

- When a task is completed or failed (via agent_runner or PATCH), a corresponding record appears in the metrics store (JSONL).
- `GET /api/agent/metrics` returns 200 with structure `success_rate`, `execution_time`, `by_task_type`, `by_model`.
- With no metrics (or empty window), `GET /api/agent/metrics` returns 200 with zeroed/empty structure (no 404/500).
- Aggregates use only records within the defined rolling window (e.g. 7 days).

## Out of Scope

- Phase 2: A/B variants (prompt_variant, skill_version), cost/token tracking.
- Alternative backends (SQLite, PostgreSQL) unless already agreed in 026 Decision Gates.
- Pydantic response model required only if project convention requires it; dict is acceptable for Phase 1.

## Decision Gates (if any)

- **Storage** — JSONL vs SQLite vs PostgreSQL: align with 026 (current implementation uses JSONL at `api/logs/metrics.jsonl`).
- **Call site** — Persist from agent_runner only, or also when API PATCH sets status to completed/failed (both is acceptable).

## See Also

- [026-pipeline-observability-and-auto-review.md](026-pipeline-observability-and-auto-review.md) — Parent spec; Phases 2–6.
- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — Agent API; GET /api/agent/metrics listed there.
- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — Backlog item: Implement spec 026 Phase 1.

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
python3 -m pytest api/tests/test_agent_task_persistence.py -x -v
```
