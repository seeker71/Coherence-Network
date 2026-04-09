---
idea_id: portfolio-governance
title: Portfolio Governance and Measurement
stage: implementing
work_type: feature
pillar: realization
specs:
  - [grounded-cost-value-measurement](../specs/grounded-cost-value-measurement.md)
  - [grounded-idea-portfolio-metrics](../specs/grounded-idea-portfolio-metrics.md)
  - [portfolio-governance-effectiveness](../specs/portfolio-governance-effectiveness.md)
  - [portfolio-governance-health](../specs/portfolio-governance-health.md)
---

# Portfolio Governance and Measurement

Every idea has a cost, a value, and a relationship to the whole. This idea is the signal layer: the scoring framework, coherence metrics, and governance dashboards that let us reason about the portfolio as one coherent thing. Without measurement, prioritization becomes guesswork; with it, we can show which ideas are pulling their weight and which are noise.

## Problem

With 338 ideas in the system, the signal-to-noise ratio collapses unless every idea is measured against a shared rubric. "Prioritization" without grounded scoring is just vibes. We need triadic scoring (tensegrity + coherence + resonance − distance), explanation traces that show WHY something scores what it does, and governance health snapshots that catch stale ideas, value gaps, and throughput regressions before they become structural.

## Key Capabilities

- **Triadic scoring framework**: Every idea scored via T (tensegrity — structural fit), C (coherence — semantic/logical/affective alignment), R (resonance — value/symbolic/narrative affinity), minus D (distance — epistemic/affective distance from belief graph). Weights tunable per portfolio.
- **Grounded cost and value**: Real signals, not estimates. Task CC cost from execution logs, idea value from A/B ROI measurements. Grounded metrics beat speculative ones.
- **Coherence signal depth**: Increase measurement fidelity by replacing keyword matching with semantic/triadic analysis. The signal gets deeper over time as more data accumulates.
- **Explanation traces**: Every score comes with a "why" — which concepts it resonates with, which beliefs it stretches, what distance penalty it pays. No black-box rankings.
- **Governance effectiveness snapshot**: Throughput rate, value gap trend, question-answer rate, stale-idea list. Surfaces whether the portfolio is healthy or stuck.
- **Growth-edge detection**: Surface ideas that stretch the current belief graph without breaking it — the frontier where learning happens.

## What Success Looks Like

- Every curated idea has a triadic score with a visible explanation trace
- Governance snapshot queryable via `GET /api/ideas/portfolio/governance`
- Stale ideas (no activity > 30 days) surfaced automatically
- Value gap shrinks month over month as measurement accumulates

## Absorbed Ideas

- **portfolio-governance**: Unified idea portfolio governance — single view of throughput, value gap, stale ideas, and question-answer rate across the whole portfolio.
- **coherence-signal-depth**: Increase coherence signal depth with real data — replace placeholder scoring with measured triadic components.
- **grant-triadic-scoring**: Triadic scoring equation — wT·T + wC·C + wR·R − wD·D with configurable weights.
- **grant-coherence-triadic**: Triadic coherence score (C) — semantic, logical, and affective alignment components.
- **grant-resonance-triadic**: Triadic resonance score (R) — value, symbolic, and narrative affinity components.
- **grant-tensegrity-score**: Tensegrity score (T) — structural fit without breaking the belief graph.
- **grant-distance-penalty**: Distance penalty (D) — epistemic and affective distance from belief graph.
- **grant-five-scale-scoring**: Five-scale recursive aggregation — statement to worldview.
- **grant-explanation-traces**: Explanation traces — why something resonates, distances, or grows.
- **grant-growth-edge**: Growth-edge detection — surface items that stretch without breaking.
- **grant-human-calibration**: Human judgment calibration — tune weights against real feedback not theory.
- **grant-idea-triadic**: Wire triadic scoring into idea discovery and recommendation.
- **grant-news-triadic**: Wire triadic scoring into news resonance — replace keyword matching.
- **grant-coherence-upgrade**: Upgrade network coherence signal from heuristics to triadic framework.
- **grant-concept-store**: Normalized concept store with source provenance and feature templates.
- **grant-belief-graph**: Belief graph — per-user and per-contributor knowledge structure.
- **grant-source-ingestion**: Grant source document ingestion — extract, normalize, operationalize.
- **validation-quality-gates**: Validation quality gates that separate real value from noise.
