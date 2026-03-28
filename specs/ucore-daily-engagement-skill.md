# Spec: ucore-daily-engagement-skill (OpenClaw daily engagement)

## Goal

Deliver a single API bundle that powers the OpenClaw **coherence-daily-engagement** skill: personalized morning brief (news × staked ideas), ideas with open questions that fit the contributor’s skill surface, pending agent tasks for providers, nearby contributors, and lightweight “network patterns” (trending keywords + recent idea activity).

## Files to modify

- `api/app/models/daily_engagement.py` — response models
- `api/app/services/daily_engagement_service.py` — aggregation logic
- `api/app/routers/daily_engagement.py` — HTTP routes
- `api/app/main.py` — register router
- `specs/ucore-daily-engagement-skill.md` — this spec
- `skills/coherence-network/daily-engagement/SKILL.md` — OpenClaw skill metadata + usage

## API

- `GET /api/engagement/daily/{contributor_id}`
  - Query: `refresh`, `news_limit`, `top_news_matches`, `task_limit`, `peer_limit`
  - Returns JSON matching `DailyEngagementResponse`

## Behavior

1. **Morning brief** — Reuse RSS fetch + `news_resonance_service` with ideas filtered to contributor staked ideas (via contribution ledger); if none staked, use full portfolio (same as `/news/resonance/{id}` fallback).
2. **Ideas needing skills** — Ideas with unanswered `open_questions`; rank by Jaccard overlap between question text and keyword surface from staked ideas; if no stakes, derive a weak keyword surface from the first 40 ideas in the portfolio.
3. **Tasks for providers** — `list_tasks(status=pending)` capped by `task_limit`.
4. **Contributors nearby** — Graph `list_nodes(type=contributor)` excluding the request contributor by name match.
5. **Network patterns** — Top trending keywords from news + `get_resonance_feed` rows.

## Verification

- `cd api && .venv/bin/python -c "from app.main import app; assert any(getattr(r,'path',None)=='/api/engagement/daily/{contributor_id}' for r in app.routes)"`
- `curl -s "http://127.0.0.1:8000/api/engagement/daily/seeker71"` with API running returns JSON keys: `morning_brief`, `ideas_needing_skills`, `tasks_for_providers`, `contributors_nearby`, `network_patterns`

## Risks and Assumptions

- Assumes contribution ledger and graph are available; both degrade gracefully with empty lists.
- Trending and resonance feeds depend on news ingestion and governance data quality.

## Known Gaps and Follow-up Tasks

- Optional web UI card linking to this JSON.
- Stronger “nearby” using graph edges (co-contribution) instead of recency-only listing.
