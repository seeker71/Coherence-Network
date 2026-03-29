# Spec: Configurable news sources (API, CLI, DB, health, contributor topics)

## Summary

News ingestion today uses a **mutable JSON file** (`config/news-sources.json`, env `NEWS_SOURCES_CONFIG`) with **HTTP CRUD** already exposed at `/api/news/sources`, plus partial **CLI** coverage (`cc news sources`, `cc news source add`). The system still **defaults to three hardcoded feeds** when no config exists, **filters fetch to `type == "rss"` only** (skipping JSON Feed sources even if configured), parses RSS and Atom in one path but does not treat **JSON Feed** as a first-class format, stores state **outside PostgreSQL**, has **no durable per-contributor topic subscriptions**, and **does not persist feed health** beyond log lines.

This spec defines the **product-complete** version: **relational storage** as the source of truth, **aligned POST bodies** (name, url, category — server assigns stable ids), **explicit support for RSS 2.0, Atom, and JSON Feed**, **CLI commands** that match the API contract, **contributor-level topic preferences** (not only raw feed URLs), and **observable source health** (last success, failure reason, consecutive failures) suitable for dashboards and automation.

## Purpose

Contributors and operators need to **add, list, update, and remove** news sources without code deploys, prove ingestion is **healthy**, and tune **what topics** they care about — not only which syndication endpoints exist. Persisting configuration in the **primary database** enables backups, multi-instance consistency, auditing, and future federation. Health signals make it obvious **whether the feature is working** and **which feeds are broken**, improving trust over time.

## Requirements

### Core (MVP — must ship together)

1. **R1 — REST CRUD** — Expose stable, documented endpoints:
   - `GET /api/news/sources` — list all configured sources with health metadata.
   - `GET /api/news/sources/{id}` — single source (404 if missing).
   - `POST /api/news/sources` — create source; body **must** accept `name`, `url`, and `category` (string or single entry in `categories[]`); server assigns `id` (UUID or slug) unless `id` explicitly provided by admin; returns **201** with full record.
   - `PATCH /api/news/sources/{id}` — partial update (name, url, category/categories, `type`, `is_active`, fetch tuning fields).
   - `DELETE /api/news/sources/{id}` — remove; **404** if not found; **204** or JSON confirmation per existing API style.
   - Mutating routes remain **protected** by existing API key middleware (`require_api_key`) unless a separate auth model is approved in a `needs-decision` note.

2. **R2 — Persistence in DB, not code** — Replace JSON file as authoritative store with **PostgreSQL** tables (see Data model). File-based config may remain as **one-time import/migration** path for existing deployments.

3. **R3 — Syndication formats** — Ingestion must support:
   - **RSS 2.0** (`type`: `rss` or `rss2`),
   - **Atom** (`type`: `atom` or auto-detected from content-type / root element),
   - **JSON Feed** (`type`: `jsonfeed`, MIME `application/feed+json` or `.json` URL heuristic).
   - `fetch_feeds` must not skip non-`rss` types when `type` is configured correctly.

4. **R4 — CLI parity** — The published `cc` CLI must support:
   - `cc news sources` — lists sources (same data as `GET /api/news/sources`), table or JSON via global output flag if present.
   - `cc news add <url> <name>` **or** `cc news source add <url> <name>` — **both** must work (alias); calls `POST /api/news/sources` with correct JSON (including API key from env/config).
   - Optional: `cc news source rm <id>` → `DELETE /api/news/sources/{id}`.

5. **R5 — Full create–read–update cycle** — API and tests must prove **POST → GET list → PATCH → GET by id → DELETE** with stable ids.

### Extended (same release if feasible; else sequenced follow-ups with explicit flags)

6. **R6 — Per-contributor source / topic preferences** — Contributors can subscribe to **topics** (tags/categories/keywords) that **filter or rank** `/api/news/feed` and `/api/news/resonance` when `X-Contributor-Id` or session identity is present. Storage: join table `contributor_news_preferences` with `contributor_id`, preference kind (`topic` | `source_id` | `exclude_keyword`), and value.

