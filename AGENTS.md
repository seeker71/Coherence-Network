# Agent Instructions — Coherence Network

## Project Summary

Coherence Network maps the open source ecosystem as an intelligence graph. Tech stack: FastAPI (Python) API, Next.js 15 web (web/), Neo4j + PostgreSQL.

## Workflow

Spec → Test → Implement → CI → Review → Merge

- Specs in `specs/`
- Tests before implementation
- Do NOT modify tests to make implementation pass
- Only modify files listed in spec/issue

## Mandatory Delivery Contract (No Exceptions)

1. Worktree-only execution
   - Never edit or run implementation commands in the primary workspace.
   - Every task must start in a new git worktree under `~/.claude-worktrees/...`.
2. Start gate (required before any edits)
   - Run: `python3 scripts/ensure_worktree_start_clean.py --json`
   - If it fails, stop and fix blockers first.
3. Pre-commit local gate (required)
   - Run: `git fetch origin main && git rebase origin/main` (must be cleanly rebased before push)
   - Run: `python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main`
   - Run: `python3 scripts/check_pr_followthrough.py --stale-minutes 90 --fail-on-stale --strict`
   - If either fails, do not commit.
4. Evidence contract (required per commit)
   - Add/update `docs/system_audit/commit_evidence_<date>_<topic>.json`.
   - Validate it: `python3 scripts/validate_commit_evidence.py --file <path>`.
5. PR + CI contract
   - Open PR immediately after push.
   - Monitor checks until green, or report blocker with failing check links and remediation command.
6. Finish contract
   - No partial/abandoned work. If incomplete, leave explicit blocking status and next exact command.
   - Do not start a new task while previous task has unresolved blocking checks.

## Key Files

- `CLAUDE.md` — Project config, conventions, guardrails
- `docs/WORKTREE-QUICKSTART.md` — Mandatory worktree-only startup flow and failure recovery
- `docs/STATUS.md` — Current implementation status, sprint progress
- `docs/SPEC-COVERAGE.md` — Spec → implementation → test mapping
- `docs/SPEC-TRACKING.md` — Quick reference: spec status, test mapping, verification
- `docs/SPEC-QUALITY-GATE.md` — Required quality contract for changed specs
- `docs/REFERENCE-REPOS.md` — Reference repos (crypo-coin, living-codex); read-only context
- `docs/PLAN.md` — Consolidated vision and roadmap
- `docs/MODEL-ROUTING.md` — AI model cost optimization
- `docs/AGENT-DEBUGGING.md` — Add tasks, run pipeline, debug failures
- `docs/PIPELINE-ATTENTION.md` — What needs attention, fixes, effectiveness checklist
- `docs/PIPELINE-MONITORING-AUTOMATED.md` — Automated monitor: check issues, react, improve
- `docs/META-QUESTIONS.md` — Questions to validate setup, monitoring, effectiveness; catch misconfigurations
- `docs/RUNBOOK.md` — Log locations, restart, pipeline recovery
- `docs/PR-CHECK-FAILURE-TRIAGE.md` — PR check failure detection, auto-retry, remediation mapping
- `docs/DEPLOY.md` — Deploy checklist
- `docs/GLOSSARY.md` — Terms (coherence, backlog, pipeline)
- `specs/TEMPLATE.md` — Spec format

## Interface

- **Cursor** — Primary manual development interface
- **Chat (Grok, OpenAI)** — Copy/paste for hard framework/architecture issues (no API)
- **Future** — OpenClaw, Agent Zero, etc. when multi-agent framework is set up

## Commands

