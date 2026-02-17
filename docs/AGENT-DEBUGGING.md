# Agent Task Debugging

How to add tasks, run them, and debug when something goes wrong.

## Adding a Task

**Via API:**
```bash
curl -X POST http://127.0.0.1:8000/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction": "Create api/test_hello.txt with content hello", "task_type": "impl"}'
```

**Via Telegram:** Message the bot: `/direction Create api/test_hello.txt with content hello`

**Via script:**
```bash
cd api && .venv/bin/python scripts/test_agent_run.py "Create api/test_hello.txt with content hello"
```
(Use `.venv/bin/python` if `python` points to system Python.)

## Running the Agent

**Overnight pipeline (recommended):** Start API first, then:
```bash
cd api && ./scripts/run_overnight_pipeline.sh
```
Uses `specs/006-overnight-backlog.md` (85 items, 8h run). Starts project manager + agent runner, resets overnight state. Stops overnight_orchestrator if running (they conflict). Use one orchestrator only. Track via pipeline status every 60s and `check_pipeline.py`.

**One task (good for testing):**
```bash
cd api && .venv/bin/python scripts/agent_runner.py --once -v
```

**Manual (two terminals):**
```bash
# Terminal 2
.venv/bin/python scripts/agent_runner.py --interval 10 -v

# Terminal 3 — project manager only (not overnight_orchestrator)
.venv/bin/python scripts/project_manager.py --interval 15 --hours 8 -v
```

**Verbose** (`-v`) prints progress to stdout. Logs always go to `api/logs/agent_runner.log`.

## When Something Goes Wrong

### 1. Check task status

**API:** `GET /api/agent/tasks/{task_id}` or `GET /api/agent/tasks?status=failed`

**Integration coverage:** `GET /api/agent/integration` returns role-agent bindings, profile coverage, optional executor binary checks, and any remaining integration gaps.

**Runtime coverage exerciser:** `POST /api/runtime/exerciser/run` performs safe real GET calls across discovered API GET routes and raises `with_usage_events` coverage over time.

**Telegram:** `/tasks failed` or `/task {task_id}`

### 2. Check full output

Task `output` in the API is truncated to 4000 chars. Full output is in:
```
api/logs/task_{task_id}.log
```

```bash
tail -100 api/logs/task_task_xxx.log
```

### 2b. Control context budget before opening more files

Before opening many files for analysis, run:

```bash
python3 scripts/context_budget.py --token-budget 50000 \
  api/app/services/release_gate_service.py \
  docs/PIPELINE-MONITORING-AUTOMATED.md
```

It prints:
- byte size / line count / rough token cost per file
- compact cached summaries to choose what to open next
- cache reuse path (`.cache/context_budget/summary_cache.json`) for future turns

If one file is still large, read its summary first and open only targeted slices:

```bash
python3 scripts/context_budget.py --force-summaries api/app/services/release_gate_service.py
sed -n '1,140p' api/app/services/release_gate_service.py
```

### 3. Check runner log

```bash
tail -50 api/logs/agent_runner.log
```

Shows: task_id, command, exit code, output length, any errors.

### 4. Pipeline status and visibility

**Quick status:**
```bash
.venv/bin/python scripts/check_pipeline.py
```
Shows: running task (model, duration), pending (wait time), recent completed (duration), PM state.

**Full task log (prompt + response):**
```bash
.venv/bin/python scripts/check_pipeline.py --task-id task_xxx
```

**API endpoints:**
- `GET /api/agent/pipeline-status` — running, pending, recent completed, PM state, latest_request, latest_response
- `GET /api/agent/tasks/{id}/log` — full log (command, output, log file)

**Latest LLM activity:** Pipeline status includes `latest_request` (prompt/direction) and `latest_response` (output preview) so you can see what the model was asked and what it returned.

**Live progress:** The agent runner streams task output to `api/logs/task_{id}.log` during execution. Pipeline status includes `live_tail` (last 25 lines) for the running task. Use `check_pipeline.py` or `GET /api/agent/tasks/{id}/log` to see progress without waiting for completion.

**Ollama request count:** Each agent turn = 1 `POST /v1/messages`. Check Ollama/GIN logs for request count.

### 6. Pipeline stuck

**Symptom:** No tasks progressing for 10+ minutes; pipeline-status shows pending but nothing runs.

**Checks:**
- Is the agent runner running? `ps aux | grep agent_runner`
- Is the API reachable? `curl -s http://localhost:8000/api/health`
- Any errors in `api/logs/agent_runner.log`?
- Is there a `needs_decision` task blocking? `GET /api/agent/tasks/attention` or `/attention` via Telegram

**Fixes:**
- Restart agent runner: stop it, then `./scripts/run_overnight_pipeline.sh` or `python scripts/agent_runner.py --interval 10`
- If blocked on needs_decision: reply via Telegram `/reply {task_id} yes` or PATCH the task with `{"decision": "yes"}`

### 7. Task hangs

**Symptom:** Task shows "running" for >1 hour; no progress; log file stops growing.

**Checks:**
- `tail -f api/logs/task_{id}.log` — is output still streaming?
- Is Claude Code/Ollama process still alive? `ps aux | grep claude` or `ps aux | grep ollama`

**Fixes:**
- Kill the stuck process: find PID from `ps`, `kill -9 <pid>`
- PATCH task to `failed` with output: `curl -X PATCH ... -d '{"status":"failed","output":"Killed: hung"}'`
- Increase timeout: `AGENT_TASK_TIMEOUT=7200` for 2h
- Simplify the direction or split into smaller tasks

### 8. Task timeout

