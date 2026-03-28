# Spec: Geo-location (task_568bd9ca41fd0dcf)

> Companion spec to Spec 170. Spec ID: task_568bd9ca41fd0dcf

---

## Problem

- Contributors currently have no spatial identity — a contributor in São Paulo and one in
  Berlin look identical in the graph.
- Local meetups and regional collaboration are blocked: there is no way to find other
  contributors within reasonable travel distance.
- News resonance is computed globally; headlines relevant to a specific region surface the
  same as remote global events, reducing signal for local contributors.
- The Living Codex `SpatialGraphModule` demonstrated that city-level location dramatically
  improves community cohesion and local event coordination without requiring PII.

---

## Solution

A lightweight **location profile** is attached to each contributor, exposing:

1. **Location set/clear** — `PATCH /api/contributors/{id}/location` — city, country, lat/lon
   are stored at city centroid precision only (≈1 km grid snap). Contributor controls
   `visibility` (public | network | private).
2. **Nearby discovery** — `GET /api/nearby?lat=&lon=&radius_km=` — returns contributors and
   ideas within a geographic radius, ordered by distance.
3. **Local news resonance** — `GET /api/news/resonance/local?location=` — returns news items
   whose resonance score is boosted by a geographic proximity factor to the named location.
4. **CLI** — `cc nearby` and `cc location set <city>` for terminal-first workflows.
5. **Web** — a `/map` page rendering contributor clusters and idea density as a heatmap.

Privacy guardrails are enforced at the API layer: exact coordinates are never returned; only
city name + country + approximate distance are exposed to callers.

---

## Acceptance Criteria

1. `PATCH /api/contributors/{id}/location` accepts `{"city": "...", "country": "...",
   "lat": ..., "lon": ..., "visibility": "public|network|private"}` and returns the
   contributor's updated location profile. Missing `lat`/`lon` are geocoded server-side
   from `city` + `country`.
2. `GET /api/contributors/{id}/location` returns city, country, region, and `visibility`
   but **never** exposes raw lat/lon to callers; snapped centroid coordinates are stored
   internally but not returned.
3. `DELETE /api/contributors/{id}/location` removes the contributor's location profile
   and makes them invisible in all nearby queries.
4. `GET /api/nearby?lat=&lon=&radius_km=` returns a JSON object with `contributors` and
   `ideas` arrays, each item including `distance_km` (truncated to 1 decimal), `name`,
   `id`, and for contributors `visibility` must be `public` or `network` (private
   contributors are excluded).
5. `GET /api/nearby` without required params returns 422.
6. `GET /api/news/resonance/local?location=<city>` returns the standard resonance payload
   with an additional `geo_boost` field per item (float 0.0–1.0) indicating how much the
   contributor's region amplified that item's score.
7. `GET /api/news/resonance/local` without `location` param returns 422.
8. `GET /api/geo/roi` returns aggregate stats: `contributors_with_location`,
   `top_cities` (top 5), `ideas_with_location`, `avg_radius_km_used`, and
   `spec_ref: "spec-170"`.
9. All contributors with `visibility: private` are excluded from `GET /api/nearby`
   responses regardless of distance.
10. All 10 integration tests in `api/tests/test_geo_location.py` pass.

---

## Data Model

### `ContributorLocation` (Pydantic model — `api/app/models/geo.py`)

```python
class LocationVisibility(str, Enum):
    PUBLIC = "public"
    NETWORK = "network"
    PRIVATE = "private"

class ContributorLocationSet(BaseModel):
    city: str
    country: str
    lat: Optional[float] = None   # snapped to city centroid, optional
    lon: Optional[float] = None   # snapped to city centroid, optional
    visibility: LocationVisibility = LocationVisibility.PUBLIC

class ContributorLocationProfile(BaseModel):
    contributor_id: str
    city: str
    country: str
    region: Optional[str] = None
    visibility: LocationVisibility
    updated_at: datetime
    # NOTE: lat/lon intentionally omitted from response model

class NearbyContributor(BaseModel):
    id: str
    name: str
    city: str
    country: str
    distance_km: float
    visibility: LocationVisibility

class NearbyIdea(BaseModel):
    id: str
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    distance_km: float

class NearbyResponse(BaseModel):
    contributors: list[NearbyContributor]
    ideas: list[NearbyIdea]
    radius_km: float
    center_lat: float
    center_lon: float

class LocalResonanceItem(BaseModel):
    idea_id: str
    news_title: str
    score: float
    geo_boost: float   # 0.0–1.0 extra weight from geographic proximity
    location: str      # city name matched

class GeoROI(BaseModel):
    contributors_with_location: int
    top_cities: list[dict]   # [{city, country, count}]
    ideas_with_location: int
    avg_radius_km_used: float
    spec_ref: str = "spec-170"
```

