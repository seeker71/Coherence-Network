# Spec 171 — Visible Contribution Recognition and Growth Tracking

## Goal

Make every contribution — a question, a spec, a review, a share — immediately visible to the
contributor and the community. Track growth over time. Make the invisible labor of thinking,
connecting, and caring explicit and valued so that contributors receive timely recognition,
understand their impact, and the network can prove that participation drives coherence.

---

## Problem

- Contributors currently have no unified view of their contributions across all activity types
  (ideas, specs, reviews, questions, shares, comments, upvotes).
- Growth is invisible: a contributor who has written 50 specs has no way to see their trajectory
  alongside a newcomer's first question — both look flat in the graph.
- Community recognition is absent: there is no mechanism to surface "this contributor has been
  doing meaningful work" to other participants.
- The "invisible labor" of thinking (drafting a question that unlocks a stuck spec) and caring
  (reviewing a PR at midnight) produces no visible signal.
- Without evidence of working recognition systems, the idea cannot prove its own value over time.

---

## Solution

A **Contribution Activity Stream** with a **Growth Profile** per contributor, backed by a new
`contribution_events` graph-node layer and exposed through:

1. **Event recording** — `POST /api/contributions/events` — logs any recognized contribution
   type with optional metadata. Idempotent by `(contributor_id, event_type, ref_id)`.
2. **Stream** — `GET /api/contributors/{id}/activity` — paginated, reverse-chronological feed
   of all contribution events for a single contributor.
3. **Growth profile** — `GET /api/contributors/{id}/growth` — aggregate summary: total events,
   streak (consecutive active days), weekly/monthly deltas, type breakdown, and a `growth_score`
   (0.0–1.0) representing trajectory relative to network median.
4. **Leaderboard** — `GET /api/contributions/leaderboard` — top contributors ranked by
   `growth_score`, filterable by `type`, `period` (7d/30d/all), and `min_events`.
5. **Recognition badges** — `GET /api/contributors/{id}/badges` — milestone badges earned
   (e.g. "First Spec", "10-Day Streak", "Community Anchor").
6. **ROI endpoint** — `GET /api/contributions/roi` — aggregate proof that the recognition
   system is working: median growth_score before/after recognition events, badge issuance
   rate, active-contributor retention rate, `spec_ref: "spec-171"`.

Each endpoint is read-only except `POST /api/contributions/events` (write). All responses
are Pydantic models. All timestamps are ISO 8601 UTC.

---

## Acceptance Criteria

1. `POST /api/contributions/events` accepts a JSON body with `contributor_id`, `event_type`
   (one of: `idea`, `spec`, `review`, `question`, `share`, `comment`, `upvote`, `badge`),
   `ref_id` (optional string), `metadata` (optional dict), and returns HTTP 201 with the
   created event including `id`, `timestamp`, `event_type`, `contributor_id`, `ref_id`.
2. Duplicate `POST` with the same `(contributor_id, event_type, ref_id)` returns HTTP 200
   (not 201, not 409) — idempotent, returning the existing record.
3. `POST` with an invalid `event_type` returns HTTP 422.
4. `POST` with missing `contributor_id` returns HTTP 422.
5. `GET /api/contributors/{id}/activity` returns `{"items": [...], "total": N, "page": 1,
   "page_size": 20}` — items are reverse-chronological `ContributionEvent` objects. Supports
   `?page=`, `?page_size=`, `?event_type=` filters.
6. `GET /api/contributors/{id}/activity` for an unknown contributor returns HTTP 404.
7. `GET /api/contributors/{id}/growth` returns an object containing: `contributor_id`,
   `total_events`, `streak_days`, `weekly_delta`, `monthly_delta`, `type_breakdown` (dict
   mapping event_type → count), `growth_score` (float 0.0–1.0), `last_active` (ISO 8601 UTC).
8. `GET /api/contributions/leaderboard` returns `{"items": [...], "period": "30d", "total": N}`
   where each item has `contributor_id`, `display_name`, `growth_score`, `total_events`,
   `streak_days`. Supports `?period=7d|30d|all`, `?type=<event_type>`, `?limit=` (max 100).
9. `GET /api/contributors/{id}/badges` returns `{"badges": [...]}` where each badge has
   `id`, `name`, `description`, `awarded_at`, and `ref_event_id`. Empty list for new
   contributors (not 404).
