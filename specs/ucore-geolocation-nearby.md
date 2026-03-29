# U-Core — Geolocation awareness (nearby contributors, local ideas, regional news)

**Idea ID:** `ucore-geolocation-nearby`  
**Parent:** `ucore-integration` (U-Core architecture adoption from Living Codex)  
**Related spec:** `specs/geolocation-awareness-geocoding.md` (geocoding chain, task proximity, detailed ACs)

## Summary

Coherence Network should treat **place** as a first-class signal: contributors can share **city-level** location; the API resolves free-text places via a **Living Codex–style GeocodingService** (OpenCage when `OPENCAGE_API_KEY` is set, **Nominatim** with a descriptive User-Agent, then a small static fallback). That stack feeds **proximity**: find **nearby collaborators**, **ideas** tied to nearby authors, **agent tasks** with geo in `context`, and **regional news** matched to a location string.

**Today (implemented):** graph-backed contributor `geo_location`, Haversine **nearby** search, **local news resonance** by keyword overlap, **forward geocode**, and **geo-filtered agent tasks**.  
**Next (this idea’s product scope):** unify these under U-Core UX and observability; add **explicit proximity filters** on the ideas portfolio where missing; optional **web surface** for “near me”; **health and metrics** so reviewers can prove the feature works in production without reading source.

## Purpose

- Help contributors discover **who and what is near them**, not only global rankings.
- Reuse **one geocoding abstraction** (`api/app/services/geocoding_service.py`) everywhere we resolve strings to coordinates.
- Make **proof of operation** explicit: health endpoints, counters, and runnable verification scenarios—so the capability is auditable over time.

## Requirements

- [ ] **R1** Geocoding chain (OpenCage → Nominatim → fallback) with tests and rounded coordinates.
- [ ] **R2** Contributor location PATCH/GET/DELETE with visibility and privacy rules.
- [ ] **R3** `GET /api/nearby` returns sorted contributors and ideas within `radius_km`.
- [ ] **R4** `GET /api/news/resonance/local` returns scored regional news for a location string.
- [ ] **R5** `GET /api/geo/tasks/nearby` filters agent tasks by `context` geo or contributor location.
- [ ] **R6** `GET /api/ideas` supports proximity filtering (lat/lon/radius or resolved place)—*gap*.
- [ ] **R7** Web page `/explore/nearby` calls nearby + local news APIs—*gap*.
- [ ] **R8** `GET /api/health/geolocation` exposes non-secret operational proof—*gap*.

Each numbered requirement below lists the **primary file(s)** expected to change when implemented.

### R1 — Geocoding service parity (Living Codex pattern)

- **Acceptance:** Forward geocode uses **OpenCage → Nominatim → fallback**; coordinates and labels are **rounded** (~1 km); Nominatim requests use a static identifying **User-Agent** per OSM policy.
- **Files:** `api/app/services/geocoding_service.py` (provider chain), `api/app/models/geocoding.py` (response DTOs), `api/tests/test_geolocation_geocoding_proximity.py` (and/or dedicated geocoding tests).

### R2 — Contributor location CRUD (graph properties)

- **Acceptance:** Contributors can **set**, **read**, and **delete** city-level location; visibility respects `public` | `contributors_only` | `private`; **private** contributors never appear in public nearby results.
- **Files:** `api/app/services/geolocation_service.py` — `set_contributor_location`, `get_contributor_location`, `delete_contributor_location`; `api/app/models/geolocation.py` — `ContributorLocation`, `ContributorLocationSet`; `api/app/routers/geolocation.py` — `PATCH|GET|DELETE /api/contributors/{contributor_id}/location`.

### R3 — Nearby contributors and local ideas

- **Acceptance:** Given `lat`, `lon`, `radius_km`, return **contributors** and **ideas** from authors within radius, sorted by **distance_km**; response includes totals and query echo fields.
- **Files:** `api/app/services/geolocation_service.py` — `find_nearby`; `api/app/models/geolocation.py` — `NearbyResult`, `NearbyContributor`, `NearbyIdea`; `api/app/routers/geolocation.py` — `GET /api/nearby`.

### R4 — Regional / local news

- **Acceptance:** Given a **location** string, return recent articles whose text **token-overlaps** with location keywords, with **resonance_score** and matched tokens (not vague “news works”).
- **Files:** `api/app/services/geolocation_service.py` — `local_news_resonance`; `api/app/models/geolocation.py` — `LocalNewsResonanceResponse`; `api/app/routers/geolocation.py` — `GET /api/news/resonance/local` (mounted under API prefix with other news routes—verify router registration in `api/app/main.py`).

