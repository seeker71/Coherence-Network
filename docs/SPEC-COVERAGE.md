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
| 007 Sprint 0 Landing | ✓ | ✓ | ✓ | Root, /docs, health (007-sprint-0-landing.md) |
| 007 Meta-Pipeline Backlog | — | ✓ | — | Backlog doc (007-meta-pipeline-backlog.md); not impl spec |
| 008 Sprint 1 Graph | ✓ | ✓ | ✓ | Via 019; `--target 5000` closes gap; GET projects/search |
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
| 026 Phase 1 Task Metrics | ? | ✓ | ? | Persist metrics, GET /api/agent/metrics |
| 027 Fully Automated Pipeline | ✓ | ✓ | ✓ | Auto-update, metrics, attention |
| 027 Auto Update Framework | ✓ | ✓ | ✓ | update_spec_coverage.py, CI step |
| 028 Parallel By Phase Pipeline | ✓ | ✓ | ✓ | workers=5, meta-ratio, atomic state |
| 029 GitHub API Integration | ? | ✓ | ? | P0 for coherence; spec only |
| 030 Pipeline Full Automation | ? | ✓ | ? | Auto-commit, meta tasks; pending |
| 030 Spec Coverage Update | ✓ | ✓ | — | Doc-only; this spec |
| 031 Setup Troubleshooting Venv | ? | ✓ | — | SETUP.md; pending |
| 032 Attention Heuristics Pipeline Status | ✓ | ✓ | ✓ | pipeline-status attention flags |
| 033 README Quick Start Qualify | ? | ✓ | — | Doc-only; pending |
| 034 Ops Runbook | ✓ | ✓ | ✓ | RUNBOOK.md; sections present |
| 035 Glossary | ✓ | ✓ | ✓ | docs/GLOSSARY.md; required terms; test_glossary |
| 036 Check Pipeline Hierarchical View | ? | ✓ | ? | check_pipeline.py Goal→PM→Tasks→Artifacts; pending |
| 037 POST invalid task_type 422 | ✓ | ✓ | ✓ | test_post_task_invalid_task_type_returns_422 |
| 038 POST empty direction 422 | ✓ | ✓ | ✓ | test_post_task_empty_direction_returns_422 |
| 039 Pipeline Status Empty State 200 | ✓ | ✓ | ✓ | test_pipeline_status_returns_200_when_no_running_task_empty_state |
| 040 PM load_backlog Malformed Test | ✓ | ✓ | ✓ | test_load_backlog_malformed_missing_numbers; mixed numbered/unnumbered lines |
| 041 PM --state-file Flag Test | ✓ | ✓ | ✓ | test_state_file_flag_uses_alternate_path, test_project_manager_state_file_flag_uses_alternate_state_path |
| 042 PM --reset Clears State Test | ✓ | ✓ | ✓ | test_reset_clears_state_and_starts_from_index_zero |
| 043 Agent spec→local Route Test | ✓ | ✓ | ✓ | test_spec_tasks_route_to_local (GET /route?task_type=spec, tier local) |
| 044 Agent test→local Route Test | ✓ | ✓ | ✓ | test_test_tasks_route_to_local (GET /route?task_type=test, local model) |
| 045 Effectiveness Plan Progress Phase 6  | ? | ? | ? | Pending |
| 046 Agent Debugging Pipeline Stuck Task Hang | ? | ? | ? | Pending |
| 047 Heal Completion Issue Resolutio | ? | ? | ? | Pending |
| 048 Value Lineage and Payout Attribution | ✓ | ✓ | ✓ | idea->spec->impl->usage->payout preview trace API |
| 049 System Lineage Inventory and Runtime Telemetry | ✓ | ✓ | ✓ | unified inventory with runtime usage summary |
| 050 Canonical Route Registry and Runtime Mapping | ✓ | ✓ | ✓ | canonical route contract and runtime idea map |
| 051 Question Answering and Minimum E2E Flow | ✓ | ✓ | ✓ | answer questions + minimum value-lineage E2E check |
| 052 Portfolio Cockpit UI | ✓ | ✓ | ✓ | `/portfolio` human governance workflow |
| 053 Standing Questions ROI and Next Task Generation | ✓ | ✓ | ✓ | standing question policy + auto next-task suggestion |
| 054 Web UI Standing Questions and Cost/Value Signals | ✓ | ✓ | ✓ | web-ui-governance idea + `/portfolio` UI value/cost signals |
| 055 Contributor Attribution and Idea ROI Insights | ✓ | ✓ | ✓ | inventory exposes human/machine attribution + ROI rankings |
| 056 Operating Console Estimated ROI Queue | ✓ | ✓ | ✓ | tracks operating console rank and pulls next estimated-ROI task |
| 057 Inventory Issue Detection and Auto-Tasking | ✓ | ✓ | ✓ | duplicate-question detection + scan endpoint + monitor integration |
| 058 Evidence Contract and Automated ROI Questioning | ✓ | ✓ | ✓ | per-subsystem claim/evidence/falsifier checks + automated evidence scan |
| 059 Core Idea Completeness, Manifestation Visibility, and Question Dedupe | ✓ | ✓ | ✓ | core system/component ideas + manifestations inventory + auto dedupe |
| 060 High-ROI Auto-Answer and Derived Idea Generation | ✓ | ✓ | ✓ | auto-answer top ROI questions + optional derived ideas |
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
| All response fields (status, version, timestamp) are strings | `routers/health.py` | `test_health_response_value_types` |
| Full API contract (200, exact keys, status ok, semver, ISO8601 UTC) | `routers/health.py` | `test_health_api_contract` |

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

