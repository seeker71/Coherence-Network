# Agent Task Debugging

How to add tasks, run them, and debug when something goes wrong.

## Pipeline validation: highest-ROI unvalidated idea

To validate the full idea → spec → impl → test → review → acceptance pipeline, pick the **highest-ROI idea that has not passed acceptance yet** and run it **through the agent CLI**, then confirm with the acceptance checklist.

### Order of operations (required)

1. **Agent CLI does the work** — The pipeline must use **agent CLI calls** (via the runner) to:
   - **Spec:** update or create the spec for the idea (e.g. spec 053 for portfolio-governance).
   - **Impl:** implement the spec (code, tests, files per spec).
   - **Test:** run tests (agent runs pytest/verification commands).
   - **Review:** review implementation against the spec (agent produces pass/fail and, on fail, PATCH_GUIDANCE).
   - Loop impl → test → review until review passes (see spec 108, project_manager).
2. **Then validate acceptance** — **Only after** the agent has completed spec → impl → test → review do you run the **acceptance validation** (the checklist or `run_pinned_idea_acceptance.py`) to confirm that acceptance has passed. That validation is the final gate; it does not replace the agent doing spec/impl/review.

So: **agent updates spec, implementation, and review first; only then do we validate that acceptance has passed.**

**Current pick:** **portfolio-governance** (Unified idea portfolio governance)

- **Idea ID:** `portfolio-governance`
- **ROI (free_energy_score):** highest among unvalidated ideas (e.g. ~5.1 from `potential_value=82`, `confidence=0.75`, `estimated_cost=10`, `resistance_risk=2`)
- **Status:** `manifestation_status: partial` (not yet `validated`)
- **Spec:** `specs/053-ideas-prioritization.md` — Ideas Prioritization API (implements list/score/update; spec now has full quality gate: Verification, Risks, Gaps)

**Acceptance checklist — one path, proof at each step:**

1. **Agent does the work:** spec → impl → test → review (via runner). After the pipeline, open the **review** task log and confirm the payload contains **`VERIFICATION_RESULT=PASS`** (not FAIL). If it says FAIL, fix implementation per the review’s PATCH_GUIDANCE and re-run review.

2. **Run the acceptance script** (from repo root, with API running):  
   `python3 scripts/run_pinned_idea_acceptance.py`  
   It runs four steps in order and prints **`[PROOF]`** for each so you have required data and files that passed. Use `--force` to re-run all steps.

3. **Mark idea accepted** only when the script finishes with `[PROOF] acceptance_complete: all steps passed`:  
   `PATCH /api/ideas/portfolio-governance` with `{"manifestation_status": "validated"}`.

**How to use this for pipeline validation:** Start the API, then (1) run the **agent** (project manager or explicit spec → impl → test → review tasks for this idea) so the agent CLI updates the spec, implementation, and review; (2) **then** run the acceptance checklist (or script below) to validate that acceptance has passed. Fix any blocking test/guard failures and re-run the agent or validation as needed so the idea can move to accepted.

**Why did review run before spec?** The runner does not enforce phase order. The API returns pending tasks **newest-first** (`created_at.desc()` in `agent_task_store_service.load_tasks_page`). If you create tasks in order spec → impl → test → review, the **review** task (created last) is first in the list, so the runner picks it first. To get **spec-first** order, create tasks in **reverse** order (review, test, impl, spec) so spec is newest and runs first, or add phase-aware ordering to the list endpoint / runner.

### Run pinned-idea acceptance — one path, proof at each step

**Guidance:** After the agent has completed spec → impl → test → review, run the script once. It runs four steps in order and prints **`[PROOF]`** with the required data and files for each step that passes.

```bash
# From repo root. Start API first: cd api && uvicorn app.main:app --port 8000
python3 scripts/run_pinned_idea_acceptance.py

# Re-run all steps (ignore saved state)
python3 scripts/run_pinned_idea_acceptance.py --force
```

**What the script does (in order):**