10. `GET /api/contributions/roi` returns JSON with `median_growth_score`,
    `active_contributor_count`, `badge_issuance_rate`, `retention_rate_30d`,
    `measurement_period_days`, and `spec_ref: "spec-171"`.
11. All 12 integration tests in `api/tests/test_contribution_recognition.py` pass.
12. `cc contrib-growth <contributor_id>` CLI command prints a one-line summary:
    `<name>: <total_events> events | streak <N>d | score <score>`.

---

## Data Model

### `ContributionEvent` (Pydantic model — `api/app/models/contribution_event.py`)

```yaml
ContributionEvent:
  properties:
    id:           { type: string, format: uuid, generated }
    contributor_id: { type: string, format: uuid, required }
    event_type:   { type: string, enum: [idea, spec, review, question, share, comment, upvote, badge], required }
    ref_id:       { type: string, nullable: true }
    metadata:     { type: object, default: {} }
    timestamp:    { type: string, format: datetime, ISO8601 UTC, generated }
```

### `ContributorGrowthProfile` (Pydantic model — `api/app/models/contribution_event.py`)

```yaml
ContributorGrowthProfile:
  properties:
    contributor_id:   { type: string, format: uuid }
    total_events:     { type: integer, min: 0 }
    streak_days:      { type: integer, min: 0 }
    weekly_delta:     { type: integer }
    monthly_delta:    { type: integer }
    type_breakdown:   { type: object, additionalProperties: { type: integer } }
    growth_score:     { type: number, min: 0.0, max: 1.0 }
    last_active:      { type: string, format: datetime, nullable: true }
```

### `ContributorBadge` (Pydantic model — `api/app/models/contribution_event.py`)

```yaml
ContributorBadge:
  properties:
    id:            { type: string, format: uuid }
    contributor_id: { type: string, format: uuid }
    name:          { type: string, enum: [First Contribution, First Spec, 10-Day Streak, 30-Day Streak, Community Anchor, Top Reviewer, Idea Catalyst] }
    description:   { type: string }
    awarded_at:    { type: string, format: datetime }
    ref_event_id:  { type: string, format: uuid, nullable: true }
```

### Graph Storage

Events are stored as graph nodes:
- `type: "contribution_event"` with all fields as node properties
- Edge: `contributor_node → HAS_EVENT → contribution_event_node` (type: `"has_event"`)
- Uniqueness index: `(contributor_id, event_type, ref_id)` for idempotency

---

## API Contract

### `POST /api/contributions/events`

**Request body**
```json
{
  "contributor_id": "uuid",
  "event_type": "spec",
  "ref_id": "spec-171",
  "metadata": { "title": "Contribution Recognition" }
}
```

**Response 201 (new event)**
```json
{
  "id": "uuid",
  "contributor_id": "uuid",
  "event_type": "spec",
  "ref_id": "spec-171",
  "metadata": { "title": "Contribution Recognition" },
  "timestamp": "2026-03-28T07:00:00Z"
}
```

**Response 200 (duplicate — idempotent)**
Same as 201 body, HTTP 200.

**Response 422** — invalid `event_type` or missing required fields.

---

### `GET /api/contributors/{id}/activity`

**Query params**: `page` (int, default 1), `page_size` (int, default 20, max 100), `event_type` (optional filter)

