# Spec: Geolocation awareness — nearby contributors, local ideas, regional news

**Spec / task ID:** `task_ce06deb4e7944a33`  
**Role:** Product definition and implementation contract for Coherence Network  
**Related:** `specs/geolocation-awareness-geocoding.md` (forward geocode chain), `specs/task_6313cc742c4d9739.md` (prior draft), `specs/e165294430dc487b.md` (narrative alignment)

## Summary

Coherence Network should use **geography** as a discoverability and collaboration signal: contributors optionally share **coarse** location on profiles; the API resolves place names via a **GeocodingService** following the **Living Codex** pattern (**OpenCage** when configured, **Nominatim** with compliant User-Agent, then a **deterministic fallback** so dev/CI never hard-crash); clients discover **nearby contributors**, **ideas** tied to those contributors, **regional news** (keyword resonance today; optional coordinate-based news later), and **agent tasks** with geographic context. This document states **requirements**, **API and data contracts**, **verification scenarios** runnable in production, **risks**, and **how we prove the feature works and improves over time** (health, metrics, revision markers).

## Purpose

- **Who benefits:** Contributors looking for local collaborators; readers of place-relevant news; operators measuring regional engagement.
- **Failure/cost avoided:** Silent wrong-city substitution, provider abuse, and unobservable geolocation regressions — mitigated by explicit provider `source`, rounding, caching, throttling, and health surfaces.

## Living Codex borrow: GeocodingService

**Intent:** Implement a thin adapter (not a symlink into `references/` — those repos are read-only per project rules) that mirrors Living Codex behavior:

1. **Primary:** **OpenCage** forward geocoding when `OPENCAGE_API_KEY` is set.
2. **Secondary:** **Nominatim** at `https://nominatim.openstreetmap.org` with a **static, descriptive User-Agent** identifying Coherence Network, per [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/) (rate limits, no bulk unthrottled scraping; cache aggressively).
3. **Fallback:** Small static or deterministic fallback for known tokens in dev/test; **no** silent substitution of an arbitrary city when both providers fail — response must expose `found: false` or equivalent.
4. **Output:** Coordinates **rounded** to ~1 km (two decimal places) aligned with contributor location storage; include `source` ∈ `{opencage, nominatim, fallback}` where applicable.

**Code anchor (current implementation):** `api/app/services/geocoding_service.py`, exposed as **`GET /api/geocode/forward?q=`** in `api/app/routers/geolocation.py`.

## Current state (baseline — must remain backward compatible)

Router prefix: **`/api`** (`geolocation.router` in `api/app/main.py`).

| Capability | Method | Path |
|------------|--------|------|
| Set contributor location (city-level, rounded coords) | `PATCH` | `/api/contributors/{contributor_id}/location` |
| Read location | `GET` | `/api/contributors/{contributor_id}/location` |
| Remove location | `DELETE` | `/api/contributors/{contributor_id}/location` |
| Nearby contributors + ideas (haversine) | `GET` | `/api/nearby?lat=&lon=&radius_km=&limit=` |
| Local news (text resonance for a place name) | `GET` | `/api/news/resonance/local?location=&limit=` |
| Forward geocode (OpenCage → Nominatim → fallback) | `GET` | `/api/geocode/forward?q=` |
| Agent tasks near a point | `GET` | `/api/geo/tasks/nearby?lat=&lon=&radius_km=&limit=` |

**Implementation references:** `api/app/routers/geolocation.py`, `api/app/services/geolocation_service.py`, `api/app/services/geocoding_service.py`, `api/app/models/geolocation.py`, `api/app/models/geocoding.py`.

### Gaps (implementation backlog relative to full vision)

- **`GET /api/ideas`** — optional `near_lat`, `near_lon`, `radius_km`, and/or `location_query` (resolved via GeocodingService) to filter or rank ideas by contributor geography (today, proximity for ideas is primarily via **`GET /api/nearby`** which returns ideas + contributors).
- **Contributor profile / portfolio DTOs** — optional `location_summary` (city/region/country) when visibility allows; never finer than stored policy.
- **`GET /api/health/geolocation`** — configured providers (boolean flags only, no secrets), cache stats, last successful geocode timestamp, optional `feature_revision` integer.
- **Web:** dedicated page **`/explore/nearby`** (Next.js under `web/app/`) using browser geolocation (opt-in) or manual place search, calling **`GET /api/nearby`** and **`GET /api/geocode/forward`**.
- **Optional:** `GET /api/news/resonance/proximity` when article metadata includes coordinates (not required for MVP if keyword resonance suffices).