## Spec 004: CI Pipeline

| Requirement | Implementation | Test |
|-------------|----------------|------|
| Workflow at .github/workflows/test.yml | `.github/workflows/test.yml` | `test_workflow_file_exists` |
| Triggers on push and pull_request (main/master) | workflow `on:` | `test_workflow_triggers_on_push_and_pull_request` |
| Python 3.13 (latest CI runtime), 3.9+ contract | setup-python step | `test_workflow_uses_python_39_or_newer` |
| pip install -e ".[dev]" in api/ | Install step | `test_workflow_installs_api_dev_deps` |
| pytest -v in api/ | Run API tests step | `test_workflow_runs_pytest_in_api` |
| README CI badge (workflow test.yml) | README.md | `test_readme_has_ci_badge` |

**Files:** `.github/workflows/test.yml`, `README.md`, `api/tests/test_ci_pipeline.py`

**Contract (spec 004):** Workflow present; runs on push/PR to main or master; installs Python 3.9+ (currently pinned to 3.13 in CI), API dev deps, runs pytest -v in api/; README contains badge for test.yml. Tests define the contract; do not modify tests to make implementation pass.

---

## Spec 007: Sprint 0 Landing

| Requirement | Implementation | Test |
|-------------|----------------|------|
| Root returns name, version, docs, health | `main.py` root handler | `test_root_returns_landing_info` |
| Root API contract (200, exact keys, types, docs/health values) | `main.py` root handler | `test_root_landing_api_contract_spec_007` |
| GET /docs reachable | FastAPI built-in | `test_docs_returns_200` |
| Landing verifiable via automated tests | `api/tests/test_health.py` | (above) |

**Files:** `api/app/main.py`, `api/tests/test_health.py`

**Contract (spec 007):** GET / returns 200 with exactly `name`, `version`, `docs`, `health` (no extra keys); `name` and `version` are non-empty strings; `docs` is `/docs`; `health` is `/api/health`. GET /docs returns 200. Tests define the contract; do not modify tests to make implementation pass.

**Note:** Spec 007 has two docs: `007-sprint-0-landing.md` (this section) and `007-meta-pipeline-backlog.md` (backlog of pipeline improvements; not an implementation spec, no test mapping).

---

