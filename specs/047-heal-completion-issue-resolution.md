# Spec: Heal Completion → Issue Resolution

## Purpose

When a heal task completes and the related monitor condition clears on the next check, the pipeline must record that resolution for effectiveness measurement and, optionally, persist the resolution in monitor_issues.json so operators and APIs can see which issues were resolved (and whether a heal task was attributed). This closes the loop between "monitor created heal" and "condition cleared" and supports heal_resolved_count and auditability.

## Requirements

- [ ] When the monitor runs and a previously reported condition is no longer present, the monitor **records a resolution** (existing behavior): append to `api/logs/monitor_resolutions.jsonl` with `condition`, `resolved_at` (ISO8601 UTC), and when the previous issue had a `heal_task_id`, include `heal_task_id` in the resolution record so effectiveness can attribute to heal.
- [ ] When recording resolution for a condition that had an associated `heal_task_id` on the previous run, the monitor **must** pass that `heal_task_id` into the resolution record (already implemented; spec makes this contract explicit).
- [ ] **Optional auto-resolve in monitor_issues.json**: When configured (e.g. env `MONITOR_PERSIST_RESOLVED=1` or equivalent), when a condition clears the monitor persists the resolution in `monitor_issues.json` by appending a resolved entry (condition, issue id if available, resolved_at, heal_task_id if any) to a `resolved` array in that file; the array is capped (e.g. last 50 entries) to avoid unbounded growth. GET /api/agent/monitor-issues continues to return the file content, so the response may include `resolved` when present.
- [ ] Open issues in `monitor_issues.json` remain the current list of issues (conditions currently firing). Resolved entries are for audit/recent-resolution visibility only and do not change the semantics of `issues` or `resolved_since_last`.

## API Contract (if applicable)

### `GET /api/agent/monitor-issues`

**Response 200** — Unchanged required shape; optional field added when optional persistence is enabled:

- `issues`: array of open issues (unchanged)
- `last_check`: string (ISO8601) or null (unchanged)
- `history`: array (unchanged, monitor-defined)
- `resolved_since_last`: array of condition strings cleared this run (already produced by monitor for status report; may be exposed in response if present in file)
- `resolved`: (optional) array of resolution records, newest last, capped (e.g. 50). Each entry: `condition`, `resolved_at` (ISO8601 UTC), optional `heal_task_id`, optional `issue_id`

When `monitor_issues.json` is missing or invalid, response remains `{ "issues": [], "last_check": null }` (no `resolved` required).

### Resolution record (monitor_resolutions.jsonl)

Each line is JSON: `{ "condition": string, "resolved_at": string (ISO8601 UTC), "heal_task_id": string (optional) }`. No change to existing format.

## Data Model (if applicable)

**monitor_issues.json** (persisted by monitor):

```yaml
issues: array of Issue
last_check: string | null
history: array of { at, condition, severity }
resolved_since_last: array of string   # condition names cleared this run
resolved: array of { condition, resolved_at, heal_task_id?, issue_id? }  # optional; capped
```

**Issue** (unchanged): id, condition, severity, priority, message, suggested_action, created_at, resolved_at (null when open), heal_task_id (optional).

## Files to Create/Modify

- `api/scripts/monitor_pipeline.py` — Ensure resolution always includes heal_task_id from previous issue when condition clears; add optional persistence of resolved entries to monitor_issues.json (resolved array, capped) when MONITOR_PERSIST_RESOLVED=1 or equivalent.
- `docs/PIPELINE-MONITORING-AUTOMATED.md` — Document resolution recording and optional persist-resolved behavior and response shape.
- Optionally `api/app/routers/agent.py` — No change required if file is returned as-is; response may include `resolved` when present in file.

## Acceptance Tests

- When monitor runs and a condition that was present (with heal_task_id) is no longer present: a resolution record is appended to monitor_resolutions.jsonl with that condition, resolved_at, and heal_task_id. (Existing behavior; test can live in api/tests/test_agent.py or a dedicated test for monitor resolution.)
- When optional persist-resolved is enabled and a condition clears: monitor_issues.json contains a `resolved` array with an entry for that condition including resolved_at and heal_task_id if applicable; array is capped (e.g. 50).
- GET /api/agent/monitor-issues when file has `resolved`: response includes `resolved` array (or at least does not strip it). GET when file has no `resolved`: response unchanged (issues, last_check, history as today).

See `api/tests/test_agent.py` (and any new tests for monitor resolution / optional persist) — all must pass. Do not modify tests to make implementation pass; fix the implementation.

## Out of Scope

- Changing how heal tasks are created or how conditions are detected.
- Webhook or callback when a heal task completes (resolution is detected on next monitor check only).
- Changing heal_resolved_count formula or effectiveness response shape beyond exposing optional `resolved` in monitor-issues response.

## Decision Gates (if any)

- Adding a new env var (e.g. MONITOR_PERSIST_RESOLVED) is a config change; document in RUNBOOK or PIPELINE-MONITORING-AUTOMATED. If the project requires human approval for new env vars, escalate per CLAUDE.md.

## See also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — Item 2 (this spec); Item 5 (heal task effectiveness tracking / heal_resolved_count).
- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — GET /api/agent/monitor-issues, GET /api/agent/effectiveness.
- [docs/PIPELINE-MONITORING-AUTOMATED.md](../docs/PIPELINE-MONITORING-AUTOMATED.md) — Monitor flow, resolution tracking, issue shape.
