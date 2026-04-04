---
idea_id: agent-pipeline
title: Agent Pipeline
stage: implementing
work_type: feature
pillar: pipeline
specs:
  - [002-agent-orchestration-api](../specs/002-agent-orchestration-api.md)
  - [005-project-manager-pipeline](../specs/005-project-manager-pipeline.md)
  - [139-coherence-network-agent-pipeline](../specs/139-coherence-network-agent-pipeline.md)
  - [026-pipeline-observability-and-auto-review](../specs/026-pipeline-observability-and-auto-review.md)
  - [032-attention-heuristics-pipeline-status](../specs/032-attention-heuristics-pipeline-status.md)
  - [159-split-review-deploy-verify-phases](../specs/159-split-review-deploy-verify-phases.md)
---

# Agent Pipeline

The execution engine that turns ideas into working software through structured spec-driven cycles. Ideas do not build themselves. The agent pipeline is the labor force that picks up specced ideas, routes them to the right provider (Claude, Codex, Gemini, OpenRouter), executes the work, and tracks every step from task submission to production verification.

## Problem

Manual software development does not scale. A single human cannot spec, implement, test, review, deploy, and verify hundreds of ideas. AI agents can, but only if there is a structured pipeline that orchestrates their work, routes tasks to the right provider, tracks execution, and catches failures before they cascade. Without orchestration, agents duplicate work, miss failures, and waste CC.

## Key Capabilities

- **Task orchestration**: Submit tasks with a direction (natural language instruction), route to the appropriate provider based on model routing rules, track execution status through `pending` -> `running` -> `completed`/`failed`. Each provider runs only its own models (Claude runs claude-*, Codex runs gpt-*, etc.).
- **Project manager pipeline**: Automatically runs the full cycle: spec -> implement -> test -> review -> deploy -> verify. Each phase produces artifacts that feed the next. The PM does not write code -- it coordinates the agents that do.
- **Pipeline observability**: Execution time per task, success rate per provider, cost per task in CC, throughput over time. All metrics are queryable via API and visible on the web dashboard. No log inspection required for basic health assessment.
- **Attention heuristics**: Surface stuck runs (no progress for >2x expected duration), repeated failures (same task failed 3+ times), and low success rate (provider below 60% success) without requiring anyone to read logs. The system tells you what needs attention.
- **Split review phases**: The old review phase tried to verify code quality AND production deployment in one step, causing 60-80% failure rates. Now split into three distinct phases: (1) code-review -- does the code meet spec requirements, (2) deploy -- push to production, (3) verify-production -- confirm the deployed code actually works.
- **Phase advancement gating**: A task cannot advance to the next phase until its code reaches `origin/main`. No more phantom completions where the code exists only in a local branch.

## What Success Looks Like

- Every specced idea has a pipeline running within 24 hours of spec approval
- Review phase failure rate drops from 60-80% to under 20% after the split
- Stuck tasks are surfaced within 10 minutes, not discovered hours later
- Provider routing is correct 100% of the time (no cross-provider model assignment)

## Absorbed Ideas

- **split-review-into-phases**: Current review tries to verify code quality AND production deployment in one step, resulting in 60-80% failure rate. Split into: (1) code-review -- static analysis and spec compliance, (2) deploy -- push code to production environment, (3) verify-production -- confirm endpoints respond correctly, data persists, no regressions.
- **pipeline-data-flow-fixes**: Phase auto-advance fires before push confirmation, causing tasks to advance before code is actually on the remote. Push failures are hardcoded as `execution_error` instead of the more specific `push_failed`, making diagnostics harder.
- **validation-requires-production**: Review phase asks the provider to verify production behavior, but the provider cannot deploy. The runner itself must check endpoints after deploy -- providers verify code quality, the runner verifies production state.
