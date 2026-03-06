# Proof: Claude selected and run (local API mode) — 2026-03-05

## 1. API selected Claude (task command + context)

Task `task_35fe62eb31deaa2d` was created with `context.executor=claude`. The API returned a **claude** command (no fallback to Cursor):

```
context.executor: claude
command (first 100 chars): 'claude -p "Role agent: dev-engineer. Task type: impl. Respect role boundaries, spec scope, and accep'
```

So the API honored the requested executor and built a `claude -p "..."` command.

## 2. Runner selected Claude (log excerpt)

Runner was started with `AGENT_TASK_ID=task_35fe62eb31deaa2d`. Log output:

```
2026-03-05 15:11:10,126 task=task_35fe62eb31deaa2d runner_cli_present:claude:claude:/Users/ursmuff/.local/bin/claude
2026-03-05 15:11:10,126 task=task_35fe62eb31deaa2d using claude CLI auth requested=oauth effective=oauth oauth_session=True source=session_file:/Users/ursmuff/.claude/.credentials.json oauth_bootstrap=none
2026-03-05 15:11:10,126 task=task_35fe62eb31deaa2d using Claude Code CLI (OAuth/session)
2026-03-05 15:11:11,255 task=task_35fe62eb31deaa2d starting command=claude -p "Role agent: dev-engineer. Task type: impl. Respect role boundaries, spec scope, and acceptance criteria. Dire
```

So the runner used **Claude Code CLI** (not Cursor) and started the `claude -p "..."` command.

## 3. Run outcome and changes

- This run ended with status **failed** with output `[Timeout 600s]`. Claude was selected and the `claude -p "..."` command was started and ran until the 600s runner timeout; the failure is the timeout, not executor selection.
- **Proof that Claude was used:** API assigned `command=claude -p ...` and `context.executor=claude`; runner log shows `using Claude Code CLI` and `starting command=claude -p`.
- **Produced changes:** No new file edits from this specific run (it failed). The **diffs** below are the **framework changes** from this session that ensure Claude is selected and the right task is run (executor always honored, AGENT_TASK_ID, script).