## Spec 008: Sprint 1 Graph Foundation

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GraphStore, Project nodes, dependency edges | spec 019 `adapters/graph_store.py`, `InMemoryGraphStore` | `test_graph_store.py`: `test_get_project_missing_returns_none`, `test_search` |
| Indexer (deps.dev + npm), index ≥ 5K | `indexer_service.py`, `scripts/index_npm.py` | Manual: `index_npm.py --target 5000` |
| GET /api/projects/{ecosystem}/{name} | `routers/projects.py` | `test_get_project_returns_200_when_exists`, `test_get_project_response_shape_defines_contract_spec_008`, `test_get_project_returns_404_when_missing`, `test_get_project_pypi_returns_200_when_exists` |
| GET /api/search?q= | `routers/projects.py` | `test_search_returns_matching_results`, `test_search_response_shape_defines_contract_spec_008`, `test_search_empty_query_returns_empty` |

**Files:** `api/app/adapters/graph_store.py`, `api/app/routers/projects.py`, `api/app/services/indexer_service.py`, `api/scripts/index_npm.py`, `api/app/models/project.py`, `api/tests/test_projects.py`, `api/tests/test_graph_store.py`

**Contract (spec 008):** GET /api/projects/{eco}/{name} 200: exactly `name`, `ecosystem`, `version`, `description`, `dependency_count` (no extra keys); types string/string/string/string/int. GET /api/search?q= 200: exactly `results` (array) and `total` (int); each result has `name`, `ecosystem`, `description`. Tests define the contract; do not modify tests to make implementation pass.

**Status:** API + indexer via 019; 5K via `index_npm.py --target 5000`. PyPI via spec 024.

---

## Spec 039: Pipeline Status Empty State 200

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GET /api/agent/pipeline-status returns 200 in empty state (no running task) | `routers/agent.py`, `agent_service.get_pipeline_status` | `test_pipeline_status_returns_200_when_no_running_task_empty_state` |
| Response includes running, pending, recent_completed, attention, running_by_phase | pipeline-status handler | (above); `test_pipeline_status_response_shape_defines_contract` |
| running is empty list when no running task | agent_service | (above) |

**Files:** `api/app/routers/agent.py`, `api/app/services/agent_service.py`, `api/tests/test_agent.py`

**Contract (spec 039):** With no running task (empty or only pending/completed), GET /api/agent/pipeline-status returns 200; body includes required keys; `running` is [].

---

## Spec 037: POST invalid task_type 422

| Requirement | Implementation | Test |
|-------------|----------------|------|
| POST /api/agent/tasks with invalid task_type returns 422 | `models/agent.py` TaskType enum, `routers/agent.py` | `test_post_task_invalid_task_type_returns_422` |
| 422 response has detail array; item references task_type (loc/msg/type) | FastAPI/Pydantic validation | (above); test_api_error_handling.py test_spec_009_422_* |

**Files:** `api/app/models/agent.py`, `api/app/routers/agent.py`, `api/tests/test_agent.py`, `api/tests/test_api_error_handling.py`

**Contract (spec 037):** POST with `task_type` not in `{ spec, test, impl, review, heal }` returns 422; detail is array of validation items (spec 009). See also spec 009 (422 schema), spec 010 (task_type enum).

---

## Spec 038: POST empty direction 422

| Requirement | Implementation | Test |
|-------------|----------------|------|
| POST /api/agent/tasks with empty direction returns 422 | `models/agent.py` Field(min_length=1), `routers/agent.py` | `test_post_task_empty_direction_returns_422` |
| 422 response has detail array; item references direction (loc/msg/type) | FastAPI/Pydantic validation | (above); test_api_error_handling.py test_spec_009_422_* |

**Files:** `api/app/models/agent.py`, `api/app/routers/agent.py`, `api/tests/test_agent.py`, `api/tests/test_api_error_handling.py`

**Contract (spec 038):** POST with `direction: ""` (and valid task_type) returns 422; detail is array of validation items (spec 009). See also spec 009 (422 schema), spec 010 (direction min_length).

---

## Spec 040: Project Manager load_backlog Malformed File Test

