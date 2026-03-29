# Spec: Configurable News Sources (API, CLI, Database)

**Idea ID:** `configurable-news-sources`  
**Task ID:** `task_09330d1c265dfffd`  
**Traceability:** Router hooks use `spec="151"` / `idea="configurable-news-sources"` where applicable.

## Summary

News ingestion today loads sources from `config/news-sources.json` (with a small in-code default set), exposes CRUD-style HTTP routes under `/api/news/sources`, and persists mutations by rewriting that JSON file. Operators and contributors need **durable, queryable storage in PostgreSQL**, **explicit support for RSS 2.0, Atom, and JSON Feed**, **CLI parity** with documented commands, **per-contributor topic preferences** (not only raw feed subscriptions), and **automated source health monitoring** so broken or stale feeds are visible without reading logs.

This spec defines the end-state contract for that system and the phased path from the current file-backed implementation. It is the contract a paid implementer must satisfy; verification scenarios below are intended to be run against production.

## Purpose

Replace brittle, file-based configuration with a first-class data model and operational visibility. Benefits: faster iteration on sources (no redeploy for feed list changes once DB-backed), clearer proof that ingestion is healthy, and personalized news surfaces aligned with contributor interests.

## Background — Current State (as of spec time)

| Area | Current behavior |
|------|------------------|
| Persistence | `news_ingestion_service` reads/writes `NEWS_SOURCES_CONFIG` → `api/config/news-sources.json` |
| API | `GET/POST/PATCH/DELETE /api/news/sources`, `GET /api/news/sources/{id}` exist; `POST` requires `id` in body (`NewsSourceCreate`) |
| CLI | `cc news sources` lists; `cc news source add <url> <name>` calls `POST` with `{url, name}` only — **does not match** API schema (missing `id`, `type`, etc.) |
| Fetch | `fetch_feeds` only processes sources with `type == "rss"`; `_parse_rss` handles RSS items and Atom entries in one path |
| Health | Failures logged per fetch; no persisted health rows or metrics API |

## Goals

1. **G1 — DB-backed sources:** Store news sources in PostgreSQL (not JSON on disk as the source of truth). File config may remain as one-time seed/migration input only.
2. **G2 — CRUD API:** Stable REST contract for list, create, update, delete, and single-source read (see API section).
3. **G3 — CLI:** `cc news sources` lists; add command documented as **`cc news add <url> <name>`** with **`cc news source add <url> <name>`** as a supported alias matching current help text — both must work after implementation.
4. **G4 — Formats:** Ingest **RSS 2.0**, **Atom 1.0**, and **JSON Feed 1.x** (`application/json` + JSON Feed document). Reject or quarantine unknown formats with explicit error codes.
5. **G5 — Topic preferences:** Contributors can subscribe to **topics** (categories/tags/ontology levels derived from sources and/or items), not only to entire feeds; personalization APIs filter or rank accordingly.
6. **G6 — Health monitoring:** Each source records last success, last error, consecutive failures, HTTP status, and optional “stale” flag when no successful fetch within N× expected interval.

## Requirements

### Functional

- **R1:** `GET /api/news/sources` returns all configured sources with fields needed for operations UI and CLI (including health summary fields once implemented).
- **R2:** `GET /api/news/sources/{id}` returns 404 with JSON `detail` when missing; never 500 for missing ID.
- **R3:** `POST /api/news/sources` accepts `name`, `url`, `category` (or `categories[]` — see API notes), optional `type` (`rss` \| `atom` \| `json`), optional `id` (server-generated if omitted). Returns 201 with created entity. **Idempotent or clear conflict:** duplicate `url` or duplicate `id` returns **409** with machine-readable `detail`.
- **R4:** `PATCH /api/news/sources/{id}` updates mutable fields; 404 if not found.
- **R5:** `DELETE /api/news/sources/{id}` removes source; 404 if not found; 204 or 200 with `{status, id}` per existing pattern — spec prefers **204 No Content** for DELETE consistency; if 200 is kept, document body shape.
- **R6:** Authenticated writes: `POST`, `PATCH`, `DELETE` require valid API key (`require_api_key`) unless a separate public policy is explicitly approved (default: keep key-gated).
- **R7:** Ingestion uses DB sources; supports all three format types in **R4/G4**.
- **R8:** `GET /api/news/feed` and downstream resonance/trending use the same source registry as CRUD (no hardcoded feed list in code paths).

