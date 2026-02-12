# Spec: Logging and Audit

## Purpose

Standardize logging across the API and scripts so ops can diagnose issues, logs are safe for production (no secrets), and log volume is bounded via levels and rotation. Optional structured (JSON) format enables future aggregation and querying.

## Requirements

- [ ] All log locations documented in docs/RUNBOOK.md
- [ ] No API keys, tokens, or secrets logged (mask or omit)
- [ ] Log levels: DEBUG (verbose/detail), INFO (normal flow), WARNING (recoverable), ERROR (failures); level configurable via env (e.g. LOG_LEVEL) for API; scripts use --verbose for DEBUG
- [ ] Scripts use consistent format: `%(asctime)s %(levelname)s %(message)s` for file handlers
- [ ] Unhandled exceptions: log.exception() in main.py
- [ ] Telegram: user_id/chat_id OK; token never logged
- [ ] Structured logging: API may optionally emit JSON log lines (one JSON object per line) when LOG_FORMAT=json; format defined below
- [ ] Log rotation: file handlers use RotatingFileHandler with documented maxBytes and backupCount; task logs (task_{id}.log) remain under cleanup_temp/scripts

## Log Levels (usage)

| Level    | Use for |
|----------|--------|
| DEBUG    | Verbose detail, request IDs, cache hits, external call details |
| INFO     | Normal flow: request completion, task start/end, phase transitions |
| WARNING  | Recoverable: retries, missing optional config, 4xx from external API |
| ERROR    | Failures: unhandled exceptions, 5xx, task failure after retries |

## Structured log format (optional, LOG_FORMAT=json)

When enabled, each log line is a single JSON object (no pretty-print). Required fields; extra fields allowed.

```yaml
# Per-line JSON (one object per line)
ts:        ISO 8601 UTC
level:     "debug" | "info" | "warning" | "error"
message:   string
logger:    string   # e.g. "app.routers.agent"
```

Optional common fields: `request_id`, `path`, `method`, `status_code`, `duration_ms`, `task_id`, `error` (exception type or message). No `token`, `api_key`, `password`, or equivalent.

Example line:

```json
{"ts":"2025-02-12T10:00:00.000Z","level":"info","message":"task completed","logger":"app.routers.agent","task_id":"abc-123","duration_ms":1500}
```

## Log rotation

- **Application log files** (e.g. agent_runner.log, project_manager.log, telegram.log, overnight_orchestrator.log): use `logging.handlers.RotatingFileHandler` with:
  - `maxBytes`: 5 * 2^20 (5 MiB) per file
  - `backupCount`: 3 (keep current + 3 rotated)
- **Task logs** (task_{id}.log): remain under existing cleanup (cleanup_temp.py / scripts); no rotation required for ephemeral files.
- **Uvicorn/stdout**: not under this spec; process manager or OS handles.

## Current log files

| Path | Source | Purpose |
|------|--------|---------|
| `api/logs/agent_runner.log` | agent_runner.py | Task pickups, completions, HTTP retries |
| `api/logs/telegram.log` | agent.py, telegram_adapter | Webhook events, send results |
| `api/logs/project_manager.log` | project_manager.py | Backlog, phase, task creation |
| `api/logs/overnight_orchestrator.log` | overnight_orchestrator.py | Overnight pipeline |
| `api/logs/task_{id}.log` | Per-task stdout/stderr | Full command output |

## Files to create/modify

- `api/app/main.py` — optional JSON handler when LOG_FORMAT=json; RotatingFileHandler for telegram.log; no secrets in logs; exception handler uses log.exception
- `api/app/routers/agent.py` — verify token never logged; direction truncation OK
- `api/app/services/telegram_adapter.py` — verify token never logged
- `api/scripts/agent_runner.py` — RotatingFileHandler; has_key not value; format consistency
- `api/scripts/project_manager.py` — RotatingFileHandler; format consistency
- `api/scripts/overnight_orchestrator.py` — RotatingFileHandler; format consistency
- `docs/RUNBOOK.md` — log locations and rotation policy (file size/count)

## Acceptance tests

- Grep for token/key patterns in logging calls: none expose raw secrets
- All script file handlers use RotatingFileHandler with maxBytes=5MiB, backupCount=3 (or equivalent)
- Script file formatter: `%(asctime)s %(levelname)s %(message)s` (or equivalent)
- docs/RUNBOOK.md lists all log files and states rotation (5 MiB, 3 backups)
- If LOG_FORMAT=json: API file/stream emits one JSON object per line with ts, level, message, logger

## Out of scope

- Log aggregation or external sinks (e.g. Loki, CloudWatch)
- Changing Uvicorn access log format
- Audit trail persistence (separate audit spec if needed)

## See also

- [014-deploy-readiness.md](014-deploy-readiness.md) — deploy checklist
- [docs/RUNBOOK.md](../docs/RUNBOOK.md) — log locations

## Decision gates

- Adding a new pip dependency solely for JSON logging: needs-decision (stdlib only preferred).
