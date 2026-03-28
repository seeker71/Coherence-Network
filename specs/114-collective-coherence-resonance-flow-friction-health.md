# Spec 114: Collective Coherence, Resonance, Flow, and Friction Health

## Summary

Expose system-level progress toward the project's core values by making coherence, resonance, flow, and friction measurable from live operational data. A single `GET /api/agent/collective-health` endpoint returns explicit scores for all four pillars, a composite `collective_value` score, a ranked friction queue, and ranked improvement opportunities — so contributors can steer collective outcomes directly instead of relying on implicit internal heuristics.

---

## Goals

1. **Observability**: Make the four health pillars visible as numeric scores (0.0–1.0) derived from real task/runtime/friction data.
2. **Actionability**: Return a top friction queue and top opportunities list so any contributor can immediately identify the highest-leverage intervention.
3. **Composability**: The `collective_value` metric is a single multiplicative product — a universal signal for overall system health.
4. **Graceful degradation**: Sparse or empty data must never crash the endpoint; it falls back to neutral scores (0.5) rather than 0.

---

## Requirements

- [x] `GET /api/agent/collective-health` returns HTTP 200 with all four pillar scores.
- [x] Scores are computed from live task, friction, and runtime data — no hardcoded or mock values.
- [x] `collective_value = coherence × resonance × flow × (1 − friction)` — all four clamped to [0, 1].
- [x] Each pillar returns diagnostic sub-fields so callers understand the derivation.
- [x] `top_friction_queue` lists up to 5 friction entry points ranked by `signal = energy_loss + 0.5 × event_count`.
- [x] `top_opportunities` lists up to 5 recommended actions ranked by `impact_estimate`.
- [x] Optional `window_days` query param (integer, 1–30, default 7) scopes time-windowed metrics.
- [x] `api/app/services/collective_health_service.py` implements all scoring logic with no direct route dependencies.
- [x] `api/tests/test_agent_collective_health_api.py` proves endpoint shape, score ranges, and friction queue presence.
- [x] Score range contract: all values in `scores` are floats in [0.0, 1.0].

---

## Research Inputs

- `api/app/services/collective_health_service.py` — complete scoring implementation with four pillar functions
- `api/app/routers/agent_issues_routes.py:100` — route registration at `GET /api/agent/collective-health`
- `api/tests/test_agent_collective_health_api.py` — two integration tests proving payload shape and friction queue
- `specs/050-friction-analysis.md` — friction events model and `friction_service` API
- `specs/018-coherence-algorithm-spec.md` — original coherence scoring algorithm context

---

## Task Card

```yaml
goal: Expose collective health scores for coherence, resonance, flow, and friction via a live read-only API endpoint
files_allowed:
  - api/app/services/collective_health_service.py
  - api/app/routers/agent_issues_routes.py
  - api/tests/test_agent_collective_health_api.py
  - specs/114-collective-coherence-resonance-flow-friction-health.md
done_when:
  - GET /api/agent/collective-health returns 200 with all required fields
  - all scores in [0.0, 1.0]
  - collective_value == coherence * resonance * flow * (1 - friction)
  - top_friction_queue and top_opportunities present as lists
  - pytest api/tests/test_agent_collective_health_api.py passes (2 tests)
commands:
  - cd api && pytest -q tests/test_agent_collective_health_api.py
constraints:
  - read-only endpoint — no writes, no schema migrations
  - all scores degrade gracefully to 0.5 when data is sparse
  - window_days clamped to [1, 30]
```

---

## API Contract

### `GET /api/agent/collective-health`

**Query parameters**

| Name          | Type    | Default | Constraints  | Description                              |
|---------------|---------|---------|--------------|------------------------------------------|
| `window_days` | integer | 7       | min=1, max=30 | Look-back window for time-sensitive metrics |

**Response 200** — full payload shape:

