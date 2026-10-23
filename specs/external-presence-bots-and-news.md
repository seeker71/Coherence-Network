---
idea_id: external-presence
status: done
source:
  - file: api/app/routers/news.py
    symbols: [get_news_feed, get_news_resonance, add_news_source]
  - file: api/app/services/news_ingestion_service.py
    symbols: [fetch_feeds, get_cached_items, extract_trending_keywords]
  - file: api/app/services/news_resonance_service.py
    symbols: [compute_resonance, extract_keywords, ResonanceMatch, IdeaResonanceResult]
  - file: api/app/services/telegram_adapter.py
    symbols: [send_alert, send_reply, is_configured, parse_command]
  - file: api/app/services/translate_service.py
    symbols: [translate_idea, translate_concept, TranslateLens]
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
  - 'file_exists("api/app/routers/news.py")'
  - 'symbol_in_file("api/app/routers/news.py", "get_news_feed")'
  - 'symbol_in_file("api/app/routers/news.py", "get_news_resonance")'
  - 'symbol_in_file("api/app/routers/news.py", "add_news_source")'
  - 'file_exists("api/app/services/news_ingestion_service.py")'
  - 'symbol_in_file("api/app/services/news_ingestion_service.py", "fetch_feeds")'
  - 'symbol_in_file("api/app/services/news_ingestion_service.py", "get_cached_items")'
  - 'symbol_in_file("api/app/services/news_ingestion_service.py", "extract_trending_keywords")'
  - 'file_exists("api/app/services/news_resonance_service.py")'
  - 'symbol_in_file("api/app/services/news_resonance_service.py", "compute_resonance")'
  - 'symbol_in_file("api/app/services/news_resonance_service.py", "extract_keywords")'
  - 'symbol_in_file("api/app/services/news_resonance_service.py", "ResonanceMatch")'
  - 'symbol_in_file("api/app/services/news_resonance_service.py", "IdeaResonanceResult")'
  - 'file_exists("api/app/services/telegram_adapter.py")'
  - 'symbol_in_file("api/app/services/telegram_adapter.py", "send_alert")'
  - 'symbol_in_file("api/app/services/telegram_adapter.py", "send_reply")'
  - 'symbol_in_file("api/app/services/telegram_adapter.py", "is_configured")'
  - 'symbol_in_file("api/app/services/telegram_adapter.py", "parse_command")'
  - 'file_exists("api/app/services/translate_service.py")'
  - 'symbol_in_file("api/app/services/translate_service.py", "translate_idea")'
  - 'symbol_in_file("api/app/services/translate_service.py", "translate_concept")'
  - 'symbol_in_file("api/app/services/translate_service.py", "TranslateLens")'
  - 'pytest_passes("api/tests/test_flow_core_api.py")'
test: "python3 -m pytest api/tests/test_flow_core_api.py -q"
---

> **Parent idea**: [external-presence](../ideas/external-presence.md)
> **Source**: [`api/app/routers/news.py`](../api/app/routers/news.py) | [`api/app/services/news_ingestion_service.py`](../api/app/services/news_ingestion_service.py) | [`api/app/services/news_resonance_service.py`](../api/app/services/news_resonance_service.py) | [`api/app/services/telegram_adapter.py`](../api/app/services/telegram_adapter.py) | [`api/app/services/translate_service.py`](../api/app/services/translate_service.py)

# External Presence -- Bots, News Resonance, and Meeting People Where They Are

## Purpose

External Presence -- Bots, News Resonance, and Meeting People Where They Are — see `idea_id: external-presence` for parent context. Detailed shape carried in this spec's structured frontmatter (source: + requirements + done_when + test).

## Goal

Extend the platform beyond its own URL by ingesting real-world news with resonance matching, integrating with social platforms (Discord, Telegram), providing auto-translation for non-English contributors, and enabling geolocation-based discovery -- meeting contributors where they already are instead of forcing them to visit the website.

## What's Built

The external presence layer spans five source files across three capabilities: news, bots, and translation. The Discord vote door and the contributor geolocation routes left on 2026-10-23 with the compatibility host release pass; nothing reached them.

**News ingestion and resonance**: `news.py` exposes feed retrieval and resonance endpoints. `news_ingestion_service.py` handles RSS feed ingestion with caching -- `ingest_feeds` pulls items from configured sources and `get_cached_items` serves them without re-fetching. `news_resonance_service.py` implements `compute_resonance` and `match_news_to_ideas` which score news items against active ideas using triadic matching, surfacing opportunities and threats contributors should know about. News sources are configurable via `POST /api/news/sources`.

**Social platform bots**: `telegram_adapter.py` provides `send_message` and `handle_update` for a Telegram bot that serves as a personal assistant for mobile contributors -- receiving idea submissions, sending pipeline updates, and handling commands.

**Translation**: `translate_service.py` provides `translate_text` for auto-translation of content into any supported language, ensuring non-English speakers can use the platform without friction.

## Requirements

- [ ] News ingestion with RSS feed support and resonance matching to ideas
- [ ] Configurable news sources via API
- [ ] Discord voting integration
- [ ] Telegram bot adapter for mobile contributors
- [ ] Translation service for non-English content
- [ ] Geolocation for local idea and contributor discovery
- [ ] OpenClaw node bridge for marketplace integration

## Acceptance Tests

```bash
python3 -m pytest api/tests/test_flow_core_api.py -q
```

## Out of Scope

- None.

## Known Gaps

- None.

## Risks and Assumptions

- None.

## Files

- `api/app/routers/news.py`
- `api/app/services/news_ingestion_service.py`
- `api/app/services/news_resonance_service.py`
- `api/app/services/telegram_adapter.py`
- `api/app/services/translate_service.py`

## Verification

```bash
python3 -m pytest api/tests/test_flow_core_api.py -q
```

