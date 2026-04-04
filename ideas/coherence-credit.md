---
idea_id: coherence-credit
title: Coherence Credit (CC)
stage: implementing
work_type: feature
pillar: economics
specs:
  - [119-coherence-credit-internal-currency](../specs/119-coherence-credit-internal-currency.md)
  - [124-cc-economics-and-value-coherence](../specs/124-cc-economics-and-value-coherence.md)
  - [114-mvp-cost-and-acceptance-proof](../specs/114-mvp-cost-and-acceptance-proof.md)
  - [115-grounded-cost-value-measurement](../specs/115-grounded-cost-value-measurement.md)
  - [116-grounded-idea-portfolio-metrics](../specs/116-grounded-idea-portfolio-metrics.md)
  - [126-portfolio-governance-effectiveness](../specs/126-portfolio-governance-effectiveness.md)
---

# Coherence Credit (CC)

CC is the internal unit of account for Coherence Network. Every action has a cost denominated in CC, every outcome has a value denominated in CC, and the delta between them is the signal that drives prioritization. CC is not speculative currency -- it tracks real value created by real work.

## Problem

Without a common unit of account, you cannot compare the cost of writing a spec to the value of deploying a feature. Teams argue about priorities based on gut feeling because there is no shared measure of "worth doing." Estimated costs are fiction -- actual costs diverge wildly, and nobody tracks the delta.

## Key Capabilities

- **CC as currency**: Earned by contributing (writing specs, implementing features, reviewing code), spent by staking on ideas you believe should be built. The earn/spend cycle creates a market signal for what work the community values.
- **MVP cost tracking**: Actual vs estimated cost with acceptance proof. Every idea has an estimated CC cost at spec time and an actual CC cost at completion. The ratio between them feeds back into better future estimates.
- **Grounded cost/value measurement**: Real execution data (provider billing, runtime telemetry, friction events) feeds A/B ROI comparisons. Two approaches to the same problem can be compared on actual CC cost and actual value delivered, not projections.
- **Grounded portfolio metrics**: Portfolio health dashboard showing actual vs potential value across all ideas. Which ideas are over-invested? Which are under-invested relative to their ROI? The dashboard answers these questions with real data.
- **Portfolio governance**: Measure whether governance decisions (prioritization changes, resource allocation shifts) actually improve outcomes. If the governance committee re-prioritized last week, did total CC ROI improve this week?
- **CC economics and value coherence**: CC supply tracks real value created, not speculation. There is no CC inflation -- new CC is minted only when measurable value is created (feature deployed, friction reduced, adoption increased).

## What Success Looks Like

- Every idea has CC-denominated cost estimates that are within 2x of actual cost by the third iteration
- Portfolio dashboard shows real-time CC ROI for every active idea
- Governance decisions show measurable improvement in aggregate CC ROI within 2 weeks
- CC supply correlates with platform value metrics (ideas completed, friction reduced, adoption)

## Absorbed Ideas

- **market-driven-exchange-rates**: Replace hardcoded 1 ETH = 1000 CC with oracle-fed pricing. Fetch live prices from CoinGecko/Chainlink. CC value tracks real contribution value, not crypto speculation. Exchange rates update at most daily to prevent gaming.
