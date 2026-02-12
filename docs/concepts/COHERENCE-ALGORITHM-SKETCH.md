# Coherence Algorithm — Sketch

From docs/PLAN.md. Initial formula for project health 0.0–1.0. Formal spec per specs/018-coherence-algorithm-spec.md.

## Inputs (8 components)

| Input | Description | Source (future) |
|-------|-------------|-----------------|
| contributor_diversity | Bus factor; number of significant contributors | GitHub/deps.dev |
| dependency_health | Are dependencies maintained? | deps.dev |
| activity_cadence | Releases, commit frequency, responsiveness | GitHub |
| documentation_quality | README, docs, examples | Heuristic / LLM |
| community_responsiveness | Issue/PR response time | GitHub |
| funding_sustainability | Sponsors, Open Collective, etc. | GitHub Sponsors, etc. |
| security_posture | Vulns, Dependabot, disclosure | deps.dev, GitHub |
| downstream_impact | How many packages depend on this? | npm/PyPI graph |

Each component yields a 0.0–1.0 sub-score. Aggregation TBD (weighted average or composite).

## Output

- **score**: float 0.0–1.0 per project
- **components**: optional breakdown per input (for dashboards)

Future API: `GET /api/projects/{id}/coherence` → `{"score": 0.72, "components": {...}}`

## Weights Stub

Default: equal weight per component. Override via config when implemented. Actual weight values are a decision gate.

## Pitfalls to Guard Against

- **Balance contribution types** — code, docs, triage should all count; avoid code-only metrics
- **Prevent gaming** — fake commits, artificial inflation; use heuristics (e.g. commit message quality, PR review depth)
- **Balance short-term vs long-term** — recent activity + historical stability; avoid "last 30 days only" or "all-time only"

## Status

Spec only. Implementation in Sprint 2+.
