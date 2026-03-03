# Spec: Sprint 2 — Coherence API

## Purpose

Per docs/PLAN.md Sprint 2: coherence scores on project pages. Expose coherence score via API so web can show `/project/npm/react` with score. Builds on spec 018 (algorithm) and 008 (graph data).

## Requirements

- [x] `GET /api/projects/{ecosystem}/{name}/coherence` returns coherence score and components
- [x] Score 0.0–1.0; components per spec 018 (real: downstream_impact, dependency_health; 0.5 when no data)
- [x] 404 if project not found (same as GET project)
- [x] Uses GraphStore; no Neo4j dependency for MVP
- [x] Optional `components_with_data` (0–8) so consumers can show "preliminary" when most components are stubbed

## API Contract

### `GET /api/projects/{ecosystem}/{name}/coherence`

**Response 200**
```json
{
  "score": 0.72,
  "components_with_data": 2,
  "components": {
    "contributor_diversity": 0.8,
    "dependency_health": 0.7,
    "activity_cadence": 0.65,
    "documentation_quality": 0.5,
    "community_responsiveness": 0.5,
    "funding_sustainability": 0.5,
    "security_posture": 0.5,
    "downstream_impact": 0.9
  }
}
```

**Response 404** — Project not found

## Data Model

```yaml
CoherenceResponse:
  score: float (0.0–1.0)
  components_with_data: int (0–8)  # count of components with real data; rest are 0.5 stub
  components: dict[str, float]  # 8 components from spec 018
```

## Data confidence

Only 2 of 8 components currently use real data: `downstream_impact`, `dependency_health`. The other 6 return 0.5 (neutral) until Contributor/Organization data and GitHub API integration exist (see PLAN.md gaps). Consumers should use `components_with_data` to show a "preliminary" or "based on N of 8 signals" indicator when appropriate.

## Files to Create/Modify

- `api/app/routers/projects.py` — add /coherence route
- `api/app/services/coherence_service.py` — score computation (stub or real)
- `api/app/models/coherence.py` — Pydantic models

## Acceptance Tests

- GET /api/projects/npm/react/coherence returns 200 with score and components
- GET /api/projects/npm/nonexistent/coherence returns 404
- Score and components in valid ranges [0.0, 1.0]

## Out of Scope

- Full algorithm implementation (can stub with placeholder values)
- PyPI coherence
- Web UI (separate spec)

## See also

- [018-coherence-algorithm-spec.md](018-coherence-algorithm-spec.md) — algorithm definition
- [008-sprint-1-graph-foundation.md](008-sprint-1-graph-foundation.md) — graph data

## Decision Gates

- Weight values require human approval (spec 018)
- Stub vs real computation: start stub, iterate when data available
