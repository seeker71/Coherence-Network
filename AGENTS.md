# Agent Instructions — Coherence Network

## Project Summary

Coherence Network maps the open source ecosystem as an intelligence graph. Tech stack: FastAPI (Python) API, Next.js 15 web (web/), Neo4j + PostgreSQL.

## Workflow

Spec → Test → Implement → CI → Review → Merge

- Specs in `specs/`
- Tests before implementation
- Do NOT modify tests to make implementation pass
- Only modify files listed in spec/issue

## Key Files

- `CLAUDE.md` — Project config, conventions, guardrails
- `docs/STATUS.md` — Current implementation status, sprint progress
- `docs/SPEC-COVERAGE.md` — Spec → implementation → test mapping
- `docs/SPEC-TRACKING.md` — Quick reference: spec status, test mapping, verification
- `docs/REFERENCE-REPOS.md` — Reference repos (crypo-coin, living-codex); read-only context
- `docs/PLAN.md` — Consolidated vision and roadmap
- `docs/MODEL-ROUTING.md` — AI model cost optimization
- `docs/AGENT-DEBUGGING.md` — Add tasks, run pipeline, debug failures
- `docs/PIPELINE-ATTENTION.md` — What needs attention, fixes, effectiveness checklist
- `docs/PIPELINE-MONITORING-AUTOMATED.md` — Automated monitor: check issues, react, improve
- `docs/META-QUESTIONS.md` — Questions to validate setup, monitoring, effectiveness; catch misconfigurations
- `docs/RUNBOOK.md` — Log locations, restart, pipeline recovery
- `docs/DEPLOY.md` — Deploy checklist
- `docs/GLOSSARY.md` — Terms (coherence, backlog, pipeline)
- `specs/TEMPLATE.md` — Spec format

## Interface

- **Cursor** — Primary manual development interface
- **Chat (Grok, OpenAI)** — Copy/paste for hard framework/architecture issues (no API)
- **Future** — OpenClaw, Agent Zero, etc. when multi-agent framework is set up

## Commands

```bash
# API
cd api && uvicorn app.main:app --reload --port 8000

# Web
cd web && npm run dev

# Tests (CI runs full; PM validation excludes holdout)
cd api && pytest -v
cd api && pytest -v --ignore=tests/holdout   # agent validation

# Scripts
cd api && .venv/bin/python scripts/project_manager.py --dry-run   # preview next task
cd api && .venv/bin/python scripts/run_backlog_item.py --index 5  # run single item
cd api && .venv/bin/python scripts/check_pipeline.py --json       # pipeline status

# Autonomous pipeline (one command, no interaction; fatal issues only)
cd api && ./scripts/run_autonomous.sh

# Or manual: overnight pipeline (API must be running)
cd api && ./scripts/run_overnight_pipeline.sh

# Check what needs attention (run before or during pipeline)
cd api && ./scripts/ensure_effective_pipeline.sh

# With auto-restart on stale version (use watchdog)
PIPELINE_AUTO_RECOVER=1 ./scripts/run_overnight_pipeline_watchdog.sh
```

## Conventions

- **Holdout tests** — `api/tests/holdout/` excluded from agent context; CI runs full suite
- **Overnight backlog** — `specs/006-overnight-backlog.md` (85+ items)
- **Spec cross-links** — specs have "See also" sections
- **Ruff** — `ruff check .` in api/; per-file ignores in pyproject.toml

## Agent Orchestration API (spec 002)

Run the API, then from Cursor (or terminal) call the agent endpoints to route tasks and track status.

```bash
# Start API (if not running)
cd api && uvicorn app.main:app --reload --port 8000
```

**Submit a task and get the command to run:**
```bash
curl -X POST http://localhost:8000/api/agent/tasks \
  -H "Content-Type: application/json" \
  -d '{"direction": "Add GET /api/projects endpoint", "task_type": "impl"}'
```

**List tasks:**
```bash
curl http://localhost:8000/api/agent/tasks
```

**Get routing for a task type (no persistence):**
```bash
curl "http://localhost:8000/api/agent/route?task_type=impl"
```

**Check monitor issues (automated pipeline health):**
```bash
curl http://localhost:8000/api/agent/monitor-issues
```
If `issues` non-empty, follow `suggested_action` per issue (sorted by priority). See `docs/PIPELINE-MONITORING-AUTOMATED.md`.

**Measure pipeline effectiveness (throughput, issues, goal proximity):**
```bash
curl http://localhost:8000/api/agent/effectiveness
```

**Hierarchical status report (Layer 0 Goal → 1 Orchestration → 2 Execution → 3 Attention):**
```bash
curl http://localhost:8000/api/agent/status-report
# Or read: api/logs/pipeline_status_report.txt (human) or .json (machine)
```

**Update status when Claude Code finishes:**
```bash
curl -X PATCH http://localhost:8000/api/agent/tasks/{task_id} \
  -H "Content-Type: application/json" \
  -d '{"status": "completed", "output": "Done"}'
```

Use the `command` from the POST response to run Claude Code. Patch the task when status changes.

### Telegram Integration

Configure `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_IDS`, `TELEGRAM_ALLOWED_USER_IDS` in `.env`. When a task is marked `needs_decision` or `failed`, the router sends an alert to Telegram. To receive and send commands from Telegram:

1. Create bot via @BotFather, get token. Get your chat ID from @userinfobot.
2. Set webhook: `curl "https://api.telegram.org/bot{TOKEN}/setWebhook?url={API_URL}/api/agent/telegram/webhook"`
3. Commands: `/status`, `/tasks`, `/task {id}`, `/direction "..."` or type a direction to create a task.
