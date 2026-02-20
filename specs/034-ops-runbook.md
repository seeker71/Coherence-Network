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

## API Contract (if applicable)

N/A — documentation only.

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
- 024 PyPI Indexing (legacy spec reference; see docs/SPEC-COVERAGE.md) — index_pypi.py usage in RUNBOOK
- [030 Pipeline Full Automation](030-pipeline-full-automation.md) — auto-commit/autonomous behavior in RUNBOOK

## Decision Gates (if any)

None. Doc-only change.