## Requirements

### Functional

- [ ] **R1 — GeocodingService:** OpenCage → Nominatim → fallback; normalized query **cache** (e.g. in-memory TTL 24h, Redis-ready later); never persist full street addresses (two-decimal rounding).
- [ ] **R2 — Profile enrichment:** Contributor read/portfolio responses may expose optional **location summary** when `visibility` is `public` or `contributors_only` as policy allows; never leak precision beyond stored fields.
- [ ] **R3 — Ideas:** Either extend **`GET /api/ideas`** with proximity query params **or** document that **`GET /api/nearby`** is the supported way to discover local ideas — spec chosen at implementation time and reflected in OpenAPI.
- [ ] **R4 — News:** Maintain **`GET /api/news/resonance/local`**; optionally add coordinate-based resonance when metadata exists.
- [ ] **R5 — Tasks:** **`GET /api/geo/tasks/nearby`** remains the contract for tasks near a point; **`GET /api/agent/tasks`** may gain optional proximity filters when product approves.
- [ ] **R6 — Web:** Ship **`/explore/nearby`** (or equivalent under app router) for discoverability.

### Non-functional

- [ ] **N1 — Privacy:** `visibility=private` excludes from public/nearby aggregates.
- [ ] **N2 — Rate limits:** Server-side throttle on geocode endpoints; respect Nominatim policy.
- [ ] **N3 — Observability:** Counters or health fields for geocode and nearby usage (see Open questions).

## API changes (target vs shipped)

| Method | Path | Status | Role |
|--------|------|--------|------|
| `GET` | `/api/geocode/forward` | **Shipped** | Resolve `q` to lat/lon + label + source |
| `GET` | `/api/nearby` | **Shipped** | Nearby contributors and ideas |
| `GET` | `/api/geo/tasks/nearby` | **Shipped** | Tasks near a point |
| `GET` | `/api/news/resonance/local` | **Shipped** | Regional news by place keyword |
| `GET` | `/api/health/geolocation` | **Planned** | Operator proof: providers, cache, revision |
| `GET` | `/api/ideas` | **Extend** | Optional `near_lat`, `near_lon`, `radius_km`, `location_query` |

### Web pages (required for full feature acceptance)

| Route | Purpose |
|-------|---------|
| `/explore/nearby` | Discover nearby contributors and ideas; links to profiles and ideas |

### CLI (optional)

- `cc geo nearby` — thin wrapper over `GET /api/nearby` — **not** blocking for MVP.

## Data model

### Geocode result (API)

```yaml
GeocodeForwardResponse:
  query: string
  latitude: float | null
  longitude: float | null
  label: string | null
  source: string  # opencage | nominatim | fallback
  found: boolean
```

### Contributor location (stored)

- Graph `properties.geo_location` (see `geolocation_service`): city, region, country, rounded lat/lon, `visibility`.

### Cache entry (implementation)

- Key: normalized query + schema version  
- Value: resolved coordinates + label + source + `cached_at` (ISO 8601 UTC)

## Open questions — improve the idea, show it works, clearer proof over time

| Question | Direction |
|----------|-----------|
| How can we **improve** this idea? | Phased delivery: (1) stabilize geocode chain + tests, (2) profile DTO enrichment + ideas filter **or** documented “use `/api/nearby`”, (3) web `/explore/nearby`, (4) proximity news when metadata exists; optional **friction** event type `wrong_location_suggestion` for user reports. |
| How do we show **whether it is working**? | **`GET /api/health/geolocation`** with `opencage_configured`, `cache_entries`, `last_geocode_success_at`; runtime metrics `geocode_requests_total{source}`, `nearby_requests_total`; Grafana or `GET /api/runtime/endpoints/summary` trends if wired. |
| **Clearer proof over time** | Monotonic **`geolocation_feature_revision`** in health when behavior changes; release notes link **this spec ID** and commit SHA; reviewer checklist in `docs/RUNBOOK.md` § geolocation curls; weekly snapshot: count of contributors with `geo_location` and non-empty `/api/nearby` responses. |

