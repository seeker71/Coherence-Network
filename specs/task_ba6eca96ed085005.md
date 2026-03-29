# Spec: Configurable news sources — DB-backed feeds, CLI parity, formats, preferences, health

**Idea ID**: `configurable-news-sources` (traceability: `spec="151"` in `api/app/routers/news.py`)  
**Task ID**: `task_ba6eca96ed085005`  
**Status**: Draft — product specification (implementation follows in a separate impl task)  
**Author**: product-manager agent  
**Date**: 2026-03-28

## Summary

News ingestion today is **partially configurable**: the FastAPI router exposes `GET/POST/PATCH/DELETE` under `/api/news/sources`, and the CLI can list sources and add one via `cc news source add <url> <name>`. Persistence is **`config/news-sources.json`** (or `NEWS_SOURCES_CONFIG`) with an in-process cache and **default feeds embedded in code** (`news_ingestion_service._DEFAULT_SOURCES`). Fetching supports **RSS item elements and Atom entries** in one XML path; **`type: "rss"`** gates which sources are fetched, and **JSON Feed** is not implemented. There is **no PostgreSQL table** for sources, **no per-contributor topic subscriptions** beyond stake-filtered resonance, and **no durable feed health metrics**.

This spec closes the gap between “editable file” and **production-grade configuration**: sources and health state live in the **relational DB**, ingestion honors **RSS, Atom, and JSON Feed**, the **CLI** matches documented ergonomics (including optional alias `cc news add` for discoverability), and contributors can **subscribe to topics** with clear **verification and proof signals** over time.

## Purpose

Operators and contributors need to add, remove, and audit news inputs **without redeploying**, with **persistence that survives multi-instance API** deployments, and **observable proof** that feeds work and that personalization matches intent.

## Current baseline (as of spec time)

| Area | Today |
|------|--------|
| List sources | `GET /api/news/sources` → `{ count, sources }` |
| Add source | `POST /api/news/sources` (requires API key) — body includes `id`, `url`, optional `name`, `categories`, etc. |
| Update | `PATCH /api/news/sources/{source_id}` |
| Delete | `DELETE /api/news/sources/{source_id}` |
| Storage | JSON file via `news_ingestion_service`, not SQL |
| CLI list | `cc news sources` → `GET /api/news/sources` |
| CLI add | `cc news source add <url> <name>` — **implementation must send `id` + auth** (see gaps) |
| Formats | RSS + Atom XML in `_parse_rss`; JSON Feed not parsed |
| Health | Log warnings only; no `last_ok`, `last_error`, HTTP status history |

## Requirements

### Must have (MVP for this spec’s implementation phase)

1. **Database as source of truth** — Replace (or migrate from) `news-sources.json` with a `news_source` (name TBD) table in PostgreSQL: `id`, `name`, `url`, `type` (`rss` \| `atom` \| `json`), `categories` (JSON array or junction), `is_active`, `priority`, `update_interval_minutes`, `created_at`, `updated_at`. Seed from existing file/env on first migration.
2. **API contract** — Keep public paths stable:
   - `GET /api/news/sources` — list all (query: `active_only` preserved).
   - `POST /api/news/sources` — create; accept `name`, `url`, `category` or `categories` (normalize to array), optional `id` or **server-generated** opaque id if omitted.
   - `DELETE /api/news/sources/{id}` — remove by primary key.
   - `PATCH /api/news/sources/{id}` — update fields (existing behavior retained).
3. **Formats** — Ingestion must support **RSS 2.0**, **Atom**, and **JSON Feed** (`application/json` / `.json` URLs) with a single internal `NewsItem` model.
4. **CLI** — Support:
   - `cc news sources` — list (unchanged UX; may add columns for health).
   - `cc news source add <url> <name>` — add with API key from user config (existing).
   - **`cc news add <url> <name>`** — **alias** delegating to the same handler as `news source add` (reduces confusion vs docs that say “add”).
