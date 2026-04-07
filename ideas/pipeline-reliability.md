---
idea_id: pipeline-reliability
title: Pipeline Reliability
stage: implementing
work_type: feature
pillar: pipeline
specs:
  - [failed-task-diagnostics-contract](../specs/failed-task-diagnostics-contract.md)
  - [auto-heal-from-diagnostics](../specs/auto-heal-from-diagnostics.md)
  - [incident-response-and-self-healing](../specs/incident-response-and-self-healing.md)
  - [smart-reap](../specs/smart-reap.md)
  - [data-driven-timeout-resume](../specs/data-driven-timeout-resume.md)
  - [heal-completion-issue-resolution](../specs/heal-completion-issue-resolution.md)
  - [stale-task-reaper](../specs/stale-task-reaper.md)
  - [task-deduplication](../specs/task-deduplication.md)
---

# Pipeline Reliability

Self-healing execution: every failure is diagnosed, partial work is preserved, and stuck tasks are resumed automatically. The pipeline should run indefinitely without human intervention. When something breaks, the system diagnoses the failure, generates a targeted fix, and resumes -- not from scratch, but from the last checkpoint.

## Problem

The pipeline fails in multiple ways: provider timeouts, executor crashes, validation failures, push failures, and unknown errors. Without diagnostics, failed tasks show `error_summary=None` (we found 9 of these). Without deduplication, the system created 799 spec tasks for 147 ideas -- a 5.4x waste of CC. Without smart reaping, the reaper blindly marks tasks as `timed_out` with zero diagnostics, destroying any partial work. Every undiagnosed failure is CC burned with no learning.

## Key Capabilities

- **Failed task diagnostics**: Every failed task persists `error_summary` (human-readable) and `error_category` (one of: `timeout`, `executor_crash`, `provider_error`, `validation_failure`, `push_failed`, `unknown`). No more silent failures -- stderr, exit codes, and timeout info are always captured.
- **Auto-heal from diagnostics**: When a task fails, the system generates a targeted heal task based on the error category. A `validation_failure` gets a fix-and-retry. A `provider_error` gets rerouted to a different provider. A `timeout` gets extended and resumed.
- **Smart reap**: Before marking a task as `timed_out`, the reaper checks if the runner and provider are still alive. If the task is slow but making progress, extend the timeout. If truly stuck, capture partial output before reaping. No more blind timeout kills.
- **Data-driven timeouts**: Replace the fixed 300-second timeout with per-provider, per-task-complexity timeouts derived from historical execution data. A spec task for Claude takes ~45s on average; an implementation task takes ~180s. Timeouts should reflect reality.
- **Task resume**: When a task times out or fails partway, preserve partial work (generated code, test results, error context) so the next attempt starts from the checkpoint, not from scratch. This alone can save 50%+ of wasted CC on retries.
- **Stale task reaper**: Automatically timeout tasks running beyond 2x their expected duration. Catches abandoned tasks where the runner crashed without reporting.
- **Task deduplication**: Before creating a new task, check if a completed or in-progress task already exists for the same idea + phase combination. Prevent the 5.4x waste we observed.
- **Incident response**: Detect cascading failures (3+ tasks failing with the same error category in a 5-minute window) and auto-pause affected pipelines. Resume after the root cause is resolved.

## What Success Looks Like

- Zero tasks with `error_summary=None` -- every failure has a diagnosis
- Task duplication ratio drops from 5.4x to under 1.1x
- Smart reap preserves partial work on 80%+ of timed-out tasks
- Auto-heal resolves 60%+ of failures without human intervention
- Mean time to failure detection drops from hours to under 10 minutes

## Absorbed Ideas

- **smart-reap-diagnose-resume**: Current reaper blindly marks `timed_out` with zero diagnostics. Fix: query runner health, check provider status, extend timeout if slow but alive, capture partial work before killing. The reaper should be the last resort, not the first response.
- **silent-failure-detection**: 9 failed tasks with `error_summary=None`. The runner must capture stderr, exit code, timeout info, and partial output for every failure. Silent failures are the most expensive kind -- you pay the CC cost and learn nothing.
- **task-deduplication**: 799 spec tasks for 147 ideas. Before creating a new task, check completed_tasks table. If a task with the same idea_id and phase already exists and succeeded, skip it. If it failed, check error_category before retrying.
- **data-driven-timeout-resume**: Replace fixed 300s timeouts with measurement-derived ones. Track P50, P90, P99 execution times per provider per task type. Set timeout at 2x P90. Resume from partial work on timeout instead of restarting.
