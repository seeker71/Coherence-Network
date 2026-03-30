# Spec: Collective Coherence–Resonance–Flow–Friction Health Scorecard

**Idea ID**: `114-collective-coherence-resonance-flow-friction-health`
**Status**: `impl-ready`
**Date**: 2026-03-28

---

## Purpose

Expose system-level progress toward the project's core values by making coherence,
resonance, flow, and friction measurable from live operational data. A single endpoint
returns a multi-pillar health scorecard and a `collective_value` score (0.0–1.0) so
contributors and agents can steer collective outcomes directly rather than relying on
implicit internal heuristics.

Without this endpoint, operators and orchestrators must independently query four separate
data sources and manually combine their signals. The unified scorecard eliminates that
overhead, enables release-gate checks, and gives every agent node a shared "how healthy
is the system right now?" signal.

---

## Requirements

- [ ] **R1** — `GET /api/agent/collective-health` returns HTTP 200 with a JSON body that
  includes `scores.collective_value` (float 0.0–1.0) and pillar breakdowns for
  `coherence`, `resonance`, `flow`, and `friction`.
- [ ] **R2** — Caller may pass `?window_days=N` (1 ≤ N ≤ 30, default 7) to control the
  time window used by resonance and friction sub-scores. Value is echoed in the response.
- [ ] **R3** — `collective_value` is computed as:
  `coherence × resonance × flow × (1 − friction)` where each factor is clamped to [0,1].
- [ ] **R4** — When the system has zero tasks or events, each pillar score defaults to
  0.5 (neutral) rather than 0.0 to avoid false alarms on a fresh instance.
- [ ] **R5** — `top_opportunities` contains up to 5 items sorted by `impact_estimate`
  descending. Each item has: `pillar`, `signal`, `action` (human-readable), and
  `impact_estimate` (float).
- [ ] **R6** — `top_friction_queue` contains up to 5 items from the friction entry-points
  report. Each item has: `key`, `title`, `severity`, `signal`, `recommended_action`.
- [ ] **R7** — Response always includes `generated_at` (ISO 8601 UTC ending in `Z`) and
  `window_days` echo to enable reliable cache-busting.
- [ ] **R8** — On import error the endpoint degrades gracefully: returns HTTP 200 with
  empty pillar objects and zero scores rather than HTTP 500.
- [ ] **R9** — `friction.score` represents *badness* (higher = more friction); all other
  pillar scores represent *goodness* (higher = better). This asymmetry must be preserved
  in the `collective_value` formula.
- [ ] **R10** — `window_days` values outside [1, 30] are silently clamped server-side
  without returning HTTP 422.

---

## Research Inputs

- `2026-03-28` — `api/app/services/collective_health_service.py` — live implementation
  of `get_collective_health()` with four pillar sub-functions.
- `2026-03-28` — `api/app/routers/agent_issues_routes.py` — endpoint mount at
  `GET /agent/collective-health` under the `/api` prefix (via `agent.py` include).
- `2026-03-28` — `api/app/services/friction_service.py` — source of friction events,
  energy-loss calculations, and entry-point reports.
- `2026-03-28` — `api/app/routers/agent.py` — `router.include_router(issues_router,
  prefix="/agent")` establishes the full path `/api/agent/collective-health`.

---

## Task Card

```yaml
goal: formalise and validate the collective health scorecard at GET /api/agent/collective-health
files_allowed:
  - api/app/routers/agent_issues_routes.py
  - api/app/services/collective_health_service.py
  - api/tests/test_agent_collective_health_api.py
done_when:
  - GET /api/agent/collective-health returns 200 with collective_value in [0,1]
  - window_days query param accepted and echoed in response
  - collective_value equals coherence * resonance * flow * (1 - friction) to 4dp
  - pytest api/tests/test_agent_collective_health_api.py passes with 0 failures
commands:
  - cd api && pytest -q tests/test_agent_collective_health_api.py
constraints:
  - Do not modify test files to force passing behavior
  - collective_value formula must match R3 exactly
  - friction score must remain asymmetric (higher = worse)
```

---

## API Contract

### `GET /api/agent/collective-health`

**Query parameters**

| Name | Type | Default | Constraints |
|------|------|---------|-------------|
| `window_days` | integer | `7` | 1 ≤ N ≤ 30, clamped silently |

**Response 200 (nominal)**

