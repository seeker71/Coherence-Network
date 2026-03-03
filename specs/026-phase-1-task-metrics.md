# Spec: 026 Phase 1 — Persist Task Metrics; GET /api/agent/metrics

*Parent: [026-pipeline-observability-and-auto-review.md](026-pipeline-observability-and-auto-review.md). Format: [TEMPLATE.md](TEMPLATE.md).*

## Purpose

Implement the core metrics slice of spec 026: persist one metric record per completed or failed agent task, and expose aggregates via `GET /api/agent/metrics` so the pipeline can be measured and improved (success rate, execution time, breakdowns by task_type and model).

## Requirements

- [ ] **Persist on completion** — When a task reaches status `completed` or `failed`, append one task metric record (task_id, task_type, model, duration_seconds, status, created_at). Call from agent_runner (or from PATCH /api/agent/tasks when status is set to completed/failed).
- [ ] **Metrics store** — Persist records in a single append-only store (e.g. JSONL at `api/logs/metrics.jsonl`). One JSON object per line.
- [ ] **GET /api/agent/metrics** — Returns 200 with aggregates over a rolling window (e.g. 7 days): success_rate (completed, failed, total, rate), execution_time (p50_seconds, p95_seconds), by_task_type, by_model. Empty or zeroed structure when no metrics exist.
- [ ] **No persistence on other statuses** — Do not record metrics for pending, running, or needs_decision.

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
