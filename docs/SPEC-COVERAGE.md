# Spec Coverage — Coherence Network

Audit of spec → implementation → test mapping. All implementations are spec-driven; tests use real API (no mocks).

## Status Summary

| Spec | Present | Spec'd | Tested | Notes |
|------|---------|--------|--------|-------|
| 001 Health | ✓ | ✓ | ✓ | Complete |
| 002 Agent Orchestration | ✓ | ✓ | ✓ | Complete |
| 003 Decision Loop | ✓ | ✓ | ✓ | Agent runner: smoke test only (see shortcuts) |
| 004 CI Pipeline | ✓ | ✓ | ✓ | GitHub Actions for pytest |
| 005+ | — | — | — | Not started |
| PLAN Month 1 (Graph, indexer, Neo4j) | — | — | — | Future |

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

## Spec 001: Health Check

| Requirement | Implementation | Test |
|-------------|----------------|------|
| GET /api/health returns 200 | `routers/health.py` | `test_health_returns_200` |
| Response: status, version, timestamp (ISO8601) | `routers/health.py` | `test_health_returns_valid_json` |

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