Local models can run long. Default timeout is 1 hour (3600s). Override via env:
- `AGENT_TASK_TIMEOUT` — subprocess timeout (default 3600)
- `AGENT_HTTP_TIMEOUT` — HTTP request timeout in seconds (default 30)
- `AGENT_HTTP_RETRIES` — retries for transient API errors (default 3)
```bash
export AGENT_TASK_TIMEOUT=7200   # 2 hours
export AGENT_HTTP_RETRIES=5      # more retries if API is flaky
python scripts/agent_runner.py --interval 10
```

### 9. Headless mode: `--allowedTools` required

Claude Code in `-p` (headless) mode prompts for tool approval by default. With no user to respond, it exits without running Edit/Bash. **The command must include `--allowedTools Read,Edit,Grep,Glob,Bash`** so tools run automatically. The agent service adds this; if you run commands manually, include it.

### 10. Proven setup (local → cloud → claude fallback)

**Model fallback chain:** local (glm-4.7-flash) → cloud (glm-5:cloud) → Claude. Default is local.

For Edit/Bash tools to work:

- **Local:** `glm-4.7-flash:latest` — Ollama 0.15.x+, native tool calling
- **Cloud fallback:** `glm-5:cloud` — use `model_override: "glm-5:cloud"` in context; requires `ollama signin`
- **Claude fallback:** `claude-3-5-haiku-20241022` — use `model_override`; requires `ANTHROPIC_API_KEY`

```bash
ollama pull glm-4.7-flash:latest
# Cloud: ollama signin && ollama pull glm-5:cloud
```

Set in `api/.env`: `OLLAMA_MODEL=glm-4.7-flash:latest`

**Alternatives:** `command_override` runs raw bash (no Claude); `model_override` forces cloud or Claude. Agent runner sets telemetry env vars to suppress Ollama 404s.

### 11. Common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `command not found: claude` | Claude Code not installed | `curl -fsSL https://claude.ai/install.sh \| bash` |
| `connection refused` to localhost:11434 | Ollama not running | `ollama serve` |
| `model not found` | Model not pulled | `ollama pull glm-4.7-flash:latest` (proven for tool use) |
| Exit 1, "Error" in output | Claude/Ollama returned error | Check `task_{id}.log` for full trace |
| Timeout 300s | Task too complex or hung | Simplify direction; increase timeout in runner |
| `No command` | Malformed task | Ensure API returned command; check agent_service |

### 12. Smoke test (pipeline validation)

To verify the full pipeline (create → run → update) without relying on Claude Code:

```bash
# Create smoke task (runs raw bash, bypasses claude)
curl -X POST http://127.0.0.1:8000/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction": "smoke", "task_type": "impl", "context": {"command_override": "echo agent-e2e-ok > api/test_agent_e2e.txt"}}'

# Run agent
cd api && .venv/bin/python scripts/agent_runner.py --once -v

# Verify
cat api/test_agent_e2e.txt   # should show: agent-e2e-ok
```

If the smoke test passes but Claude tasks don't create files: use **glm-4.7-flash** (local) or **glm-5:cloud** (model_override) or Claude (ANTHROPIC_API_KEY). See MODEL-ROUTING.md for fallback chain.

### 13. Run command manually

Copy the `command` from the task and run it in a terminal:
```bash
cd /path/to/Coherence-Network
ANTHROPIC_AUTH_TOKEN=ollama ANTHROPIC_BASE_URL=http://localhost:11434 ANTHROPIC_API_KEY="" \
  claude -p "Your direction" --agent dev-engineer --model glm-4.7-flash:latest --allowedTools Read,Edit,Grep,Glob,Bash --dangerously-skip-permissions
```

Observe stdout/stderr directly.

## File locations

| File | Purpose |
|------|---------|
| `api/logs/agent_runner.log` | Runner: task start, completion, errors |
| `api/logs/task_{id}.log` | Full stdout+stderr for each run |
| `api/logs/telegram.log` | Webhook events, send results |

## Prerequisites

- API running (`./scripts/start_with_telegram.sh` or `uvicorn app.main:app`)
- Ollama running (`ollama serve`)
- Model pulled (`ollama pull glm-4.7-flash:latest` for tool use)
- Claude Code installed (see API-KEYS-SETUP.md)

## GitHub Auth Preflight (Avoid `gh` 401 / Missing GH_TOKEN)

Some Codex threads require `gh` (create PRs, check CI, merge). `gh` stores auth in the OS keychain, but **does not** automatically export `GH_TOKEN`.

### One-time: authenticate `gh` (persists in keychain)

```bash
gh auth login -h github.com
gh auth setup-git
gh auth status
```

### Recommended: set `GH_TOKEN` automatically for login shells

Add this block to `~/.zprofile` (login shells) so `zsh -lc` and CI helper scripts see it:

```bash
# >>> codex gh token sync >>>
if [ -z "$GH_TOKEN" ] && command -v gh >/dev/null 2>&1; then
  export GH_TOKEN="$(gh auth token 2>/dev/null)"
fi
# <<< codex gh token sync <<<
```

Verify:

```bash
zsh -lc 'echo GH_TOKEN_len=${#GH_TOKEN}; test -n "$GH_TOKEN" && echo ok'
```

If you need `GH_TOKEN` in the current shell (non-login), run:

```bash
source scripts/source_gh_token.sh
echo GH_TOKEN_len=${#GH_TOKEN}
```

### Preflight script (safe: never prints token)

```bash
python3 scripts/check_dev_auth.py
python3 scripts/check_dev_auth.py --json
```

### Notes

- `api/.env` is for the API process; it won’t automatically configure `gh` unless you export variables into your shell.
- Do not commit tokens into the repo. Use keychain-backed `gh auth login` and environment export.
