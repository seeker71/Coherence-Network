---
idea_id: coherence-credit
title: Coherence Credit (CC)
stage: implementing
work_type: feature
specs:
  - 119-coherence-credit-internal-currency
  - 124-cc-economics-and-value-coherence
  - 114-mvp-cost-and-acceptance-proof
  - 115-grounded-cost-value-measurement
  - 116-grounded-idea-portfolio-metrics
  - 126-portfolio-governance-effectiveness
---

# Coherence Credit (CC)

The internal unit of account. Every cost and value is denominated in CC.

## What It Does

- CC is the universal unit for cost vectors (compute, infrastructure, human attention) and value vectors (adoption, lineage, friction avoided, revenue)
- Real signals (provider billing, runtime telemetry, friction events) feed into A/B ROI measurement
- Portfolio metrics derived from actual system signals, not hand-typed values
- Governance effectiveness measured and surfaced

## API

- `GET /api/ideas` — shows CC-denominated scores (free_energy, roi_cc, remaining_cost_cc)
- `POST /api/ideas/{id}/stake` — stake CC on an idea
- `GET /api/ideas/health` — portfolio governance effectiveness

## Why It Matters

Without a unit of account, you can't measure whether work is worth doing. CC makes costs and value comparable across all ideas.