7. **R7 — Source health monitoring** — For each source, persist: `last_fetch_at`, `last_success_at`, `last_error_at`, `last_error_message`, `consecutive_failures`, `last_status_code`. Background job or inline fetch updates these fields. Expose via `GET /api/news/sources` and optional `GET /api/news/health` summary.

## Current implementation snapshot (for gap analysis)

| Area | Today | Target |
|------|--------|--------|
| Storage | `config/news-sources.json` + in-memory `_sources` | PostgreSQL tables + repository layer |
| POST body | `NewsSourceCreate` requires `id` | `id` optional; `name`, `url`, `category` required |
| CLI POST | `{ url, name }` only | Aligned with API; derive `id` server-side |
| Fetch loop | `type == "rss"` only | Branch on `rss` / `atom` / `jsonfeed` |
| Contributor prefs | Resonance uses staked ideas only | Explicit topic/source preferences |
| Health | Log warnings only | Persistent metrics + listable API fields |

## API changes

### `GET /api/news/sources`

**Query:** `active_only` (bool, default false)

**Response 200**
```json
{
  "count": 2,
  "sources": [
    {
      "id": "uuid-or-slug",
      "name": "Example",
      "url": "https://example.com/feed.xml",
      "type": "rss",
      "categories": ["technology"],
      "is_active": true,
      "last_fetch_at": "2026-03-28T12:00:00Z",
      "last_success_at": "2026-03-28T12:00:00Z",
      "last_error_at": null,
      "last_error_message": null,
      "consecutive_failures": 0,
      "health_status": "ok"
    }
  ]
}
```

### `POST /api/news/sources`

**Request**
```json
{
  "name": "My Feed",
  "url": "https://example.com/atom.xml",
  "category": "science",
  "type": "atom"
}
```

**Response 201** — full source object including server-generated `id`.

**Response 400** — invalid URL, unknown type, duplicate URL.

**Response 409** — duplicate `id` if client supplied conflicting id (if ids are client-suppliable for admins).

### `PATCH /api/news/sources/{id}`

**Response 200** — updated object; **404** if missing.

### `DELETE /api/news/sources/{id}`

**Response** — match existing pattern (`{"status":"removed","id":...}`) with **404** for unknown id.

### Contributor preferences (R6)

- `GET /api/contributors/{contributor_id}/news/preferences`
- `PUT /api/contributors/{contributor_id}/news/preferences` — replace set of topic/source preferences.

(Exact paths may nest under `/api/news/preferences` if contributor router ownership prefers; implementation must pick one and document OpenAPI.)

## Data model

### Table: `news_sources`

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | Server-generated |
| name | text | Display name |
| url | text | Unique per deployment |
| type | text | `rss`, `atom`, `jsonfeed` |
| categories | jsonb / text[] | Normalized from `category` on write |
| is_active | boolean | |
| priority | int | Sort / fetch order |
| update_interval_minutes | int | |
| last_fetch_at | timestamptz | nullable |
| last_success_at | timestamptz | nullable |
| last_error_at | timestamptz | nullable |
| last_error_message | text | nullable |
| consecutive_failures | int | default 0 |
| created_at / updated_at | timestamptz | |

### Table: `contributor_news_preferences` (R6)

| Column | Type | Notes |
|--------|------|--------|
| id | UUID PK | |
| contributor_id | text FK | Matches existing contributor identity |
| kind | text | `topic`, `source`, `exclude` |
| value | text | topic name, source id, or keyword |

Indexes on `(contributor_id, kind)`.

## Files to create / modify (implementation phase)

- `api/app/services/news_ingestion_service.py` — DB-backed source list; format-specific fetch; health updates.
- `api/app/routers/news.py` — Request/response models aligned with R1; optional contributor preference routes.
- `api/app/models/` — Pydantic models for API.
- Database migration — new tables + seed from `news-sources.json` where present.
- `cli/lib/commands/news.mjs` — `cc news add` alias; POST body fix; optional delete.
- `cli/bin/cc.mjs` — Help text for new/alias commands.
- `api/tests/test_news_sources.py` (or extend existing) — CRUD + health + format coverage.

## Acceptance criteria