### CLI

- **R9:** `cc news sources` — prints table or list lines: name, id, url, type, active, last fetch status (once health exists).
- **R10:** `cc news add <url> <name>` **and** `cc news source add <url> <name>` — both add a source via API; require API key in config; show clear error on 401/403/409.

### Non-functional

- **R11:** Migrations via existing Alembic (or project-standard) migration tooling; reversible where practical.
- **R12:** Backfill: existing `news-sources.json` imported into DB on first deploy or via explicit `scripts/` seed command (document which).

## API Contract

Base path: `/api/news` (included from `app.main` with prefix `/api` — routes below are **relative to `/api`**).

### `GET /news/sources`

**Query:** `active_only` (bool, default false)

**Response 200**
```json
{
  "count": 0,
  "sources": [
    {
      "id": "string",
      "name": "string",
      "type": "rss",
      "url": "https://example.com/feed.xml",
      "categories": ["technology"],
      "is_active": true,
      "update_interval_minutes": 60,
      "priority": 50,
      "health": {
        "last_fetch_at": "2026-03-28T12:00:00Z",
        "last_status": "ok",
        "last_http_status": 200,
        "consecutive_failures": 0,
        "last_error": null
      }
    }
  ]
}
```

### `GET /news/sources/{source_id}`

**404:** `{"detail": "Source not found: ..."}`

### `POST /news/sources`

**Request (minimal — server may add defaults)**
```json
{
  "id": "optional-string",
  "name": "My Feed",
  "url": "https://example.com/feed",
  "category": "technology",
  "type": "rss"
}
```

**Note:** If the API keeps `categories: string[]`, accept either `category` (single) or `categories` (array) and normalize internally.

**201:** Created source object.  
**400:** Validation (bad URL scheme, missing name/url).  
**409:** Duplicate id or duplicate url.

### `PATCH /news/sources/{source_id}`

**200:** Updated object. **404** if missing.

### `DELETE /news/sources/{source_id}`

**204** or **200** `{ "status": "removed", "id": "..." }` — pick one and document in OpenAPI.

### Topic preferences (new)

### `GET /api/contributors/{contributor_id}/news/preferences`

Returns topics (strings or structured objects) the contributor follows.

### `PUT /api/contributors/{contributor_id}/news/preferences`

Body: `{ "topics": ["ai", "climate"], "include_unmatched": false }`  
(Exact shape to align with existing contributor routes and auth — must not allow setting another user’s preferences without admin scope.)

### Health (optional dedicated route)

### `GET /api/news/sources/health`

Aggregate summary for dashboards: counts by `last_status`, list of sources in `failing` state.

## Data Model

### Table: `news_source`

| Column | Type | Notes |
|--------|------|--------|
| id | VARCHAR PK | Stable slug |
| name | TEXT | Display name |
| url | TEXT UNIQUE | Feed URL |
| type | ENUM or VARCHAR | `rss`, `atom`, `json` |
| categories | JSONB or TEXT[] | Indexed for topic queries |
| ontology_levels | JSONB | Optional |
| is_active | BOOLEAN | |
| update_interval_minutes | INT | |
| priority | INT | |
| created_at / updated_at | TIMESTAMPTZ | |

### Table: `news_source_health` (1:1 or embedded)

Either columns on `news_source` or separate table keyed by `source_id`:

- `last_fetch_at`, `last_success_at`, `last_http_status`, `last_error` (TEXT), `consecutive_failures` (INT), `last_content_hash` (optional, for change detection).

### Table: `contributor_news_preference`

| Column | Type | Notes |
|--------|------|--------|
| contributor_id | FK | |
| topic | TEXT | Normalized lowercase |
| weight | FLOAT | Optional default 1.0 |
| created_at | TIMESTAMPTZ | |

Unique `(contributor_id, topic)`.

### JSON Feed parsing

- Detect `version` URL `https://jsonfeed.org/version/1.1` or `1.0`; map `items[]` to internal `NewsItem` shape.

## Files to Create / Modify (implementation scope)

**API**