| Requirement | Implementation | Test |
|-------------|----------------|------|
| Test with backlog file containing both numbered and unnumbered lines | `api/tests/test_project_manager.py` | `test_load_backlog_malformed_missing_numbers` |
| load_backlog returns only parsed items from numbered lines (order preserved); unnumbered lines skipped | `project_manager.load_backlog`, `_parse_backlog_file` | (above): asserts `["First item", "Second item"]` |
| No mocks; real file I/O and real load_backlog | test uses tmp_path, pm.BACKLOG_FILE | (above) |

**Files:** `api/tests/test_project_manager.py`, `api/scripts/project_manager.py`

**Contract (spec 040):** Lines matching `^\d+\.\s+(.+)$` are included; other lines ignored. Test uses mixed content (e.g. "1. First item", "Unnumbered line", "2. Second item") and expects only the two numbered items. See also spec 005 (project manager).

---

## Spec 041: Project Manager --state-file Flag Test

| Requirement | Implementation | Test |
|-------------|----------------|------|
| --state-file uses alternate path for state (read/write) | `project_manager.py` STATE_FILE, load_state/save_state | `test_state_file_flag_uses_alternate_path` (in-process), `test_project_manager_state_file_flag_uses_alternate_state_path` (subprocess --state-file + --dry-run) |
| No mocks; real file I/O | tmp_path, STATE_FILE override or CLI --state-file | (above) |

**Files:** `api/scripts/project_manager.py`, `api/tests/test_project_manager.py`

**Contract (spec 041):** When script is run with `--state-file <path>` (or STATE_FILE set to that path), state is read from and/or written to that path. Subprocess test pre-populates alternate state, runs --dry-run, asserts stdout reflects that state (backlog index, phase, next item).

---

## Spec 042: Project Manager --reset Clears State Test

| Requirement | Implementation | Test |
|-------------|----------------|------|
| --reset clears state and run starts from index 0 | `project_manager.py` --reset handling, state file removal or reset to defaults | `test_reset_clears_state_and_starts_from_index_zero` |
| Test uses --state-file to tmp path so default state not touched | subprocess with --reset --dry-run --state-file <tmp> --backlog <tmp> | (above): pre-populate state with backlog_index=5, assert post-run backlog_index=0, phase=spec |

**Files:** `api/scripts/project_manager.py`, `api/tests/test_project_manager.py`

**Contract (spec 042):** With --reset and --state-file <path>, existing state at that path is cleared; run proceeds from beginning (backlog_index 0, phase "spec"). Either state file is removed or file contains defaults.

---

## Spec 043: Agent Service spec→local Route Test

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GET /api/agent/route?task_type=spec returns 200, model local, tier local | `agent_service.get_route`, ROUTING[TaskType.SPEC], `routers/agent.py` | `test_spec_tasks_route_to_local` |
| Model indicates local (ollama/glm/qwen); tier is "local" | ROUTING in agent_service.py | (above) |

**Files:** `api/app/services/agent_service.py`, `api/app/routers/agent.py`, `api/app/models/agent.py` (RouteResponse with tier), `api/tests/test_agent.py`

**Contract (spec 043):** GET /api/agent/route?task_type=spec returns 200; body has task_type, model, command_template, tier, executor; model string indicates local (ollama/glm/qwen); tier is "local" per routing table (002).

---

## Spec 044: Agent Service test→local Route Test

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GET /api/agent/route?task_type=test returns 200, model local | `agent_service.get_route`, ROUTING[TaskType.TEST], `routers/agent.py` | `test_test_tasks_route_to_local` |
| Model indicates local (ollama/glm/qwen) | ROUTING in agent_service.py | (above) |

**Files:** `api/app/services/agent_service.py`, `api/app/routers/agent.py`, `api/tests/test_agent.py`

**Contract (spec 044):** GET /api/agent/route?task_type=test returns 200; body has model indicating local (ollama/glm/qwen). See also spec 043 (spec→local), spec 002 (routing table).

