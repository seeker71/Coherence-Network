# Spec 151 — Configurable News Sources

**Idea ID**: configurable-news-sources
**Status**: In Progress
**Author**: Product Manager Agent
**Date**: 2026-03-28
**Priority**: High

---

## Summary

News sources are currently partially configurable via a JSON config file. This spec formalises the full feature: CRUD API for sources, CLI management commands, database-backed persistence, support for RSS/Atom/JSON feed formats, per-contributor topic subscriptions, and source health monitoring. The goal is that news sources become a first-class entity — operators can add, update, and remove feeds without redeploying code.

---

## Problem Statement

Before this feature, RSS feeds were hardcoded in `news_ingestion_service.py`. An operator who wants to add a new feed must edit code and redeploy. This creates:

1. **Slow feedback loops** — feed changes require a deploy cycle.
2. **No visibility** — it is not clear which feeds are healthy or failing.
3. **No personalisation** — all contributors see the same news regardless of interests.
4. **Format lock-in** — only RSS/Atom feeds work; modern JSON Feed sources are unsupported.

---

## Goals

| # | Goal |
|---|------|
| G1 | Sources stored in the database (PostgreSQL), not in code or flat files. |
| G2 | Full CRUD via REST API — add, list, update, delete sources. |
| G3 | CLI commands: `cc news sources`, `cc news add <url> <name>`, `cc news remove <id>`. |
| G4 | Support RSS 2.0, Atom 1.0, and JSON Feed 1.1 feed formats. |
| G5 | Per-contributor topic subscriptions — contributors subscribe to topics, not just raw feeds. |
| G6 | Source health monitoring — track last-fetch status, error counts, and mark dead feeds. |

---

## Non-Goals

- Real-time push from sources (polling only).
- Full-text search indexing of ingested articles.
- Authenticated (paywalled) feed access.

---

## Data Model

### `news_source` table (PostgreSQL)

```sql
CREATE TABLE news_source (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    url              TEXT NOT NULL UNIQUE,
    type             TEXT NOT NULL DEFAULT 'rss',  -- 'rss' | 'atom' | 'json'
    categories       TEXT[],                        -- e.g. ['technology', 'ai']
    ontology_levels  TEXT[],                        -- e.g. ['layer-3', 'layer-5']
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    update_interval_minutes INTEGER NOT NULL DEFAULT 60,
    priority         INTEGER NOT NULL DEFAULT 50,
    -- Health fields
    last_fetched_at  TIMESTAMPTZ,
    last_fetch_ok    BOOLEAN,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `contributor_topic_subscription` table

```sql
CREATE TABLE contributor_topic_subscription (
    id              SERIAL PRIMARY KEY,
    contributor_id  TEXT NOT NULL,
    topic           TEXT NOT NULL,     -- e.g. 'ai', 'crypto', 'climate'
    weight          FLOAT NOT NULL DEFAULT 1.0,  -- boost factor for resonance
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (contributor_id, topic)
);
```

**Note**: Until DB migration is complete, sources continue to be stored in `config/news-sources.json` with health data added as new fields. The DB migration path is tracked as a follow-up task.

---

## API Endpoints

All endpoints live under the `/api` prefix.

### Source CRUD

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/news/sources` | None | List all sources (optional `?active_only=true`) |
| `GET`  | `/api/news/sources/{id}` | None | Get a single source by ID |
| `POST` | `/api/news/sources` | API Key | Add a new source |
| `PATCH`| `/api/news/sources/{id}` | API Key | Update a source (partial) |
| `DELETE` | `/api/news/sources/{id}` | API Key | Remove a source |

### Source Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/news/sources/{id}/health` | None | Health details for one source |
| `POST` | `/api/news/sources/{id}/check` | API Key | Trigger an immediate health check |

### Contributor Topic Subscriptions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/api/contributors/{contributor_id}/topics` | None | List topic subscriptions |
| `POST` | `/api/contributors/{contributor_id}/topics` | API Key | Add a topic subscription |
| `DELETE` | `/api/contributors/{contributor_id}/topics/{topic}` | API Key | Remove a topic subscription |