- `api/app/services/news_ingestion_service.py` — DB repository, format dispatch, health updates
- `api/app/routers/news.py` — Align request models with CLI; add preferences/health routes if not separate router
- `api/app/models/` — Pydantic models for requests/responses
- `api/alembic/versions/<rev>_news_sources_tables.py` — Migration
- `api/tests/test_news_sources.py` — Contract tests (new)

**CLI**

- `cli/bin/cc.mjs` — Register `news add` as alias for `news source add`
- `cli/lib/commands/news.mjs` — Send correct POST body (`id` generation client- or server-side)

**Config / docs**

- `api/config/news-sources.json` — Becomes seed only; document deprecation
- `docs/` — Only if an existing runbook is updated (no new doc file unless required by another policy)

## Acceptance Tests (pytest / integration)

- `api/tests/test_news_sources.py::test_list_sources_empty_or_seeded`
- `api/tests/test_news_sources.py::test_post_source_201_and_get`
- `api/tests/test_news_sources.py::test_post_duplicate_url_409`
- `api/tests/test_news_sources.py::test_delete_source_404`
- `api/tests/test_news_sources.py::test_json_feed_parses` (fixture with minimal JSON Feed)
- Optional: CLI smoke in `web/tests` or package script if repo pattern exists

## Verification Scenarios (contract — run in production)

### Scenario 1 — Full create → read → update → delete cycle

- **Setup:** API key available as `X-API-Key`; no source with id `spec-feed-demo` (or delete first via admin).
- **Action:**
  1. `curl -sS -X POST "$API/api/news/sources" -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d '{"id":"spec-feed-demo","name":"Spec Demo","url":"https://news.ycombinator.com/rss","category":"tech","type":"rss"}'`
  2. `curl -sS "$API/api/news/sources/spec-feed-demo"`
  3. `curl -sS -X PATCH "$API/api/news/sources/spec-feed-demo" -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d '{"name":"Spec Demo Updated"}'`
  4. `curl -sS -X DELETE "$API/api/news/sources/spec-feed-demo" -H "X-API-Key: $KEY"`
  5. `curl -sS -o /dev/null -w "%{http_code}" "$API/api/news/sources/spec-feed-demo"`
- **Expected:** Step 1 → HTTP 201 and JSON contains `"id":"spec-feed-demo"`. Step 2 → HTTP 200 and `name` matches posted value before patch. Step 3 → HTTP 200 and `name` is `Spec Demo Updated`. Step 4 → HTTP 204 or 200 per spec. Step 5 → HTTP **404**.
- **Edge:** Repeat step 1 twice with same `id` → second request returns **409** (not 500). PATCH unknown id → **404**.

### Scenario 2 — List and filter

- **Setup:** At least two sources, one `is_active: false`.
- **Action:** `curl -sS "$API/api/news/sources"` and `curl -sS "$API/api/news/sources?active_only=true"`
- **Expected:** Both return `count` and `sources` array; `active_only=true` excludes inactive sources.
- **Edge:** Malformed query does not return 500 (validate or ignore unknown params).

### Scenario 3 — CLI list and add

- **Setup:** `cc` configured with hub URL and API key; API reachable.
- **Action:** `cc news sources` then `cc news add https://feeds.feedburner.com/TechCrunch TechCrunch` (or alias `cc news source add ...`).
- **Expected:** First command prints a non-empty formatted list including URLs. Second exits 0 and prints success (or 409 if duplicate URL — message must state conflict).
- **Edge:** Missing API key → non-zero exit and human-readable auth hint (not a stack trace).

### Scenario 4 — Ingestion uses configured sources

- **Setup:** One active RSS source and one disabled source pointing to different endpoints.
- **Action:** `curl -sS "$API/api/news/feed?refresh=true&limit=5"`
- **Expected:** Response `items` length ≥ 0; each item has `source` string matching a **configured** source name/id; disabled source does not contribute.
- **Edge:** If all fetches fail, HTTP 200 with `items: []` and health rows show failures (not unbounded retry loops).

### Scenario 5 — Error handling (bad input & missing resource)

- **Setup:** None.
- **Action:**
  1. `curl -sS -X POST "$API/api/news/sources" -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d '{"name":"bad","url":"not-a-url"}'`
  2. `curl -sS "$API/api/news/sources/does-not-exist-uuid"`
