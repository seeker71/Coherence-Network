---
idea_id: external-presence
status: done
source:
  - file: api/app/routers/news.py
    symbols: [get_news_feed, get_news_resonance, add_news_source]
  - file: api/app/services/news_ingestion_service.py
    symbols: [ingest_feeds, get_cached_items]
  - file: api/app/services/news_resonance_service.py
    symbols: [compute_resonance, match_news_to_ideas]
  - file: api/app/routers/discord_votes.py
    symbols: [cast_discord_vote]
  - file: api/app/services/telegram_adapter.py
    symbols: [send_message, handle_update]
  - file: api/app/services/translate_service.py
    symbols: [translate_text]
  - file: api/app/routers/geolocation.py
    symbols: [set_location, get_nearby]
requirements:
  - News ingestion with RSS feed support and resonance matching to ideas
  - Configurable news sources via API
  - Discord voting integration
  - Telegram bot adapter for mobile contributors
  - Translation service for non-English content
  - Geolocation for local idea and contributor discovery
  - OpenClaw node bridge for marketplace integration
done_when:
  - GET /api/news/feed returns cached news items
  - GET /api/news/resonance matches news to ideas with scores
  - POST /api/news/sources adds configurable feed
  - Discord and Telegram adapters functional
  - Translation endpoint callable
  - All tests pass
test: "python3 -m pytest api/tests/test_flow_core_api.py -q"
---

> **Parent idea**: [external-presence](../ideas/external-presence.md)
> **Source**: [`api/app/routers/news.py`](../api/app/routers/news.py) | [`api/app/services/news_ingestion_service.py`](../api/app/services/news_ingestion_service.py) | [`api/app/services/news_resonance_service.py`](../api/app/services/news_resonance_service.py) | [`api/app/routers/discord_votes.py`](../api/app/routers/discord_votes.py) | [`api/app/services/telegram_adapter.py`](../api/app/services/telegram_adapter.py) | [`api/app/services/translate_service.py`](../api/app/services/translate_service.py) | [`api/app/routers/geolocation.py`](../api/app/routers/geolocation.py)

# External Presence -- Bots, News Resonance, and Meeting People Where They Are

## Goal

Extend the platform beyond its own URL by ingesting real-world news with resonance matching, integrating with social platforms (Discord, Telegram), providing auto-translation for non-English contributors, and enabling geolocation-based discovery -- meeting contributors where they already are instead of forcing them to visit the website.

## What's Built

The external presence layer spans seven source files across four capabilities: news, bots, translation, and geolocation.

**News ingestion and resonance**: `news.py` exposes feed retrieval and resonance endpoints. `news_ingestion_service.py` handles RSS feed ingestion with caching -- `ingest_feeds` pulls items from configured sources and `get_cached_items` serves them without re-fetching. `news_resonance_service.py` implements `compute_resonance` and `match_news_to_ideas` which score news items against active ideas using triadic matching, surfacing opportunities and threats contributors should know about. News sources are configurable via `POST /api/news/sources`.

**Social platform bots**: `discord_votes.py` implements Discord voting integration so contributors can cast votes from Discord channels without visiting the web UI. `telegram_adapter.py` provides `send_message` and `handle_update` for a Telegram bot that serves as a personal assistant for mobile contributors -- receiving idea submissions, sending pipeline updates, and handling commands.

**Translation**: `translate_service.py` provides `translate_text` for auto-translation of content into any supported language, ensuring non-English speakers can use the platform without friction.

**Geolocation**: `geolocation.py` exposes `set_location` and `get_nearby` for location-aware discovery -- finding nearby contributors, local ideas, and regional news resonance. The platform is globally coherent and locally relevant.

## Requirements

1. News ingestion with RSS feed support and resonance matching to ideas
2. Configurable news sources via API
3. Discord voting integration
4. Telegram bot adapter for mobile contributors
5. Translation service for non-English content
6. Geolocation for local idea and contributor discovery
7. OpenClaw node bridge for marketplace integration

## Acceptance Tests

```bash
python3 -m pytest api/tests/test_flow_core_api.py -q
```
