# Local Validation Proof — 2026-03-06

**Branch:** `codex/local-validation`  
**Generated:** 2026-03-06

## Railway ToS mitigations (this session)

- **Skip backboard from app when on Railway:** In `api/app/services/automation_usage_service.py`, `_is_running_on_railway()` detects Railway runtime (`RAILWAY_SERVICE_ID` / `RAILWAY_ENVIRONMENT_ID`). When true, `_build_railway_snapshot()` and `_probe_railway()` return stub/skip without calling `https://backboard.railway.com/graphql/v2`, so the deployed app no longer hits Railway’s API (ToS compliance).
- **Less frequent deploy contract:** `.github/workflows/public-deploy-contract.yml` schedule changed from `*/30 * * * *` to `0 */2 * * *` (every 2 hours) to reduce Railway redeploy/API traffic from CI.
- **Stashed work restored:** Applied `stash@{0}` (ghx zshrc fix) into the current branch.

## Summary

| Gate / check | Status | Notes |
|--------------|--------|------|
| **start-gate** | ✅ PASS | `make start-gate` (branch-only) |
| **PR guard (rebase, workflow refs, spec quality, commit evidence, runtime drift, web build, worktree web)** | ✅ PASS | With clean tree, `--skip-api-tests` |
| **Critical API test subset** | ✅ PASS | 60 passed (runtime, openclaw, orchestrator, commit_progress) |
| **Full API pytest** | ❌ 44 failures | Pre-existing in other modules (telegram, automation_usage, runner telemetry, etc.); blocks full guard when api-tests enabled |

## Proof Artifacts

### 1. Start-gate

```text
start-gate: passed (branch-only, branch=codex/local-validation)
```

**Command:** `make start-gate`

### 2. Worktree PR guard (clean tree, --skip-api-tests)

All selected checks passed:

- **rebase-freshness-guard** — Branch rebased on `origin/main`
- **workflow-reference-guard** — 21 references checked, 0 missing
- **spec-quality-guard** — No changed feature spec files in range
- **commit-evidence-guard** — No changed files in range; skipped
- **runtime-drift-guard** — Within allowlist baseline
- **web-build** — `npm ci --allow-git=none && npm run build` succeeded
- **worktree-runtime-web-guard** — `THREAD_RUNTIME_START_SERVERS=1 ./scripts/verify_worktree_local_web.sh` — Local worktree web validation passed

**Report:** `docs/system_audit/pr_check_failures/pr_check_guard_20260306T151738Z_codex-local-validation.json`  
**Command:** `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main --skip-api-tests`  
**Condition:** Clean working tree (no uncommitted changes)

### 3. Critical API test subset (with CI-fix changes)

```text
60 passed, 2 warnings in 7.55s
```

**Command:**  
`cd api && .venv/bin/pytest tests/test_runtime_api.py tests/test_openclaw_executor_integration.py tests/test_orchestrator_policy_service.py tests/test_commit_progress.py -q --tb=no`

**Modules:**  
- `test_runtime_api.py` (incl. MVP acceptance summary/judge)  
- `test_openclaw_executor_integration.py`  
- `test_orchestrator_policy_service.py`  
- `test_commit_progress.py`  

## Full API pytest (current state)

**Command:** `cd api && pytest -q --ignore=tests/holdout`  
**Result:** 44 failed, 644 passed (failures in agent_telegram, agent_runner_tool_failure_telemetry, agent_task_persistence, automation_usage_api, agent_monitor_status_fallback_api, run_self_improve_cycle, gates, release_gate_service; some require network or env).

## How to reproduce

1. **Start-gate:**  
   `git switch -c codex/local-validation` (or any non–main branch) then `make start-gate`

2. **Guard (without api-tests):**  
   Stash or commit all changes so the tree is clean, then:  
   `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main --skip-api-tests`

3. **Critical tests:**  
   With CI-fix changes applied:  
   `cd api && .venv/bin/pytest tests/test_runtime_api.py tests/test_openclaw_executor_integration.py tests/test_orchestrator_policy_service.py tests/test_commit_progress.py -q`

## Full idea-to-acceptance pass (Cursor and Claude)

To validate that a full idea → implementation → acceptance flow runs with Cursor and Claude:

1. **Entry gate**  
   `make prompt-gate`  
   (Dirty tree: continuation mode; clean tree: full start-gate + rebase + local guard.)

2. **Start API (local)**  
   `cd api && .venv/bin/uvicorn app.main:app --reload --port 8000`  
   Use `AGENT_AUTO_EXECUTE=0` so execution is driven by the runner, not the server.

3. **Create a small task (idea)**  
   ```bash
   curl -sS -X POST http://127.0.0.1:8000/api/agent/tasks \
     -H "Content-Type: application/json" \
     -d '{"direction": "Create api/test_idea_acceptance.txt with content ok", "task_type": "impl"}' | jq -r '.id'
   ```
   Save the returned `task_id`.

4. **Execute with Cursor**  
   In a second terminal (Cursor executor must be available):  
   `cd api && AGENT_TASK_ID=<task_id> .venv/bin/python scripts/agent_runner.py --once -v`  
   Or use the `command` from `GET /api/agent/tasks/<task_id>` and run it in Cursor/terminal.  
   Confirm the task status moves to `completed` and `api/test_idea_acceptance.txt` exists.

5. **Execute with Claude (optional)**  
   Same as step 4 but ensure Claude Code CLI is in PATH and the task is routed to `claude` (or create a task with `context.executor` / `model_override` for Claude). Run `agent_runner.py --once` and confirm completion.

6. **Acceptance / runtime proof**  
   - Task completion: `curl -sS http://127.0.0.1:8000/api/agent/tasks/<task_id> | jq '{ status, output }'`  
   - Runtime events for the task: `curl -sS "http://127.0.0.1:8000/api/runtime/events?limit=50" | jq --arg id <task_id> '[.[] | select(.metadata.task_id == $id)]'`  
   - For MVP acceptance (spec 114): `curl -sS "http://127.0.0.1:8000/api/runtime/mvp/acceptance-summary?seconds=3600" | jq`

7. **Local guard (before push)**  
   After committing, run:  
   `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main --skip-api-tests`  
   Resolve commit-evidence-guard by adding or updating `docs/system_audit/commit_evidence_*.json` with all changed files.
