# Spec: Collective Health Signals for Coherence, Resonance, Flow, and Friction

## Purpose

Expose system-level progress toward the project's core values by making coherence, resonance, flow, and friction measurable from live operational data. This allows contributors to steer collective outcomes directly, instead of relying on implicit internal heuristics.

## Requirements

- [x] Add `GET /api/agent/collective-health` that returns explicit scores for coherence, resonance, flow, and friction.
- [x] Compute scores from real task/runtime/friction data already available in the system.
- [x] Return a single `collective_value` score derived from `coherence * resonance * flow * (1 - friction)`.
- [x] Include component diagnostics and counts so contributors can understand what drives each score.
- [x] Include a top friction queue to make blocking points visible.
- [x] Include top opportunities for improving coherence/resonance/flow in the same payload.
- [x] Add API tests proving payload shape and score ranges.
- [x] Add before/after proof artifacts showing endpoint availability and changed behavior.

## API Contract (if applicable)

### `GET /api/agent/collective-health`

**Response 200**
```json
{
  "generated_at": "2026-02-28T09:00:00Z",
  "window_days": 7,
  "scores": {
    "coherence": 0.72,
    "resonance": 0.63,
    "flow": 0.58,
    "friction": 0.34,
    "collective_value": 0.17
  },
  "coherence": {"...": "component metrics"},
  "resonance": {"...": "component metrics"},
  "flow": {"...": "component metrics"},
  "friction": {"...": "component metrics"},
  "top_friction_queue": [],
  "top_opportunities": []
}
```

## Data Model (if applicable)

```yaml
CollectiveHealth:
  generated_at: string
  window_days: integer
  scores:
    coherence: number
    resonance: number
    flow: number
    friction: number
    collective_value: number
  top_friction_queue:
    - key: string
      title: string
      severity: string
      signal: number
  top_opportunities:
    - pillar: string
      signal: string
      impact_estimate: number
```

## Files to Create/Modify

- `specs/114-collective-coherence-resonance-flow-friction-health.md`
- `api/app/services/collective_health_service.py`
- `api/app/routers/agent.py`
- `api/tests/test_agent_collective_health_api.py`
- `docs/system_audit/collective_health_before_2026-02-28.json`
- `docs/system_audit/collective_health_after_2026-02-28.json`
- `docs/system_audit/collective_health_delta_2026-02-28.md`

## Acceptance Tests

- `cd api && pytest -q tests/test_agent_collective_health_api.py`

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.




## Verification

```bash
cd api && pytest -q tests/test_agent_collective_health_api.py
cd api && python3 - <<'PY'
import asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app

async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        r = await client.get('/api/agent/collective-health')
        print(r.status_code)
        print(r.json())

asyncio.run(main())
PY
```

## Out of Scope

- New database tables for collective metrics history.
- UI redesign for collective health visualizations.

## Risks and Assumptions

- Some environments may have sparse task/friction data; metrics must degrade gracefully.
- Score formulas are initial heuristics and should be tuned with real usage feedback.

## Known Gaps and Follow-up Tasks

- Follow-up task: add a web dashboard panel for collective health trends.
- Follow-up task: persist daily snapshots for longitudinal collective learning.

## Decision Gates (if any)

- No decision gate required for read-only API metric exposure.