**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "contributor_id": "uuid",
      "event_type": "review",
      "ref_id": "pr-42",
      "metadata": {},
      "timestamp": "2026-03-28T06:30:00Z"
    }
  ],
  "total": 47,
  "page": 1,
  "page_size": 20
}
```

**Response 404** — contributor not found.

---

### `GET /api/contributors/{id}/growth`

**Response 200**
```json
{
  "contributor_id": "uuid",
  "total_events": 47,
  "streak_days": 12,
  "weekly_delta": 8,
  "monthly_delta": 31,
  "type_breakdown": {
    "spec": 12,
    "review": 15,
    "idea": 5,
    "question": 10,
    "share": 3,
    "comment": 2
  },
  "growth_score": 0.74,
  "last_active": "2026-03-28T06:30:00Z"
}
```

**Response 404** — contributor not found.

---

### `GET /api/contributions/leaderboard`

**Query params**: `period` (7d|30d|all, default 30d), `type` (optional), `limit` (int, default 10, max 100)

**Response 200**
```json
{
  "items": [
    {
      "contributor_id": "uuid",
      "display_name": "alice",
      "growth_score": 0.91,
      "total_events": 120,
      "streak_days": 22
    }
  ],
  "period": "30d",
  "total": 47
}
```

---

### `GET /api/contributors/{id}/badges`

**Response 200**
```json
{
  "badges": [
    {
      "id": "uuid",
      "contributor_id": "uuid",
      "name": "First Spec",
      "description": "Wrote their first specification",
      "awarded_at": "2026-03-01T10:00:00Z",
      "ref_event_id": "uuid"
    }
  ]
}
```

---

### `GET /api/contributions/roi`

**Response 200**
```json
{
  "median_growth_score": 0.52,
  "active_contributor_count": 34,
  "badge_issuance_rate": 0.8,
  "retention_rate_30d": 0.71,
  "measurement_period_days": 30,
  "spec_ref": "spec-171"
}
```

---

## Files to Create/Modify

- `api/app/models/contribution_event.py` — Pydantic models for `ContributionEvent`, `ContributorGrowthProfile`, `ContributorBadge`, ROI response
- `api/app/routers/contribution_recognition.py` — all routes defined above
- `api/app/services/contribution_recognition_service.py` — business logic: event dedup, growth score calc, streak calc, badge evaluation, leaderboard ranking
- `api/app/main.py` — register `contribution_recognition` router
- `api/tests/test_contribution_recognition.py` — 12 integration tests (see Acceptance Criteria)

---

## Growth Score Formula

`growth_score` is a normalized 0.0–1.0 float computed as:

```
raw = (log1p(total_events_period) * 0.4) + (streak_days * 0.02) + (type_diversity * 0.2)
growth_score = min(raw / network_p95_raw, 1.0)
```

Where:
- `total_events_period`: events in the selected period window (default 30d)
- `streak_days`: longest consecutive-day streak within the period
- `type_diversity`: number of distinct `event_type` values used (0–8), normalized 0–1
- `network_p95_raw`: 95th percentile of `raw` across all contributors (cached, recomputed hourly)

This formula rewards breadth (many types), consistency (streak), and volume, normalized against
the network to prevent score inflation as the network grows.

---

## Badge Evaluation Rules

Badges are evaluated automatically after each `POST /api/contributions/events`:

| Badge name | Trigger condition |
|---|---|
| First Contribution | `total_events == 1` |
| First Spec | `type_breakdown["spec"] == 1` |
| 10-Day Streak | `streak_days >= 10` |
| 30-Day Streak | `streak_days >= 30` |
| Community Anchor | `total_events >= 100 AND type_diversity >= 5` |
| Top Reviewer | `type_breakdown["review"] >= 20` |
| Idea Catalyst | `type_breakdown["idea"] >= 10 AND type_breakdown["question"] >= 10` |

Badge issuance is idempotent — same badge is never awarded twice to the same contributor.

---

## Verification Scenarios

### Scenario 1 — Record a contribution event and retrieve it

**Setup**: A contributor exists with a known `id` (e.g. `contrib-abc`).

**Action**:
```bash
API=https://api.coherencycoin.com
curl -s -X POST $API/api/contributions/events \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"contrib-abc","event_type":"spec","ref_id":"spec-171","metadata":{"title":"Test spec"}}'
```

**Expected result**: HTTP 201, response contains `id` (UUID), `event_type: "spec"`,
`ref_id: "spec-171"`, `timestamp` (ISO 8601 UTC), `contributor_id: "contrib-abc"`.

**Then**:
```bash
curl -s $API/api/contributors/contrib-abc/activity
```
Returns `items` array with the recorded event, `total >= 1`.

**Edge — duplicate**:
```bash
# POST same body again
curl -s -o /dev/null -w "%{http_code}" -X POST $API/api/contributions/events \
  -d '{"contributor_id":"contrib-abc","event_type":"spec","ref_id":"spec-171","metadata":{"title":"Test spec"}}'
