# Spec Coverage — Coherence Network

Audit of spec → implementation → test mapping. All implementations are spec-driven; tests use real API (no mocks).

## Status Summary

| Spec | Present | Spec'd | Tested | Notes |
|------|---------|--------|--------|-------|
| 001 Health | ✓ | ✓ | ✓ | Complete |
| 002 Agent Orchestration | ✓ | ✓ | ✓ | Complete |
| 003 Decision Loop | ✓ | ✓ | ✓ | Agent runner: smoke test only (see shortcuts) |
| 004 CI Pipeline | ✓ | ✓ | ✓ | GitHub Actions for pytest |
| 005 Project Manager | ✓ | ✓ | ✓ | Complete |
| 007 Sprint 0 Landing | ✓ | ✓ | ✓ | Root, /docs, health |
| 008 Sprint 1 Graph | ✓ | ✓ | ✓ | Via 019; `--target 5000` closes gap |
| 019 GraphStore Abstraction | ✓ | ✓ | ✓ | In-memory, indexer, projects API |
| 009 API Error Handling | ✓ | ✓ | ✓ | Complete |
| 010 Request Validation | ✓ | ✓ | ✓ | Complete |
| 011 Pagination | ✓ | ✓ | ✓ | Complete |
| 012 Web Skeleton | ✓ | ✓ | ✓ | Next.js 15 + shadcn; build in CI |
| 013 Logging Audit | ✓ | ✓ | ✓ | RUNBOOK, no-secrets, format (docs) |
| 014 Deploy Readiness | ✓ | ✓ | ✓ | DEPLOY.md, CORS env, health (test_health) |
| 016 Holdout Tests | ✓ | ✓ | ✓ | Pattern implemented |
| 017 Web CI | ✓ | ✓ | ✓ | Web build in test.yml CI |
| 018 Coherence Algorithm Spec | ✓ | ✓ | ✓ | COHERENCE-ALGORITHM-SKETCH; spec 020 impl |
| 020 Sprint 2 Coherence API | ✓ | ✓ | ✓ | GET /coherence; real downstream_impact + dependency_health |
| 021 Web Project Search UI | ✓ | ✓ | ✓ | /search, /project/[eco]/[name]; build in CI |
| 022 Sprint 3 Import Stack | ✓ | ✓ | ✓ | POST lockfile; tests in test_import_stack |
| 023 Web Import Stack UI | ✓ | ✓ | ✓ | /import; file upload; build in CI |
| 024 PyPI Indexing | ✓ | ✓ | ✓ | index_pypi.py; deps.dev + PyPI; GET /projects/pypi/ tested |
| 025 requirements.txt Import | ✓ | ✓ | ✓ | POST accepts .txt; pypi lookup; tests pass |
| PLAN Month 1 (Graph, indexer) | ✓ | — | — | MVP done via 019 |

| 006 Overnight Backlog | ? | ? | ? | Pending |
| 015 Placeholder | ? | ? | ? | Pending |
| 026 Pipeline Observability And Auto Review | ? | ? | ? | Pending |
| 027 Fully Automated Pipeline | ✓ | ✓ | ✓ | Auto-update, metrics, attention |
| 028 Parallel By Phase Pipeline | ✓ | ✓ | ✓ | workers=5, meta-ratio, atomic state |
| 029 GitHub API Integration | ? | ✓ | ? | P0 for coherence; spec only |
**Present:** Implemented. **Missing:** Not implemented. **Shortcuts:** See below.

---

## Known Shortcuts / Limitations

| Item | Status | Action |
|------|--------|--------|
| **Agent runner test** | Smoke test only — verifies script runs, no import error. Does *not* run full E2E (API + poll + execute). | Full E2E: run API in one terminal, `python scripts/agent_runner.py --once` in another. |
| **In-memory store** | MVP; spec 002 notes future PostgreSQL. | No action until migration spec. |
| **Diagnostic endpoints** | GET /diagnostics, POST /test-send not in specs. | Operational tooling; keep. |

**No mocks, no fake data** in tests. Real `ASGITransport(app=app)` and in-memory store.

---

## Holdout Tests (spec 016)

| Location | Purpose |
|----------|---------|
| `api/tests/holdout/` | Tests excluded from agent context; prevent "return true" gaming |
| CI | Runs full suite including holdout: `pytest -v` |
| Project manager validation | Runs `pytest --ignore=tests/holdout` so agent impl is validated against visible tests only |
| Holdout failure | CI fails; agent never saw the test, so cannot game it |

---