---

## Spec 034: Ops Runbook

| Requirement | Implementation | Test |
|-------------|----------------|------|
| docs/RUNBOOK.md exists, canonical ops runbook | `docs/RUNBOOK.md` | `test_runbook_md_exists`, `test_runbook_has_all_required_sections` |
| Log Locations section | RUNBOOK.md table (Path, Purpose) | `test_runbook_has_log_locations_section`, `test_runbook_log_locations_has_table` |
| API Restart section | RUNBOOK.md uvicorn, pkill, port | `test_runbook_has_api_restart_section`, `test_runbook_api_restart_documents_uvicorn_pkill_port` |
| Pipeline Recovery section | RUNBOOK.md effectiveness, restart, needs_decision | `test_runbook_has_pipeline_recovery_section`, `test_runbook_pipeline_recovery_documents_effectiveness_restart_needs_decision` |
| Autonomous Pipeline / Pipeline Effectiveness / Key Endpoints | RUNBOOK.md sections | `test_runbook_has_one_of_autonomous_effectiveness_key_endpoints` |
| Indexing (index_npm, index_pypi), check_pipeline, tests/cleanup | RUNBOOK.md | `test_runbook_documents_indexing`, `test_runbook_documents_check_pipeline`, `test_runbook_documents_tests_and_cleanup` |

**Files:** `docs/RUNBOOK.md`, `api/tests/test_runbook.py`

**Contract (spec 034):** RUNBOOK.md exists; contains headings for Log Locations, API Restart, Pipeline Recovery, and at least one of (Autonomous Pipeline, Pipeline Effectiveness, Key Endpoints).

---

## Spec 035: Glossary

| Requirement | Implementation | Test |
|-------------|----------------|------|
| docs/GLOSSARY.md exists, canonical glossary | `docs/GLOSSARY.md` | `test_glossary_md_exists` |
| Table format (Term \| Definition) | GLOSSARY.md table | `test_glossary_has_table_format` |
| Required terms: Backlog, Coherence, Pipeline, Task type, Direction, needs_decision, Agent runner, Project manager, Holdout tests, Spec-driven | GLOSSARY.md definitions | `test_glossary_defines_all_required_terms`, `test_glossary_definitions_non_empty` |
| Coherence score range 0.0–1.0 | GLOSSARY.md Coherence definition | `test_glossary_coherence_score_range` |
| Task type values: spec, test, impl, review, heal | GLOSSARY.md Task type definition | `test_glossary_task_type_values` |

**Files:** `docs/GLOSSARY.md`, `api/tests/test_glossary.py`

**Contract (spec 035):** GLOSSARY.md exists; table with Term/Definition; defines all required terms with non-trivial definitions; Coherence mentions 0.0–1.0; Task type mentions allowed values.

---

## Spec 036: Check Pipeline Hierarchical View

| Requirement | Implementation | Test |
|-------------|----------------|------|
| check_pipeline.py hierarchical view (Goal → PM → Tasks → Artifacts) | `api/scripts/check_pipeline.py` | Pending |
| --hierarchical / --flat, --json with hierarchical structure | Script flags, JSON output | Pending |
| status-report / effectiveness fallback for Goal section | Script reads status-report or GET /api/agent/effectiveness | Pending |

**Files:** `api/scripts/check_pipeline.py`

**Status:** Spec defined; implementation pending. When implemented, add tests and update this section.

---

## Spec 027: Auto Update Framework

| Requirement | Implementation | Test |
|-------------|----------------|------|
| Script runs after pytest, updates SPEC-COVERAGE when tests pass | `api/scripts/update_spec_coverage.py` | `test_update_spec_coverage_dry_run` (test_agent, test_update_spec_coverage) |
| Additive rows only; STATUS update (test count / specs list) | `update_spec_coverage.py` | Script tests in test_update_spec_coverage.py |
| --dry-run, idempotent, CI step after pytest (continue-on-error) | Script, `.github/workflows/test.yml` | `test_update_spec_coverage_dry_run`, `test_ci_runs_update_spec_coverage_after_pytest` |

