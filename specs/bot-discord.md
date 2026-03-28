# Spec: Discord bot — channels per idea, slash commands, live pipeline feed

**ID:** bot-discord  
**Status:** implemented  
**Stack:** Discord.js (Node 18+) in `discord-bot/`, FastAPI aggregation in `api/`

## Requirements

1. **Slash commands** (Discord.js application commands):
   - `/cc-idea` — submit a portfolio idea via `POST /api/ideas` with a generated `discord-{user}-{time}` id.
   - `/cc-status` — show pipeline health from `GET /api/integrations/discord/snapshot`.
   - `/cc-stake` — stake CC via `POST /api/ideas/{id}/stake` with `provider: discord` and `provider_id: <snowflake>`.

2. **Channels per active idea** — When `DISCORD_GUILD_ID` and `DISCORD_IDEAS_CATEGORY_ID` are set, periodically sync `GET /api/integrations/discord/ideas/active`, create a text channel per idea under the category, post a rich embed, add 👍/👎 reactions, and create a thread for each unanswered open question.

3. **Live pipeline feed** — When `DISCORD_PIPELINE_FEED_CHANNEL_ID` is set, poll the snapshot endpoint and post new runtime events (deduped by event id in `discord-bot/data/seen-event-ids.json`).

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/integrations/discord/snapshot` | Pipeline loop + agent pipeline + active ideas + recent runtime events |
| GET | `/api/integrations/discord/ideas/active` | Active ideas as card-shaped JSON |

## Environment (discord-bot)

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | yes | Bot token |
| `DISCORD_CLIENT_ID` | yes | Application id for REST command registration |
| `DISCORD_GUILD_ID` | no | Guild for guild-scoped commands and channel sync |
| `DISCORD_IDEAS_CATEGORY_ID` | no | Parent category for idea channels |
| `DISCORD_PIPELINE_FEED_CHANNEL_ID` | no | Text channel for runtime feed posts |
| `COHERENCE_API_BASE_URL` | no | Default `https://api.coherencycoin.com` |
| `DISCORD_FEED_POLL_MS` | no | Default 60000 |
| `DISCORD_CHANNEL_SYNC_MS` | no | Default 300000 |

## Files

- `api/app/services/discord_integration_service.py`
- `api/app/routers/discord_integration.py`
- `api/app/main.py` (router include)
- `discord-bot/package.json`
- `discord-bot/src/index.mjs`

## Verification

- `cd api && .venv/bin/python -c "from app.main import app; print([r.path for r in app.routes if 'integrations/discord' in getattr(r,'path','')])"`
- `cd discord-bot && npm install && node --check src/index.mjs` (syntax)

## Risks and Assumptions

- Assumes public read access to snapshot endpoints and unauthenticated `POST /api/ideas` / stake as in current API policy; production may require API keys or bot-only proxy.
- Discord Message Content intent is requested for future features; channel sync may need **Manage Channels** permission.
- First feed poll seeds seen ids without posting to avoid flooding history.

## Known Gaps and Follow-up Tasks

- OAuth2 link flow for named contributor profiles instead of raw `discord:{id}` identities.
- Optional `POST` webhook from API to Discord instead of polling for lower latency feed.
- Dashboard for reaction counts mapped back to governance votes.
