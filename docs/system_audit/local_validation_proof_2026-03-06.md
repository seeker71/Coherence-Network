# Local Validation Proof — 2026-03-06

**Branch:** `codex/local-validation`  
**Generated:** 2026-03-06

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
