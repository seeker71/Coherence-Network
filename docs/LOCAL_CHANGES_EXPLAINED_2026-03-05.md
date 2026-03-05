# Local changes explained (2026-03-05)

Summary of all current local changes, grouped by purpose. Used to decide what to integrate and deploy.

---

## 1. Local tool guard unblock (this session)

**Purpose:** Stabilize local tool validation, gate vs canary for executor matrix, invariant baseline, and cleanup.

| Change | Description |
|--------|-------------|
| **.gitignore** | Ignore `docs/system_audit/production_db_*.json|*.md`, `git_trace.txt`, `out.txt` so one-off audit/temp files are not merged. |
| **api/app/routers/ideas.py** | Add query param `read_only_guard`; when true, list_ideas does not persist ensure logic (for invariant runs). |
| **api/app/services/idea_service.py** | `_read_ideas(persist_ensures=True)`; `list_ideas(..., read_only_guard=False)`. When `read_only_guard=True` / `persist_ensures=False`, no DB writes from ensure logic. |
| **api/scripts/run_cli_task_flow_matrix.py** | `--non-blocking-executors` (e.g. codex); spec-stage fallback: if task output missing markers but local `spec.md` has them, treat contract_ok; spec prompt asks for exact VERIFICATION_PLAN/ACCEPTANCE_CRITERIA headers. |
| **api/scripts/capture_local_tool_baseline.py** | New script: warm GET /api/ideas, capture baseline (counts + idea_ids, spec_ids) to JSON; `--diff BASELINE` for ID-level invariant check; `--allow-idea-id-prefix` for flow-idea drift. |
| **docs/LOCAL-TOOL-GUARD.md** | Doc: guards, baseline capture, tool order, Tool 2 gate vs canary, Tool 4 deterministic command, completion criteria, allow prefix for diff. |
| **.playwright-cli/** (deleted) | Removed old page-*.yml captures (temp artifacts). |

---

## 2. Agent / runtime refactor and new modules

**Purpose:** Split agent and runtime logic into dedicated packages; add automation usage and inventory submodules.

| Area | Files | Description |
|------|--------|-------------|
| **Agent routing** | `api/app/services/agent_routing/*` (new), `agent_routing_service.py` (M) | Routing config, executor config, model config, command templates, provider classification. |
| **Agent run state** | `api/app/services/agent_run_state/*` (new), `agent_run_state_service.py` (M) | Run state DB, local store, models, service. |
| **Agent service split** | `agent_service_*.py` (new), existing services (M) | completion_tracking, crud, executor, friction, list, store, task_derive. |
| **Automation usage** | `api/app/services/automation_usage/*` (new) | Constants and usage tracking. |
| **Inventory** | `api/app/services/inventory/*` (new), `inventory_service.py` (M) | cache, constants, evidence, flow_helpers, impl_questions, lineage, proactive, route_evidence, spec_discovery. |
| **Runtime** | `api/app/services/runtime/*` (new) | cache, events, ideas, paths, routes, store. |
| **Adapters** | `postgres_store.py` (M), `postgres_models.py` (new) | Postgres adapter and models. |

---

## 3. Web UI: flow, tasks, usage, api-coverage

**Purpose:** New or refactored pages and shared logic for flow, tasks, usage, and API coverage.

| Area | Files | Description |
|------|--------|-------------|
| **Flow** | `web/app/flow/page.tsx` (M), `FlowItemCard.tsx`, `FlowSummaryCards.tsx`, `FlowTopContributors.tsx`, `FlowUnblockQueue.tsx`, `load-flow-data.ts`, `types.ts`, `utils.ts` | Flow page and components. |
| **Tasks** | `web/app/tasks/page.tsx` (M), `EvidenceTrail.tsx`, `TasksListSection.tsx`, `types.ts`, `utils.ts` | Tasks page and components. |
| **Usage** | `web/app/usage/page.tsx` (M), `data.ts`, `types.ts`, `sections/*` (Friction, HostRunner, NavLinks, Providers, QualityAwareness, RuntimeCost, TopToolsAttention, ViewPerformance) | Usage page and sections. |
| **API coverage** | `web/app/api-coverage/page.tsx` (M), `lib.ts`, `types.ts`, `use-api-coverage.ts` | API coverage page and hooks. |

---

## 4. Docs and scripts

| File | Description |
|------|-------------|
| **docs/RUNBOOK.md** (M) | Runbook updates. |
| **docs/MERGE_PROGRESS_2026-03-05.md** (??) | Merge progress and branch integration notes. |
| **scripts/integrate_one_branch.sh** (??) | Script to integrate one branch (rebase/merge) into main. |

---

## What to integrate for deploy

- **Needed for deploy (recommended):** All of **(1)** and the refactors in **(2)** and **(3)** that the running app and web depend on (imports and routes). The repo currently has main with these changes; API imports succeed.
- **Optional:** MERGE_PROGRESS and integrate_one_branch.sh are useful for branch workflow; can be committed or kept local.
- **Deploy:** Railway auto-deploys from `main`. Push to `origin main` after integrating; then run `./scripts/verify_web_api_deploy.sh ...` per DEPLOY.md to confirm public contract.

---

## Pre-push / pre-deploy checks (from AGENTS.md and DEPLOY.md)

1. `git fetch origin main && git rebase origin/main` (if integrating onto main).
2. `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main`
3. `./scripts/verify_worktree_local_web.sh` (local API + web contract).
4. After push: `VERIFY_REQUIRE_API_HEALTH_SHA=1 VERIFY_REQUIRE_WEB_HEALTH_PROXY_SHA=1 ./scripts/verify_web_api_deploy.sh <api_url> <web_url>` (public contract).

Commit evidence: if the pre-push guard requires it, add `docs/system_audit/commit_evidence_2026-03-05_<topic>.json` with the changed file list and validate with `python3 scripts/validate_commit_evidence.py --file <path>`.