```json
{
  "generated_at": "2026-03-28T12:00:00Z",
  "window_days": 7,
  "scores": {
    "coherence": 0.72,
    "resonance": 0.65,
    "flow": 0.80,
    "friction": 0.15,
    "collective_value": 0.3991
  },
  "coherence": {
    "score": 0.72,
    "task_count": 42,
    "target_state_coverage": 0.85,
    "task_card_coverage": 0.78,
    "task_card_quality": 0.81,
    "evidence_coverage": 0.60
  },
  "resonance": {
    "score": 0.65,
    "task_count": 42,
    "tracked_reference_total": 38,
    "reused_reference_count": 18,
    "reference_reuse_ratio": 0.47,
    "completion_event_count": 30,
    "traceable_completion_ratio": 0.70,
    "learning_capture_ratio": 0.50
  },
  "flow": {
    "score": 0.80,
    "task_count": 42,
    "completion_ratio": 0.82,
    "active_flow_ratio": 0.75,
    "throughput_factor": 0.60,
    "latency_factor": 0.90,
    "status_counts": {
      "completed": 28,
      "failed": 6,
      "running": 3,
      "pending": 2,
      "needs_decision": 1,
      "cancelled": 2
    }
  },
  "friction": {
    "score": 0.15,
    "event_count": 20,
    "open_events": 3,
    "ignored_events": 1,
    "open_density": 0.15,
    "energy_loss": 12.5,
    "issue_count": 2
  },
  "top_friction_queue": [
    {
      "key": "task_retry_loop",
      "title": "Repeated retry on same task",
      "severity": "warn",
      "signal": 3.5,
      "recommended_action": "Investigate retry root cause"
    }
  ],
  "top_opportunities": [
    {
      "pillar": "coherence",
      "signal": "task_card_coverage",
      "action": "Increase task-card completeness on new tasks.",
      "impact_estimate": 0.22
    }
  ]
}
```

**Response 200 (degraded — import failure)**

```json
{
  "generated_at": "2026-03-28T12:00:00Z",
  "window_days": 7,
  "scores": {
    "coherence": 0.0,
    "resonance": 0.0,
    "flow": 0.0,
    "friction": 0.0,
    "collective_value": 0.0
  },
  "coherence": {},
  "resonance": {},
  "flow": {},
  "friction": {},
  "top_friction_queue": [],
  "top_opportunities": []
}
```

No HTTP 4xx or 5xx is returned for import failures.

---

## Data Model

```yaml
CollectiveHealthResponse:
  generated_at:     { type: string, format: "ISO 8601 UTC (ends in Z)" }
  window_days:      { type: integer, range: "[1, 30]" }
  scores:           { type: ScoreSummary }
  coherence:        { type: CoherenceDetail }
  resonance:        { type: ResonanceDetail }
  flow:             { type: FlowDetail }
  friction:         { type: FrictionDetail }
  top_friction_queue: { type: "array[FrictionQueueItem]", max: 5 }
  top_opportunities:  { type: "array[OpportunityItem]", max: 5 }

ScoreSummary:
  coherence:        { type: float, range: "[0.0, 1.0]" }
  resonance:        { type: float, range: "[0.0, 1.0]" }
  flow:             { type: float, range: "[0.0, 1.0]" }
  friction:         { type: float, range: "[0.0, 1.0]", note: "higher = worse" }
  collective_value: { type: float, range: "[0.0, 1.0]",
                      formula: "coherence * resonance * flow * (1 - friction)" }

CoherenceDetail:
  score:                 { type: float, range: "[0.0, 1.0]" }
  task_count:            { type: int, min: 0 }
  target_state_coverage: { type: float, range: "[0.0, 1.0]" }
  task_card_coverage:    { type: float, range: "[0.0, 1.0]" }
  task_card_quality:     { type: float, range: "[0.0, 1.0]" }
  evidence_coverage:     { type: float, range: "[0.0, 1.0]" }

ResonanceDetail:
  score:                      { type: float, range: "[0.0, 1.0]" }
  task_count:                 { type: int, min: 0 }
  tracked_reference_total:    { type: int, min: 0 }
  reused_reference_count:     { type: int, min: 0 }
  reference_reuse_ratio:      { type: float, range: "[0.0, 1.0]" }
  completion_event_count:     { type: int, min: 0 }
  traceable_completion_ratio: { type: float, range: "[0.0, 1.0]" }
  learning_capture_ratio:     { type: float, range: "[0.0, 1.0]" }

FlowDetail:
  score:             { type: float, range: "[0.0, 1.0]" }
  task_count:        { type: int, min: 0 }
  completion_ratio:  { type: float, range: "[0.0, 1.0]" }
  active_flow_ratio: { type: float, range: "[0.0, 1.0]" }
  throughput_factor: { type: float, range: "[0.0, 1.0]" }
  latency_factor:    { type: float, range: "[0.0, 1.0]" }
  status_counts:     { type: object, keys: [completed, failed, running, pending, needs_decision, cancelled] }

FrictionDetail:
  score:          { type: float, range: "[0.0, 1.0]", note: "higher = worse" }
  event_count:    { type: int, min: 0 }
  open_events:    { type: int, min: 0 }
  ignored_events: { type: int, min: 0 }
  open_density:   { type: float, range: "[0.0, 1.0]" }
  energy_loss:    { type: float, min: 0.0 }
  issue_count:    { type: int, min: 0 }

FrictionQueueItem:
  key:                { type: string }
  title:              { type: string }
  severity:           { type: string, enum: [info, warn, error] }
  signal:             { type: float, min: 0.0 }
  recommended_action: { type: string }

OpportunityItem:
  pillar:          { type: string, enum: [coherence, resonance, flow, friction] }
  signal:          { type: string }
  action:          { type: string }
  impact_estimate: { type: float, min: 0.0 }
```