- [ ] All endpoints in **API changes** return documented status codes for success and not-found.
- [ ] No production path **requires** editing Python lists or JSON in-repo for normal add/remove.
- [ ] `pytest` covers CRUD, duplicate URL, bad URL, delete missing id, and at least one JSON Feed fixture.
- [ ] CLI commands succeed against local API with `API_KEY` set (documented in Verification).
- [ ] Health fields update after fetch attempt (success and forced failure in test).

## Verification Scenarios

### Scenario 1 — Full CRUD cycle (API)

- **Setup:** Database migrated; `NEWS_API_KEY` available; no source with url `https://example.com/feed.xml`.
- **Action:**
  1. `curl -sS -X POST "$API/api/news/sources" -H "Authorization: Bearer $NEWS_API_KEY" -H "Content-Type: application/json" -d '{"name":"Example","url":"https://example.com/feed.xml","category":"tech","type":"atom"}'`
  2. `curl -sS "$API/api/news/sources"`
  3. `curl -sS -X PATCH "$API/api/news/sources/<id_from_step1>" -H "Authorization: Bearer $NEWS_API_KEY" -H "Content-Type: application/json" -d '{"name":"Example Renamed"}'`
  4. `curl -sS "$API/api/news/sources/<id_from_step1>"`
  5. `curl -sS -X DELETE "$API/api/news/sources/<id_from_step1>" -H "Authorization: Bearer $NEWS_API_KEY"`
  6. `curl -sS -o /dev/null -w "%{http_code}" "$API/api/news/sources/<id_from_step1>"`
- **Expected:** Step 1 returns **201** and JSON with non-empty `id` and `categories` containing `tech`. Step 2 lists the new source in `sources`. Step 3 returns **200** and `name` is `Example Renamed`. Step 4 returns that record. Step 5 returns **200** or **204** per contract. Step 6 returns **404**.
- **Edge:** POST the same `url` again before delete returns **400** or **409** with a clear message (not **500**).

### Scenario 2 — Error handling and auth

- **Setup:** Valid API base URL; optional key rotated off.
- **Action:**
  1. `curl -sS -X POST "$API/api/news/sources" -H "Content-Type: application/json" -d '{"name":"X","url":"not-a-url","category":"x"}'`
  2. `curl -sS -X POST "$API/api/news/sources" -H "Authorization: Bearer $NEWS_API_KEY" -H "Content-Type: application/json" -d '{"name":"X","url":"not-a-url","category":"x"}'`
  3. `curl -sS -X DELETE "$API/api/news/sources/00000000-0000-0000-0000-000000000000" -H "Authorization: Bearer $NEWS_API_KEY"`
- **Expected:** Step 1 returns **401** or **403** (mutate without key). Step 2 returns **400** with validation detail (invalid URL). Step 3 returns **404**.
- **Edge:** PATCH with empty body returns **200** with unchanged resource or **422** if validation forbids empty — must not return **500**.

### Scenario 3 — CLI list and add

- **Setup:** `COHERENCE_API_URL` points to staging or local API; `COHERENCE_API_KEY` exported; CLI installed (`cc` in PATH).
- **Action:**
  1. `cc news sources`
  2. `cc news add "https://www.jsonfeed.org/feed.json" "JSON Feed Blog"`  
     (and/or `cc news source add ...` — both must succeed per R4)
- **Expected:** Step 1 prints a table or list including `count` consistent with `GET /api/news/sources`. Step 2 prints success and new source appears in step 1 when repeated.
- **Edge:** Missing API key prints a **clear error** (not a stack trace) pointing to config.

### Scenario 4 — Multi-format ingestion smoke

- **Setup:** Three sources configured: RSS (`type: rss`), Atom (`type: atom`), JSON Feed (`type: jsonfeed`) pointing to **stable public fixtures** or recorded test URLs.
- **Action:** `curl -sS "$API/api/news/feed?refresh=true" | jq '.count, (.items|length)'`
- **Expected:** `items` non-empty when fixtures are reachable; each item has `title`, `url`, `source`; ingestion logs show per-format parse success.
- **Edge:** If one feed is down, `items` may be partial but `GET /api/news/sources` shows `consecutive_failures` incremented for that source only — not a global **500**.

### Scenario 5 — Contributor topic preference (R6)