```bash
# Mandatory first step for every thread
python3 scripts/ensure_worktree_start_clean.py --json

# Worktree setup for Codex thread start
git fetch origin main
git worktree add ~/.claude-worktrees/Coherence-Network/<thread-name> -b codex/<thread-name> origin/main
cd ~/.claude-worktrees/Coherence-Network/<thread-name>
python3 scripts/ensure_worktree_start_clean.py --json

# API
cd api && uvicorn app.main:app --reload --port 8000

# Web
cd web && npm run dev

# Local worktree web + API validation (Codex default)
./scripts/verify_worktree_local_web.sh
# Optional ports when running multiple worktrees:
API_PORT=18100 WEB_PORT=3110 ./scripts/verify_worktree_local_web.sh
# Optional npm cache override (default is per-worktree .cache/npm):
NPM_CACHE=/tmp/coherence-npm-cache ./scripts/verify_worktree_local_web.sh

# Public production verify (required before merge/roll-forward)
./scripts/verify_web_api_deploy.sh

# Start gate (required before starting a new task)
python3 scripts/ensure_worktree_start_clean.py --json

# PR check failure prevention + tracking (default before commit/push)
python3 scripts/worktree_pr_guard.py --mode local --base-ref origin/main
# Include remote PR check tracking (requires GH_TOKEN/GITHUB_TOKEN):
python3 scripts/worktree_pr_guard.py --mode all --branch "$(git rev-parse --abbrev-ref HEAD)"
# Dedicated triage for open PR check failures (+ optional auto-rerun for flaky GitHub Actions checks):
python3 scripts/pr_check_failure_triage.py --repo seeker71/Coherence-Network --base main --head-prefix codex/ --fail-on-detected
python3 scripts/pr_check_failure_triage.py --repo seeker71/Coherence-Network --base main --head-prefix codex/ --rerun-failed-actions --fail-on-detected
# Tighten deploy freshness requirement if needed (default 6h):
python3 scripts/worktree_pr_guard.py --mode all --branch "$(git rev-parse --abbrev-ref HEAD)" --deploy-success-max-age-hours 2

# Spec quality gate (run when changing specs)
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD

# Tests (CI runs full; PM validation excludes holdout)
cd api && pytest -v
cd api && pytest -v --ignore=tests/holdout   # agent validation

# Scripts
cd api && .venv/bin/python scripts/project_manager.py --dry-run   # preview next task
cd api && .venv/bin/python scripts/run_backlog_item.py --index 5  # run single item
cd api && .venv/bin/python scripts/check_pipeline.py --json       # pipeline status

# Optional PR → public deploy contract validation
cd api && .venv/bin/python scripts/validate_pr_to_public.py --branch codex/<thread-name> --wait-public

# Autonomous pipeline (one command, no interaction; fatal issues only)
cd api && ./scripts/run_autonomous.sh

# Or manual: overnight pipeline (API must be running)
cd api && ./scripts/run_overnight_pipeline.sh

# Check what needs attention (run before or during pipeline)
cd api && ./scripts/ensure_effective_pipeline.sh

# With auto-restart on stale version (use watchdog)
PIPELINE_AUTO_RECOVER=1 ./scripts/run_overnight_pipeline_watchdog.sh
```

## Full Pipeline for Codex Work

- Clone or switch into the linked worktree path for each thread before submitting task commands.
- Keep task execution in worktree mode by running all Codex/agent commands from that worktree.
- Start each run with a file-impact manifest to avoid context overrun:
  - `python3 scripts/context_budget.py <files-or-globs>`
- Cache summaries in `.cache/context_budget/summary_cache.json`.
  - Use `--force-summaries` only when a file changes materially or cache is stale.
- Codex/openclaw execution path is already wired for worktree mode:
  - default command template includes `codex exec ... --model gpt-5.3-codex-spark --reasoning-effort high --worktree`.
  - set `OPENCLAW_MODEL` to override if needed.
- Paid-provider override is accepted by execute endpoint as `force_paid_*` query flags or `X-Force-Paid-Providers` header.
- Suggested full deployment flow:
  - `./scripts/verify_worktree_local_web.sh` (local API+web contract)
  - `./scripts/verify_web_api_deploy.sh` (public API+web contract + CORS)
  - For automated long-running instances, rely on `.github/workflows/public-deploy-contract.yml` (schedule + on-push) and keep `RAILWAY_*` + `GITHUB_TOKEN` secrets set so retries and reporting survive process restarts.
- Keep cost pressure controlled:
  - Set per-task budget inputs where possible (`max_cost_usd`, `estimated_cost_usd`) and environment budgets (`AGENT_TASK_MAX_COST_USD`).
  - Enforce an internal rule to use <=1/3 of known 8h/week usage windows for a single loop before escalation.
  - Treat `cost_overrun` and `paid_provider_blocked` friction events as execution blockers until explicitly reviewed.
  - Paid-provider window settings:
    - `PAID_TOOL_8H_LIMIT` for the rolling 8h call cap.
    - `PAID_TOOL_WEEK_LIMIT` for the rolling 7-day call cap.
    - `PAID_TOOL_WINDOW_BUDGET_FRACTION` for hard cap fraction (default `0.333`).

- Context-budget workflow before large reads:
  - Start each large-read session with `python3 scripts/context_budget.py --token-budget 50000 <file-globs>`.
  - Reuse `.cache/context_budget/summary_cache.json` to choose what to open first.
  - If a file still risks overrun, use `--force-summaries` then read minimal slices.

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
