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


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 002, 034

## Task Card

```yaml
goal: Ensure operators can diagnose and recover when the agent pipeline stops making progress or a single task runs indefinitely.
files_allowed:
  - docs/AGENT-DEBUGGING.md
done_when:
  - `docs/AGENT-DEBUGGING.md` has a Pipeline stuck section (or equivalent heading) that includes:
  - `docs/AGENT-DEBUGGING.md` has a Task hangs section (or equivalent heading) that includes:
  - Content is specific and actionable (problem → check → fix). Commands and endpoints are concrete (paths, curl examples...
  - Only `docs/AGENT-DEBUGGING.md` is modified; no new files.
commands:
  - python3 -m pytest api/tests/test_agent_run_state_api.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

N/A — documentation only.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

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

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add distributed locking for multi-worker pipelines.


## Verification

```bash
python3 -m pytest api/tests/test_agent_run_state_api.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
