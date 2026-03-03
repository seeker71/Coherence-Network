# Spec: Expand docs/AGENT-DEBUGGING.md — Pipeline stuck and Task hangs

## Purpose

Ensure operators can diagnose and recover when the agent pipeline stops making progress or a single task runs indefinitely. The doc must have dedicated, actionable sections for "Pipeline stuck" and "Task hangs" so debugging is findable and consistent.

## Requirements

- [ ] `docs/AGENT-DEBUGGING.md` has a **Pipeline stuck** section (or equivalent heading) that includes:
  - **Symptom**: No tasks progressing for a sustained period (e.g. 10+ minutes); pipeline-status shows pending but nothing runs.
  - **Checks**: At least (1) agent runner process running, (2) API reachable (e.g. health), (3) runner log for errors, (4) whether a `needs_decision` task is blocking (e.g. `/api/agent/tasks/attention` or Telegram `/attention`).
  - **Fixes**: Restart agent runner (and how); how to unblock on `needs_decision` (Telegram reply or PATCH task with decision).
- [ ] `docs/AGENT-DEBUGGING.md` has a **Task hangs** section (or equivalent heading) that includes:
  - **Symptom**: Task shows "running" for an extended time (e.g. >1 hour); no progress; task log file stops growing.
  - **Checks**: Whether task log is still streaming (e.g. `tail -f`); whether Claude Code / Ollama (or model process) is still alive.
  - **Fixes**: How to kill the stuck process; how to PATCH the task to `failed` with a short output; optional timeout increase (env var); simplifying or splitting the direction.
- [ ] Content is specific and actionable (problem → check → fix). Commands and endpoints are concrete (paths, curl examples, or script names).
- [ ] Only `docs/AGENT-DEBUGGING.md` is modified; no new files.

## API Contract (if applicable)

N/A — documentation only.

## Data Model (if applicable)

N/A.

## Files to Create/Modify

- `docs/AGENT-DEBUGGING.md` — add or expand "Pipeline stuck" and "Task hangs" sections to satisfy the requirements above. Existing numbering (e.g. §6, §7) may be kept; heading names may match or be equivalent.

## Acceptance Tests

- Manual: An operator can find "Pipeline stuck" and "Task hangs" in the doc and follow checks/fixes without guessing.
- Optional: Grep or checklist that the file contains subsection-level content for symptom, checks, and fixes in both sections (exact wording not asserted).

## Out of Scope

- Changing agent runner, API, or timeout implementation.
- Adding new scripts or endpoints; only documenting existing ones.
- Other sections of AGENT-DEBUGGING.md unless needed to avoid duplication or to cross-link.

## See also

- [034 Ops Runbook](034-ops-runbook.md) — pipeline recovery; RUNBOOK may cross-link to AGENT-DEBUGGING for stuck/hangs.
- [002 Agent Orchestration API](002-agent-orchestration-api.md) — tasks, pipeline-status, PATCH task.
- [TEMPLATE](TEMPLATE.md) — spec format.

## Decision Gates (if any)

None.