```json
{
  "generated_at": "2026-03-27T10:00:00Z",
  "window_days": 7,
  "scores": {
    "coherence": 0.72,
    "resonance": 0.63,
    "flow": 0.58,
    "friction": 0.34,
    "collective_value": 0.2777
  },
  "coherence": {
    "score": 0.72,
    "task_count": 45,
    "target_state_coverage": 0.80,
    "task_card_coverage": 0.71,
    "task_card_quality": 0.68,
    "evidence_coverage": 0.55
  },
  "resonance": {
    "score": 0.63,
    "task_count": 45,
    "tracked_reference_total": 38,
    "reused_reference_count": 14,
    "reference_reuse_ratio": 0.37,
    "completion_event_count": 22,
    "traceable_completion_ratio": 0.59,
    "learning_capture_ratio": 0.67
  },
  "flow": {
    "score": 0.58,
    "task_count": 45,
    "completion_ratio": 0.62,
    "active_flow_ratio": 0.50,
    "throughput_factor": 0.55,
    "latency_factor": 0.80,
    "status_counts": {
      "pending": 8,
      "running": 3,
      "completed": 28,
      "failed": 4,
      "needs_decision": 2
    }
  },
  "friction": {
    "score": 0.34,
    "event_count": 12,
    "open_events": 7,
    "ignored_events": 2,
    "open_density": 0.58,
    "energy_loss": 31.5,
    "issue_count": 3
  },
  "top_friction_queue": [
    {
      "key": "stage:execution",
      "title": "Execution timeout block",
      "severity": "high",
      "signal": 12.5,
      "recommended_action": "Reduce task scope, increase runner timeout"
    }
  ],
  "top_opportunities": [
    {
      "pillar": "coherence",
      "signal": "task_card_coverage",
      "action": "Increase task-card completeness on new tasks.",
      "impact_estimate": 0.29
    }
  ]
}
```

**Response fields**

| Field | Type | Description |
|-------|------|-------------|
| `generated_at` | ISO 8601 string | UTC timestamp of scorecard generation |
| `window_days` | integer | Effective look-back window after clamping |
| `scores` | object | Top-level summary scores for all five indicators |
| `scores.coherence` | float [0,1] | Task specification quality score |
| `scores.resonance` | float [0,1] | Cross-task learning and traceability score |
| `scores.flow` | float [0,1] | Pipeline throughput and latency score |
| `scores.friction` | float [0,1] | Open blockers and energy loss score (higher = worse) |
| `scores.collective_value` | float [0,1] | `coherence × resonance × flow × (1 − friction)` |
| `coherence` | object | Pillar diagnostics; fields listed below |
| `resonance` | object | Pillar diagnostics |
| `flow` | object | Pillar diagnostics including `status_counts` |
| `friction` | object | Pillar diagnostics excluding `top_friction_queue` |
| `top_friction_queue` | array | Up to 5 ranked friction entry points |
| `top_opportunities` | array | Up to 5 ranked improvement actions |

**No 4xx/5xx error responses** — the endpoint is read-only, never mutates state, and degrades gracefully on sparse data. A missing or unreadable friction log returns `friction.score = 0.0`; a zero-task environment returns neutral scores of 0.5 per pillar.

---

## Score Formulas

### Coherence
Measures how precisely tasks are specified — target state contracts, task-card completeness, and success evidence.

```
coherence_score = clamp01(
    0.35 × target_state_coverage
  + 0.30 × task_card_quality
  + 0.20 × task_card_coverage
  + 0.15 × evidence_coverage
)
# Falls back to 0.5 when task_count == 0
```

### Resonance
Measures how well outcomes are traceable and reused across tasks — shared spec/idea references, traceable completion events, and failure learning capture.

```
resonance_score = clamp01(
    0.40 × reference_reuse_ratio
  + 0.35 × traceable_completion_ratio
  + 0.25 × learning_capture_ratio
)
# Falls back to 0.5 when task_count == 0
```

### Flow
Measures pipeline throughput and latency — completion vs. failure ratio, active runner utilization, weekly throughput, and P95 task latency.

```
flow_score = clamp01(
    0.35 × completion_ratio       # completed / (completed + failed)
  + 0.25 × active_flow_ratio      # running / (running + pending + needs_decision)
  + 0.25 × throughput_factor      # clamp01(completed_7d / 20)
  + 0.15 × latency_factor         # 1 - clamp01(p95_seconds / 1800)
)
# Falls back to 0.5 when task_count == 0
```

### Friction
Measures open blockers and energy loss — open event density, energy-loss intensity, and monitor issue count.

```
friction_score = clamp01(
    0.50 × open_density           # open_events / total_events
  + 0.30 × energy_norm            # clamp01((total_energy_loss / max(total_events,1)) / 10)
  + 0.20 × issue_norm             # clamp01(len(monitor_issues) / 10)
)
# Higher is worse — used as (1 - friction) in collective_value
```

### Collective Value
```
collective_value = coherence × resonance × flow × (1 − friction)
```
All four terms are independently clamped to [0.0, 1.0] before multiplication.

---

## Data Model

