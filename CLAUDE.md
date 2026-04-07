# Coherence Network

**Mission**: Idea realization platform for humanity. Every idea tracked, funded, built, measured.

## Quick Lookup

| What | Where | CLI |
|------|-------|-----|
| Ideas (12 consolidated) | `ideas/INDEX.md` → `ideas/{slug}.md` | `cc idea {slug}` (DB has raw ideas, not consolidated) |
| Specs (59) | `specs/INDEX.md` → `specs/{slug}.md` | `cc spec {slug}` |
| Pipeline tasks | — | `cc tasks --status pending` |
| Tracking | `docs/EXTERNAL_ENABLEMENT_TRACKING.md` | — |

**Files vs CLI**: The 12 idea .md files have problem statements, capabilities, spec links, and absorbed ideas. The DB has ~300 raw ideas with auto-generated descriptions. For understanding "what are we building," read the .md files. For task pipeline operations, use CLI.

**Spec frontmatter** (~25 lines) has everything an agent needs: `source:` (files + symbols), `requirements:`, `done_when:`, `test:`, `constraints:`. Read with `limit=30` — the body is reference for humans.

## Architecture

- **API**: FastAPI (Python) in `api/`
- **Web**: Next.js 15 + shadcn/ui in `web/`
- **Graph DB**: Neo4j — **Relational DB**: PostgreSQL
- **Tests**: `api/tests/` (177 flow-centric tests, ~8s)

## Workflow

Spec → Test → Implement → CI → Review → Merge

## Key Conventions

- API paths: `/api/{resource}/{id}` — Responses: Pydantic models
- Coherence scores: 0.0–1.0 — Dates: ISO 8601 UTC
- Spec IDs = file stems (e.g. `agent-orchestration-api`) — same as registry key
- Idea IDs = slugs (e.g. `agent-pipeline`) — same as API path and filename

## Agent Guardrails

- Do not modify tests to force passing behavior
- Implement exactly what the spec requires — read the spec frontmatter `source:` map first
- Keep changes scoped to requested files/tasks
- Escalate via `needs-decision` for security or architecture changes
- **Record every new idea via `POST /api/ideas` before session ends**
- For spec authoring: run `python3 scripts/validate_spec_quality.py`

## Navigation

All paths converge: **idea → specs → source files**

| From | How |
|------|----|
| Keyword | `Grep` → source file → spec frontmatter `idea_id:` → `ideas/{id}.md` |
| Idea | `ideas/{slug}.md` spec links → `specs/{slug}.md` `source:` map |
| Code | `Grep` specs/ for filename → spec frontmatter `idea_id:` |
| Task | `cc task {id}` → `context.idea_id` → `ideas/{id}.md` |

## MCP Tools

60 tools. Key operations:

| Verb | MCP tool | CLI equivalent |
|------|----------|---------------|
| Navigate | `coherence_trace` | `cc trace idea {slug}` |
| Advance | `coherence_advance_idea` | — |
| Spec CRUD | `coherence_create_spec`, `coherence_update_spec` | `cc rest POST /api/spec-registry` |
| Task flow | `coherence_task_seed` → `coherence_task_report` | `cc task seed {idea}` → `cc task report` |
| Select work | `coherence_select_idea` | `cc idea select` |

## Context Budget

1. **Spec frontmatter** (25 lines avg) — `Read specs/{slug}.md limit=30` gets source, requirements, done_when, test, constraints. Body (200 lines avg) is human reference — skip unless you need API contract or data model detail.
2. **Idea .md files** (35-52 lines) — problem, capabilities, spec links, absorbed ideas. Always worth reading in full.
3. **CLI** for pipeline operations — `cc tasks`, `cc task {id}`, `cc status`, `cc idea {slug}`
4. For large source files: use targeted line ranges from the `source:` symbols

## Code Isolation

**NEVER edit files in the main repo path.** All work in worktrees.

- Main repo (`/Users/ursmuff/source/Coherence-Network/`) is read-only — runner lives there
- Ship: commit → push branch → PR → merge → deploy VPS → restart runner

## Deploy

```bash
# Quick deploy (after merge to main)
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network/repo && git pull origin main && \
   cd /docker/coherence-network && docker compose build --no-cache api web && \
   docker compose up -d api web'
```

Verify: `curl https://api.coherencycoin.com/api/health`

### Infrastructure

- **VPS**: `187.77.152.42` (Hostinger) — **SSH key**: `~/.ssh/hostinger-openclaw`
- **Services**: api, web, postgres, neo4j via Docker Compose behind Traefik + Cloudflare
- **Repo on VPS**: `/docker/coherence-network/repo` (main branch)
- **Push bypass**: `SKIP_PR_GUARD=1 git -c "url.https://x-access-token:$(gh auth token)@github.com/.insteadOf=https://github.com/" push origin <branch>`

## Provider Model Rules

| Provider | Models | Cannot run |
|----------|--------|------------|
| claude | claude-* | gpt-*, gemini-*, openrouter/* |
| codex | gpt-*, o1-*, o3-* | claude-*, gemini-* |
| cursor | auto, cursor-* | other providers |
| gemini | gemini-* | claude-*, gpt-* |
| openrouter | openrouter/* | anything without prefix |

Fallbacks stay within provider. Config: `api/config/model_routing.json`.

## Multi-Agent Coordination

Multiple agents (Claude Code, Codex, Cursor) may work in parallel on different tasks using git worktrees.

**Before starting work**: Run `python3 scripts/agent_status.py --diff` to check for file-level conflicts with other active worktrees.

**Worktree conventions**:
- Each agent session gets its own worktree under `.claude/worktrees/` or `.codex/worktrees/`
- Never edit files in the main repo path — it's read-only (the runner lives there)
- Ship: commit → push branch → PR → merge

**Conflict avoidance**:
- If `agent_status.py --diff` reports overlapping files, coordinate before proceeding
- Prefer non-overlapping task assignments across agents
- When conflicts are unavoidable, the first PR merged wins — the other rebases

## API Keys

**Keystore**: `~/.coherence-network/keys.json` (mode 600, not in git). Code loads keystore first, `.env` fallback. Never commit keys.
