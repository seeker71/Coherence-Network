# Coherence Network — Project Configuration

## Overview

Coherence Network is operated as a spec-driven OSS intelligence platform.

## Active Priorities

1. API and graph correctness
2. Pipeline stability and observability
3. Fast, test-backed implementation cycles
4. Clear status/spec documentation alignment

## Architecture

- **API**: FastAPI (Python) in `api/`
- **Web**: Next.js 15 + shadcn/ui in `web/`
- **Graph DB**: Neo4j
- **Relational DB**: PostgreSQL
- **Specs**: `specs/`

## Workflow: Spec → Test → Implement → CI → Review → Merge

1. **Spec** — approved spec in `specs/`
2. **Test** — expected behavior encoded in tests
3. **Implement** — implementation to satisfy tests
4. **CI** — automated validation
5. **Review** — human approval

## Key Conventions

- API paths: `/api/{resource}/{id}`
- All responses: Pydantic models
- Coherence scores: 0.0–1.0
- Dates: ISO 8601 UTC

## Agent Guardrails

- Do not modify tests to force passing behavior.
- Implement exactly what the spec requires.
- For spec authoring/updates, run `python3 scripts/validate_spec_quality.py` before implementation.
- Every changed feature spec must include explicit `Verification`, `Risks and Assumptions`, and `Known Gaps and Follow-up Tasks` sections.
- Keep changes scoped to requested files/tasks.
- Escalate via `needs-decision` for security-sensitive or high-impact architecture changes.
- **Every new idea discussed in a session MUST be recorded via `POST /api/ideas` before the session ends.** Ideas are the atomic unit — if it's not in the system, it doesn't exist for tracking, attribution, or value lineage. See `docs/RUNBOOK.md` § "Idea Tracking" for the full protocol.

## Code Isolation Rules

**NEVER edit files in the main repo path directly.** All work happens in worktrees.

- **Your worktree** is your workspace. Edit files there, commit there, push from there.
- **Main repo** (`/Users/ursmuff/source/Coherence-Network/`) is read-only for agents. The runner lives there — touching it can break running tasks.
- **Worktrees must be rebased** to `origin/main` before starting work. They carry only their own diff, nothing inherited.
- **Ship workflow**: commit in worktree → push worktree branch → create PR → merge to main → deploy VPS → restart runner. Never `git push origin main` from a worktree.

## Runner & Deployment Order

The runner is an **isolated process** with its own code copy. Changing files on disk does not change the running runner.

1. **Commit and push** your changes to a branch
2. **Merge to main** via PR (squash)
3. **Deploy API** to VPS: `ssh root@187.77.152.42 'cd /docker/coherence-network/repo && git pull && cd .. && docker compose build --no-cache api && docker compose up -d api'`
4. **Restart runner** after deploy — kill old process, start new one. The runner self-updates on next poll but only if on `main` branch.
5. **Verify** with `cc nodes` (both nodes show updated SHA) and `curl api/health`

## Provider Model Rules

Each provider runs **only its own models**. Never assign a model from one provider to another.

| Provider | Models it can run | Cannot run |
|----------|-------------------|------------|
| claude | claude-* (haiku, sonnet, opus) | gpt-*, gemini-*, openrouter/* |
| codex | gpt-*, o1-*, o3-* | claude-*, gemini-* |
| cursor | auto, cursor-* | explicit model names from other providers |
| gemini | gemini-* | claude-*, gpt-* |
| openrouter | openrouter/* | anything without openrouter/ prefix |

- Fallback chains stay **within the same provider**. Claude falls back to another Claude model, never to openrouter.
- Routing config: `api/config/model_routing.json`. Validation: `model_routing_loader.validate_model_for_executor()`.
- When diagnosing routing issues, **root-cause first** — understand why the wrong model was selected before blocking anything. Blocking is not a fix.

## Production Deployment (Hostinger VPS)

The site runs at **coherencycoin.com** on a Hostinger VPS (`187.77.152.42`) via Docker Compose behind Cloudflare + Traefik.

### Quick Deploy (after merging to main)

```bash
# SSH key: ~/.ssh/hostinger-openclaw
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network/repo && git pull origin main && \
   cd /docker/coherence-network && docker compose build --no-cache api web && \
   docker compose up -d api web'
```

### Full Deploy Steps

1. **Merge PR to main** — `gh pr merge <PR_NUM> --squash --admin`
2. **SSH into VPS** — `ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42`
3. **Pull latest** — `cd /docker/coherence-network/repo && git pull origin main`
4. **Rebuild** — `cd /docker/coherence-network && docker compose build --no-cache api web`
5. **Restart** — `docker compose up -d api web`
6. **Verify** — `curl https://api.coherencycoin.com/api/health && curl -sI https://coherencycoin.com/`

### Infrastructure

- **VPS**: Hostinger KVM at `187.77.152.42` (hostname: `srv1482815`)
- **SSH key**: `~/.ssh/hostinger-openclaw`
- **Docker services**: `coherence-network-api-1`, `coherence-network-web-1`, `coherence-network-postgres-1`, `coherence-network-neo4j-1`
- **Reverse proxy**: Traefik with Let's Encrypt TLS
- **CDN**: Cloudflare (proxying both `coherencycoin.com` and `api.coherencycoin.com`)
- **Repo on VPS**: `/docker/coherence-network/repo` (tracks `main` branch)
- **Docker Compose**: `/docker/coherence-network/docker-compose.yml`
- **Dockerfiles**: `/docker/coherence-network/Dockerfile.api`, `/docker/coherence-network/Dockerfile.web`

### Push bypass (worktree branches)

```bash
SKIP_PR_GUARD=1 git -c "url.https://x-access-token:$(gh auth token)@github.com/.insteadOf=https://github.com/" push origin <branch>
```

## API Keys & Provider Credentials

**Canonical keystore**: `~/.coherence-network/keys.json` (mode 600, not in git).
This survives `.env` replacements. Code loads from keystore first, `.env` as fallback.

```json
// ~/.coherence-network/keys.json structure:
{
  "openrouter": { "api_key": "sk-or-v1-...", "management_key": "sk-or-v1-..." }
}
```

- **OpenRouter**: Free tier: 26 models, 20 req/min. Key stored in keystore only.
- **VPS**: Keys loaded from keystore or env vars as fallback.
- **Never commit keys to git** — use `~/.coherence-network/keys.json` (mode 600).

## Context-Conscious Exploration

Before scanning many files for a task, run the budget helper first:

- `python3 scripts/context_budget.py <files-or-dirs-or-patterns>`

The helper reports file sizes, estimated token cost, and compact summaries using a cache in
`.cache/context_budget/summary_cache.json`, so future passes avoid re-reading large files.

Suggested workflow:
1. Run a manifest pass to see sizes and estimated token impact.
2. Open only the highest-signal file subset.
3. If a file is large, use a cached summary first (`--force-summaries` only when needed),
   then read targeted line ranges.
