# Spec: Telegram Personal Assistant Bot

## Purpose

Add a second Telegram bot endpoint dedicated to personal assistant requests so a user can send research/action prompts from Telegram and have the backend pick them up in the background as agent tasks.

## Requirements

- [ ] Add a dedicated webhook endpoint for a second Telegram bot that uses separate configuration from the existing agent operations bot.
- [ ] Support assistant-oriented commands from Telegram: at minimum `/research`, `/do`, `/status`, `/task {id}`, and plain-text input fallback.
- [ ] Assistant requests must create tasks with context metadata marking source/chat/user for traceability.
- [ ] Background execution must be optionally queued immediately after task creation (enabled by config), so requests can run without manual `/execute` calls.
- [ ] Enforce optional allowlist security for assistant bot users.

## API Contract (if applicable)

### `POST /api/assistant/telegram/webhook`

**Request**
- Telegram Update payload (message or edited_message)

**Behavior**
- If bot token missing or user is not allowed, return success envelope without processing.
- `/research <prompt>` creates a `TaskType.SPEC` task.
- `/do <prompt>` creates a `TaskType.IMPL` task.
- Plain text behaves like `/do <text>`.
- `/status` returns a compact view of recent assistant-origin tasks for the current chat.
- `/task {id}` returns task summary when found.

**Response 200**
```json
{ "ok": true }
```

## Data Model (if applicable)

N/A - no new persisted model types. Existing task context is extended with assistant metadata keys:

```yaml
Task.context:
  source: "telegram_personal_assistant"
  assistant_request_kind: "research" | "action"
  telegram_user_id: string
  telegram_chat_id: string
```

## Files to Create/Modify

- `specs/108-telegram-personal-assistant-bot.md`
- `api/app/routers/assistant_telegram.py`
- `api/app/routers/agent.py`
- `api/app/services/telegram_personal_adapter.py`
- `api/tests/test_assistant_telegram_webhook.py`
- `api/.env.example`
- `api/scripts/start_with_telegram.sh`

## Acceptance Tests

- `api/tests/test_assistant_telegram_webhook.py::test_assistant_research_command_creates_spec_task_and_queues_execution`
- `api/tests/test_assistant_telegram_webhook.py::test_assistant_plain_text_creates_impl_task`
- `api/tests/test_assistant_telegram_webhook.py::test_assistant_status_lists_recent_chat_tasks`
- `api/tests/test_assistant_telegram_webhook.py::test_assistant_rejects_disallowed_user`

## Verification

```bash
cd api && pytest -q tests/test_assistant_telegram_webhook.py
```

## Out of Scope

- Multi-turn memory beyond persisted task context.
- New task types beyond existing enum values.
- Automatic Telegram webhook provisioning outside the existing startup helper script.

## Risks and Assumptions

- Risk: if `TELEGRAM_PERSONAL_ALLOWED_USER_IDS` is left unset, any user who can reach the bot may submit requests; mitigation is explicit allowlist support and documented env var.
- Assumption: existing task execution services are sufficient for assistant requests without adding a separate worker runtime.

## Known Gaps and Follow-up Tasks

- Follow-up task: add richer intent classification (research vs. action) from natural-language prompts beyond explicit `/research` and `/do` commands.

## Decision Gates (if any)

None.