## Spec 001: Health Check

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GET /api/health returns 200 | `routers/health.py` | `test_health_returns_200` |
| Response is valid JSON (Content-Type application/json; body parses as JSON) | `routers/health.py` | `test_health_response_is_valid_json` |
| Response includes required fields (status, version, timestamp; basic ISO8601) | `routers/health.py` | `test_health_returns_valid_json` |
| timestamp is ISO8601 UTC (parseable; Z or +00:00) | `routers/health.py` | `test_health_timestamp_iso8601_utc` |
| Response has exactly the required keys (no extra top-level keys) | `routers/health.py` | `test_health_response_schema` |
| version is semantic-version format (^\d+\.\d+\.\d+) | `routers/health.py` | `test_health_version_semver` |

**Files:** `api/app/main.py`, `api/app/routers/health.py`, `api/tests/test_health.py`

---

## Spec 002: Agent Orchestration API

| Requirement | Implementation | Test |
|-------------|----------------|------|
| POST /api/agent/tasks | `routers/agent.py`, `agent_service.py` | `test_post_task_returns_201_with_routed_model_and_command` |
| GET /api/agent/tasks (filters) | `routers/agent.py` | `test_get_tasks_list_with_filters` |
| GET /api/agent/tasks/{id} | `routers/agent.py` | `test_get_task_by_id_404_when_missing`, `test_get_task_by_id_returns_full_task` |
| PATCH /api/agent/tasks/{id} | `routers/agent.py` | `test_patch_task_updates_status` |
| GET /api/agent/route | `routers/agent.py` | `test_route_endpoint_returns_model_and_template` |
| Routing: impl→local, heal→subscription | `agent_service.py` | `test_impl_tasks_route_to_local`, `test_heal_tasks_route_to_claude` |

**Files:** `api/app/models/agent.py`, `api/app/services/agent_service.py`, `api/app/services/telegram_adapter.py`, `api/app/routers/agent.py`, `api/app/main.py`, `api/tests/test_agent.py`

**Note:** Command templates use `--agent {name}` (subagents) per AGENT-ARCHITECTURE; spec 002 showed `--allowedTools` as example.

---

## Spec 003: Agent-Telegram Decision Loop

| Requirement | Implementation | Test |
|-------------|----------------|------|
| /reply {task_id} {decision} | Webhook handler in `routers/agent.py` | `test_reply_command_records_decision_and_updates_status` |
| /attention | Webhook handler, `get_attention_tasks` | `test_attention_lists_only_needs_decision_and_failed` |
| progress_pct, current_step, decision_prompt, decision | `models/agent.py`, `agent_service.py` | `test_patch_accepts_progress_and_decision` |
| PATCH extended fields | `agent_service.update_task` | (above) |
| Agent runner script | `api/scripts/agent_runner.py` | `test_agent_runner_polls_and_executes_one_task` |
| Alert includes decision_prompt | `_format_alert` in router | (manual via Telegram) |

**Files:** `api/app/models/agent.py`, `api/app/services/agent_service.py`, `api/app/routers/agent.py`, `api/scripts/agent_runner.py`

---

## Spec 007: Sprint 0 Landing

| Requirement | Implementation | Test |
|-------------|----------------|------|
| Root returns name, version, docs, health | `main.py` root handler | `test_root_returns_landing_info` |
| GET /docs reachable | FastAPI built-in | `test_docs_returns_200` |

**Files:** `api/app/main.py`, `api/tests/test_health.py`

---

## Spec 008: Sprint 1 Graph Foundation

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GraphStore, indexer, project/search API | spec 019 (InMemoryGraphStore, indexer, projects router) | test_projects, test_graph_store |
| Index ≥ 5K packages | `scripts/index_npm.py` | Manual run |

**Status:** API + indexer via 019; 5K via `index_npm.py --target 5000`. PyPI via spec 024.

---

## Spec 009: API Error Handling

| Requirement | Implementation | Test |
|-------------|----------------|------|
| 404/400/422/500 consistent schema | `main.py` exception handler, routers | `test_get_task_by_id_404`, `test_post_task_*_422`, `test_patch_*_422`, `test_unhandled_exception_returns_500` |

---

## Spec 010: Request Validation

| Requirement | Implementation | Test |
|-------------|----------------|------|
| task_type enum, direction 1–5000, progress_pct 0–100 | `models/agent.py` Field constraints | `test_post_task_*_422`, `test_patch_task_progress_pct_*_422` |

---

## Spec 011: Pagination

| Requirement | Implementation | Test |
|-------------|----------------|------|
| limit, offset on GET /api/agent/tasks | `routers/agent.py`, `agent_service.py` | `test_get_tasks_list_with_filters` (pagination) |

---

## Spec 022 + 025: Import Stack (lockfile + requirements.txt)