### R5 — Agent tasks by proximity

- **Acceptance:** Tasks with `context.geo_lat` / `context.geo_lon` or resolvable `contributor_id` within **radius_km** appear in results with **distance_km**; invalid lat/lon → **422**.
- **Files:** `api/app/services/geolocation_service.py` — `filter_agent_tasks_by_proximity`; `api/app/routers/geolocation.py` — `GET /api/geo/tasks/nearby`; `api/app/models/geocoding.py` — `NearbyAgentTasksResponse`.

### R6 — Ideas portfolio proximity filter (gap — to implement)

- **Acceptance:** `GET /api/ideas` accepts optional `lat`, `lon`, `radius_km` (and/or `location` string resolved via geocoder); when set, restrict returned ideas to those whose **author** has graph location within radius **or** idea node carries optional future `geo` metadata (product choice: author-based v1).
- **Files:** `api/app/routers/ideas.py` — query params; `api/app/services/idea_service.py` — filter hook calling `geolocation_service` or shared helper; `api/app/models/idea.py` — only if response needs `distance_km` per idea; `api/tests/test_ideas.py` or new `api/tests/test_ideas_proximity.py`.

### R7 — Web: surface “nearby” (gap — to implement)

- **Acceptance:** A documented page (e.g. **`/explore/nearby`**) loads the viewer’s or chosen coordinates (browser geolocation or manual), calls **`GET /api/nearby`** and shows contributors + ideas; links to ideas; shows **regional news** via **`GET /api/news/resonance/local?location=...`**.
- **Files:** `web/app/explore/nearby/page.tsx` (or agreed route under `web/app/`); shared client in `web/lib/api.ts` or existing API helper; minimal UI components under `web/components/`.

### R8 — Proof over time: health + metrics (gap — to implement)

- **Acceptance:** `GET /api/health/geolocation` (or nested under existing health) reports: `opencage_configured`, `nominatim_reachable` (or last check), optional **non-secret** cache stats; Prometheus-style or runtime counters: `geocode_requests_total`, `nearby_requests_total` (implementation may use existing runtime event pipeline—see `api/app/services` patterns).
- **Files:** `api/app/routers/health.py` or `api/app/main.py` health section; `api/app/services/geocoding_service.py` — instrumentation hooks; `docs/` only if project standards require runbook update (prefer extending existing health docs in-place).

## API changes

### Must exist (contract for reviewers)

| Method | Path | Role |
|--------|------|------|
| GET | `/api/nearby` | Proximity: contributors + ideas |
| GET | `/api/news/resonance/local` | Regional news by location string |
| GET | `/api/geocode/forward` | Forward geocode (`q` query) |
| GET | `/api/geo/tasks/nearby` | Agent tasks near a point |
| PATCH | `/api/contributors/{contributor_id}/location` | Set/update location |
| GET | `/api/contributors/{contributor_id}/location` | Read location |
| DELETE | `/api/contributors/{contributor_id}/location` | Opt out |

### Planned (this idea)

| Method | Path | Role |
|--------|------|------|
| GET | `/api/ideas` | Add `lat`, `lon`, `radius_km` (and/or `near_location`) |
| GET | `/api/health/geolocation` | Operational proof (non-secret config + reachability) |

## Data model

**Contributor (graph node `properties.geo_location`):**

```yaml
geo_location:
  city: string
  region: string | null
  country: string
  latitude: float    # 2-decimal rounded
  longitude: float   # 2-decimal rounded
  visibility: enum [public, contributors_only, private]
  updated_at: ISO8601 UTC string
```

**Geocode forward response** (see `api/app/models/geocoding.py`): `query`, `found`, `latitude`, `longitude`, `display_name`, `source` ∈ `{opencage, nominatim, fallback}`.

**Nearby bundle** (`NearbyResult`): contributors and ideas with `distance_km`; excludes `private` visibility from listings.

## Files to create or modify

Implementation agents should create or modify:

- `specs/ucore-geolocation-nearby.md` — this umbrella spec (U-Core scope + proof).
- `api/app/services/geocoding_service.py` — OpenCage → Nominatim → fallback (reuse; extend for metrics if needed).
- `api/app/services/geolocation_service.py` — nearby, local news, task proximity; any shared helper for idea filtering.
- `api/app/models/geocoding.py` — geocode and nearby-task DTOs.
- `api/app/models/geolocation.py` — contributor location and nearby/news DTOs.
- `api/app/routers/geolocation.py` — routes listed above.
- `api/app/routers/ideas.py` — proximity query params when R6 is implemented.
- `api/app/services/idea_service.py` — proximity filter logic for R6.
- `api/tests/test_geolocation_interface.py`, `api/tests/test_geo_location.py`, `api/tests/test_geolocation_geocoding_proximity.py` — extend for new behaviors.
- `web/app/explore/nearby/page.tsx` — optional UI (R7).
- `api/app/routers/health.py` (or equivalent) — geolocation health (R8).

## Acceptance criteria

- Automated: `cd api && .venv/bin/pytest -q tests/test_geolocation_interface.py tests/test_geo_location.py tests/test_geolocation_geocoding_proximity.py` passes for shipped behaviors (R1–R5).
- Manual validation: run **Verification Scenarios** 1–5 against production or staging `API` base URL; document any environment-specific contributor IDs.
- When R6–R8 ship: extend pytest with `api/tests/test_ideas_proximity.py` and health route tests; add Playwright or smoke for `/explore/nearby` if UI lands.

## Verification

```bash
python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
python3 scripts/validate_spec_quality.py --file specs/ucore-geolocation-nearby.md
cd api && .venv/bin/pytest -q tests/test_geolocation_interface.py tests/test_geo_location.py tests/test_geolocation_geocoding_proximity.py
# Smoke (set API=https://api.coherencycoin.com): curl -sS "$API/api/nearby?lat=52.52&lon=13.41&radius_km=100"
```

## Verification Scenarios

Production reviewers should execute these with `API=https://api.coherencycoin.com` (or staging). Replace IDs with real graph-backed contributor IDs from your environment.

### Scenario 1 — Contributor location full cycle (create → read → delete)

- **Setup:** Contributor node `contrib-geo-demo` exists (create via normal onboarding or test fixture).
- **Action:**  
  `curl -sS -X PATCH "$API/api/contributors/contrib-geo-demo/location" -H "Content-Type: application/json" -d '{"city":"Berlin","region":"BE","country":"DE","latitude":52.52,"longitude":13.41,"visibility":"public"}'`  
  Then: `curl -sS "$API/api/contributors/contrib-geo-demo/location"`  
  Then: `curl -sS -X DELETE "$API/api/contributors/contrib-geo-demo/location" -o /dev/null -w "%{http_code}\n"`
- **Expected:** PATCH returns **200** JSON with `city` Berlin and coordinates **rounded to two decimals**; GET returns **200** with matching fields; DELETE returns **204**.
- **Edge:** PATCH with `latitude` **95** → **422** with JSON `detail`. GET after DELETE → **404** with JSON `detail`, not **500**.

### Scenario 2 — Nearby collaborators and ideas (read)

- **Setup:** At least one **public** contributor with `geo_location` near **52.52, 13.41** and at least one idea authored by that contributor.
- **Action:** `curl -sS "$API/api/nearby?lat=52.52&lon=13.41&radius_km=100&limit=20"`
- **Expected:** **200** JSON with `contributors` (each with `contributor_id`, `name`, `distance_km`, `city`, `country`), `ideas` (each with `idea_id`, `title`, `distance_km`), `total_contributors`, `total_ideas`, `query_lat`, `query_lon`, `radius_km`. Lists sorted by increasing `distance_km` where applicable.
- **Edge:** Omit `lon` → **422**. `lat=100` → **422**.

### Scenario 3 — Forward geocode (read)

- **Action:** `curl -sS "$API/api/geocode/forward?q=Berlin%2C%20Germany"`
- **Expected:** **200** JSON with `found: true`, `latitude`, `longitude`, `display_name`, `source` one of `opencage`, `nominatim`, `fallback`.
- **Edge:** `q=a` (too short) → **422**.

### Scenario 4 — Regional news resonance (read)

- **Action:** `curl -sS "$API/api/news/resonance/local?location=Berlin&limit=10"`
- **Expected:** **200** JSON with `location`, `items` array (each item has `title`, `resonance_score` between 0 and 1, `local_keywords` array), `total` ≥ 0.
- **Edge:** Missing `location` → **422**. Empty cache / no matches → **200** with `items: []` and `total: 0` (not **500**).

### Scenario 5 — Agent tasks nearby + error handling