### Storage

Location data is stored as properties on the `contributor` graph node:

| Property | Type | Notes |
|---|---|---|
| `geo_city` | str | Human-readable city name |
| `geo_country` | str | ISO 3166-1 alpha-2 country code |
| `geo_region` | str | Optional region/state |
| `geo_lat_snap` | float | City centroid lat, snapped to 0.1° grid |
| `geo_lon_snap` | float | City centroid lon, snapped to 0.1° grid |
| `geo_visibility` | str | `public`, `network`, or `private` |
| `geo_updated_at` | ISO 8601 | Last update timestamp |

Ideas can also carry location metadata (populated when an idea is created with a
`location` field or subsequently tagged):

| Property | Type | Notes |
|---|---|---|
| `geo_city` | str | City where idea originated |
| `geo_lat_snap` | float | Snapped centroid |
| `geo_lon_snap` | float | Snapped centroid |

---

## API Contract

### `PATCH /api/contributors/{id}/location`

**Request body** (`ContributorLocationSet`)
```json
{
  "city": "Berlin",
  "country": "DE",
  "lat": 52.52,
  "lon": 13.405,
  "visibility": "public"
}
```

**Response 200** (`ContributorLocationProfile`)
```json
{
  "contributor_id": "contributor:test-alice",
  "city": "Berlin",
  "country": "DE",
  "region": "Berlin",
  "visibility": "public",
  "updated_at": "2026-03-28T12:00:00Z"
}
```

**Errors**
- 404 — contributor not found
- 422 — invalid visibility value or missing required fields

---

### `GET /api/contributors/{id}/location`

**Response 200** (`ContributorLocationProfile`)
Same shape as PATCH response. Returns 404 if contributor not found or location not set.

---

### `DELETE /api/contributors/{id}/location`

**Response 204** — location removed.
- 404 if contributor not found or location not set.

---

### `GET /api/nearby`

**Query params**
- `lat` (float, required) — caller's latitude
- `lon` (float, required) — caller's longitude
- `radius_km` (float, default=50.0) — search radius
- `limit` (int, default=20, max=100) — max results per category

**Response 200** (`NearbyResponse`)
```json
{
  "contributors": [
    {
      "id": "contributor:alice",
      "name": "Alice",
      "city": "Berlin",
      "country": "DE",
      "distance_km": 2.4,
      "visibility": "public"
    }
  ],
  "ideas": [
    {
      "id": "idea-abc",
      "name": "Local mesh networking",
      "city": "Berlin",
      "country": "DE",
      "distance_km": 1.1
    }
  ],
  "radius_km": 50.0,
  "center_lat": 52.52,
  "center_lon": 13.405
}
```

**Errors**
- 422 — `lat` or `lon` missing
- 422 — `radius_km` > 5000 (global cap)

---

### `GET /api/news/resonance/local`

**Query params**
- `location` (str, required) — city name or "city,country" string
- `top_n` (int, default=10) — max items returned

**Response 200**
```json
{
  "location": "Berlin, DE",
  "items": [
    {
      "idea_id": "idea-abc",
      "news_title": "Berlin startup scene accelerates",
      "score": 0.82,
      "geo_boost": 0.35
    }
  ]
}
```

**Errors**
- 422 — `location` missing or unresolvable

---

### `GET /api/geo/roi`

**Response 200** (`GeoROI`)
```json
{
  "contributors_with_location": 14,
  "top_cities": [
    {"city": "Berlin", "country": "DE", "count": 4},
    {"city": "São Paulo", "country": "BR", "count": 3}
  ],
  "ideas_with_location": 27,
  "avg_radius_km_used": 48.3,
  "spec_ref": "spec-170"
}
```

---

## Files to Create / Modify

| File | Action | Description |
|---|---|---|
| `api/app/models/geo.py` | Create | Pydantic models: ContributorLocationSet, ContributorLocationProfile, NearbyResponse, etc. |
| `api/app/services/geo_service.py` | Create | Business logic: set/get/delete location, nearby search (haversine), geo_boost computation |
| `api/app/routers/geo.py` | Create | FastAPI router: PATCH/GET/DELETE location, GET /api/nearby, GET /api/news/resonance/local, GET /api/geo/roi |
| `api/app/main.py` | Modify | Register `geo.router` with prefix `/api` |
| `api/tests/test_geo_location.py` | Create | 10 integration tests covering all ACs |
| `web/src/app/map/page.tsx` | Create | Map view: contributor clusters + idea density heatmap |
| `cli/commands/geo.py` | Create | `cc nearby` and `cc location set <city>` commands |

