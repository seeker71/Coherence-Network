# Coherence Network

**Mission**: Idea realization platform for humanity. Every idea tracked, funded, built, measured.

## Quick Lookup (use these before scanning files)

| What | Where | API |
|------|-------|-----|
| Ideas (12) | `ideas/INDEX.md` → `ideas/{slug}.md` | `GET /api/ideas/{slug}` |
| Specs (59) | `specs/INDEX.md` → `specs/{slug}.md` | `GET /api/spec-registry/{slug}` |
| Archived specs (150+) | `docs/specs-archive/` | — |
| Tracking | `docs/EXTERNAL_ENABLEMENT_TRACKING.md` | — |

**Spec frontmatter** has `idea_id`, `status`, and `source` (files + symbols). Read the frontmatter first — it tells you exactly which source files implement the spec.

**Idea frontmatter** has `idea_id`, `title`, `stage`, `work_type`, and `specs` list.

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
- Spec IDs = file stems (e.g. `002-agent-orchestration-api`) — same as registry key
- Idea IDs = slugs (e.g. `agent-pipeline`) — same as API path and filename

## Agent Guardrails

- Do not modify tests to force passing behavior
- Implement exactly what the spec requires — read the spec frontmatter `source:` map first
- Keep changes scoped to requested files/tasks
- Escalate via `needs-decision` for security or architecture changes
- **Record every new idea via `POST /api/ideas` before session ends**
- For spec authoring: run `python3 scripts/validate_spec_quality.py`

## Context-Efficient Exploration

Before scanning many files:
1. Read the relevant INDEX.md (specs or ideas) to find the right file
2. Read the spec frontmatter — it has the `source:` map pointing to exact files and symbols
3. Use `python3 scripts/context_budget.py <files>` for large reads
4. Open only the highest-signal file subset; use targeted line ranges for large files

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

## API Keys

**Keystore**: `~/.coherence-network/keys.json` (mode 600, not in git). Code loads keystore first, `.env` fallback. Never commit keys.
