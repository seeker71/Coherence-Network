# Collective Health Before/After Delta (2026-02-28)

## Endpoint Availability

- Before: `GET /api/agent/collective-health` -> HTTP `404` (`Not Found`)
- After: `GET /api/agent/collective-health` -> HTTP `200` (scored payload)

## Pillar Progress (Real Output Snapshot)

| Pillar | Before | After | Concrete change |
|---|---:|---:|---|
| coherence | unavailable | 0.0 | New coherence score + coverage diagnostics in API payload |
| resonance | unavailable | 0.35 | New resonance score + reuse/traceability/learning signals |
| flow | unavailable | 0.6267 | New flow score + completion/throughput/latency factors |
| friction | unavailable | 0.5 | New friction score + visible `top_friction_queue` |
| collective_value | unavailable | 0.0 | New composite objective score |

Source: `docs/system_audit/collective_health_after_2026-02-28.json`

## Proof That System Behavior Changed

1. New route exists and returns computed metrics from live data.
- File: `api/app/routers/agent.py`
- Behavior: new `GET /api/agent/collective-health` route.

2. New scoring service computes pillar values from real task/runtime/friction records.
- File: `api/app/services/collective_health_service.py`
- Inputs: `agent_service`, `metrics_service`, `runtime_service`, `friction_service`, monitor issues file.

3. New API tests validate the endpoint payload and formula.
- File: `api/tests/test_agent_collective_health_api.py`
- Result: `2 passed`.

4. Friction is now visible as a prioritized queue in the same health payload.
- After snapshot: `top_friction_queue_count=5`.

5. Opportunity guidance is now returned for direct action.
- After snapshot: `top_opportunities_count=3`.
