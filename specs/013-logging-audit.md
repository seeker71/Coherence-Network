# Spec: Logging Audit

## Purpose

Document and standardize logging across the API and scripts so ops can diagnose issues and logs are safe for production. No secrets, consistent formats, predictable locations.

## Requirements

- [x] All log locations documented in docs/RUNBOOK.md
- [x] No API keys, tokens, or secrets logged (mask or omit)
- [x] Scripts use consistent format: `%(asctime)s %(levelname)s %(message)s` for file handlers
- [x] Log levels: DEBUG for verbose/detail, INFO for normal flow, WARNING for recoverable, ERROR for failures
- [x] Unhandled exceptions: log.exception() in main.py
- [x] Telegram: user_id/chat_id OK; token never logged

## Current Log Files

| Path | Source | Purpose |
|------|--------|---------|
| `api/logs/agent_runner.log` | agent_runner.py | Task pickups, completions, HTTP retries |
| `api/logs/telegram.log` | agent.py, telegram_adapter | Webhook events, send results |
| `api/logs/project_manager.log` | project_manager.py | Backlog, phase, task creation |
| `api/logs/overnight_orchestrator.log` | overnight_orchestrator.py | Overnight pipeline |
| `api/logs/task_{id}.log` | Per-task stdout/stderr | Full command output |

## Files to Audit/Modify

- `api/app/main.py` — verify no secrets in logs; exception handler uses log.exception
- `api/app/routers/agent.py` — verify token never logged; direction truncation OK
- `api/app/services/telegram_adapter.py` — verify token never logged
- `api/scripts/agent_runner.py` — verify has_key not value; format consistency
- `api/scripts/project_manager.py` — format consistency
- `api/scripts/overnight_orchestrator.py` — format consistency
- `docs/RUNBOOK.md` — add overnight_orchestrator.log if missing

## Acceptance Tests

- Grep for token/key patterns in logging calls: none expose raw secrets
- All script file handlers use same formatter (or equivalent)
- docs/RUNBOOK.md lists all log files

## Out of Scope

- Structured JSON logging (separate spec if needed)
- Log aggregation or external sinks
- Log rotation (os handles; cleanup_temp covers task logs)

## See also

- [014-deploy-readiness.md](014-deploy-readiness.md) — deploy checklist
- [docs/RUNBOOK.md](../docs/RUNBOOK.md) — log locations

## Decision Gates

None.