- **Setup:** Contributor `contrib_e2e` exists; at least one source tagged `climate`.
- **Action:**
  1. `curl -sS -X PUT "$API/api/contributors/contrib_e2e/news/preferences" -H "Content-Type: application/json" -d '{"topics":["climate"]}'`
  2. `curl -sS "$API/api/news/feed?contributor_id=contrib_e2e"` (or header per final design)
- **Expected:** Response prefers or filters items matching `climate` vs unauthenticated feed (documented behavior).
- **Edge:** Unknown contributor returns **404** or empty prefs per policy — not **500**.

## Verification (CI / local)

```bash
cd api && pytest -q tests/test_news_sources.py tests/test_news_ingestion.py
cd api && ruff check app/services/news_ingestion_service.py app/routers/news.py
node cli/bin/cc.mjs news sources
```

## Research inputs

- `2026-03-28` — [JSON Feed Spec](https://www.jsonfeed.org/version/1.1/) — Required fields and MIME type for R3.
- `2026-03-28` — [RFC 4287 Atom](https://www.rfc-editor.org/rfc/rfc4287) — Interop for Atom entries.
- `2026-03-28` — Coherence Network `api/app/services/news_ingestion_service.py` — Current parser and file store behavior.

## Task card (implementation handoff)

```yaml
goal: Move news sources to PostgreSQL, align POST with name/url/category, support RSS/Atom/JSON Feed, CLI aliases, health metrics, and contributor topic prefs.
files_allowed:
  - api/app/services/news_ingestion_service.py
  - api/app/routers/news.py
  - api/app/models/news.py
  - cli/lib/commands/news.mjs
  - cli/bin/cc.mjs
  - api/tests/test_news_sources.py
done_when:
  - pytest covers CRUD, health, and format branch for JSON Feed fixture
  - GET /api/news/sources returns DB-backed rows with health columns
  - cc news add and cc news source add both create a source via API
commands:
  - cd api && pytest -q tests/test_news_sources.py
  - cd api && ruff check app/routers/news.py app/services/news_ingestion_service.py
constraints:
  - Do not weaken API key protection on mutating routes without explicit security spec
  - No editing tests to mask failures; fix implementation
```

## Out of scope

- Web UI for managing feeds (unless a separate UX spec is approved).
- Paid third-party news APIs (LexisNexis, etc.).
- Cross-region CDN caching of feeds.

## Risks and assumptions

- **Risk:** Public RSS URLs are unreliable; **mitigation:** health counters + backoff + operator alerts (future: `needs-decision` on webhooks).
- **Assumption:** PostgreSQL is available in all target deployments; SQLite fallback would be a separate spec.
- **Risk:** CLI/API mismatch caused current `POST` only accepting `id`; **mitigation:** this spec makes `id` server-owned by default.

## Known gaps and follow-up tasks

- Federated source sharing between instances (see federation specs).
- Alerting (Telegram/email) when `consecutive_failures` exceeds threshold.
- Web-based “subscribe to topic” UX.

## Open questions — improving the idea, proof of “working,” clarity over time

1. **Health dashboard contract** — Expose a single **machine-readable** `GET /api/news/health` with `ok_count`, `failing_count`, `last_global_fetch_at` so monitors and the web UI can show green/red **without parsing logs**.
2. **Proof ladder** — Level 0: source listed in DB; Level 1: `last_success_at` within SLA; Level 2: non-zero items in `/api/news/feed` for that source in the last 24h; Level 3: contributor preference changes **measurable ranking** delta (A/B hash in metrics).
3. **Idempotency** — `POST` with duplicate URL should return **409** with existing `id` so automation can reconcile state safely.
4. **Traceability** — Reuse `@traces_to(spec="task_3d0ac3e0921ec81a", ...)` on new routes for audit correlation.

## Failure / retry reflection

- **Failure mode:** External feed returns 403/Cloudflare challenge.  
- **Blind spot:** User-agent or IP blocking not visible as “parse error.”  
- **Next action:** Record HTTP status on failure and surface in `last_error_message`.

---

**Idea / task reference:** `task_3d0ac3e0921ec81a`  
**Related traces in code:** `spec="151"`, `idea="configurable-news-sources"` on existing news routes (may be rebased to this task id when implemented).
