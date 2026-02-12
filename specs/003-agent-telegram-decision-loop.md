# Spec: Agent-Telegram Decision Loop & Progress Tracking

## Purpose

Close the loop between agent tasks and human: when a task needs a decision, the user can reply via Telegram and the system records the decision for the agent to act on. Add progress tracking and an `/attention` command so the user knows what requires action and how far each task has progressed.

Extends spec 002 (Agent Orchestration API).

## Requirements

- [ ] Telegram `/reply {task_id} {decision}` — record decision on task, update status to running (or completed if decision is terminal)
- [ ] Telegram `/attention` — list only tasks with status needs_decision or failed
- [ ] Agent task: add `progress_pct` (0–100), `current_step`, `decision_prompt` (optional), `decision` (user reply)
- [ ] PATCH /api/agent/tasks/{id}: accept `progress_pct`, `current_step`, `decision` in request body
- [ ] Agent runner script: polls pending tasks, runs command, PATCHes progress, blocks on needs_decision until decision present, then continues or stops
- [ ] Telegram alert for needs_decision includes `decision_prompt` (what to decide) when provided

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
- `api/app/routers/agent.py` — add GET /attention, extend PATCH handler, add /reply and /attention to webhook
- `api/app/services/telegram_adapter.py` — parse_command handles "reply"
- `api/scripts/agent_runner.py` — new: poll, run, PATCH loop

## Acceptance Tests

- test_reply_command_records_decision_and_updates_status
- test_attention_lists_only_needs_decision_and_failed
- test_patch_accepts_progress_and_decision
- test_agent_runner_polls_and_executes_one_task

## Out of Scope

- Auto-resume agent from decision (MVP: decision recorded only)
- PostgreSQL persistence (still in-memory)
- Rich progress from Claude Code (runner infers from output or uses simple heuristic)

## Decision Gates

- Agent runner: run in same process as API or separate? Recommend separate (script) for MVP.
