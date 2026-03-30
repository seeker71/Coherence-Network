# Acceptance: tracking-mechanism-efficiency

## Idea

**tracking-mechanism-efficiency** — Improve pipeline efficiency by enabling targeted metric queries (time, success, by_task_type, by_model) without full payload.

## Implementation

### Files Changed

- `api/app/routers/agent_issues_routes.py` — Added `metric` query param to `GET /api/agent/metrics`
- `api/tests/test_agent_integration_api.py` — Added `test_agent_metrics_returns_200_and_supports_metric_filter`

### API Contract

- `GET /api/agent/metrics` — Full response (backward compatible)
- `GET /api/agent/metrics?metric=time` — Returns only `execution_time`
- `GET /api/agent/metrics?metric=success` — Returns only `success_rate`
- `GET /api/agent/metrics?metric=by_task_type` — Returns only `by_task_type`
- `GET /api/agent/metrics?metric=by_model` — Returns only `by_model`

### Verification

1. **Tests**: `cd api && pytest -q tests/test_agent_integration_api.py::test_agent_metrics_returns_200_and_supports_metric_filter`
2. **Live API** (after restart): `curl -s "http://localhost:8000/api/agent/metrics?metric=time" | jq`
3. **Full**: `curl -s "http://localhost:8000/api/agent/metrics" | jq`

## Shippable Change

- Backward compatible (no param = full response)
- Test-covered
- Enables pipeline scripts to request smaller payloads for time/success checks

## Post-Restart Verification Proof (2026-03-06)

| Step | Check | Proof |
|------|-------|-------|
| 1 | Full metrics (no filter) | `[PROOF] step_1_full_metrics: {"status": "pass", "keys": ["by_model", "by_task_type", "execution_time", "success_rate"]}` |
| 2 | metric=time | `[PROOF] step_2_metric_time: {"status": "pass", "keys": ["execution_time"]}` |
| 3 | metric=success | `[PROOF] step_3_metric_success: {"status": "pass", "keys": ["success_rate"]}` |
| 4 | metric=by_task_type | `[PROOF] step_4_metric_by_task_type: {"status": "pass", "keys": ["by_task_type"]}` |
| 5 | metric=by_model | `[PROOF] step_5_metric_by_model: {"status": "pass", "keys": ["by_model"]}` |
| 6 | pytest | 1 passed (test_agent_metrics_returns_200_and_supports_metric_filter) |
| 7 | Idea status | `[PROOF] step_7_idea_status: {"status": "pass", "manifestation_status": "validated"}` |
| 8 | Idea counts | `[PROOF] step_8_idea_counts: {"validated": 4, "unvalidated": 48}` |

**Acceptance:** All parts accepted. Changes present and working after API restart.