| Requirement | Implementation | Test |
|-------------|----------------|------|
| POST /api/import/stack (package-lock.json) | `routers/import_stack.py`, `import_stack_service.py` | `test_import_stack_returns_200_with_packages_and_risk`, `test_import_stack_known_package_has_coherence`, `test_import_stack_unknown_package_has_unknown_status` |
| POST /api/import/stack (requirements.txt) | `parse_requirements`, `process_requirements` | `test_import_stack_requirements_txt_returns_200`, `test_import_stack_requirements_unknown_package` |
| Invalid JSON / no file | Router validation | `test_import_stack_invalid_json_returns_400`, `test_import_stack_no_file_returns_400` |

**Files:** `api/app/routers/import_stack.py`, `api/app/services/import_stack_service.py`, `api/app/models/import_stack.py`, `api/tests/test_import_stack.py`

---

## Spec 019: GraphStore Abstraction

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GraphStore interface | `adapters/graph_store.py` | `test_graph_store.py` |
| In-memory + JSON persist | `InMemoryGraphStore` | `test_upsert_and_get_project`, `test_count_projects` |
| GET /api/projects | `routers/projects.py` | `test_get_project_returns_200_when_exists`, `test_get_project_returns_404_when_missing`, `test_get_project_pypi_returns_200_when_exists` |
| GET /api/search | `routers/projects.py` | `test_search_returns_matching_results` |
| Indexer (deps.dev + npm) | `services/indexer_service.py`, `scripts/index_npm.py` | Manual: `index_npm.py --limit 3` |
| Indexer (deps.dev + pypi) | `index_pypi_packages`, `scripts/index_pypi.py` | Manual: `index_pypi.py --limit 3` |

**Files:** `api/app/adapters/graph_store.py`, `api/app/models/project.py`, `api/app/routers/projects.py`, `api/app/services/indexer_service.py`, `api/scripts/index_npm.py`, `api/scripts/index_pypi.py`

---

## Files Not in Specs (Operational / Tooling)

| File | Purpose |
|------|---------|
| `api/app/services/telegram_diagnostics.py` | In-memory webhook/send diagnostics for debugging |
| `api/app/routers/agent.py` | GET /diagnostics, POST /test-send (diagnostic endpoints) |
| `api/scripts/telegram_diagnostics.py` | CLI to run diagnostics |
| `api/scripts/test_agent_run.py` | Create task + optionally run command |
| `api/scripts/test_routing.py` | Verify routing per task_type |
| `api/scripts/test_telegram.py` | Send test alert to Telegram |
| `api/scripts/setup_ollama_claude.sh` | Setup Ollama + Claude Code |
| `api/scripts/setup_telegram_webhook.sh` | Set webhook URL |
| `api/scripts/start_with_telegram.sh` | Start API + tunnel + webhook |

These support development and operations; they are not spec'd but are documented in `docs/API-KEYS-SETUP.md`, `docs/SETUP.md`.

---

## Documents

| Doc | Purpose |
|-----|---------|
| `AGENT-FRAMEWORKS.md` | Framework candidates; points to research |
| `AGENT-FRAMEWORKS-RESEARCH.md` | Detailed research (Agent Zero, OpenClaw, SKILL) |
| `AGENT-ARCHITECTURE.md` | Read/Edit/Execute, subagents, Spec Guard |
| `API-KEYS-SETUP.md` | Webhook, Ollama, keys setup |
| `MODEL-ROUTING.md` | Task type → model routing |
| `PLAN.md` | Vision, roadmap |
| `REFERENCE-REPOS.md` | Symlinks to Crypo-Coin, Living-Codex |
| `SETUP.md` | API setup, tests, env |
| `RUNBOOK.md` | Ops: log locations, restart, pipeline recovery |
| `GLOSSARY.md` | Terms: coherence, backlog, pipeline, etc. |
| `DEPLOY.md` | Deploy checklist, env vars, health probes |

`AGENT-FRAMEWORKS.md` and `AGENT-FRAMEWORKS-RESEARCH.md` are complementary (short index vs detailed research).

---

## Test Data

- **No mocks** — Tests use `ASGITransport(app=app)` with real FastAPI app.
- **In-memory store** — Reset per test via `reset_store` fixture.
- **Realistic data** — Directions like "Add GET /api/projects endpoint" are representative, not fake IDs.

---

## Patterns Used

- **FastAPI** — Industry-standard async API framework
- **Pydantic** — Request/response validation
- **In-memory store** — MVP; spec notes future PostgreSQL
- **Telegram** — OpenClaw-style gateway (docs/AGENT-FRAMEWORKS-RESEARCH)
- **Subagents** — Claude Code `.claude/agents/` (docs/AGENT-ARCHITECTURE)
- **Skills** — AgentSkills SKILL.md format (docs/AGENT-FRAMEWORKS-RESEARCH)