**Files:** `api/scripts/update_spec_coverage.py`, `docs/SPEC-COVERAGE.md`, `docs/STATUS.md`, `.github/workflows/test.yml`, `api/tests/test_update_spec_coverage.py`

---

## Spec 032: Attention Heuristics Pipeline Status

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GET /api/agent/pipeline-status returns attention object (stuck, repeated_failures, low_success_rate, flags) | `routers/agent.py`, pipeline-status handler; attention from task store + metrics | `test_pipeline_status_returns_200`, `test_pipeline_status_response_shape_defines_contract` |
| Stuck: pending, no running, wait > threshold | Attention logic (e.g. agent_service or pipeline_status) | (above) |
| Repeated failures: last N completed all failed | Attention logic | (above) |
| Low success rate: windowed rate < threshold when sample ≥ min | metrics_service.get_aggregates() | (above) |

**Files:** `api/app/routers/agent.py`, `api/app/services/agent_service.py` (or pipeline-status/attention module), `api/tests/test_agent.py`

**Note:** Configurable thresholds (env) and check_pipeline.py --attention are spec'd but optional; when implemented, add to this section.

---

## Spec 009: API Error Handling

| Requirement | Implementation | Test |
|-------------|----------------|------|
| 404/400/422/500 consistent schema | `main.py` exception handler, `models/error.py` ErrorDetail, routers `responses=` | `test_get_task_by_id_404_when_missing`, `test_post_task_*_422`, `test_patch_*_422`, `test_unhandled_exception_returns_500` |
| 422 validation (FastAPI default) | No override; Pydantic produces detail array | `test_post_task_invalid_task_type_returns_422`, `test_post_task_empty_direction_returns_422` |
| 404 consistency (detail string only) | HTTPException(detail=str); ErrorDetail in OpenAPI | 404 tests assert `body == {"detail": "..."}` and `list(body.keys()) == ["detail"]` |

**Files:** `api/app/main.py`, `api/app/models/error.py`, `api/tests/test_api_error_handling.py`, `api/tests/test_agent.py`, `api/tests/test_health.py`

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

## Spec 048: Value Lineage and Payout Attribution

| Requirement | Implementation | Test |
|-------------|----------------|------|
| POST /api/value-lineage/links creates lineage link (idea/spec/implementation/contributors/cost) | `routers/value_lineage.py`, `services/value_lineage_service.py`, `models/value_lineage.py` | `test_create_and_get_lineage_link` |
| GET /api/value-lineage/links/{id} fetches persisted lineage | same as above | `test_create_and_get_lineage_link` |
| POST /api/value-lineage/links/{id}/usage-events appends measurable value signals | same as above | `test_usage_events_roll_up_to_valuation` |
| GET /api/value-lineage/links/{id}/valuation returns measured value, estimated cost, ROI, event count | same as above | `test_usage_events_roll_up_to_valuation` |
| POST /api/value-lineage/links/{id}/payout-preview returns role-weighted payouts | same as above | `test_payout_preview_uses_role_weights` |
| Missing lineage returns 404 with exact detail | router raises HTTPException | `test_lineage_404_contract` |

**Files:** `api/app/models/value_lineage.py`, `api/app/services/value_lineage_service.py`, `api/app/routers/value_lineage.py`, `api/app/main.py`, `api/tests/test_value_lineage.py`

---