5. **Source health monitoring** — Persist per source: `last_fetch_at`, `last_success_at`, `last_http_status`, `last_error` (short text), `consecutive_failures`. Update on each fetch attempt. Expose **read-only** fields on `GET /api/news/sources` (and optional `GET /api/news/sources/{id}`).
6. **Tests** — `pytest` coverage for CRUD, duplicate id, bad URL, JSON Feed parsing, and health fields updated after mocked fetch.

### Should have (phase 2 — may be separate PR if scoped)

7. **Per-contributor source/topic preferences** — Data model: `contributor_news_preference` linking `contributor_id` to `topic` strings and/or `source_id` with `enabled`. Filter `GET /api/news/feed` and `/api/news/resonance/{contributor_id}` (or dedicated endpoint) when preferences exist. **Topics** are tags matched against `categories` and/or extracted keywords — exact matching rules must be documented in implementation.

### Won’t have (explicit)

- Crawling HTML pages as “feeds” (only RSS, Atom, JSON Feed URLs).
- Rate-limiting external sites beyond existing polite `User-Agent` and timeouts (unless a follow-up spec).

## API changes

### Existing endpoints (normative — must remain)

| Method | Path | Auth | Notes |
|--------|------|------|--------|
| GET | `/api/news/sources` | Public | List; include health fields when implemented |
| GET | `/api/news/sources/{source_id}` | Public | Single source |
| POST | `/api/news/sources` | API key | Create |
| PATCH | `/api/news/sources/{source_id}` | API key | Partial update |
| DELETE | `/api/news/sources/{source_id}` | API key | Delete |

### Request/response shapes (MVP)

**POST `/api/news/sources`** — body (JSON):

```json
{
  "id": "optional-string",
  "name": "Display Name",
  "url": "https://example.com/feed.xml",
  "type": "rss",
  "categories": ["tech"],
  "is_active": true
}
```

- If `id` omitted: server generates `ns_<ulid>` or slug from host + hash collision check.
- `category` (singular) accepted as alias for one-element `categories`.

**GET `/api/news/sources`** — each item includes health:

```json
{
  "count": 1,
  "sources": [
    {
      "id": "hackernews",
      "name": "Hacker News",
      "url": "https://news.ycombinator.com/rss",
      "type": "rss",
      "categories": ["technology"],
      "is_active": true,
      "last_fetch_at": "2026-03-28T12:00:00Z",
      "last_success_at": "2026-03-28T12:00:01Z",
      "last_http_status": 200,
      "last_error": null,
      "consecutive_failures": 0
    }
  ]
}
```

### Optional (phase 2)

- `GET /api/news/sources/{id}/health` — last N fetch attempts (ring buffer) if product needs history beyond last row.

## Data model

### Table: `news_source` (SQLAlchemy / Alembic)

| Column | Type | Notes |
|--------|------|--------|
| id | VARCHAR PK | Stable external id |
| name | VARCHAR | |
| url | TEXT UNIQUE NOT NULL | |
| type | ENUM or VARCHAR | `rss`, `atom`, `json` |
| categories | JSONB | string array |
| ontology_levels | JSONB | optional, preserve if present |
| is_active | BOOLEAN | default true |
| update_interval_minutes | INT | default 60 |
| priority | INT | default 50 |
| last_fetch_at | TIMESTAMPTZ NULL | |
| last_success_at | TIMESTAMPTZ NULL | |
| last_http_status | INT NULL | |
| last_error | TEXT NULL | truncated |
| consecutive_failures | INT | default 0 |
| created_at / updated_at | TIMESTAMPTZ | |

### Table: `contributor_news_preference` (phase 2)

| Column | Type | Notes |
|--------|------|--------|
| contributor_id | VARCHAR FK | |
| topic | VARCHAR NULL | normalized lowercase |
| source_id | VARCHAR FK NULL | optional narrow subscription |
| enabled | BOOLEAN | default true |
| UNIQUE | (contributor_id, topic, source_id) | de-dupe |

## Files to create/modify (implementation task — not this commit)

