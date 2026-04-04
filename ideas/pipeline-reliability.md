---
idea_id: pipeline-reliability
title: Pipeline Reliability
stage: implementing
work_type: feature
specs:
  - 113-failed-task-diagnostics-contract
  - 114-auto-heal-from-diagnostics
  - 125-incident-response-and-self-healing
  - 169-smart-reap
  - 186-data-driven-timeout-resume
  - 047-heal-completion-issue-resolution
  - stale-task-reaper
  - task-deduplication
---

# Pipeline Reliability

Self-healing execution: diagnose failures, auto-heal, resume stuck tasks.

## What It Does

- Every failed task persists error_summary and error_category for debugging
- Auto-generates targeted heal tasks when a task fails
- Smart reap: diagnose stuck tasks, check runner/provider health, extend timeout if slow
- Data-driven timeouts from execution history; resume preserves partial work
- Stale task reaper catches abandoned tasks
- Task deduplication prevents parallel workers from duplicating effort

## API

- `GET /api/agent/diagnostics` — failure diagnostics
- `GET /api/agent/tasks/{id}` — task detail with error info
- `PATCH /api/agent/tasks/{id}` — update task status/output

## Why It Matters

Unreliable execution wastes CC. Self-healing keeps the pipeline running without human intervention.