| Step | What it checks | Proof printed |
|------|----------------|---------------|
| step_1_no_placeholder | Spec + impl files have no placeholder/mock/fake/TODO implement | `files_checked`, `result: no_forbidden_tokens` |
| step_2_spec_quality | Spec 053 passes quality validator; has Purpose, Requirements, Verification, Risks, Known Gaps | `spec_file`, `validator_exit: 0`, `sections_present` |
| step_3_pytest | `pytest -q tests/test_ideas.py` passes | `exit_code: 0`, `tests_passed`, `output_tail` |
| step_4_live_api | GET /api/ideas returns JSON with non-empty ideas and summary (real data) | `url`, `status`, `summary`, `ideas_returned`, `first_idea_ids`, `shape_ok` |

**Example proof output (success):** Each step prints `[PROOF] step_id: { ... }` with the evidence above. At the end you get `[PROOF] acceptance_complete: all steps passed.` If a step fails, the script prints `[FAILURE]` with `suggested_action` and exits; fix the cause and re-run (completed steps are skipped unless you use `--force`).

**Review payload:** The script does not read task logs. After the pipeline, open the **review** task log (e.g. `api/logs/task_<review_task_id>.log`) and confirm the payload contains **`VERIFICATION_RESULT=PASS`**. If it says FAIL, fix implementation per the review’s PATCH_GUIDANCE and re-run the review task, then run this script again.

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

### 3. Reviewer-visible execution packet

Before handing off task results to humans, keep reviewer visibility explicit by using:
`docs/system_audit/MINIMAL_EXECUTION_PACKET_TEMPLATE.md`
and filling `Validation Commands`/`Validation Results` from the actual command outputs.

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

### 4. Claude PID and whether it is still running

For a **running** task, the runner stores the **Claude (child) process PID** in the task context so you can check if the CLI is still alive and what it’s doing.

- **`context.runner_pid`** — PID of the **child process** (the `claude -p "..."` subprocess). This is the Claude CLI process.
- **`context.runner_id`** — `hostname:pid` of the **runner** (Python) process, e.g. `Urss-MacBook-Pro.local:2821`.

**Check if Claude is still running:**
```bash
# Get task (replace TASK_ID)
curl -s "http://127.0.0.1:8000/api/agent/tasks/TASK_ID" | jq '{status, progress_pct, current_step, "claude_pid": .context.runner_pid, "runner_id": .context.runner_id, "runner_last_seen_at": .context.runner_last_seen_at}'

# If claude_pid is set, check process (replace 2914)
ps -p 2914 -o pid,stat,etime,command
```
If the task is still **running** but `ps -p <runner_pid>` shows “no such process”, the child exited (e.g. crash or finished) and the runner will soon update the task status.

### 5. Latest logs and how progress is made

- **Task log (streaming output from Claude):** `api/logs/task_{task_id}.log`  
  The runner writes a header (task_id, command) then streams the child’s stdout line-by-line. Use `tail -f api/logs/task_TASK_ID.log` to watch live.

- **Progress fields (updated every heartbeat):** The runner patches the task periodically with:
  - **`current_step`** — Latest parsed activity (e.g. "Thinking", "Tool: read_file") or "Running" when no structured events yet.
  - **`context.runner_recent_activity`** — List of recent step labels from agent output (when using stream-json or parseable JSON lines).
  - **`context.runner_log_tail`** — last lines of captured output (same as tail of the task log).
  - **`context.runner_last_seen_at`** — last heartbeat time (UTC).
  - **`progress_pct`** — Not set during run (no misleading time-based %). Set to 100 only when the task completes.

So: **actual progress** = `current_step` and `context.runner_recent_activity`; **logs** = task log file and `runner_log_tail`. For real-time steps/tools/thinking, use `CLAUDE_CODE_OUTPUT_FORMAT=stream-json` (Claude) or have the agent emit **`[STATUS] <step>`** lines at least every 2 minutes (the runner parses these). **Resume:** set `context.resume` or `context.resume_session_id` when creating a task to continue a previous session. Resume is applied in a provider-agnostic way (Claude: `-c`; Codex/Cursor/Gemini: add in `apply_resume_to_command` when supported). **Task reuse:** when creating a task, pass `context.task_fingerprint`; if an active (pending/running) task with that fingerprint exists, it is returned instead of creating a new one. **Resume before restart:** To validate without losing the current run, start the runner with `AGENT_TASK_ID=<id>` set to the existing running task so it claims that task and sends a running heartbeat. Orphan recovery only reaps tasks when a runner reports *idle* and the task is past the stale threshold and was claimed by that same runner, so the task you want to resume is not reaped while the new runner is starting. If you stopped the previous runner and want a *new* runner to take over the same task, either wait for the run-state lease to expire (~2 min) or clear the task to pending so the new runner can claim.

