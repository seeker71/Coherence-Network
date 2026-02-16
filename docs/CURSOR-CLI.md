# Cursor CLI Integration

The orchestration agent can use **Cursor CLI** (`agent` command) as an alternative to Claude Code CLI for spec, impl, test, and review tasks. Cursor CLI is headless and scriptable, ideal for CI/CD and overnight runs.

## Default executor

When `AGENT_EXECUTOR_DEFAULT=cursor` is set in `api/.env`, all tasks use Cursor CLI by default. Override with `--claude` when running project manager. Default Cursor model is `auto` (avoids per-model usage limits).

## Prerequisites

1. **Install Cursor CLI:**
   ```bash
   curl https://cursor.com/install -fsS | bash
   ```

2. **Verify:** Cursor must be signed in (Cursor app uses its own auth; no ANTHROPIC_API_KEY needed).
   ```bash
   agent "print('hello')"
   ```

## Usage

### API: context.executor

When creating a task, pass `context: {"executor": "cursor"}` to use Cursor CLI:

```bash
curl -X POST http://localhost:8000/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction": "Implement GET /api/foo", "task_type": "impl", "context": {"executor": "cursor"}}'
```

### Project Manager: --cursor

Run the full spec→impl→test→review pipeline with Cursor CLI:

```bash
cd api && python scripts/project_manager.py --cursor --verbose --once
```

For overnight runs:

```bash
./scripts/run_overnight_pipeline.sh --backlog specs/006-overnight-backlog.md
# Then in project_manager invocation, add --cursor if using the pipeline script
```

### Route Endpoint

Check Cursor routing for a task type:

```bash
curl "http://localhost:8000/api/agent/route?task_type=impl&executor=cursor"
```

## Model Mapping

| Task Type | Cursor Model | Env Override |
|-----------|--------------|--------------|
| spec, impl, test | composer-1 (fast) | `CURSOR_CLI_MODEL` |
| review, heal | claude-4-opus (deep) | `CURSOR_CLI_REVIEW_MODEL` |

Set in `api/.env`:

```bash
CURSOR_CLI_MODEL=composer-1
CURSOR_CLI_REVIEW_MODEL=claude-4-opus
```

## Command Format

- **Claude Code (default):** `claude -p "direction" --agent dev-engineer --model glm-4.7-flash ...`
- **Cursor CLI:** `agent "direction" --model composer-1`

Cursor CLI uses simpler syntax; the agent_runner detects `agent `-prefixed commands and skips Claude/Ollama env overrides so Cursor uses its own auth.

## Best Practices

1. **Dev/QA cycles:** Use `composer-1` for speed on impl and test; reserve `claude-4-opus` for review.
2. **Isolation:** Run in a git worktree or DevContainer for safety.
3. **Context:** Cursor respects `.cursor/rules/` in the repo; ensure rules are in place for consistency.
4. **Fallback:** If Cursor CLI fails (exit 127), the task is marked failed; use Claude Code as fallback by omitting `--cursor`.

## Limitations

- Cursor CLI has no `--agent` subagent flag; role is implied by the direction/prompt.
- Agent runner does not set ANTHROPIC_* for Cursor; Cursor uses app login.
- Requires Cursor Pro+ for best models (composer-1, claude-4-opus).

## OpenClaw Integration

OpenClaw is supported as an additional executor through `context.executor=openclaw` or `AGENT_EXECUTOR_DEFAULT=openclaw`.

### Required env

Set in `api/.env`:

```bash
AGENT_EXECUTOR_DEFAULT=openclaw
OPENCLAW_MODEL=openrouter/free
OPENCLAW_REVIEW_MODEL=openrouter/free
OPENCLAW_COMMAND_TEMPLATE='openclaw run "{{direction}}" --model {{model}}'
OPENCLAW_API_KEY=...
OPENCLAW_BASE_URL=...
```

### API usage

```bash
curl -X POST http://localhost:8000/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction":"Implement GET /api/foo","task_type":"impl","context":{"executor":"openclaw"}}'
```

### Routing check

```bash
curl "http://localhost:8000/api/agent/route?task_type=impl&executor=openclaw"
```

Notes:
- `OPENCLAW_COMMAND_TEMPLATE` must include `{{direction}}`; `{{model}}` is optional and replaced automatically.
- Runner telemetry classifies OpenClaw runs under `executor=openclaw` for usage/success-rate reporting.
