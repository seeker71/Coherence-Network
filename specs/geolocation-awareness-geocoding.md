# Geolocation awareness — geocoding chain, proximity tasks, proof

## Goal

Enable **address → coordinates** resolution for enriching contributor profiles and proximity features, using a **Living Codex–style provider chain**: OpenCage (when configured), **Nominatim** (OpenStreetMap, with required User-Agent), then a **small static fallback** for offline/dev so the pipeline never hard-fails. Expose HTTP endpoints so integrators and reviewers can verify behavior without reading source.

Existing surfaces remain authoritative for “who is nearby” and “local news”:

- `GET /api/nearby` — contributors + ideas by Haversine distance  
- `GET /api/news/resonance/local` — regional/news resonance by location string  
- `PATCH/GET/DELETE /api/contributors/{id}/location` — city-level profile location  

This spec **adds** forward geocoding and **agent task proximity** (tasks that carry `geo_lat`/`geo_lon` or a resolvable `contributor_id` in `context`).

## Files to create or modify

| File | Action |
|------|--------|
| `specs/geolocation-awareness-geocoding.md` | This spec |
| `api/app/models/geocoding.py` | Pydantic models for geocode + nearby-task responses |
| `api/app/services/geocoding_service.py` | OpenCage → Nominatim → fallback |
| `api/app/services/geolocation_service.py` | `filter_agent_tasks_by_proximity` (uses agent + contributor location) |
| `api/app/routers/geolocation.py` | `GET /geocode/forward`, `GET /geo/tasks/nearby` |
| `api/tests/test_geolocation_geocoding_proximity.py` | Pytest contract |

## API contracts (exact paths)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/geocode/forward?q=...` | Resolve a free-text place to rounded lat/lon + `source` |
| GET | `/api/geo/tasks/nearby?lat=&lon=&radius_km=` | Agent tasks within radius (context geo or contributor location) |

Existing (unchanged but part of the story):

| GET | `/api/nearby?lat=&lon=&radius_km=` |
| GET | `/api/news/resonance/local?location=...` |
| PATCH | `/api/contributors/{id}/location` |

## Web / CLI

- **Web**: No new page required; geocoding is API-first. Optional future: automation/settings page calling `/api/geocode/forward`.  
- **CLI**: None required; reviewers use `curl` as below.

## Acceptance criteria

1. **Provider order**: If `OPENCAGE_API_KEY` is set and OpenCage returns a result, `source=opencage`. If not, try Nominatim; on success `source=nominatim`. If both fail, static fallback may return `source=fallback` for known tokens; otherwise `found=false`.  
2. **Privacy**: API returns coordinates rounded to **two decimal places** (~1 km), consistent with contributor location storage.  
3. **Nominatim compliance**: Requests include a descriptive `User-Agent` identifying Coherence Network (OSM usage policy).  
4. **Task proximity**: Tasks with `context.geo_lat` and `context.geo_lon` are included when within `radius_km`. Tasks with `context.contributor_id` (or `assigned_contributor`) are included if that contributor has a stored graph location within radius.  
5. **Errors**: Empty or too-short `q` on `/api/geocode/forward` → **422**. Invalid lat/lon on `/api/geo/tasks/nearby` → **422**.

## Open questions — how we improve proof over time

1. **Observability**: Add `GET /api/geocode/forward` response field `source` + optional `latency_ms` in a later iteration so dashboards show OpenCage vs Nominatim vs fallback rates.  
2. **SLO**: Track 4xx/5xx ratio for Nominatim and rate-limit client calls server-side (1 req/s) to respect OSM.  
3. **Product proof**: Surface “last geocode source” on a contributor profile admin JSON for support.  
4. **Tasks**: Encourage runners to set `context.geo_lat` / `context.geo_lon` when creating regional tasks so `/api/geo/tasks/nearby` stays populated.

## Verification scenarios

### Scenario 1 — Forward geocode (happy path, mocked OpenCage)

- **Setup**: Unit test patches `httpx.Client.get` to return OpenCage JSON with one geometry.  
- **Action**: Call `forward_geocode("Berlin, Germany")` in process.  
- **Expected**: `found is True`, `source == "opencage"`, latitude/longitude rounded to 2 decimals, Berlin-ish coords.  
- **Edge**: Empty query returns `None` or API 422; malformed JSON from provider does not raise uncaught exception (falls through).

### Scenario 2 — Fallback chain (OpenCage fails, Nominatim succeeds)

- **Setup**: Patch OpenCage to fail/empty; Nominatim returns one result.  
- **Action**: `forward_geocode("Test City")`.  
- **Expected**: `source == "nominatim"`.  
- **Edge**: Both HTTP failures → try `fallback`; unknown string → `found=False` on HTTP layer.

### Scenario 3 — HTTP GET `/api/geocode/forward`

- **Setup**: Running ASGI app (httpx AsyncClient), mock `forward_geocode` to return a fixed result.  
- **Action**: `GET /api/geocode/forward?q=Paris`  
- **Expected**: HTTP 200, JSON includes `found`, `latitude`, `longitude`, `source`.  
- **Edge**: `GET /api/geocode/forward?q=a` (too short) → **422**.

### Scenario 4 — Task proximity full read cycle

- **Setup**: Monkeypatch `agent_service.list_tasks` to return two tasks: one with `context.geo_lat/geo_lon` inside radius, one outside.  
- **Action**: Call `filter_agent_tasks_by_proximity` or `GET /api/geo/tasks/nearby?lat=52.52&lon=13.405&radius_km=500`.  
- **Expected**: Only the inside-radius task appears; each item has `distance_km` ≥ 0.  
- **Edge**: No tasks → empty list, HTTP 200, `total=0`.

### Scenario 5 — Error handling

- **Action**: `GET /api/geo/tasks/nearby?lat=200&lon=0`  
- **Expected**: **422** (latitude out of range).  
- **Action**: `GET /api/geocode/forward` with no `q`  
- **Expected**: **422**.

## Risks and assumptions

- **Assumption**: Nominatim allows low-volume server use with proper User-Agent; production may need a self-hosted Nominatim or commercial geocoder for scale.  
- **Risk**: OpenCage key absent in CI — tests **must** mock HTTP, not rely on live keys.

## Known gaps and follow-up tasks

- Rate limiting and caching for `/api/geocode/forward`.  
- Persist last geocode source on contributor node (optional).  
- Extend `GET /api/ideas` with `lat`/`lon`/`radius` filters (not in this spec).