## Verification Scenarios

Reviewers run these against **`$API=https://api.coherencycoin.com`** (or staging). Replace `contrib-geo-test` with a real contributor id if the test id does not exist (create via **`POST /api/contributors`** per existing API).

### Scenario 1 — Full location create–read–update–delete

- **Setup:** Contributor `contrib-geo-test` exists; no location or known clean state.
- **Action:**  
  `curl -sS -X PATCH "$API/api/contributors/contrib-geo-test/location" -H "Content-Type: application/json" -d '{"city":"Boulder","region":"CO","country":"US","latitude":40.02,"longitude":-105.27,"visibility":"public"}'`  
  Then: `curl -sS "$API/api/contributors/contrib-geo-test/location"`  
  Then: `curl -sS -X PATCH "$API/api/contributors/contrib-geo-test/location" -H "Content-Type: application/json" -d '{"city":"Boulder","region":"CO","country":"US","latitude":40.03,"longitude":-105.28,"visibility":"public"}'`  
  Then: `curl -sS -X DELETE "$API/api/contributors/contrib-geo-test/location"`
- **Expected:** First PATCH **200** with lat/lon rounded to two decimals; GET **200** with `city` **Boulder** and `visibility` **public**; second PATCH **200** with updated rounded coordinates; DELETE **204**; GET after DELETE **404** with JSON `detail` string.
- **Edge:** PATCH with `"latitude": 91` → **422**; GET after DELETE → **404** (not **500**).

### Scenario 2 — Nearby contributors and ideas (distance semantics)

- **Setup:** At least one contributor with `visibility` `public` and stored coords near **(40.015, -105.28)**; optional idea linked to that contributor per graph model.
- **Action:** `curl -sS "$API/api/nearby?lat=40.015&lon=-105.28&radius_km=50&limit=20"`
- **Expected:** **200** JSON `NearbyResult` with `contributors` and `ideas` arrays; entries within radius show approximate `distance_km` (or documented field); no raw exact coordinates of other users beyond policy.
- **Edge:** `lat=200` → **422**; `radius_km=0` → **422** (must be `gt=0` per router).

### Scenario 3 — Forward geocode (happy path and no-match)

- **Setup:** No API key required for reviewer if Nominatim/fallback allowed on environment.
- **Action:** `curl -sS "$API/api/geocode/forward?q=Boulder%2C+Colorado%2C+USA"`  
  Then: `curl -sS "$API/api/geocode/forward?q=zzzzzznonexistentplace12345"`
- **Expected:** First call **200** with `found: true`, numeric `latitude`/`longitude`, non-empty `source` (e.g. `opencage`, `nominatim`, or `fallback`). Second call **200** with `found: false` **or** documented error — behavior must match `GeocodeForwardResponse` and tests.
- **Edge:** `q=a` (too short if min length enforced) → **422** per `Query(..., min_length=2)`.

### Scenario 4 — Regional news resonance (read path)

- **Setup:** News index populated or empty (both valid).
- **Action:** `curl -sS "$API/api/news/resonance/local?location=Denver&limit=5"`
- **Expected:** **200** with a list/array of items and resonance scores in **0.0–1.0** range per model; empty list acceptable if no articles match.
- **Edge:** `location=` (empty) → **422**.

### Scenario 5 — Agent tasks near a point (error handling)

- **Setup:** None.
- **Action:** `curl -sS "$API/api/geo/tasks/nearby?lat=40.0&lon=-105.0&radius_km=100&limit=10"`  
  Then: `curl -sS -o /dev/null -w "%{http_code}" "$API/api/geo/tasks/nearby?lat=999&lon=-105.0&radius_km=100"`
- **Expected:** First **200** with `tasks` array (possibly empty) and `total` consistent with length; second request **422** (invalid latitude).
- **Edge:** Valid coords, `radius_km=30000` → **422** if above router max (`le=20000`).