```
Returns HTTP **200** (not 201, not 409).

---

### Scenario 2 — Growth profile reflects recorded events

**Setup**: Contributor `contrib-abc` has 5 events recorded across 3 types over 3 days.

**Action**:
```bash
curl -s $API/api/contributors/contrib-abc/growth
```

**Expected result**: HTTP 200, `total_events >= 5`, `type_breakdown` contains at least 3
keys, `growth_score` between 0.0 and 1.0 (not null, not negative), `last_active` is an
ISO 8601 UTC timestamp within the last hour.

**Edge — unknown contributor**:
```bash
curl -s -o /dev/null -w "%{http_code}" $API/api/contributors/does-not-exist-999/growth
```
Returns HTTP **404**.

---

### Scenario 3 — Invalid event_type is rejected

**Setup**: Any state.

**Action**:
```bash
curl -s -X POST $API/api/contributions/events \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"contrib-abc","event_type":"invalid_type_xyz"}'
```

**Expected result**: HTTP **422**, response body contains `"detail"` array indicating
`event_type` validation failure.

**Edge — missing contributor_id**:
```bash
curl -s -X POST $API/api/contributions/events \
  -H "Content-Type: application/json" \
  -d '{"event_type":"spec"}'
```
Returns HTTP **422**.

---

### Scenario 4 — Leaderboard returns ranked contributors

**Setup**: At least 3 contributors have recorded events within the last 30 days.

**Action**:
```bash
curl -s "$API/api/contributions/leaderboard?period=30d&limit=5"
```

**Expected result**: HTTP 200, `items` is an array (length 0–5), each item has
`contributor_id`, `display_name`, `growth_score` (0.0–1.0), `total_events` (>= 0),
`streak_days` (>= 0). Array is sorted descending by `growth_score`.

**Edge — filter by type**:
```bash
curl -s "$API/api/contributions/leaderboard?period=30d&type=spec&limit=10"
```
Returns same shape, but `growth_score` is computed from `spec` events only.

---

### Scenario 5 — Badge is awarded on milestone and is idempotent

**Setup**: Contributor `contrib-new` has zero events.

**Action**: POST one `spec` event for `contrib-new`.

```bash
curl -s -X POST $API/api/contributions/events \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"contrib-new","event_type":"spec","ref_id":"first-spec-001"}'
```

**Then**:
```bash
curl -s $API/api/contributors/contrib-new/badges
```

**Expected result**: HTTP 200, `badges` array contains both `"First Contribution"` and
`"First Spec"` badges, each with `awarded_at` timestamp and `ref_event_id`.

**Edge — idempotency**:
```bash
# POST same event again
curl -s -X POST $API/api/contributions/events \
  -H "Content-Type: application/json" \
  -d '{"contributor_id":"contrib-new","event_type":"spec","ref_id":"first-spec-001"}'
curl -s $API/api/contributors/contrib-new/badges
```
`badges` array still has exactly the same 2 badges — no duplicates.

---

## ROI and Proof of Working

`GET /api/contributions/roi` is the primary evidence endpoint. It proves the feature is
working by exposing:

- `active_contributor_count` — grows when contributors engage; stagnation signals the
  feature is not driving participation.
- `badge_issuance_rate` — fraction of active contributors who earned at least one badge
  in the period; low rate means milestones are miscalibrated.
- `retention_rate_30d` — fraction of contributors active in weeks 1–2 who are also
  active in weeks 3–4; growth without retention is vanity.
- `median_growth_score` — rising median means the network is collectively improving, not
  just a few power users dominating.

**Baseline at launch**: record all four metrics on day 0. At 30 and 90 days, compare.
If `retention_rate_30d >= 0.6` and `median_growth_score` is trending up, the feature is
proving its value. If not, the badge thresholds or scoring formula require recalibration.

---

## Task Card

```yaml
goal: Expose contributor activity, growth scores, and recognition badges via API
files_allowed:
  - api/app/models/contribution_event.py
  - api/app/routers/contribution_recognition.py
  - api/app/services/contribution_recognition_service.py
  - api/app/main.py
  - api/tests/test_contribution_recognition.py
done_when:
  - POST /api/contributions/events returns 201 for new events, 200 for duplicates
  - GET /api/contributors/{id}/activity returns paginated event list
  - GET /api/contributors/{id}/growth returns growth profile with growth_score
  - GET /api/contributions/leaderboard returns ranked contributors
  - GET /api/contributors/{id}/badges returns earned badges
  - GET /api/contributions/roi returns aggregate proof metrics with spec_ref "spec-171"
  - All 12 tests in api/tests/test_contribution_recognition.py pass
commands:
  - cd api && pytest -q tests/test_contribution_recognition.py
