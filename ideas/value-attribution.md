---
idea_id: value-attribution
title: Value Attribution
stage: implementing
work_type: feature
specs:
  - 048-contributions-api
  - 048-value-lineage-and-payout-attribution
  - 049-distribution-engine
  - 052-assets-api
  - 083-task-claim-tracking-and-roi-dedupe
  - 086-normalize-github-commit-cost-estimation
  - 094-contributor-onboarding-and-governed-change-flow
---

# Value Attribution

Fair credit and payout for everyone who contributes to an idea.

## What It Does

- Tracks contributions (time, effort, code) with automatic coherence scoring
- Creates verifiable value chains: idea → spec → implementation → usage → payout
- Distributes value fairly among contributors weighted by coherence scores
- Manages assets (code, models, content, data) that receive contributions
- Prevents duplicate work via task claim tracking

## API

- `GET /api/contributions` — list contributions
- `POST /api/contributions` — record contribution
- `GET /api/assets` — list assets
- `GET /api/ideas/{id}/progress` — CC staked/spent, contributors

## Why It Matters

Contributors need to know their work is tracked and valued. This is the system that makes "fair attribution" real.
