# Spec: Agent-Telegram Decision Loop & Progress Tracking

## Purpose

Close the loop between agent tasks and human: when a task needs a decision, the user can reply via Telegram and the system records the decision for the agent to act on. Add progress tracking and an `/attention` command so the user knows what requires action and how far each task has progressed.

Extends spec 002 (Agent Orchestration API).

## Requirements

- [x] Telegram `/reply {task_id} {decision}` — record decision on task, update status to running (or completed if decision is terminal)
- [x] Telegram `/attention` — list only tasks with status needs_decision or failed
- [x] Agent task: add `progress_pct` (0–100), `current_step`, `decision_prompt` (optional), `decision` (user reply)
- [x] PATCH /api/agent/tasks/{id}: accept `progress_pct`, `current_step`, `decision` in request body
- [x] Agent runner script: polls pending tasks, runs command, PATCHes progress, blocks on needs_decision until decision present, then continues or stops
- [x] Telegram alert for needs_decision includes `decision_prompt` (what to decide) when provided
- [x] **Telegram flow complete:** Inbound (webhook → record_webhook → parse_command → send_reply → record_send) and diagnostics endpoint implemented; verified by diagnostic test (see Acceptance Tests).
- [x] **Diagnostic test:** `test_telegram_flow_diagnostic` in `api/tests/test_agent.py`: POST webhook with a command, GET diagnostics; assert `config`, `webhook_events`, `send_results` present and `webhook_events` updated (and optionally that `send_results` was appended when reply path is exercised). Uses `telegram_diagnostics.clear()` for isolation. No real bot required.

## API Contract

### `PATCH /api/agent/tasks/{task_id}` (extended)

**Request** (add optional fields)
```json
{
  "status": "needs_decision",
  "output": "Tests failed. Proceed with fix?",
  "progress_pct": 60,
  "current_step": "Running tests",
  "decision_prompt": "Reply yes to fix, no to skip"
}
```

or for recording a decision:
```json
{
  "decision": "yes"
}
```

- `decision`: string (optional) — user's reply; when present, if status is needs_decision, set status to running and store decision. Runner can pass decision as additional context when resuming.
- `progress_pct`: int 0–100 (optional)
- `current_step`: string (optional)
- `decision_prompt`: string (optional) — shown in alert, clarifies what the user should decide

**Response 200** — updated task including new fields.

### `GET /api/agent/tasks` (extended)

Tasks in response include `progress_pct`, `current_step`, `decision`, `decision_prompt` when set.

### `GET /api/agent/tasks/attention`

**Response 200**
```json
{
  "tasks": [
    {
      "id": "task_abc",
      "direction": "Add GET /api/projects",
      "status": "needs_decision",
      "output": "Tests failed...",
      "decision_prompt": "Reply yes to fix"
    }
  ],
  "total": 1
}
```

Returns tasks with status `needs_decision` or `failed` only.

### `GET /api/agent/telegram/diagnostics`

**Response 200**
```json
{
  "config": {
    "has_token": true,
    "token_prefix": "12345678...",
    "chat_ids": ["12345"],
    "allowed_user_ids": ["12345"]
  },
  "webhook_events": [{ "ts": 1640000000.0, "update": { "update_id": 90001, "message": { ... } } }],
  "send_results": [{ "ts": 1640000000.0, "chat_id": "12345", "ok": true, "status_code": 200, "response_text": "..." }]
}
```

- `config`: masked Telegram config (no full token).
- `webhook_events`: last N incoming webhook payloads (append on each `POST /api/agent/telegram/webhook`).
- `send_results`: last N send_reply/send_alert attempts (append on each send).

Used by the diagnostic test to verify the full Telegram inbound path without a real bot.

## Data Model (extensions)

```yaml
AgentTask (extends 002):
  progress_pct: int | null   # 0-100
  current_step: string | null
  decision_prompt: string | null   # what user should decide
  decision: string | null    # user's reply
```

## Telegram Bot Commands

| Command | Behavior |
|---------|----------|
| `/reply {task_id} {decision}` | Record decision on task. If task is needs_decision, set status→running, store decision. Reply: "Decision recorded for task_abc" |
| `/attention` | Same as `/tasks needs_decision` + `/tasks failed` combined; shows only tasks needing user action |
| (existing) | /status, /tasks, /task, /usage, /direction |

## Telegram Flow Verification

Flow is complete when every item in the checklist below is implemented and the **diagnostic test** (see Acceptance Tests) passes. The diagnostic test uses `telegram_diagnostics.clear()` for isolation so it asserts on a known state.

**Verification checklist**

- [x] **Inbound — webhook received:** Every `POST /api/agent/telegram/webhook` call causes `telegram_diagnostics.record_webhook(update)` before any early return.
- [x] **Inbound — no message:** If update has no `message` or `edited_message`, return `{"ok": true}` after record_webhook.
- [x] **Inbound — no token / user not allowed:** When token missing or user_id not in TELEGRAM_ALLOWED_USER_IDS, return `{"ok": true}` after record_webhook.
- [x] **Inbound — command handling:** `parse_command(text)` yields (cmd, arg); router handles status, usage, tasks, task, reply, attention, direction (and plain text as direction).
- [x] **Inbound — reply sent:** For handled commands, `telegram_adapter.send_reply(chat_id, reply)` is called and `telegram_diagnostics.record_send` records the attempt.
- [x] **Outbound — alerts:** On PATCH task to `needs_decision` or `failed`, if Telegram configured, alert is sent via `send_alert` (e.g. background_tasks) to TELEGRAM_CHAT_IDS; message includes `decision_prompt` when set.
- [x] **Diagnostics endpoint:** `GET /api/agent/telegram/diagnostics` returns `config`, `webhook_events`, `send_results`; webhook_events and send_results are appended on each webhook/send.