```yaml
CollectiveHealthResponse:
  generated_at: string (ISO 8601 UTC)
  window_days: integer (1-30)
  scores:
    coherence: float (0.0-1.0)
    resonance: float (0.0-1.0)
    flow: float (0.0-1.0)
    friction: float (0.0-1.0, higher = worse)
    collective_value: float (0.0-1.0)
  coherence:
    score: float
    task_count: integer
    target_state_coverage: float
    task_card_coverage: float
    task_card_quality: float
    evidence_coverage: float
  resonance:
    score: float
    task_count: integer
    tracked_reference_total: integer
    reused_reference_count: integer
    reference_reuse_ratio: float
    completion_event_count: integer
    traceable_completion_ratio: float
    learning_capture_ratio: float
  flow:
    score: float
    task_count: integer
    completion_ratio: float
    active_flow_ratio: float
    throughput_factor: float
    latency_factor: float
    status_counts: map<string, integer>
  friction:
    score: float
    event_count: integer
    open_events: integer
    ignored_events: integer
    open_density: float
    energy_loss: float
    issue_count: integer
  top_friction_queue:
    - key: string
      title: string
      severity: string (info|low|medium|high|critical)
      signal: float (energy_loss + 0.5 * event_count)
      recommended_action: string
  top_opportunities:
    - pillar: string (coherence|resonance|flow|friction)
      signal: string
      action: string
      impact_estimate: float
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `specs/114-collective-coherence-resonance-flow-friction-health.md` | Modify | This spec |
| `api/app/services/collective_health_service.py` | Create/Modify | All scoring logic |
| `api/app/routers/agent_issues_routes.py` | Modify | Register `GET /api/agent/collective-health` route |
| `api/tests/test_agent_collective_health_api.py` | Create/Modify | Integration tests |

---

## Acceptance Tests

```bash
cd api && pytest -q tests/test_agent_collective_health_api.py
```

All two integration tests must pass:
1. `test_collective_health_endpoint_returns_scores_and_components` — verifies full payload shape and collective_value formula.
2. `test_collective_health_friction_queue_surfaces_entry_points` — verifies friction queue is populated from live events.

---

## Verification Scenarios

### Scenario 1 — Full payload shape (happy path)
**Setup**: Production environment with task, friction, and metrics data present.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/agent/collective-health | python3 -c "
import json, sys
p = json.load(sys.stdin)
assert p['scores']['coherence'] is not None
assert 0.0 <= p['scores']['collective_value'] <= 1.0
print('OK', p['scores'])
"
```

**Expected result**: HTTP 200, `scores` object present, all five keys (`coherence`, `resonance`, `flow`, `friction`, `collective_value`) are floats in [0.0, 1.0], `generated_at` is a valid ISO 8601 timestamp, `window_days` equals 7.

**Edge case**: If friction log is missing or empty, `friction.score` must be 0.0 (not an error), and `collective_value` must still be a valid float.

---

### Scenario 2 — collective_value formula verification
**Setup**: Any environment where all four pillar scores are readable.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/agent/collective-health | python3 -c "
import json, sys
p = json.load(sys.stdin)
s = p['scores']
expected = round(s['coherence'] * s['resonance'] * s['flow'] * (1 - s['friction']), 4)
actual = round(s['collective_value'], 4)
assert abs(expected - actual) < 1e-5, f'Formula mismatch: expected {expected}, got {actual}'
print('collective_value formula correct:', actual)
"
```

**Expected result**: The computed `collective_value` matches `coherence × resonance × flow × (1 − friction)` to 4 decimal places.

**Edge case**: If any pillar score is 0.0 (e.g., no tasks), `collective_value` must also be 0.0, not `null` or an error.

---

### Scenario 3 — window_days parameter
**Setup**: Any live environment.

**Action**:
```bash
# Default window
curl -s https://api.coherencycoin.com/api/agent/collective-health | python3 -c "import json,sys; p=json.load(sys.stdin); assert p['window_days']==7, p['window_days']; print('default=7 OK')"

# Custom window
curl -s "https://api.coherencycoin.com/api/agent/collective-health?window_days=14" | python3 -c "import json,sys; p=json.load(sys.stdin); assert p['window_days']==14, p['window_days']; print('window_days=14 OK')"
```

**Expected result**: `window_days` in response matches query param. Default is 7.

**Edge case**: `window_days=0` must clamp to 1 (not fail). `window_days=999` must clamp to 30 (not fail). Both return HTTP 200.

```bash
curl -s "https://api.coherencycoin.com/api/agent/collective-health?window_days=0" | python3 -c "import json,sys; p=json.load(sys.stdin); assert p['window_days']==1, f'expected 1, got {p[\"window_days\"]}'; print('clamp-low OK')"
curl -s "https://api.coherencycoin.com/api/agent/collective-health?window_days=999" | python3 -c "import json,sys; p=json.load(sys.stdin); assert p['window_days']==30, f'expected 30, got {p[\"window_days\"]}'; print('clamp-high OK')"
```

---

### Scenario 4 — friction queue and opportunities present
**Setup**: At least one open friction event exists (production always has some).

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/agent/collective-health | python3 -c "
import json, sys
p = json.load(sys.stdin)
queue = p['top_friction_queue']
opps = p['top_opportunities']
assert isinstance(queue, list), 'top_friction_queue must be a list'
assert isinstance(opps, list), 'top_opportunities must be a list'
if queue:
    row = queue[0]
    assert 'key' in row and 'severity' in row and 'signal' in row, row
    assert float(row['signal']) >= 0.0
print(f'queue={len(queue)}, opportunities={len(opps)}, OK')
"
```

