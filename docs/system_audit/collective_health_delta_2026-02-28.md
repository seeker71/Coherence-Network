# Collective health endpoint — before / after (2026-02-28)

## Before

- `GET /api/agent/collective-health` was not registered; the API had no single payload for collective coherence, resonance, flow, and friction.

## After

- The route is served from `api/app/routers/agent.py` and aggregates metrics, monitor issues, and friction ledger data via `api/app/services/collective_health_service.py`.
- Responses include `scores.collective_value` as `coherence * resonance * flow * (1 - friction)`, pillar diagnostics, `top_friction_queue`, and `top_opportunities`.

## Verification

- `cd api && pytest -q tests/test_agent_collective_health_api.py`