- `api/app/services/news_ingestion_service.py` — DB-backed load/save; parsers for JSON Feed; health updates.
- `api/app/models/` or existing SQL models — `NewsSource` ORM.
- `api/alembic/versions/` — migration for `news_source` (+ optional preferences table).
- `api/app/routers/news.py` — adjust Pydantic models if `id` optional on POST; ensure responses include health.
- `cli/lib/commands/news.mjs` — register `news add` alias; ensure POST body includes `id` when required by API.
- `cli/bin/cc.mjs` — help text for alias.
- `api/tests/test_news_sources.py` (or extend existing) — CRUD + health + formats.

## Web pages

**None required for MVP** — news configuration is API + CLI first. Optional follow-up: `/settings/news` or contributor dashboard (out of scope unless listed in a web spec).

## Verification

```bash
cd api && pytest -q tests/test_news_sources.py tests/test_news_ingestion.py
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
cd api && ruff check app/services/news_ingestion_service.py app/routers/news.py
```

## Verification Scenarios

Scenarios below are **contract tests for reviewers**; they must run against a deployed API with `DATABASE_URL` set and a valid API key for writes.

### Scenario 1 — Full create → read → update → delete cycle

- **Setup**: Database migrated; note a valid `COHERENCE_API_KEY` (or project equivalent) for `Authorization` / `X-API-Key` as implemented.
- **Action**:
  1. `curl -sS -X POST "$API/api/news/sources" -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d '{"name":"Spec Test Feed","url":"https://news.ycombinator.com/rss","categories":["test"]}'`
  2. Record returned `id` as `SID`.
  3. `curl -sS "$API/api/news/sources"` — verify list contains `SID` and matching `url`.
  4. `curl -sS -X PATCH "$API/api/news/sources/$SID" -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d '{"name":"Spec Test Feed Renamed"}'`
  5. `curl -sS "$API/api/news/sources/$SID"` — `name` equals renamed value.
  6. `curl -sS -X DELETE "$API/api/news/sources/$SID" -H "X-API-Key: $KEY"`
  7. `curl -sS -w "\n%{http_code}" "$API/api/news/sources/$SID"` — **404** after delete.
- **Expected**: Step 1 returns **201** with JSON containing `id`, `url`, `name`. Steps 3–5 show consistent data. Step 6 returns **200** with `{"status":"removed","id":"<SID>"}`. Step 7 body is not found detail and HTTP **404**.
- **Edge**: POST with duplicate `id` (if client supplies same `id` twice) returns **400** or **409** with clear message, not **500**.

### Scenario 2 — CLI list and add (parity with API)

- **Setup**: CLI configured with same `$API` and key as Scenario 1; no conflicting source id for test URL.
- **Action**:
  1. `cc news sources`
  2. `cc news source add "https://feeds.arstechnica.com/arstechnica/index" "Ars CLI Test"`
  3. `cc news sources` again — new row appears.
  4. `cc news add "https://feeds.arstechnica.com/arstechnica/index" "Ars CLI Alias Test"` (if alias implemented — expect same code path; if duplicate URL rejected, document behavior).
- **Expected**: Human-readable table lists source names and URLs; add succeeds with success message; second list shows new source(s).
- **Edge**: Add with **invalid URL** or unreachable host — CLI exits non-zero or prints failure; API returns **400** if URL validation fails; **no** uncaught stack trace.

### Scenario 3 — Error handling: missing resource and bad input

- **Setup**: None.
- **Action**:
  1. `curl -sS -w "\n%{http_code}" "$API/api/news/sources/does-not-exist-12345"`
  2. `curl -sS -X POST "$API/api/news/sources" -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d '{"name":"bad","url":"not-a-valid-url"}'`
- **Expected**: (1) HTTP **404**, JSON `detail` mentions not found. (2) HTTP **422** (validation) or **400**, not **500**.
- **Edge**: POST without API key returns **401** or **403** per existing middleware.

### Scenario 4 — Feed fetch populates health (broken vs working)