## Spec 049: System Lineage Inventory and Runtime Telemetry

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GET /api/inventory/system-lineage returns unified ideas/questions/specs/implementation usage | `routers/inventory.py`, `services/inventory_service.py` | `test_system_lineage_inventory_includes_core_sections` |
| POST /api/runtime/events ingests runtime telemetry with idea mapping | `routers/runtime.py`, `services/runtime_service.py`, `models/runtime.py` | `test_runtime_event_ingest_and_summary` |
| GET /api/runtime/events returns recent runtime events | same as above | `test_runtime_middleware_records_api_calls` |
| GET /api/runtime/ideas/summary aggregates runtime and estimated cost by idea | same as above | `test_runtime_event_ingest_and_summary` |
| API middleware auto-captures endpoint runtime to telemetry store | `app/main.py` middleware + `services/runtime_service.py` | `test_runtime_middleware_records_api_calls` |
| Web runtime beacon forwards route/runtime telemetry to API | `web/app/api/runtime-beacon/route.ts`, `web/components/runtime-beacon.tsx`, `web/app/layout.tsx` | Web build validation (`npm run build`) |

**Files:** `api/app/models/runtime.py`, `api/app/services/runtime_service.py`, `api/app/services/inventory_service.py`, `api/app/routers/runtime.py`, `api/app/routers/inventory.py`, `api/app/main.py`, `api/tests/test_runtime_api.py`, `api/tests/test_inventory_api.py`, `web/app/api/runtime-beacon/route.ts`, `web/components/runtime-beacon.tsx`, `web/app/layout.tsx`

---

## Spec 050: Canonical Route Registry and Runtime Mapping

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GET /api/inventory/routes/canonical returns canonical route registry | `routers/inventory.py`, `services/route_registry_service.py`, `config/canonical_routes.json` | `test_canonical_routes_inventory_endpoint_returns_registry` |
| Runtime mapping defaults avoid `unmapped` for known API/web surfaces | `services/runtime_service.py` | `test_runtime_default_mapping_avoids_unmapped_for_known_surfaces` |

**Files:** `config/canonical_routes.json`, `api/app/services/route_registry_service.py`, `api/app/routers/inventory.py`, `api/app/services/runtime_service.py`, `api/tests/test_inventory_api.py`, `api/tests/test_runtime_api.py`

---

## Spec 051: Question Answering and Minimum E2E Flow

| Requirement | Implementation | Test |
|-------------|----------------|------|
| POST /api/ideas/{idea_id}/questions/answer persists answer and measured delta | `models/idea.py`, `routers/ideas.py`, `services/idea_service.py` | `test_answer_idea_question_persists_answer` |
| POST /api/value-lineage/minimum-e2e-flow runs minimum end-to-end lineage flow | `models/value_lineage.py`, `routers/value_lineage.py`, `services/value_lineage_service.py` | `test_minimum_e2e_flow_endpoint` |

**Files:** `api/app/models/idea.py`, `api/app/services/idea_service.py`, `api/app/routers/ideas.py`, `api/app/models/value_lineage.py`, `api/app/services/value_lineage_service.py`, `api/app/routers/value_lineage.py`, `api/tests/test_ideas.py`, `api/tests/test_value_lineage.py`

---

## Spec 052: Portfolio Cockpit UI

| Requirement | Implementation | Test |
|-------------|----------------|------|
| `/portfolio` page presents ROI-prioritized unanswered questions and runtime-by-idea summary | `web/app/portfolio/page.tsx` | `npm run build` |
| Home page links to Portfolio Cockpit | `web/app/page.tsx` | `npm run build` |
| Answer action posts to question-answer API | `web/app/portfolio/page.tsx` | Manual public validation |

**Files:** `web/app/portfolio/page.tsx`, `web/app/page.tsx`

---

## Spec 053: Standing Questions, ROI Fields, and Next-Task Generation

| Requirement | Implementation | Test |
|-------------|----------------|------|
| Every idea includes standing improvement/measurement question | `services/idea_service.py` | `test_standing_question_exists_for_every_idea` |
| Inventory exposes question and answer ROI fields | `services/inventory_service.py` | `test_system_lineage_inventory_includes_core_sections` |
| Next highest-ROI task suggestion and optional task creation | `routers/inventory.py`, `services/inventory_service.py` | `test_next_highest_roi_task_generation_from_answered_questions` |

**Files:** `api/app/services/idea_service.py`, `api/app/services/inventory_service.py`, `api/app/routers/inventory.py`, `api/tests/test_inventory_api.py`

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
