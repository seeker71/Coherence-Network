spec = """# Spec: Geo-location — Nearby Contributors, Local Ideas, Regional News Resonance

Spec ID: task_568bd9ca41fd0dcf  |  See also: specs/170-geo-location.md

This document is the authoritative task spec for implementation of the geo-location feature.
Adapted from Living Codex SpatialGraphModule. Contributors can optionally share location at
city-level granularity — enabling nearby discovery, regionally-relevant ideas, and
location-weighted news resonance. Privacy-first: optional, city-level only, contributor-controlled.

---

## Goal

Enable spatial awareness in the Coherence Network without compromising contributor privacy:

- Discover contributors and ideas within geographic proximity
- Match news resonance to regional context
- Power local meetups and city-specific collaboration clusters
- Provide a living proof-of-working dashboard via /api/geo/roi

---

## Problem

- All contributors appear equidistant; proximity is invisible.
- Local meetups cannot form without a way to find contributors within travel distance.
- Global news feeds lack geographic weight; local headlines rank identically to distant events.
- The Living Codex SpatialGraphModule demonstrated that city-level location dramatically
  improves community cohesion and local event coordination without requiring PII.

---

## Solution

1. **Location PATCH/GET/DELETE** — contributors self-report city + country. Coordinates are
   snapped to a 0.1-degree grid (~11km cells); raw input is never stored or returned.
2. **Visibility tiers** — public | network | private. Only public/network contributors
   appear in /api/nearby. Default is public.
3. **Nearby discovery** — /api/nearby?lat=&lon=&radius_km= returns contributors and ideas
   within a geographic radius, ordered by haversine distance.
4. **Local news resonance** — /api/news/resonance/local?location= returns news items with a
   geo_boost multiplier applied to scores based on proximity to the named city.
5. **ROI endpoint** — /api/geo/roi returns live adoption counters for proof-of-working.
6. **Web map** — /map page renders contributor clusters and idea density heatmap.
7. **CLI** — cc nearby, cc location set, cc location unset.

---

## Open Questions Resolved

### Q: How can we improve this idea, show whether it is working, and make proof clearer over time?

**Improvements over basic location storage:**

1. Tiered visibility (public/network/private) — better than binary on/off; lets contributors
   share with the network without appearing on the public map.
2. City + country format (Berlin,DE) — resolves disambiguation and enables ISO-standard queries.
3. Idea geo-tagging — ideas inherit contributor location at creation, enabling spatially-relevant
   idea discovery alongside contributor discovery.
4. Transparent geo_boost — /api/news/resonance/local returns a geo_boost field (0.0-1.0) per
   article, making the scoring algorithm auditable.
5. DELETE endpoint — contributors can remove all location data permanently (GDPR pattern).

**How to show it is working:**

- /api/geo/roi is the primary proof-of-working instrument: contributors_with_location,
  top_cities, ideas_with_location, avg_radius_km_used, nearby_queries_last_7d.
- /map page renders a live "Geo Stats" card calling /api/geo/roi on page load.
- Activity events logged on every cc nearby call create a growing ledger of CLI adoption.

**Making proof clearer over time:**

| Timeframe | Signal | Healthy Value |
|-----------|--------|---------------|
| Day 0     | contributors_with_location | > 0 (after first opt-in) |
| Week 2    | contributors_with_location | >= 5 |
| Week 2    | nearby_queries_last_7d | >= 10 |
| Month 1   | cities_represented count | >= 10 |
| Month 1   | ideas_with_location | >= 20 |

CI smoke test: GET /api/geo/roi runs on every deploy; contributors_with_location must not
drop below the prior run (regression guard). spec_ref field provides machine-verifiable
traceability to this exact spec.

---

## Acceptance Criteria

1. PATCH /api/contributors/{id}/location accepts {"city": "Berlin", "country": "DE",
   "geo_visibility": "public"} and returns 200 with stored city, snapped lat/lon, geo_visibility.
2. GET /api/contributors/{id}/location returns city, country, lat_snap, lon_snap,
   geo_visibility, updated_at. Returns 404 if contributor not found; {"location": null} if unset.
3. DELETE /api/contributors/{id}/location returns 204. Second DELETE returns 404 (not 500).
4. GET /api/nearby?lat=&lon=&radius_km= returns only public/network contributors within radius.
   Default radius 50km; max 500km. Missing lat or lon returns 422.
5. GET /api/news/resonance/local?location= returns news items with geo_boost in [0.0, 1.0].
   Unresolvable location returns 422. Missing location param returns 422.
6. GET /api/geo/roi returns contributors_with_location, top_cities, ideas_with_location,
   avg_radius_km_used, spec_ref="task_568bd9ca41fd0dcf".
7. Unknown city in PATCH returns 422 with detail containing "city not found".
8. radius_km > 500 returns 422 with detail "radius_km exceeds maximum of 500".
9. Web /map page loads without JS errors; cluster markers visible for located contributors.
10. CLI cc nearby outputs nearby contributors or "No contributors found within 50km". Exit 0.
11. CLI cc location set <city,country> confirms location set. Exit 0.
12. All 15 integration tests in api/tests/test_geo_location.py pass.

---

## API Contract

### PATCH /api/contributors/{id}/location

Request body:
```json
{
  "city": "Berlin",
  "country": "DE",
  "geo_visibility": "public"
}
```

Response 200:
```json
{
  "contributor_id": "abc123",
  "city": "Berlin",
  "country": "DE",
  "lat_snap": 52.5,
  "lon_snap": 13.4,
  "geo_visibility": "public",
  "updated_at": "2026-03-28T12:00:00Z"
}
```

Response 422: `{"detail": "city not found: ZZZCity999"}`
Response 404: `{"detail": "Contributor not found"}`

---

### GET /api/contributors/{id}/location

Response 200 (set):
```json
{
  "contributor_id": "abc123",
  "city": "Berlin",
  "country": "DE",
  "lat_snap": 52.5,
  "lon_snap": 13.4,
  "geo_visibility": "public",
  "updated_at": "2026-03-28T12:00:00Z"
}
```

Response 200 (not set): `{"contributor_id": "abc123", "location": null}`
Response 404: `{"detail": "Contributor not found"}`

---

### DELETE /api/contributors/{id}/location

Response 204: (no body)
Response 404: `{"detail": "Location not set"}`

---

### GET /api/nearby

Query params:
- `lat` (float, required)
- `lon` (float, required)
- `radius_km` (float, optional, default 50, max 500)
- `include` (contributors|ideas|both, optional, default both)

Response 200:
```json
{
  "center": {"lat": 52.52, "lon": 13.405},
  "radius_km": 50.0,
  "contributors": [
    {
      "contributor_id": "abc123",
      "city": "Berlin",
      "country": "DE",
      "distance_km": 3.2,
      "idea_count": 7
    }
  ],
  "ideas": [
    {
      "idea_id": "idea_xyz",
      "title": "Local mesh networks for urban neighbourhoods",
      "contributor_city": "Berlin",
      "distance_km": 3.2
    }
  ],
  "total_contributors": 1,
  "total_ideas": 1
}
```

Response 422: `{"detail": "radius_km exceeds maximum of 500"}`
Response 422: `{"detail": "lat and lon are required"}`

---

### GET /api/news/resonance/local

Query params:
- `location` (string "City,CC" format, required)
- `top_n` (int, optional, default 10, max 50)

Response 200:
```json
{
  "location": "Berlin, DE",
  "resolved_lat": 52.5,
  "resolved_lon": 13.4,
  "items": [
    {
      "id": "news_abc",
      "title": "Startup hub opens in Mitte district",
      "score": 0.87,
      "geo_boost": 0.91,
      "published_at": "2026-03-27T09:00:00Z"
    }
  ],
  "total": 1
}
```

Response 422: `{"detail": "location not found: Xanadu,ZZ"}`
Response 422: `{"detail": "location parameter is required"}`

---

### GET /api/geo/roi

Response 200:
```json
{
  "spec_ref": "task_568bd9ca41fd0dcf",
  "contributors_with_location": 12,
  "top_cities": [
    {"city": "Berlin", "country": "DE", "count": 4},
    {"city": "London", "country": "GB", "count": 3}
  ],
  "ideas_with_location": 27,
  "avg_radius_km_used": 62.5,
  "nearby_queries_last_7d": 47
}
```

---

## Data Model

```yaml
ContributorLocation:
  contributor_id: string (FK to contributors table)
  city:           string
  country:        string (ISO 3166-1 alpha-2, e.g. "DE")
  lat_snap:       float  (rounded to 0.1 degree)
  lon_snap:       float  (rounded to 0.1 degree)
  geo_visibility: enum [public, network, private] (default: public)
  updated_at:     datetime (ISO 8601 UTC)
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| api/app/models/geo_location.py | Create | Pydantic models for all request/response shapes |
| api/app/services/geo_location_service.py | Create | City resolution, coord snap, haversine, nearby query, news scoring |
| api/app/routers/geo_location.py | Create | Route handlers |
| api/app/main.py | Modify | Register geo_location router |
| api/tests/test_geo_location.py | Create | 15 integration tests |
| web/src/app/map/page.tsx | Create | Map view page with ROI stats card |
| web/src/components/MapView.tsx | Create | react-leaflet cluster component (dynamic import) |
| cli/commands/geo.py | Create | cc nearby, cc location set, cc location unset |

---

## Task Card

```yaml
goal: Privacy-first city-level geolocation — nearby contributor discovery and regional news resonance
files_allowed:
  - api/app/models/geo_location.py
  - api/app/services/geo_location_service.py
  - api/app/routers/geo_location.py
  - api/app/main.py
  - api/tests/test_geo_location.py
  - web/src/app/map/page.tsx
  - web/src/components/MapView.tsx
  - cli/commands/geo.py
done_when:
  - All 15 tests in api/tests/test_geo_location.py pass
  - PATCH /api/contributors/{id}/location stores snapped coords and returns correct shape
  - GET /api/nearby returns contributors and ideas within radius
  - GET /api/news/resonance/local returns geo-boosted articles
  - GET /api/geo/roi returns spec_ref=task_568bd9ca41fd0dcf
  - Web /map page loads without JS errors
  - cc nearby and cc location set execute with exit code 0
commands:
  - cd api && pytest -q tests/test_geo_location.py
  - cd web && npm run build
  - cc nearby
  - cc location set Berlin,DE
constraints:
  - Coordinates snapped to 0.1 degree grid; raw lat/lon never returned
  - No IP-based geolocation; city+country must be self-reported
  - geo_visibility=private excludes from ALL spatial queries immediately
  - radius_km hard cap 500
  - No external geocoding API calls; bundled city_centroids.json only
```

---

## Verification Scenarios

### Scenario 1 — Full PATCH/GET/Nearby Cycle

**Setup**: Contributor test-alice exists with no location.

**Action (set)**:
```bash
curl -s -X PATCH $API/api/contributors/contributor:test-alice/location \\
  -H "Content-Type: application/json" \\
  -d '{"city":"Berlin","country":"DE","geo_visibility":"public"}'
```
**Expected**: HTTP 200, city=Berlin, country=DE, lat_snap=52.5, lon_snap=13.4, geo_visibility=public.

**Action (read)**:
```bash
curl -s $API/api/contributors/contributor:test-alice/location
```
**Expected**: Same shape returned, updated_at is ISO 8601 UTC string.

**Action (nearby)**:
```bash
curl -s "$API/api/nearby?lat=52.52&lon=13.40&radius_km=50"
```
**Expected**: HTTP 200, contributors array contains test-alice with distance_km < 50, city=Berlin.

---

### Scenario 2 — Visibility Private Hides From Nearby

**Setup**: test-alice has Berlin location, geo_visibility=public.

**Action (set private)**:
```bash
curl -s -X PATCH $API/api/contributors/contributor:test-alice/location \\
  -H "Content-Type: application/json" \\
  -d '{"geo_visibility":"private"}'
```
**Expected**: HTTP 200, geo_visibility=private.

**Action (nearby)**:
```bash
curl -s "$API/api/nearby?lat=52.52&lon=13.40&radius_km=100"
```
**Expected**: contributors array does NOT contain test-alice.

**Edge**: Set geo_visibility=public again — test-alice reappears in next nearby query.

---

### Scenario 3 — Delete Location Removes From Nearby

**Setup**: test-alice has Berlin location (public).

**Action**:
```bash
curl -s -X DELETE $API/api/contributors/contributor:test-alice/location
```
**Expected**: HTTP 204.

**Then**:
```bash
curl -s "$API/api/nearby?lat=52.52&lon=13.40&radius_km=100"
```
**Expected**: test-alice NOT in contributors array.

**Then**:
```bash
curl -s $API/api/contributors/contributor:test-alice/location
```
**Expected**: HTTP 404.

**Edge**: DELETE again returns 404 (not 500).

---

### Scenario 4 — Error Handling

**Action (unknown city)**:
```bash
curl -s -X PATCH $API/api/contributors/contributor:test-alice/location \\
  -H "Content-Type: application/json" \\
  -d '{"city":"ZZZUnresolvableCity999","country":"ZZ","geo_visibility":"public"}'
```
**Expected**: HTTP 422, detail contains "city not found".

**Action (radius too large)**:
```bash
curl -s "$API/api/nearby?lat=52.52&lon=13.40&radius_km=9999"
```
**Expected**: HTTP 422, detail="radius_km exceeds maximum of 500".

**Action (contributor not found)**:
```bash
curl -s -X PATCH $API/api/contributors/contributor:nonexistent_xyz/location \\
  -H "Content-Type: application/json" \\
  -d '{"city":"London","country":"GB","geo_visibility":"public"}'
```
**Expected**: HTTP 404, detail="Contributor not found".

**Action (missing lat/lon)**:
```bash
curl -s "$API/api/nearby?radius_km=50"
```
**Expected**: HTTP 422, detail contains "lat and lon are required".

---

### Scenario 5 — Local News Resonance

**Setup**: At least one news article with location tags including "Berlin" or "Germany".
test-alice has location Berlin,DE set.

**Action**:
```bash
curl -s "$API/api/news/resonance/local?location=Berlin,DE&top_n=5"
```
**Expected**: HTTP 200, items is a non-empty array, each item has geo_boost in [0.0, 1.0]
and score in [0.0, 1.0].

**Edge (unresolvable)**: `location=Zephyria,ZZ` returns HTTP 422 with "location not found".
**Edge (missing param)**: No location param returns HTTP 422.

---

### Scenario 6 — ROI Proof-of-Working

**Setup**: At least 2 contributors with public location set.

**Action**:
```bash
curl -s $API/api/geo/roi
```
**Expected**: HTTP 200, contributors_with_location >= 2, spec_ref="task_568bd9ca41fd0dcf",
top_cities is a non-empty array with city, country, count fields.

---

## Privacy Design

| Concern | Mitigation |
|---------|-----------|
| Exact location tracking | 0.1-degree grid snap (~11km cells); centroid only, never raw input stored |
| Passive inference via API | Only city names returned; raw snapped coords not in nearby results |
| IP-based geolocation | Never used; all location data is explicitly self-reported |
| Forced visibility | geo_visibility=private removes from all queries; default is public not auto-set |
| Data deletion | DELETE endpoint removes all geo data permanently; returns 204 |

---

## Implementation Notes

**City Resolution**: Bundled city_centroids.json (top 5000 cities keyed by "City,CC" lowercase).
Unknown cities return 422 immediately. No external API dependency at runtime.

**Coordinate Snapping**: `lat_snap = round(raw_lat, 1)`, `lon_snap = round(raw_lon, 1)`.
Raw input coordinates are not stored. Two contributors in the same 0.1-degree cell
appear at identical snapped coordinates — this is intentional privacy behaviour.

**Haversine Distance**: Server-side computation for all /api/nearby results. O(N) over
all located contributors; sufficient up to ~10k located contributors. Index by lat_snap
bucket for scale.

**Web Map**: react-leaflet with leaflet.markercluster. OSM tiles (no API key required).
Dynamically imported on /map route only to avoid impacting main bundle.

---

## Out of Scope

- Street-level or postal-code precision
- IP-based geolocation
- Real-time location tracking or movement history
- Location-based push notifications
- External geocoding API calls at runtime

---

## Risks and Assumptions

- Risk: city_centroids.json has gaps for less-common cities. Mitigation: 422 with clear error;
  follow-up spec adds fuzzy matching and alias table.
- Risk: react-leaflet bundle size (~100KB). Mitigation: dynamic import on /map route only.
- Risk: /api/nearby linear scan slow at scale. Mitigation: bucket index by lat_snap/lon_snap
  for >50k contributors; document in implementation task.
- Assumption: contributors are identified by "contributor:{handle}" format or UUID.
- Assumption: news articles have an optional geo_tags/location_tags field, or a companion spec
  adds it. If absent, /api/news/resonance/local returns empty items list gracefully.

---

## Known Gaps and Follow-up Tasks

- Fuzzy city name matching (e.g. "Sao Paulo" matching accented form) — follow-up spec
- Location-aware idea feed (GET /api/ideas?near_me=true) — follow-up spec
- CLI cc location unset command — include in implementation
- /map page accessibility (keyboard navigation, ARIA labels) — follow-up spec
- Rate limit /api/nearby to 60 req/min per IP — implementation detail, not blocking

---

## Failure/Retry Reflection

- Failure: city not in bundled list. Blind spot: non-ASCII names. Next: add alias table post-MVP.
- Failure: snapping silently wrong due to rounding edge case. Blind spot: off-by-one near 0.
  Next: explicit unit test for snap(0.0, 0.0) == (0.0, 0.0).
- Failure: /api/nearby slow at scale. Blind spot: no DB index. Next: CREATE INDEX on lat_snap/lon_snap.

---

## Research Inputs

- 2026-03-28: Living Codex SpatialGraphModule — origin pattern for city-level proximity design
- 2024-01-01: Haversine formula https://en.wikipedia.org/wiki/Haversine_formula
- specs/170-geo-location.md — primary spec for same feature authored by parallel agent (task_0ea06459491de62f)
"""

with open("specs/task_568bd9ca41fd0dcf.md", "w") as f:
    f.write(spec)
print("written:", len(spec), "chars")