- **Setup**: One active source pointing to a known **200** RSS URL; one pointing to **invalid URL** or `http://127.0.0.1:9` (connection refused).
- **Action**:
  1. `curl -sS "$API/api/news/feed?refresh=true"` (triggers fetch).
  2. `curl -sS "$API/api/news/sources"` — inspect `last_http_status`, `consecutive_failures`, `last_error` per source.
- **Expected**: Good feed: `last_success_at` non-null, `consecutive_failures` == 0. Bad feed: `last_error` non-empty and/or `consecutive_failures` > 0, `last_http_status` null or reflects failure.
- **Edge**: Inactive source (`is_active: false`) — not fetched; health fields may remain stale; document expected behavior in implementation.

### Scenario 5 — JSON Feed parsing (when implemented)

- **Setup**: Add a source with `type: "json"` and URL of a **JSON Feed 1.1** document (public fixture or `https://jsonfeed.org/feed.json` if stable).
- **Action**: `curl -sS "$API/api/news/feed?refresh=true&limit=5"` — items include titles and links from JSON Feed.
- **Expected**: At least one item with `source` matching configured name and non-empty `title`.
- **Edge**: Malformed JSON — fetch records error in `last_error`, no process crash.

## How we improve the idea, prove it works, and clarify proof over time

1. **Dashboard metrics** — Expose `GET /api/news/sources` health fields and optionally aggregate **fetch success rate** (7d) in a later small spec so operators see trends, not only last error.
2. **Synthetic check** — Scheduled task (or CI) hits `GET /api/news/feed?refresh=true` and asserts `consecutive_failures` below threshold; failure opens a friction event or monitor issue (aligns with `docs/PIPELINE-MONITORING-AUTOMATED.md` patterns).
3. **Contributor-facing proof** — For topic preferences: show matched **topic tags** on each feed item in CLI/API responses when `?explain=true` so users see *why* an item appeared.
4. **Version stamp** — Include `schema_version` on `GET /api/news/sources` once preferences land so clients detect feature availability.

## Out of scope

- Replacing resonance scoring algorithms.
- Non-feed HTML scraping.
- OAuth for third-party feed providers.

## Risks and Assumptions

- **Assumption**: PostgreSQL is available in all target deployments where news CRUD is required; otherwise a fallback path must stay explicit (needs-decision if prod must support file-only).
- **Risk**: CLI `post` without generating `id` — today API may require `id`; **implementation must** align POST body between CLI and `NewsSourceCreate` (auto-id).
- **Risk**: Multi-instance file locking — **eliminated by DB**; migration must run before scaling out.
- **Assumption**: JSON Feed adoption is lower than RSS; parser maintenance is acceptable.

## Known Gaps and Follow-up Tasks

- `contributor_news_preference` UX on web — not defined here; API-only for phase 2.
- Historical health ring buffer — optional `GET .../health` endpoint.
- Run `python3 scripts/validate_spec_quality.py` after edits to this file.

## Failure/Retry Reflection

- **Failure mode**: External feed returns 200 but body is HTML error page — **Blind spot**: HTTP success but parse failure — **Next action**: detect non-XML/non-JSON first bytes and set `last_error` to `invalid_payload`.

## Acceptance criteria (implementation phase)

- [ ] Alembic migration applied; no runtime dependency on `news-sources.json` for production (file may remain for dev seed only).
- [ ] All five Verification Scenarios pass against staging/production with real `curl` and `cc`.
- [ ] `cc news add` works as alias OR is explicitly documented as `cc news source add` only (spec requires alias — implement alias).
- [ ] RSS, Atom, and JSON Feed items parse into unified `NewsItem`.
- [ ] Health columns updated on each refresh.

## Research inputs (required)

- `2026-03-28` — [JSON Feed Version 1.1](https://www.jsonfeed.org/version/1.1/) — schema for `type: json` parsing.
- `2005-08-19` — [RSS 2.0 spec](https://www.rssboard.org/rss-specification) — item/channel model.
- `2005-12-16` — [Atom Publishing Protocol / RFC 4287](https://www.rfc-editor.org/rfc/rfc4287) — entry model for Atom feeds.
