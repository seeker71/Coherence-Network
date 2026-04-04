---
idea_id: agent-pipeline
title: Agent Pipeline
stage: implementing
work_type: feature
specs:
  - 002-agent-orchestration-api
  - 005-project-manager-pipeline
  - 139-coherence-network-agent-pipeline
  - 026-pipeline-observability-and-auto-review
  - 032-attention-heuristics-pipeline-status
  - 159-split-review-deploy-verify-phases
---

# Agent Pipeline

The execution engine that turns ideas into working software.

## What It Does

- Orchestrates agent tasks: submit, route to provider, track status
- Project manager pipeline runs spec → implement → test → review cycles
- Pipeline observability exposes execution time, success rate, usage
- Attention heuristics surface stuck, failing, or low-success tasks
- Split phases: code-review → deploy → verify-production

## API

- `POST /api/agent/tasks` — submit task
- `GET /api/agent/tasks` — list tasks with status
- `GET /api/agent/pipeline-status` — pipeline health with attention flags
- `GET /api/agent/metrics` — execution metrics

## Why It Matters

Ideas don't build themselves. The agent pipeline is the labor force that executes spec → code → test → deploy.
