---
idea_id: pipeline-optimization
title: Pipeline Optimization
stage: implementing
work_type: feature
specs:
  - 074-tool-failure-awareness
  - 112-prompt-ab-roi-measurement
  - 113-provider-usage-coalescing-timeout-resilience
  - 127-cross-task-outcome-correlation
  - 135-provider-health-alerting
  - runner-auto-contribution
---

# Pipeline Optimization

Make execution cheaper, faster, and smarter over time.

## What It Does

- Tool failure awareness: detect and surface expensive failures (cost without gain)
- Prompt A/B ROI measurement: compare prompt variants, select winners
- Provider health alerting: auto-record friction when success rate drops
- Cross-task outcome correlation: link related tasks, track downstream effects
- Provider usage coalescing: unify duplicate usage, improve quota selection
- Runner auto-contribution: completed work automatically recorded as contributions

## API

- `GET /api/agent/metrics` — execution and cost metrics
- `GET /api/providers/usage` — provider usage and health
- `GET /api/providers` — provider list with status

## Why It Matters

Every CC spent on execution should maximize value. Optimization makes the pipeline progressively more efficient.