---

## Files to Create/Modify

- `api/app/routers/agent_issues_routes.py` — existing endpoint; no structural changes
  unless graceful degradation path needs hardening
- `api/app/services/collective_health_service.py` — core computation (exists)
- `api/tests/test_agent_collective_health_api.py` — acceptance tests (create or extend)

---

## Acceptance Tests

- `api/tests/test_agent_collective_health_api.py::test_collective_health_returns_200`
- `api/tests/test_agent_collective_health_api.py::test_collective_health_score_fields_present`
- `api/tests/test_agent_collective_health_api.py::test_collective_health_window_days_param`
- `api/tests/test_agent_collective_health_api.py::test_collective_health_collective_value_formula`
- `api/tests/test_agent_collective_health_api.py::test_collective_health_window_days_clamped`

---

## Concurrency Behavior

- **Read-only**: No writes occur during scoring; safe for concurrent requests.
- **Computation cost**: Queries up to 5000 tasks + runtime events on each call. Cache at
  the caller level if polling more than once per minute.
- **window_days clamping**: Values outside [1, 30] are silently clamped server-side;
  no HTTP 422 is raised (per R10).

---

## Verification Scenarios

### Scenario 1 — Nominal GET with default window

**Setup**: API is running with at least one task in the database.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/agent/collective-health
```

**Expected result**:
- HTTP 200
- Body contains `scores.collective_value` as a float in [0.0, 1.0]
- Body contains `scores.coherence`, `scores.resonance`, `scores.flow`, `scores.friction`
  each as floats in [0.0, 1.0]
- Body contains `generated_at` as ISO 8601 string ending in `Z`
- Body contains `window_days: 7`
- `top_opportunities` is a JSON array (may be empty, must not be null)
- `top_friction_queue` is a JSON array (may be empty, must not be null)

**Edge**: Internal exception in service layer must NOT produce HTTP 500; must return
HTTP 200 with zero scores and empty arrays (degraded path).

---

### Scenario 2 — Custom window_days echoed in response

**Setup**: API is running.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/agent/collective-health?window_days=14" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['window_days']==14, d['window_days']; print('OK')"
```

**Expected result**: Prints `OK`. `window_days` field equals `14`.

**Edge 1**: `?window_days=0` → clamped to 1 server-side; response `window_days: 1`, HTTP 200.

**Edge 2**: `?window_days=99` → clamped to 30; response `window_days: 30`, HTTP 200.

---

### Scenario 3 — collective_value formula verification

**Setup**: Live endpoint with non-zero pillar scores (any production instance with tasks).

**Action**:
```python
import requests, json

resp = requests.get("https://api.coherencycoin.com/api/agent/collective-health")
assert resp.status_code == 200
s = resp.json()["scores"]
expected = round(s["coherence"] * s["resonance"] * s["flow"] * (1 - s["friction"]), 4)
actual = s["collective_value"]
assert abs(expected - actual) < 0.0002, f"Formula mismatch: expected {expected}, got {actual}"
print("Formula verified:", actual)
```

**Expected result**: Script exits without assertion error and prints `Formula verified: <value>`.

**Edge**: If `friction = 1.0`, then `collective_value` must equal `0.0` regardless of
other pillar values (zero absorber via `1 - 1.0 = 0`).

---

### Scenario 4 — Neutral scores on empty/fresh system (unit-level)

**Setup**: Unit test that mocks `agent_service.list_tasks` to return `([], 0, None)` and
`friction_service.load_events` to return `([], 0)`.

**Action**:
```python
from unittest.mock import patch
from app.services.collective_health_service import get_collective_health

with patch("app.services.agent_service.list_tasks", return_value=([], 0, None)), \
     patch("app.services.metrics_service.get_aggregates", return_value={}), \
     patch("app.services.friction_service.load_events", return_value=([], 0)), \
     patch("app.services.friction_service.summarize", return_value={}), \
     patch("app.services.friction_service.friction_entry_points", return_value={}), \
     patch("app.services.runtime_service.list_events", return_value=[]):
    result = get_collective_health(window_days=7)

assert result["scores"]["coherence"] == 0.5, result["scores"]
assert result["scores"]["resonance"] == 0.5, result["scores"]
assert result["scores"]["flow"] == 0.5, result["scores"]
print("Neutral defaults confirmed")
```