### POST /api/news/sources — Request Body

```json
{
  "id": "mit-tech-review",
  "name": "MIT Technology Review",
  "url": "https://www.technologyreview.com/feed/",
  "type": "rss",
  "categories": ["technology", "ai"],
  "ontology_levels": ["layer-3"],
  "is_active": true,
  "update_interval_minutes": 60,
  "priority": 30
}
```

Required fields: `id`, `url`. All others have defaults.
`type` must be one of `"rss"`, `"atom"`, `"json"`.

### POST /api/news/sources — Response (201 Created)

```json
{
  "id": "mit-tech-review",
  "name": "MIT Technology Review",
  "url": "https://www.technologyreview.com/feed/",
  "type": "rss",
  "categories": ["technology", "ai"],
  "ontology_levels": ["layer-3"],
  "is_active": true,
  "update_interval_minutes": 60,
  "priority": 30,
  "last_fetched_at": null,
  "last_fetch_ok": null,
  "consecutive_failures": 0,
  "last_error": null,
  "created_at": "2026-03-28T20:00:00Z"
}
```

### GET /api/news/sources/{id}/health — Response

```json
{
  "id": "hackernews",
  "name": "Hacker News",
  "url": "https://news.ycombinator.com/rss",
  "is_active": true,
  "last_fetched_at": "2026-03-28T19:45:00Z",
  "last_fetch_ok": true,
  "consecutive_failures": 0,
  "last_error": null,
  "status": "healthy"  // "healthy" | "degraded" | "dead"
}
```

Health status rules:
- `healthy`: `last_fetch_ok == true` and `consecutive_failures == 0`
- `degraded`: `consecutive_failures` between 1 and 4
- `dead`: `consecutive_failures >= 5` or `is_active == false`

---

## CLI Commands

### List sources

```
cc news sources
```

Output:
```
  NEWS SOURCES (4)
  ────────────────────────────────────────────────────────────
  hackernews       Hacker News       https://news.ycombinator.com/rss   healthy
  techcrunch       TechCrunch        https://techcrunch.com/feed/        healthy
  mit-tech-review  MIT Tech Review   https://technologyreview.com/feed/  degraded
  dead-feed        Dead Feed         https://example.com/broken          dead
```

### Add a source

```
cc news add <url> <name> [--category <cat>] [--type rss|atom|json]
```

Example:
```
cc news add https://feeds.arstechnica.com/arstechnica/index "Ars Technica" --category technology
```

### Remove a source

```
cc news remove <id>
```

Example:
```
cc news remove dead-feed
```

### Check health

```
cc news health
```

Shows all sources with their health status, last fetch time, and error message if any.

---

## Feed Format Support

### RSS 2.0

Standard `<channel>/<item>` structure. Already supported. Fields extracted: `title`, `description`, `link`, `pubDate`.

### Atom 1.0

Already partially supported via namespace detection. Fields extracted: `title`, `link[@href]`, `content` or `summary`, `updated`.

### JSON Feed 1.1