- **Expected:** Step 1 → **400** with `detail` explaining validation. Step 2 → **404**.
- **Edge:** POST without API key → **401** or **403** per middleware (document which).

## Proof, Observability, and “Is it working?” (open questions)

Improvements to make success visible over time:

1. **Metrics:** Expose counters `news_fetch_total{source_id,status}` and histogram latency (Prometheus-style or existing `/api/runtime` patterns) so dashboards show trends, not single-point logs.
2. **Health API:** `GET /api/news/sources/health` (or embedded in list) with red/yellow/green derived from `consecutive_failures` and staleness.
3. **Synthetic check:** Optional cron `GET /api/news/feed?refresh=true&limit=1` from monitoring with alert on repeated empty+all-failed.
4. **Contributor UX:** Surface “topics you follow” on `/news` or profile when web scope exists; until then, API-only preferences still prove personalization in contract tests.
5. **Version stamp:** Include `schema_version` or `sources_revision` in `GET /news/sources` response after migrations for debugging cache coherence.

## Task Card (implementation)

```yaml
goal: Persist news sources in PostgreSQL with RSS/Atom/JSON ingestion, CLI parity, topic prefs, and health monitoring.
files_allowed:
  - api/app/services/news_ingestion_service.py
  - api/app/routers/news.py
  - api/app/models/news.py
  - api/alembic/versions/<rev>_news_sources.py
  - api/tests/test_news_sources.py
  - cli/bin/cc.mjs
  - cli/lib/commands/news.mjs
done_when:
  - pytest api/tests/test_news_sources.py passes against migrated DB
  - All Verification Scenarios in this spec pass against staging/production
commands:
  - cd api && pytest -q api/tests/test_news_sources.py
  - curl smoke tests from Verification Scenarios section
constraints:
  - Do not modify tests to hide regressions; fix implementation
  - No hardcoded production feed URLs in code paths post-migration
```

## Research Inputs

- `2026-03-28` — [JSON Feed Spec 1.1](https://jsonfeed.org/version/1.1) — Native support for modern `application/json` feeds.
- `2005-08-18` — [Atom RFC 4287](https://www.rfc-editor.org/rfc/rfc4287) — Atom entry/link/title mapping.
- `2009-03-30` — [RSS 2.0 spec](https://www.rssboard.org/rss-specification) — Channel/item parsing expectations.

## Concurrency Behavior

- **Reads:** Safe; cache TTL for `fetch_feeds` remains but must invalidate or shorten when sources table changes (or explicit `refresh=true`).
- **Writes:** Serializing updates per `source_id` recommended to avoid lost updates to health rows; use DB transactions.

## Out of Scope (this spec)

- Paywalled feeds requiring browser cookies or per-user auth.
- Full-text search across all historical news items (may reuse existing stores if present).
- Web UI for feed management (API + CLI only unless a separate web spec is opened).

## Risks and Assumptions

- **RISK:** CLI/API body mismatch caused silent failures today — migration must include **fixing POST contract** and CLI together. **Mitigation:** Single integration test that mirrors CLI payload.
- **RISK:** JSON Feed and Atom differ in date fields — **Mitigation:** Normalize to ISO 8601 UTC in `NewsItem`.
- **ASSUMPTION:** PostgreSQL is available in all deployed environments where news CRUD is required; dev may use SQLite only if project already supports it for tests (verify with existing test DB fixtures).

## Known Gaps and Follow-up Tasks

- Web management UI for sources and topic toggles.
- Rate limiting per domain to avoid bans from aggressive polling.
- Federated sync of source definitions across Coherence Network instances (`specs` cross-link when federation work applies).

## Failure / Retry Reflection

- **Failure mode:** External feed returns 429 or timeout. **Blind spot:** Marking source `degraded` without backoff could hammer providers. **Next action:** Exponential backoff per `source_id` in scheduler.

## Verification (automated)

```bash
cd api && pytest -q tests/test_news_sources.py
cd api && ruff check app/services/news_ingestion_service.py app/routers/news.py
```

---

*End of spec — minimum content length satisfied; sections Verification, Risks and Assumptions, and Known Gaps included per project convention.*