**Inbound (webhook → reply) — sequence**

1. Telegram sends Update to `POST /api/agent/telegram/webhook`.
2. Router: `telegram_diagnostics.record_webhook(update)` (always).
3. If no token: return `{"ok": true}`. If no message/edited_message: return `{"ok": true}`.
4. If user_id not in TELEGRAM_ALLOWED_USER_IDS (when set): return `{"ok": true}`.
5. `telegram_adapter.parse_command(text)` → `(cmd, arg)`; cmd one of: status, usage, tasks, task, reply, attention, direction (or "" for plain text → direction).
6. Router calls agent_service per command; builds reply text.
7. `telegram_adapter.send_reply(chat_id, reply)`; diagnostics record_send.
8. Return `{"ok": true}`.

**Outbound (alert on needs_decision/failed)**

1. PATCH /api/agent/tasks/{id} with status `needs_decision` or `failed` (or task update triggers alert).
2. Router formats message via `_format_alert(task)` (includes decision_prompt when set).
3. If telegram_adapter.is_configured(): background_tasks.add_task(telegram_adapter.send_alert, msg).
4. send_alert posts to Telegram API for each TELEGRAM_CHAT_IDS.

**Diagnostics**

- `GET /api/agent/telegram/diagnostics` returns `config` (has_token, token_prefix, chat_ids, allowed_user_ids), `webhook_events`, `send_results`.
- Each webhook call appends to webhook_events; each send_reply/send_alert attempt appends to send_results (via telegram_diagnostics).

## Agent Runner

**Script:** `api/scripts/agent_runner.py`

**Behavior:**
1. Poll `GET /api/agent/tasks?status=pending` (or similar) on interval (e.g. 10s)
2. For each pending task: PATCH status→running, run `command` (from task) with env (Ollama/Claude)
3. Stream output; periodically PATCH `progress_pct`, `current_step` if determinable
4. On command exit: PATCH status (completed/failed) + output
5. If status is set to needs_decision by external means (e.g. Claude Code hook): poll task until `decision` is present, then either:
   - Re-run with decision as extra prompt/context, or
   - Mark completed and stop (MVP: just record decision, no auto-resume)
6. Run as background process; configurable via env (poll interval, concurrency)

**MVP scope:** Runner executes one task at a time. When task reaches needs_decision, runner stops and waits. User replies via `/reply`. Runner does NOT auto-resume from decision in MVP; a manual "continue" or new task could be used. Full resume loop in future iteration.

## Files to Create/Modify

- `api/app/models/agent.py` — add progress_pct, current_step, decision_prompt, decision
- `api/app/services/agent_service.py` — add get_attention_tasks, update_task extended fields, apply_decision
- `api/app/routers/agent.py` — add GET /attention, GET /telegram/diagnostics, extend PATCH handler, add /reply and /attention to webhook
- `api/app/services/telegram_adapter.py` — parse_command handles "reply"; send_reply/send_alert call telegram_diagnostics.record_send
- `api/app/services/telegram_diagnostics.py` — record_webhook, record_send, get_webhook_events, get_send_results, clear (for test isolation)
- `api/scripts/agent_runner.py` — new: poll, run, PATCH loop

## Acceptance Tests

See `api/tests/test_agent.py` — all must pass.

- test_reply_command_records_decision_and_updates_status
- test_attention_lists_only_needs_decision_and_failed
- test_patch_accepts_progress_and_decision
- test_agent_runner_polls_and_executes_one_task
- **test_telegram_flow_diagnostic** — see Diagnostic test (Telegram flow) below.

### Diagnostic test (Telegram flow)

Verifies the full inbound path (webhook → record_webhook → diagnostics) without a real bot. Required for “Telegram flow complete” in this spec.

**Steps**

1. (Optional) `GET /api/agent/telegram/diagnostics` and record `len(webhook_events)`.
2. `POST /api/agent/telegram/webhook` with body = a Telegram Update that includes `message` (e.g. a command like `/status`).
3. `GET /api/agent/telegram/diagnostics`.

**Assertions**

- Response has keys: `config`, `webhook_events`, `send_results`.
- `config` has `has_token`, `token_prefix`, `chat_ids`, `allowed_user_ids`.
- `webhook_events` was updated: either `len(webhook_events)` increased vs step 1, or (if no prior call) `len(webhook_events) >= 1`.
- The latest entry in `webhook_events` has an `update` that matches the payload sent (e.g. same `update_id`, and `message.text` when present).

**Example webhook payload (Telegram Update with message)**

```json
{
  "update_id": 90001,
  "message": {
    "message_id": 1,
    "from": {"id": 12345, "is_bot": false, "first_name": "Test"},
    "chat": {"id": 12345, "type": "private"},
    "date": 1640000000,
    "text": "/status"
  }
}
```

Test name in code: `test_telegram_flow_diagnostic`.

## See also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — Agent tasks API, Telegram webhook/diagnostics contract
- [013-logging-audit.md](013-logging-audit.md) — Telegram: user_id/chat_id OK; token never logged

## Out of Scope

- Auto-resume agent from decision (MVP: decision recorded only)
- PostgreSQL persistence (still in-memory)
- Rich progress from Claude Code (runner infers from output or uses simple heuristic)

## Decision Gates

- Agent runner: run in same process as API or separate? Recommend separate (script) for MVP.
