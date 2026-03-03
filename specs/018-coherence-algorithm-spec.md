# Spec: Coherence Algorithm — Formal Spec

## Purpose

Formalize the coherence score algorithm from docs/concepts/COHERENCE-ALGORITHM-SKETCH.md so implementation (Sprint 2+) has clear inputs, outputs, and weights. No implementation in this spec.

## Requirements

- [x] Document inputs: contributor_diversity, dependency_health, activity_cadence, documentation_quality, community_responsiveness, funding_sustainability, security_posture, downstream_impact
- [x] Document output: score 0.0–1.0 per project
- [x] Document pitfalls: gaming prevention, contribution-type balance
- [x] Add weights stub (all equal or placeholder) — actual weights are decision gate

## API Contract (implemented in spec 020)

GET /api/projects/{ecosystem}/{name}/coherence returns `{"score": 0.0–1.0, "components": {...}}`. Path matches project lookup from spec 008.

## Files to Create/Modify

- `docs/concepts/COHERENCE-ALGORITHM-SKETCH.md` — expand with formal input/output, weights stub
- `specs/018-coherence-algorithm-spec.md` — this spec

## Acceptance Tests

- COHERENCE-ALGORITHM-SKETCH.md documents all 8 inputs
- Pitfalls section present
- Weights stub (e.g. "Default: equal weight per component; override via config")

## Out of Scope

- Implementation (Sprint 2)
- Actual weight values (decision gate)
- Data sourcing (deps.dev, GitHub — spec 008)

## See also

- [008-sprint-1-graph-foundation.md](008-sprint-1-graph-foundation.md) — graph data source
- docs/concepts/COHERENCE-ALGORITHM-SKETCH.md

## Decision Gates

- Actual weight values require human approval
- Coherence formula changes require needs-decision