- **Setup:** Optional: a task with `context` containing `geo_lat` and `geo_lon` near the query point.
- **Action:** `curl -sS "$API/api/geo/tasks/nearby?lat=0&lon=0&radius_km=500"`  
  Then: `curl -sS -o /dev/null -w "%{http_code}\n" "$API/api/geo/tasks/nearby?lat=200&lon=0&radius_km=50"`
- **Expected:** First call **200** with `tasks` array and `total` (possibly 0). Second call **422** (latitude out of range).
- **Edge:** Valid call with no matching tasks → **200**, `tasks: []`, `total: 0`.

## Open questions — improving the idea and proving it works

| Question | Direction |
|----------|-----------|
| How do we improve the idea? | **v1:** author-location-based ideas + `/api/nearby`; **v2:** optional geo on idea nodes; **v3:** federated aggregation of regional signals (see federation specs). |
| How do we show it is working? | Ship **health** + **counters** (R8); dashboard slices: % contributors with `geo_location`, `nearby_requests_total` week-over-week, geocode `source` mix. |
| Clearer proof over time? | Weekly automated check: run Scenario 1–5 against production; store pass/fail in CI or `docs/system_audit` only if repo policy requires—prefer API-native health for live truth. |

## Research Inputs (Required)

- `2026-03-28` — [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/) — User-Agent, acceptable use, no bulk abuse.
- Living Codex reference (read-only): patterns for **GeocodingService** chain — mirror behavior in `geocoding_service.py`, not by editing `references/`.

## Task Card

```yaml
goal: Deliver U-Core geolocation awareness with proven nearby contributors, local ideas, regional news, and optional ideas + web filters.
files_allowed:
  - specs/ucore-geolocation-nearby.md
  - api/app/services/geocoding_service.py
  - api/app/services/geolocation_service.py
  - api/app/services/idea_service.py
  - api/app/models/geocoding.py
  - api/app/models/geolocation.py
  - api/app/routers/geolocation.py
  - api/app/routers/ideas.py
  - api/app/routers/health.py
  - api/tests/test_geolocation_interface.py
  - api/tests/test_geo_location.py
  - api/tests/test_geolocation_geocoding_proximity.py
  - api/tests/test_ideas_proximity.py
  - web/app/explore/nearby/page.tsx
done_when:
  - pytest geolocation + geocoding tests pass
  - Verification scenarios 1–5 pass against target API
  - GET /api/health/geolocation returns non-secret status (when R8 in scope)
commands:
  - python3 scripts/validate_spec_quality.py --base origin/main --head HEAD
  - cd api && .venv/bin/pytest -q tests/test_geolocation_interface.py tests/test_geo_location.py tests/test_geolocation_geocoding_proximity.py
constraints:
  - Do not edit reference repos under references/
  - Privacy: never store full addresses; keep ~1 km rounding
```

## Out of Scope

- Editing symlinks under `references/` (Living Codex) — **read-only** per project rules.
- Self-hosted Nominatim or commercial geocoder procurement (document as follow-up if production scale requires).
- Precise GPS tracking or continuous background location on clients.

## Risks and Assumptions

- **Assumption:** Graph store lists contributors/ideas within performance bounds for O(n) nearby scans; at very large N, indexing (geohash) will be required.
- **Risk:** OpenCage absent in CI/production — service must degrade gracefully to Nominatim/fallback; tests **mock HTTP**, not live keys.
- **Risk:** **Local news** uses **keyword overlap**, not true geoparsing of articles—regional relevance may be noisy; mitigate with scoring thresholds and future NLP.
- **Assumption:** Router prefix is `/api` for all listed paths (FastAPI `include_router`); reviewers confirm actual OpenAPI at `/docs`.

## Known Gaps and Follow-up Tasks

- **R6** — `GET /api/ideas` proximity filters not yet in `ideas.py` (explicit gap until implemented).
- **R7** — Web **`/explore/nearby`** page not present in repo at spec time.
- **R8** — Dedicated **`/api/health/geolocation`** not present at spec time; add when implementing observability.
- Optional: rate limiting on `/api/geocode/forward` to protect Nominatim and cost.

## Failure/Retry Reflection

- **Failure mode:** Nominatim rate limit or timeout.
- **Blind spot:** Assuming OpenCage is always configured in production.
- **Next action:** Surface `source` and failure reason in logs/metrics; backoff and cache geocode results per normalized query.

## Decision Gates

- Whether **idea** proximity is **author-only** (v1) or also **idea-level geo** (v2)—product owner confirms before expanding `idea` graph schema.
- Whether **`/explore/nearby`** requires auth — default **public read** for aggregate nearby data; contributor PII remains city-level only.
