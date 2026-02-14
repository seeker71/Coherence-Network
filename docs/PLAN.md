# Coherence Network — Plan

## Objective

Deliver a reliable, continuously improving OSS intelligence platform by prioritizing:

1. graph/API correctness,
2. spec coverage,
3. pipeline throughput and recovery,
4. operational clarity for maintainers.

## In-Scope Work

### Product Delivery
- Project indexing and graph expansion
- Search and project/coherence endpoints
- Import stack analysis workflows
- Web/API integration for current shipped capabilities
- Public deployment maintenance (Railway API + Vercel web)

### Pipeline Delivery
- Automated task routing and execution
- Monitoring and attention heuristics
- Retry/heal workflows
- Status reporting and runbook quality

### Quality Guardrails
- Spec-first implementation
- Test-first behavior
- CI health and deterministic checks
- Minimal, scoped diffs

## Current Milestone Track

- **Milestone A: Core Stability**
  - keep API + indexers stable
  - maintain production deployment health (Railway + Vercel)
  - reduce repeated pipeline failures
  - keep status and coverage docs accurate

- **Milestone B: Execution Efficiency**
  - improve success rate and cycle time
  - improve monitor signal quality
  - reduce manual intervention per overnight run

- **Milestone C: Data/Intelligence Depth**
  - extend graph data quality
  - improve coherence signal quality
  - tighten test/spec mapping for new capabilities

## Prioritization Rules

When tradeoffs appear, prioritize in this order:

1. correctness and testability,
2. pipeline reliability,
3. observability and maintainability,
4. new feature breadth.

## Operating Principles

- Keep changes small and verifiable.
- Prefer explicit specs over implied behavior.
- Do not modify tests to force pass conditions.
- Keep documentation aligned with shipped behavior.

## Primary References

- [STATUS](STATUS.md)
- [EXECUTION-PLAN](EXECUTION-PLAN.md)
- [SPEC-COVERAGE](SPEC-COVERAGE.md)
- [SPEC-TRACKING](SPEC-TRACKING.md)