constraints:
  - event_type must be one of the defined 8 values; no free-form strings
  - duplicate events must return 200 not 409
  - growth_score must be float in [0.0, 1.0]
  - badges are never duplicated per contributor
  - exact coordinates and PII are never stored
```

---

## Research Inputs

- `2026-03-28` — Living Codex `UCore` — contributor identity, resonance, belief systems
  are the philosophical foundation for contribution value lineage in this project.
- `2026-03-28` — Existing `api/app/models/contribution.py` — current contribution model
  is financial (cost, asset, coherence_score); this spec adds behavioral/activity layer.
- `2026-03-28` — `api/app/routers/contributions.py` — existing GitHub webhook integration
  shows prior art for contribution ingestion; this spec generalizes the pattern.

---

## Concurrency Behavior

- **Read operations** (`GET /activity`, `/growth`, `/leaderboard`, `/badges`, `/roi`):
  Safe for concurrent access; growth scores are computed on-read from event counts;
  no locking required.
- **Write operations** (`POST /events`): Idempotent by `(contributor_id, event_type, ref_id)`;
  concurrent POSTs with the same triple must both succeed and return the same event id.
  Use graph-layer upsert semantics. Race between two distinct events (different `ref_id`) is
  safe: last-write-wins on node properties, event timeline grows append-only.
- **Badge evaluation**: Evaluated synchronously after event write. If two events arrive
  concurrently and both would trigger the same badge, idempotency ensures only one badge
  record is created.

---

## Out of Scope

- Social notifications (push/email on badge award) — follow-up spec.
- Public contributor profile pages (web UI) — follow-up spec.
- Cross-contributor comparison UI — follow-up spec.
- Monetary rewards tied to badges — governance decision required.
- Retroactive backfill of historical git/PR activity — separate migration task.

---

## Risks and Assumptions

- **Risk**: Growth score formula can be gamed by spamming low-effort events (e.g. 1000 `upvote`
  events). **Mitigation**: Rate-limit by `(contributor_id, event_type)` to max 10 events per
  hour per type; `upvote` events contribute 20% weight to score vs other types.
- **Risk**: `network_p95_raw` normalization yields 0.0 for everyone when only 1 contributor
  exists. **Mitigation**: Use a floor value of 1.0 for `network_p95_raw` when contributor
  count < 5.
- **Assumption**: Contributor IDs in events match existing contributor nodes in the graph.
  If not, the event is stored orphaned — `GET /activity` on the unknown contributor returns
  404 but the event exists. A follow-up cleanup job can re-associate.
- **Assumption**: All times are UTC. If a client submits a non-UTC timestamp in metadata,
  it is stored as-is but not used for streak or period calculations.

---

## Known Gaps and Follow-up Tasks

- Follow-up task: web component for `ContributorGrowthCard` embedded in idea detail view.
- Follow-up task: weekly digest email showing each contributor their growth trajectory.
- Follow-up task: `cc contrib-growth` CLI command (stub in this spec, full impl deferred).
- Follow-up task: retroactive event backfill from GitHub commit history.
- Follow-up task: threshold recalibration pass after 30-day baseline is captured.

---

## Failure/Retry Reflection

- **Failure mode**: Growth score stays 0.0 for all contributors after deploy.
  **Blind spot**: `network_p95_raw` floor not applied when contributor count is small.
  **Next action**: Check `GET /api/contributions/roi` for `active_contributor_count`;
  if < 5, apply floor fix in `contribution_recognition_service.py`.

- **Failure mode**: Duplicate events flood the activity stream.
  **Blind spot**: Idempotency key does not include `metadata` — two calls with same triple
  but different metadata both return 200 but do not create a second event (correct behavior,
  but callers may expect metadata update to be saved).
  **Next action**: Document in API contract that metadata on duplicate is ignored.

- **Failure mode**: Leaderboard is empty even after events recorded.
  **Blind spot**: `period` filter excludes events if `timestamp` indexing is wrong timezone.
  **Next action**: Verify `timestamp` is stored as UTC; query with explicit UTC window.

---

## Decision Gates

- Badge reward thresholds (streak lengths, event counts) require community input before
  final implementation — default values provided here are starting proposals.
- Whether `growth_score` should be publicly visible on contributor profiles or kept private
  to the contributor requires UX/governance decision.
- Rate-limiting policy (10 events/hour/type) is a starting constraint; if pipeline automation
  legitimately generates bursts, the limit needs exemption rules via API key scope.