### Scenario 6 (post–health endpoint) — Operator health read

- **Setup:** After `GET /api/health/geolocation` is implemented.
- **Action:** `curl -sS "$API/api/health/geolocation"`
- **Expected:** **200** JSON with boolean `opencage_configured`, no secret values, optional `feature_revision` integer.
- **Edge:** If geocoding backends all down, still **200** or **503** with explicit body — document one contract and test it.

## Research inputs

- `2026-03-28` — [OpenCage Geocoding API](https://opencagedata.com/api) — keys, quotas, response shape.
- `2026-03-28` — [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/) — User-Agent, rate limits.
- `2026-03-28` — Repository: `api/app/routers/geolocation.py`, `api/app/services/geocoding_service.py` — actual shipped paths and models.

## Task card

```yaml
goal: Complete geolocation awareness — profile enrichment, ideas proximity or documented nearby flow, health endpoint, web /explore/nearby, and measurable proof signals.
files_allowed:
  - api/app/services/geocoding_service.py
  - api/app/services/geolocation_service.py
  - api/app/routers/geolocation.py
  - api/app/routers/ideas.py
  - api/app/routers/health.py
  - api/app/main.py
  - api/app/models/geolocation.py
  - api/app/models/geocoding.py
  - api/tests/test_geolocation_geocoding_proximity.py
  - web/app/explore/nearby/page.tsx
  - specs/task_ce06deb4e7944a33.md
done_when:
  - Verification Scenarios 1–5 pass on production; Scenario 6 after health ships
  - cd api && pytest -q api/tests/test_geolocation_geocoding_proximity.py (or renamed suite) passes
  - cd web && npm run build passes when web page exists
commands:
  - cd api && pytest -q tests/test_geolocation_geocoding_proximity.py
  - cd web && npm run build
constraints:
  - No API keys in repository; environment and keystore only
  - Do not weaken tests to hide failures; fix implementation
```

## Acceptance tests (mapping)

- `api/tests/test_geolocation_geocoding_proximity.py` — geocoding chain and proximity behaviors as named in file.
- Add or extend tests when `GET /api/ideas` gains proximity params or when `/api/health/geolocation` lands.

## Concurrency behavior

- Geocode cache: safe concurrent reads; writes single-key atomicity sufficient for MVP.
- Contributor location: graph node update; nearby reads eventually consistent with index latency.

## Verification (automated)

```bash
cd api && pytest -q tests/test_geolocation_geocoding_proximity.py
```

## Out of scope (MVP)

- Continuous GPS tracking; sub-meter precision.
- Mandatory CLI `cc geo` commands.

## Risks and assumptions

- **Risk:** Nominatim blocks abusive traffic — **Mitigation:** OpenCage in production, cache, throttle, compliant User-Agent.
- **Assumption:** Contributor `geo_location` property key remains stable for stored data.
- **Assumption:** `GET /api/nearby` remains the primary aggregate API for “local ideas + contributors” until `GET /api/ideas` filters ship.

## Known gaps and follow-up tasks

- Per-idea map pins independent of contributor home city.
- Self-hosted Nominatim or commercial geocoder at high scale.

## Failure / retry reflection

- **Failure mode:** OpenCage outage + cold cache.  
- **Blind spot:** Thundering herd to Nominatim.  
- **Next action:** Exponential backoff, circuit breaker, return **503** with retry-after for geocode only.

## Decision gates

- Whether **`GET /api/ideas`** proximity params are required vs documenting **`GET /api/nearby`** as canonical — product sign-off.
- Whether **`POST`** body geocode is needed when **`GET /api/geocode/forward`** already satisfies clients — avoid duplicate endpoints unless mobile requires POST.

## Verification (spec quality)

- This spec satisfies **>500 characters** and includes **Verification**, **Risks and Assumptions**, and **Known Gaps and Follow-up Tasks** per project conventions.

## See also

- `docs/RUNBOOK.md` — deployment and curl checks.
- `specs/geolocation-awareness-geocoding.md` — forward geocode provider chain detail.
