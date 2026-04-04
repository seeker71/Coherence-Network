---
idea_id: pipeline-optimization
title: Pipeline Optimization
stage: implementing
work_type: feature
specs:
  - [074-tool-failure-awareness](../specs/074-tool-failure-awareness.md)
  - [112-prompt-ab-roi-measurement](../specs/112-prompt-ab-roi-measurement.md)
  - [113-provider-usage-coalescing-timeout-resilience](../specs/113-provider-usage-coalescing-timeout-resilience.md)
  - [127-cross-task-outcome-correlation](../specs/127-cross-task-outcome-correlation.md)
  - [135-provider-health-alerting](../specs/135-provider-health-alerting.md)
  - [runner-auto-contribution](../specs/runner-auto-contribution.md)
---

# Pipeline Optimization

Make the pipeline cheaper, faster, and smarter over time. Every CC spent on execution should produce maximum value. The optimization layer learns from every task -- which providers succeed at which task types, which prompts produce better code, which tools cost CC without producing value -- and feeds those learnings back into routing and scheduling decisions.

## Problem

The pipeline executes tasks but does not learn from them. The same prompt that fails 80% of the time on implementation tasks keeps getting used. A provider with degraded performance keeps receiving tasks until someone manually notices. Tools that cost CC without producing value (failed linters, broken formatters) keep running. Without feedback loops, the pipeline burns CC at a constant rate instead of improving.

## Key Capabilities

- **Tool failure awareness**: Detect when tools cost CC without producing value. If a linter runs on every task but fails on 90% of them, surface that as a friction event. Track tool success rate per task type and flag tools that are net-negative.
- **Prompt A/B testing**: Measure ROI of different prompts, skills, and models for the same task type. Run variant A and variant B on similar tasks, compare CC cost and outcome quality. Automatically promote winners and demote losers.
- **Provider usage coalescing**: Batch similar requests to the same provider to reduce overhead. Timeout resilience across providers -- if one provider is slow, redistribute its queue to healthy providers without losing tasks.
- **Cross-task outcome correlation**: Find patterns across tasks. Which provider/model/prompt combinations succeed for which task types? If Claude-sonnet excels at spec tasks but struggles with implementation, route accordingly. Correlations are derived from real execution data, not assumptions.
- **Provider health alerting**: Detect degraded providers before they waste CC on failures. Track success rate, latency P50/P90/P99, and error rate per provider. When a provider crosses a threshold (e.g., success rate drops below 70%), auto-record a friction event and reduce task routing to that provider.
- **Runner auto-contribution**: Automatically record a CC contribution on task completion. Every completed task generates a `POST /api/contributions/record` with the node ID, task type, idea_id, and CC amount. No manual contribution tracking needed for automated work.

## What Success Looks Like

- Pipeline CC cost per completed task decreases by 20% over 30 days through prompt optimization and provider routing
- Degraded providers are detected within 5 minutes and task routing adjusts automatically
- Tool failure rate is visible on the dashboard and net-negative tools are flagged for removal
- Every completed task has an automatic contribution record -- zero manual tracking for agent work

## Absorbed Ideas

- **runner-auto-contribution**: Auto-POST to `/api/contributions/record` with node ID, task type, idea_id, CC amount on completion. Ensures agent work is always attributed without requiring the agent to remember to record it.
- **ci-noise-reduction**: Reduced CI runs from ~44/day to ~12/day. Scheduled workflows to daily instead of per-push. Failures-only notifications instead of all-runs. This was a concrete optimization that saved CI minutes and reduced notification fatigue.