## Long runs: no timeout, progress, and resume

Avoid burning LLM budget by aborting long runs without the ability to see progress or continue. Use no timeout, snapshots, and resume.

### No timeout (recommended for costly runs)

Set **`AGENT_TASK_TIMEOUT=0`** so the runner never kills a task. The process runs until it completes, you abort via API, or a usage guard triggers. Default is 3600s; with 0 there is no time limit.

```bash
AGENT_TASK_TIMEOUT=0 .venv/bin/python scripts/agent_runner.py --once -v
```

### Seeing progress

While a task is **running**, the runner periodically patches the task with:

- **`current_step`** — Latest activity from agent output (e.g. "Thinking", "Tool: read_file") or "Running"
- **`context.runner_recent_activity`** — List of recent steps (when output is stream-json or parseable)
- **`context.runner_log_tail`** — last lines of captured stdout/stderr
- **`context.runner_last_seen_at`**, **`context.runner_pid`**
- **`progress_pct`** — not set during run (only 100 when completed)

**API:** `GET /api/agent/tasks/{task_id}` and inspect `current_step`, `context.runner_recent_activity`, `context.runner_log_tail`.

**Log file:** Output is streamed to `api/logs/task_{task_id}.log`; use `tail -f api/logs/task_{task_id}.log` to watch live.

**Status report:** `GET /api/agent/status-report` (or `check_pipeline.py`) for high-level run state.

### Snapshots on timeout or abort

If a run is stopped by a **time limit** (when `AGENT_TASK_TIMEOUT` > 0), the runner:

- Saves the **partial output** into the task (and appends to the task log file).
- Sets **`context.timeout_snapshot_at`**, **`context.partial_output_len`**, **`context.resumable`** so you can see that the run was cut by timeout and can be retried/resumed.

So you always have a snapshot of progress and can decide to requeue the same task.

### Resuming unfinished work

- **Requeue the same task:** Set the task back to **pending** (e.g. PATCH `status: "pending"`) so the runner picks it up again. The same `direction` and context are used; for PR-mode tasks the runner uses **`resume_checkpoint_sha`** / **`resume_branch`** when present.
- **PR mode:** The runner already checkpoints partial progress (git commit + push on the task branch) and can requeue with **resume_attempts** / **resume_checkpoint_sha** so the next run continues from the last checkpoint.
- **No timeout:** Prefer **`AGENT_TASK_TIMEOUT=0`** for expensive or long-running tasks so you don’t lose progress to a hard kill; use progress and manual abort if you need to stop.

### CLI step trackability and actionable failures

For **multi-step CLI flows** (e.g. pinned-idea acceptance), the runner and task context support:

- **Step visibility:** If the child process prints **`[STATUS] <step_name>`** (e.g. `[STATUS] step_2_pytest_ideas`), the runner parses it and updates **`current_step`** and run-state so you can see which step is running or last ran.
- **Actionable failure hints:** If the child prints **`[FAILURE] {"suggested_action": "...", "unblock_condition": "...", "step": "..."}`** (one JSON object), the runner stores them in task context as **`cli_failure_suggested_action`**, **`cli_failure_unblock_condition`**, **`cli_failure_step`**. Use these for LLM reasoning or human next steps.
- **Monitoring:** Use **`GET /api/agent/tasks/{task_id}`** (fields `current_step`, `context.runner_recent_activity`, `context.cli_failure_*`) and **`GET /api/agent/run-state/{task_id}`** (status, next_action, failure_class). Full output: **`api/logs/task_{task_id}.log`**.
- **Resume:** For script-based flows that support it (e.g. `scripts/run_pinned_idea_acceptance.py`), set **`RESUME_FROM_STEP=<step_id>`** when re-running so completed steps are skipped. Requeue the task (status → pending) to retry after fixing.

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
- **Claude fallback:** `claude-3-5-haiku` — use `model_override`; requires `ANTHROPIC_API_KEY`

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