**Expected result**: All three goodness pillar scores equal 0.5. `collective_value` equals
`0.5 * 0.5 * 0.5 * (1 - 0.0)` = 0.125 (friction defaults to 0.0 when no events exist).

**Edge**: `window_days=1` (minimum) must not raise an exception on an empty system.

---

### Scenario 5 — top_opportunities sorting and field completeness

**Setup**: Live endpoint responding with at least one low-scoring pillar signal.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/agent/collective-health | python3 - <<'PY'
import sys, json

data = json.load(sys.stdin)
ops = data.get("top_opportunities", [])

assert isinstance(ops, list), f"top_opportunities must be list, got {type(ops)}"
assert len(ops) <= 5, f"must be at most 5, got {len(ops)}"

for item in ops:
    for key in ("pillar", "signal", "action", "impact_estimate"):
        assert key in item, f"missing key '{key}' in {item}"
    assert item["pillar"] in ("coherence", "resonance", "flow", "friction"), item
    assert isinstance(item["impact_estimate"], (int, float)), item

impacts = [o["impact_estimate"] for o in ops]
assert impacts == sorted(impacts, reverse=True), f"not sorted desc: {impacts}"

print(f"OK — {len(ops)} opportunities, sorted correctly")
PY
```

**Expected result**: Prints `OK — N opportunities, sorted correctly` (N ≤ 5).

**Edge**: When all pillar signals are above threshold, `top_opportunities` is `[]` (empty
list, not `null`). The script must not raise an `AssertionError` on an empty list.

---

## Verification

```bash
cd api && pytest -q tests/test_agent_collective_health_api.py

# Quick live check (requires API to be running or reachable)
cd api && python3 - <<'PY'
import asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app

async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/collective-health")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "scores" in body and "collective_value" in body["scores"]
        cv = body["scores"]["collective_value"]
        assert 0.0 <= cv <= 1.0, f"Out of range: {cv}"
        print("PASS collective_value =", cv)

asyncio.run(main())
PY
```

---

## Out of Scope

- Streaming or WebSocket push for real-time score updates.
- Per-contributor health breakdowns.
- Historical time-series storage of collective health snapshots.
- Alert or webhook trigger when score drops below a threshold.
- A web dashboard panel for collective health trends.
- New database tables for collective metrics history.

---

## Risks and Assumptions

- **Risk**: `agent_service.list_tasks(limit=5000)` pulls a large result set on each call.
  At high task volume this may become slow. Mitigation: add incremental window-based query
  in a follow-up if p95 latency breaches 2 s.
- **Risk**: `friction_service.load_events()` reads from a file or DB; if the persistence
  layer is unavailable, friction score defaults to 0.0 (no friction observed). This masks
  data unavailability as a healthy state. Mitigation: log a warning when fallback is used.
- **Assumption**: All four pillar sub-services (`agent_service`, `friction_service`,
  `metrics_service`, `runtime_service`) are co-located in the same API process.
- **Assumption**: `window_days` clamping at max 30 is sufficient to prevent runaway queries
  at current task volumes.
- **Assumption**: Scores are initial heuristics; formulas should be tuned based on real
  usage feedback before hardening them in downstream gates.

---

## Known Gaps and Follow-up Tasks

- **Gap**: No Pydantic response model on the collective-health route. The `dict` return
  bypasses boundary validation. Follow-up: wrap in `CollectiveHealthResponse` Pydantic
  model in a separate spec.
- **Gap**: No caching layer. High-frequency polling recomputes from scratch each call.
  Follow-up: add a short-TTL in-memory cache (e.g., 60 s).
- **Gap**: `collective_value` of 0.0 when any single pillar is 0.0 may be too aggressive.
  The neutral-at-zero-tasks guard mitigates this for most cases, but additive aggregation
  may be preferable in some deployment contexts. Capture in backlog for future scoring
  strategy spec.

---

## Failure/Retry Reflection

- **Failure mode**: `collective_health_service` import fails (missing dependency or
  circular import)
- **Blind spot**: The service imports four other services; any sub-service error propagates
  silently into the ImportError fallback path, making all scores 0.0 without identifying
  which sub-service caused the failure.
- **Next action**: Check the logged `ImportError` message; identify the failing sub-service
  by its module path.

---

## Decision Gates

- None at spec time. The feature is implemented in `collective_health_service.py`; this
  spec formalises the contract and drives acceptance tests.
