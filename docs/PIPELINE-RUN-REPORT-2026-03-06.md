# Pipeline Run Report — 2026-03-06

## Summary

- **tracking-mechanism-efficiency**: Accepted (manifestation_status=validated)
- **api-docs-completion**: Implemented, validated, accepted
- **Validated ideas**: 5
- **Unvalidated ideas**: 47

---

## tracking-mechanism-efficiency (accepted)

| Task | CLI | Output |
|------|-----|--------|
| 1. Verify idea status | `curl -s http://127.0.0.1:8000/api/ideas/tracking-mechanism-efficiency \| python3 -c "import sys,json; d=json.load(sys.stdin); print('manifestation_status:', d['manifestation_status'])"` | `manifestation_status: validated` |
| 2. Full metrics | `curl -s 'http://127.0.0.1:8000/api/agent/metrics'` | `keys: ['by_model', 'by_task_type', 'execution_time', 'success_rate']` |
| 3. metric=time filter | `curl -s 'http://127.0.0.1:8000/api/agent/metrics?metric=time'` | `keys: ['execution_time']` |
| 4. pytest | `cd api && pytest -q tests/test_agent_integration_api.py::test_agent_metrics_returns_200_and_supports_metric_filter` | `1 passed, 2 warnings in 0.70s` |
| 5. Idea counts | `curl -s http://127.0.0.1:8000/api/ideas \| python3 -c "..."` | `validated: 4 unvalidated: 48` |

---

## api-docs-completion (next idea — implemented & validated)

| Task | CLI | Output |
|------|-----|--------|
| 1. OpenAPI summary | `curl -s http://127.0.0.1:8000/openapi.json \| python3 -c "import sys,json; d=json.load(sys.stdin); op=d['paths']['/api/agent/metrics']['get']; print('summary:', op.get('summary'))"` | `summary: Task metrics (success rate, duration, by task_type/model)` |
| 2. pytest | `cd api && pytest -q tests/test_agent_integration_api.py -k 'metrics or openapi'` | `2 passed, 7 deselected, 2 warnings in 0.78s` |
| 3. Idea status | `curl -s http://127.0.0.1:8000/api/ideas/api-docs-completion \| ...` | `manifestation_status: validated` |
| 4. Idea counts | `curl -s http://127.0.0.1:8000/api/ideas \| ...` | `validated: 5 unvalidated: 47` |

### Files changed

- `api/app/routers/agent_issues_routes.py` — Added `summary="Task metrics (...)"` to `GET /api/agent/metrics`
- `api/tests/test_agent_integration_api.py` — Added `test_openapi_metrics_has_summary`

---

## Verification

All tasks passed. Pipeline works as expected:
- Ideas marked accepted (validated)
- Live API returns expected responses after restart
- pytest passes for changed code
- Unvalidated count declined: 48 → 47