New requirement. JSON Feed ([jsonfeed.org](https://www.jsonfeed.org/version/1.1/)) structure:

```json
{
  "version": "https://jsonfeed.org/version/1.1",
  "title": "My Feed",
  "items": [
    {
      "id": "...",
      "title": "...",
      "url": "...",
      "content_text": "...",
      "date_published": "2026-03-28T10:00:00Z"
    }
  ]
}
```

Detection: if `Content-Type` is `application/feed+json` or `application/json`, or if the URL returns JSON with a `version` field starting with `https://jsonfeed.org`, treat as JSON Feed.

---

## Source Health Monitoring

### Detection Logic

The ingestion service tracks per-source fetch outcomes:

1. On successful fetch: set `last_fetch_ok = true`, `consecutive_failures = 0`, `last_fetched_at = now`.
2. On failed fetch (network error, non-2xx, parse error): increment `consecutive_failures`, set `last_fetch_ok = false`, store error in `last_error`.
3. At `consecutive_failures >= 5`: set `is_active = false` (auto-disable).
4. The `GET /api/news/sources/{id}/health` endpoint computes the `status` field from these values at query time.

### Health Check Trigger

`POST /api/news/sources/{id}/check` immediately fetches the feed (bypassing cache) and updates health fields. Returns the health object.

### CLI health view

`cc news health` calls `GET /api/news/sources` and renders a health table. Dead and degraded sources are highlighted.

---

## Per-Contributor Topic Subscriptions

Contributors can subscribe to **topics** (e.g. `ai`, `crypto`, `climate`). These topics are matched against the `categories` field of news sources and the `keywords` extracted from news items.

### Subscription semantics

- A contributor subscribes to a topic with an optional `weight` (default `1.0`).
- The resonance score for a news item is multiplied by `max(weights)` of matching topics.
- If a contributor has no subscriptions, the existing behaviour (all ideas considered) is unchanged.

### `GET /api/news/resonance/{contributor_id}`

Existing endpoint already returns contributor-filtered results by staked ideas. After this spec is implemented, it additionally boosts items matching the contributor's subscribed topics.

---

## Files to Create / Modify

| File | Action | Description |
|------|--------|-------------|
| `specs/151-configurable-news-sources.md` | Create | This spec |
| `api/app/routers/news.py` | Modify | Add health endpoints; add topic subscription endpoints |
| `api/app/services/news_ingestion_service.py` | Modify | Track health per source; add JSON Feed parser; auto-disable dead feeds |
| `api/app/models/news.py` | Create | Pydantic models for NewsSource, HealthStatus, TopicSubscription |
| `api/app/routers/contributor_topics.py` | Create | Contributor topic subscription CRUD |
| `api/app/services/contributor_topics_service.py` | Create | Business logic for topic subscriptions |
| `api/app/db/migrations/add_news_source_table.sql` | Create | SQL migration for DB-backed storage (follow-up) |
| `config/news-sources.json` | Maintain | Interim storage until DB migration |
| `cli/` (cc CLI package) | Modify | Add `news add`, `news remove`, `news health` subcommands |
| `api/tests/test_news_sources.py` | Create | Tests for all new endpoints and CLI |

---

## Verification Scenarios

### Scenario 1 — Full create-read-update-delete cycle

**Setup**: No source with ID `test-feed` exists.

**Action (Add)**:
```bash
curl -s -X POST $API/api/news/sources \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"id":"test-feed","name":"Test Feed","url":"https://feeds.arstechnica.com/arstechnica/index","type":"rss","categories":["technology"]}'
```
**Expected**: HTTP 201. Response body includes `"id":"test-feed"`, `"name":"Test Feed"`, `"consecutive_failures":0`, `"last_fetch_ok":null`.

**Action (Read)**:
```bash
curl -s $API/api/news/sources/test-feed
```
**Expected**: HTTP 200. Same object returned.

**Action (List)**:
```bash
curl -s $API/api/news/sources
```
**Expected**: HTTP 200. `sources` array contains an entry with `"id":"test-feed"`.

**Action (Update)**:
```bash
curl -s -X PATCH $API/api/news/sources/test-feed \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"priority":10}'
```
**Expected**: HTTP 200. `"priority":10` in response.

**Action (Delete)**:
```bash
curl -s -X DELETE $API/api/news/sources/test-feed \
  -H "X-API-Key: $KEY"
```
**Expected**: HTTP 200. `{"status":"removed","id":"test-feed"}`.

**Verify gone**:
```bash
curl -s $API/api/news/sources/test-feed
```
**Expected**: HTTP 404.

---

### Scenario 2 — Duplicate and invalid input

**Setup**: Source `hackernews` already exists.

**Edge (Duplicate)**:
```bash
curl -s -X POST $API/api/news/sources \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"id":"hackernews","url":"https://news.ycombinator.com/rss"}'
```
**Expected**: HTTP 400. Response body contains error message mentioning `already exists`.

**Edge (Missing URL)**:
```bash
curl -s -X POST $API/api/news/sources \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"id":"bad-source","name":"No URL"}'
```
**Expected**: HTTP 422 or 400. Response indicates `url` is required.

**Edge (Delete non-existent)**:
```bash
curl -s -X DELETE $API/api/news/sources/does-not-exist \
  -H "X-API-Key: $KEY"
```
**Expected**: HTTP 404.

**Edge (Invalid type)**:
```bash
curl -s -X POST $API/api/news/sources \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"id":"bad-type","url":"https://example.com","type":"xml"}'
```
**Expected**: HTTP 422. `type` must be one of `rss`, `atom`, `json`.

---

### Scenario 3 — CLI create and list

**Setup**: API is running locally or at `$API`.

**Action**:
```bash
cc news add https://feeds.arstechnica.com/arstechnica/index "Ars Technica" --category technology
```
**Expected**: Success message. `cc news sources` immediately shows `arstechnica` in the list.

**Action**:
```bash
cc news sources
```
**Expected**: Output table includes `Ars Technica` with its URL.

**Action**:
```bash
cc news remove arstechnica
```
**Expected**: Source removed. Subsequent `cc news sources` does not show it.

---

### Scenario 4 — Source health monitoring

**Setup**: A source with URL pointing to a non-existent host is added:
```bash
curl -s -X POST $API/api/news/sources \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"id":"broken-feed","url":"https://this-does-not-exist-xyz.example/rss","type":"rss"}'
```

**Action** (trigger health check):
```bash
curl -s -X POST $API/api/news/sources/broken-feed/check \
  -H "X-API-Key: $KEY"
```
**Expected**: HTTP 200. Response includes `"last_fetch_ok":false`, `"consecutive_failures":1`, `"last_error"` is non-null, `"status":"degraded"`.

**Action** (check health endpoint):
```bash
curl -s $API/api/news/sources/broken-feed/health
```
**Expected**: HTTP 200. `"status":"degraded"` or `"dead"` (depending on failure count).

**Edge** (after 5 failures): `is_active` automatically set to `false`. Source appears with `status: "dead"` in health listing.

---

### Scenario 5 — JSON Feed format support

**Setup**: A JSON Feed-format source is added:
```bash
curl -s -X POST $API/api/news/sources \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $KEY" \
  -d '{"id":"json-feed-test","url":"https://daringfireball.net/feeds/json","type":"json","name":"Daring Fireball"}'
```

**Action**:
```bash
curl -s "$API/api/news/feed?source=Daring+Fireball&refresh=true"
```
**Expected**: HTTP 200. `items` contains articles from the Daring Fireball JSON Feed with non-empty `title`, `url`, and optionally `published_at`.

**Edge** (wrong content type): If the URL returns XML when `type=json`, the service logs a warning and records a fetch failure for that source rather than crashing the pipeline.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|------------|
| JSON config file is not atomic — concurrent writes could corrupt it | Move to DB (PostgreSQL) ASAP; use file locking as interim measure |
| Auto-disabling dead feeds may surprise operators | Add an alert/notification before disabling; make threshold configurable |
| JSON Feed detection relies on Content-Type which can be misconfigured | Fall back to content sniffing (check `version` field in JSON body) |
| Contributor topic weights can cause resonance score inflation | Cap multiplier at `2.0`; document scoring formula |
| CLI commands require the API to be accessible | CLI must handle connection errors gracefully with a clear message |

---

## Known Gaps and Follow-up Tasks

1. **DB migration**: Sources are currently stored in `config/news-sources.json`. A PostgreSQL migration (`news_source` table) is needed for multi-process deployments and proper concurrency.
2. **Pagination** on `GET /api/news/sources` for operators with many feeds.
3. **Topic suggestion** — derive topic suggestions from existing idea categories and ontology levels.
4. **Feed discovery** — given a website URL, detect the feed URL automatically.
5. **Rate limiting** per-source fetch to avoid hammering slow servers.
6. **Web UI** — `/news/sources` page in the Next.js frontend to manage sources visually.
7. **Webhook notifications** when a source goes dead.

---

## Traceability

- Spec traces to idea: `configurable-news-sources`
- Existing implementation: `api/app/routers/news.py`, `api/app/services/news_ingestion_service.py`
- Related specs: `085-tracked-count-parity-and-source-discovery.md`, `113-ai-agent-biweekly-intelligence-feedback-loop.md`