---

## Geo Distance Algorithm

Use the Haversine formula for great-circle distance. No external geocoding service is required
at MVP — a bundled city centroid lookup table (provided as `api/data/city_centroids.json`, a
compact subset of GeoNames for the top 5000 cities by population) resolves city → lat/lon.

```python
import math

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))
```

Grid snapping to 0.1° precision prevents fingerprinting contributors even if the caller
correlates multiple queries:

```python
def snap_to_grid(lat, lon, precision=0.1):
    return round(lat / precision) * precision, round(lon / precision) * precision
```

---

## Privacy Guarantees

1. **City-level only** — raw lat/lon from the client is snapped to a 0.1° grid (~11 km cell)
   before storage. The snapped value is never returned to callers.
2. **Visibility gating** — `private` contributors never appear in nearby results.
3. **No cross-referencing** — the API does not return enough precision for contributors to
   triangulate each other's home address.
4. **Opt-in** — location is not set by default. A contributor with no location set has
   `geo_visibility = private` implicitly.
5. **Right to delete** — `DELETE /api/contributors/{id}/location` wipes all geo fields.

---

## Web: `/map` Page

- Renders a Leaflet.js (or Mapbox GL) map embedded in the Next.js app.
- Contributor markers cluster at city centroids; clicking a cluster reveals contributor
  cards (name, ideas staked, distance from viewer).
- Idea density shown as a heatmap layer using idea `geo_lat_snap` / `geo_lon_snap`.
- Toggled via a `/map` route in `web/src/app/map/`.
- Viewer's location is requested via browser Geolocation API (opt-in prompt); falls back
  to IP geolocation or no location.

---

## CLI: `cc nearby` and `cc location set`

```
cc location set "Berlin, DE"
  → PATCH /api/contributors/{current_contributor}/location
  → prints: "Location set: Berlin, DE (public)"

cc location set "São Paulo, BR" --private
  → sets visibility=private

cc nearby
  → GET /api/nearby?lat=<stored_lat>&lon=<stored_lon>&radius_km=50
  → prints table: name | city | distance_km

cc nearby --radius 200 --format json
  → raw JSON output

cc location clear
  → DELETE /api/contributors/{current_contributor}/location
```

---

## Verification Scenarios

### Scenario 1 — Set and Retrieve Location (full create-read cycle)

**Setup**: Contributor `test-alice` exists (created via POST /api/contributors).

**Action**:
```bash
curl -s -X PATCH $API/api/contributors/contributor:test-alice/location \
  -H "Content-Type: application/json" \
  -d '{"city":"Berlin","country":"DE","lat":52.52,"lon":13.405,"visibility":"public"}'
```

**Expected result**: HTTP 200, response body contains:
```json
{
  "contributor_id": "contributor:test-alice",
  "city": "Berlin",
  "country": "DE",
  "visibility": "public"
}
```
Response must NOT contain `lat` or `lon` fields.

**Then**:
```bash
curl -s $API/api/contributors/contributor:test-alice/location
```
Returns same structure with `updated_at` populated.

**Edge**: Setting `visibility` to `"invisible"` returns 422 with detail mentioning valid values.

---

### Scenario 2 — Nearby Discovery Returns Correct Results

**Setup**: Three contributors exist with locations:
- `test-alice` at Berlin (52.52, 13.40) — visibility=public
- `test-bob` at Hamburg (53.55, 10.00) — visibility=public (~254 km from Berlin)
- `test-carol` at Munich (48.14, 11.58) — visibility=private

**Action**:
```bash
curl -s "$API/api/nearby?lat=52.52&lon=13.40&radius_km=100"
```

**Expected result**: HTTP 200. `contributors` array contains `test-alice` (≈0 km) but NOT
`test-bob` (outside 100 km) and NOT `test-carol` (private). `ideas` array may be empty or
populated.

**Edge**:
```bash
curl -s "$API/api/nearby?radius_km=50"   # missing lat/lon
```
Returns 422: `{"detail": [{"loc": ["query", "lat"], "msg": "field required", ...}]}`

---