**Expected result**: Both `top_friction_queue` and `top_opportunities` are lists (may be empty). Each entry in `top_friction_queue` has `key`, `title`, `severity`, `signal`, `recommended_action`. Each entry in `top_opportunities` has `pillar`, `signal`, `action`, `impact_estimate`.

**Edge case**: When there are zero friction events and zero failing tasks, both lists return as `[]` — not `null`, not an error.

---

### Scenario 5 — pillar diagnostics fully populated
**Setup**: Production environment.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/agent/collective-health | python3 -c "
import json, sys
p = json.load(sys.stdin)

# coherence diagnostics
for key in ('score','task_count','target_state_coverage','task_card_coverage','task_card_quality','evidence_coverage'):
    assert key in p['coherence'], f'missing coherence.{key}'

# resonance diagnostics
for key in ('score','task_count','reference_reuse_ratio','traceable_completion_ratio','learning_capture_ratio'):
    assert key in p['resonance'], f'missing resonance.{key}'

# flow diagnostics
for key in ('score','task_count','completion_ratio','active_flow_ratio','throughput_factor','latency_factor','status_counts'):
    assert key in p['flow'], f'missing flow.{key}'

# friction diagnostics
for key in ('score','event_count','open_events','open_density','energy_loss','issue_count'):
    assert key in p['friction'], f'missing friction.{key}'

print('All pillar diagnostic fields present OK')
"
```

**Expected result**: All diagnostic fields present in each pillar object. No field returns `null` — numeric fields default to 0.0 on missing data, integer fields default to 0.

**Edge case**: `top_friction_queue` must NOT appear inside the `friction` pillar object — it is a top-level field. The friction pillar contains only scalar diagnostics.

---

## Failure and Retry Behavior

- **Friction log missing**: Returns `friction.score = 0.0`, empty `top_friction_queue`. Never raises 500.
- **Monitor issues file missing**: `friction.issue_count = 0`, `monitor_issue_preview = []`.
- **Zero tasks in store**: All pillar scores default to neutral 0.5. `collective_value = 0.5^3 × (1 − 0.0) = 0.125`.
- **Metrics service unavailable**: Flow score computed from task status counts only; throughput/latency factors default to 0.0.
- **Timeout on task store**: Log warning, return minimal response with empty pillar components and scores of 0.5.

---

## Out of Scope

- Persisting daily collective health snapshots for trend analysis (follow-up: add time-series history).
- Web dashboard panel for collective health visualization (follow-up spec).
- WebSocket or SSE live push of health changes.
- New database tables for collective metrics history — all current data is computed from existing stores.

---

## Risks and Assumptions

- **Sparse data risk**: In new environments with <5 tasks, scores default to neutral (0.5). This is intentional — a new system is neither healthy nor unhealthy.
- **Score gaming**: Task-card quality scores are derived from structured metadata. Contributors can inflate scores by filling required fields without substance. Mitigation: DIF verification on task cards in future spec.
- **Friction log growth**: The friction JSONL file is append-only and unbounded. Very large logs will slow `_friction_summary`. Mitigation: future spec to rotate/archive old events.
- **window_days coverage**: The resonance sub-score uses runtime completion events filtered by `window_days`. On a freshly deployed node, this will be 0, pushing resonance toward 0.0 (not neutral 0.5). This is a known limitation.

---

## Known Gaps and Follow-up Tasks

- **Follow-up spec**: Persist daily snapshots of `CollectiveHealthResponse` for longitudinal trend analysis.
- **Follow-up spec**: Add `/web/health` page rendering collective health scores as a dashboard panel.
- **Follow-up spec**: WebSocket endpoint for live collective health streaming.
- **Follow-up task**: Add `window_days` validation to return 422 on non-integer input.

---

## Decision Gates

- No decision gate required: the endpoint is read-only and exposes only pre-existing operational data.
- Score formula weight changes (e.g., adjusting the 0.35/0.30/0.20/0.15 coherence weights) require a `needs-decision` task with explicit rationale.
