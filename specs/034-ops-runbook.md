# Spec: Ops Runbook

## Purpose

Provide a single ops reference for Coherence Network so operators can restart the API, find logs, and recover the pipeline without hunting through multiple docs or scripts. Addresses backlog item 14 in spec 006.

## Requirements

- [ ] `docs/RUNBOOK.md` exists and is the canonical ops runbook.
- [ ] **Log locations**: A section (e.g. "Log Locations") lists all API/script log paths in a table with path and purpose. Must stay in sync with spec 013 (logging audit); new log files must be added to RUNBOOK.
- [ ] **API restart**: A section documents how to stop and start the API (e.g. uvicorn, optional start_with_telegram), including port and process cleanup (pkill) when relevant.
- [ ] **Pipeline recovery**: A section describes steps when the pipeline is stuck or the agent runner died: effectiveness check, API restart if needed, restarting overnight pipeline or components (agent_runner, project_manager), and how to unblock needs_decision (Telegram/API).
- [ ] **Autonomous pipeline**: Document `run_autonomous.sh`, auto-commit/auto-push env vars, fatal issues location, and report_fatal.py when applicable (per spec 030).
- [ ] **Pipeline effectiveness**: Document `ensure_effective_pipeline.sh` and when to run it (before/during pipeline).
- [ ] **Key endpoints**: Table of ops-relevant endpoints (health, ready, version, agent/tasks, pipeline-status, metrics, monitor-issues) with purpose.
- [ ] **Indexing**: Document index_npm.py and index_pypi.py usage (target/limit) per specs 008/024.
- [ ] **Check pipeline status**: Document `check_pipeline.py` and `--json` for scripting.
- [ ] **Tests and cleanup**: How to run tests; optional cleanup of old task logs (e.g. find task_*.log, mtime).


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 006, 013, 024, 030

## Task Card

```yaml
goal: Provide a single ops reference for Coherence Network so operators can restart the API, find logs, and recover the pipeline without hunting through multiple docs or scripts.
files_allowed:
  - docs/RUNBOOK.md
done_when:
  - `docs/RUNBOOK.md` exists and is the canonical ops runbook.
  - Log locations: A section (e.g. "Log Locations") lists all API/script log paths in a table with path and purpose. Must...
  - API restart: A section documents how to stop and start the API (e.g. uvicorn, optional start_with_telegram), includin...
  - Pipeline recovery: A section describes steps when the pipeline is stuck or the agent runner died: effectiveness check...
  - Autonomous pipeline: Document `run_autonomous.sh`, auto-commit/auto-push env vars, fatal issues location, and report_...
commands:
  - python3 -m pytest api/tests/test_runbook.py -x -v
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

- `docs/RUNBOOK.md` — create or expand to satisfy all requirements above. Only this file is in scope for this spec.

## Acceptance Tests

- Manual or automated check that `docs/RUNBOOK.md` exists.
- Check that the file contains section headings (or equivalent) for: Log Locations, API Restart, Pipeline Recovery, and at least one of (Autonomous Pipeline / Pipeline Effectiveness / Key Endpoints). Exact heading text may vary; intent is that an operator can find each topic quickly.

## Out of Scope

- Implementing or changing scripts, API endpoints, or log rotation; only documenting them.
- RUNBOOK content that duplicates full reference docs (e.g. full API reference); keep runbook concise.

## See also

- [006 Overnight Backlog](006-overnight-backlog.md) — item 14 requested this runbook
- [013 Logging Audit](013-logging-audit.md) — log locations and rotation; RUNBOOK must list all log files
- [024 PyPI Indexing](024-pypi-indexing.md) — index_pypi.py usage in RUNBOOK
- [030 Pipeline Full Automation](030-pipeline-full-automation.md) — auto-commit/autonomous behavior in RUNBOOK

## Decision Gates (if any)

None. Doc-only change.

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
python3 -m pytest api/tests/test_runbook.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