### Scenario 3 — Local News Resonance Returns geo_boost

**Setup**: News items exist in the system. At least one item contains "Berlin" in its title or
tags (can be seeded via existing news sources or the `POST /api/news/sources` endpoint).

**Action**:
```bash
curl -s "$API/api/news/resonance/local?location=Berlin,DE&top_n=5"
```

**Expected result**: HTTP 200, response contains `"location": "Berlin, DE"`, `items` array
where each item has `geo_boost` between 0.0 and 1.0 and `score` between 0.0 and 1.0.

**Edge**:
```bash
curl -s "$API/api/news/resonance/local"   # no location
```
Returns 422.

**Edge**:
```bash
curl -s "$API/api/news/resonance/local?location=ZZZUnknownCity999"
```
Returns 422 with message `"location not found"` OR returns 200 with `items: []`.

---

### Scenario 4 — Delete Location Removes from Nearby

**Setup**: `test-alice` has location set to Berlin (public), verified via Scenario 1.

**Action**:
```bash
curl -s -X DELETE $API/api/contributors/contributor:test-alice/location
```
Returns HTTP 204 (no body).

**Then**:
```bash
curl -s "$API/api/nearby?lat=52.52&lon=13.40&radius_km=100"
```
`contributors` array no longer contains `test-alice`.

**Then**:
```bash
curl -s $API/api/contributors/contributor:test-alice/location
```
Returns 404.

**Edge**: Calling DELETE again on the already-deleted location returns 404, not 500.

---

### Scenario 5 — ROI Endpoint Reflects Live State

**Setup**: At least 2 contributors with location set (from previous scenarios, even after
test-alice deletion — use `test-bob` and a fresh contributor).

**Action**:
```bash
curl -s $API/api/geo/roi
```

**Expected result**: HTTP 200:
```json
{
  "contributors_with_location": 2,
  "top_cities": [{"city": "...", "country": "...", "count": 1}],
  "ideas_with_location": 0,
  "avg_radius_km_used": 50.0,
  "spec_ref": "spec-170"
}
```
`contributors_with_location` must equal the actual count of contributors with `geo_visibility`
set to `public` or `network`. `spec_ref` must be exactly `"spec-170"`.

---

## How to Show It Is Working Over Time

1. **ROI endpoint trend** — `GET /api/geo/roi` polled weekly by the dashboard;
   `contributors_with_location` charted as a % of total contributors. A rising curve
   proves adoption.
2. **Nearby heatmap density** — `/map` page cluster sizes grow over time as more
   contributors opt in.
3. **Local resonance usage** — `GET /api/news/resonance/local` call count tracked via
   activity events; non-zero daily call rate proves the endpoint is live and useful.
4. **CLI adoption** — `cc nearby` and `cc location set` usage accumulates as contribution
   events in the ledger.
5. **CI green badge** — `api/tests/test_geo_location.py` runs on every PR; the green badge
   on the spec's PR is the minimum bar for considering the contract live.

---

## Risks and Assumptions

| Risk | Mitigation |
|---|---|
| Geocoding accuracy for less-common cities | Bundled `city_centroids.json` (top 5000 cities); unknown cities return 422 with "city not found" — never silently accept. |
| Privacy leakage via triangulation | 0.1° grid snap limits precision to ~11 km cells; raw lat/lon never returned; rate-limit `/api/nearby` to 60 req/min per IP. |
| Performance at scale | Haversine over all located contributors is O(N); <10ms at 10k located contributors. Index by lat_snap/lon_snap bucket for >50k scale. |
| Leaflet bundle size on web | Loaded only on `/map` route via dynamic import — no impact on main bundle. |
| City name disambiguation | Require `city,country` format; resolver prefers ISO country code when provided. |

---

## Known Gaps and Follow-up Tasks

- **Real-time map updates** — WebSocket push for contributor location changes is out of scope
  for MVP; polling every 60s is acceptable.
- **Idea geo-tagging from creation** — The idea creation API does not yet support a `location`
  field. Only contributor location is scoped here; idea geo-tagging is a follow-up
  (spec-171 candidate).
- **Regional news source weighting** — `geo_boost` is computed from keyword proximity only.
  A future spec should feed actual RSS source geography into the boost signal.
- **Federated location sharing** — In multi-node federation, location data should stay on the
  originating node. Out of scope here.
- **Mobile geolocation on web** — Requires HTTPS and user permission; graceful fallback
  needed for non-permissioned browsers. Handled by the map page's permission prompt.
