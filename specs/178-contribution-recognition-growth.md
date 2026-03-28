# Spec 178: Visible Contribution Recognition and Growth Tracking

## Purpose

Every contribution to Coherence Network — a question asked, a spec written, a review completed, a share sent, a belief staked, an idea advanced — represents real intellectual labor and care. Currently that labor is invisible: contributors have no way to see their own history over time, no signal that their work landed, no view of how they have grown. This spec makes contribution labor permanently visible to both the contributor and the community. It introduces a contribution timeline, milestone recognition, growth metrics over time, and a community recognition feed. The goal is to close the feedback loop so that invisible work becomes valued work.

---

## Problem Statement

Contributors currently face three gaps:

1. **No feedback loop** — After submitting a spec or answering a question, there is no acknowledgment, no score, no record the contributor can see.
2. **No growth signal** — A contributor who has been active for 6 months cannot see how their output, CC balance, or coherence impact has changed.
3. **No community visibility** — Other contributors cannot see who is doing what, making it impossible to recognize, learn from, or build on peer work.

This spec addresses all three by building a contribution recognition layer on top of the existing `/api/contributions` and `/api/contributors` infrastructure.

---

## Requirements

### R1 — Contribution Timeline per Contributor
- [ ] `GET /api/contributors/{contributor_id}/timeline` returns a paginated list of the contributor's contributions in reverse-chronological order
- [ ] Each entry includes: `type`, `label`, `timestamp`, `coherence_score`, `cc_value`, `idea_id` (if applicable), `task_id` (if applicable)
- [ ] Contribution types: `spec`, `test`, `impl`, `review`, `question`, `answer`, `share`, `stake`, `belief`, `vote`, `comment`, `code`
- [ ] Timeline supports `?since=<ISO8601>` and `?until=<ISO8601>` filter params
- [ ] Timeline supports `?type=<contribution_type>` filter param
- [ ] Response is paginated (default limit 50, max 200)

### R2 — Growth Metrics Summary
- [ ] `GET /api/contributors/{contributor_id}/growth` returns aggregated growth data
- [ ] Growth response includes:
  - `total_contributions` (all time)
  - `contributions_by_type` (map of type → count)
  - `cc_earned_total` (all-time CC value)
  - `cc_earned_30d`, `cc_earned_90d` (rolling windows)
  - `coherence_score_avg` (rolling 30-day average)
  - `streak_current_days` (consecutive days with ≥1 contribution)
  - `streak_longest_days` (all-time longest streak)
  - `first_contribution_at` (ISO8601 or null if none)
  - `last_contribution_at` (ISO8601 or null if none)
  - `growth_rate_pct_30d` (% change in contribution count vs prior 30-day window)

### R3 — Milestone Recognition
- [ ] `GET /api/contributors/{contributor_id}/milestones` returns all unlocked milestones with `unlocked_at` timestamps
- [ ] Milestones are computed from contribution history — no separate write path
- [ ] Milestone definitions (built-in, evaluated at read time):

| id | label | condition |
|----|-------|-----------|
| `first_contribution` | First Step | ≥1 contribution of any type |
| `first_spec` | Spec Author | ≥1 contribution of type `spec` |
| `ten_contributions` | Tenacious | ≥10 contributions (any type) |
| `fifty_contributions` | Committed | ≥50 contributions (any type) |
| `hundred_contributions` | Core Contributor | ≥100 contributions |
| `first_review` | Peer Reviewer | ≥1 contribution of type `review` |
| `week_streak` | Week of Work | ≥7-day streak |
| `month_streak` | Month of Motion | ≥30-day streak |
| `first_stake` | Believer | ≥1 contribution of type `stake` |
| `idea_advanced` | Momentum Maker | contributed to an idea that advanced stage |
| `cc_100` | Value Creator | ≥100 CC earned total |
| `cc_1000` | High Value | ≥1000 CC earned total |

- [ ] Response includes both `unlocked` (list of milestones with `unlocked_at`) and `locked` (list of milestones with `progress_pct` showing how close)

### R4 — Community Recognition Feed
- [ ] `GET /api/recognition/feed` returns a paginated feed of recent notable contribution events across all contributors
- [ ] Each feed entry includes: `contributor_id`, `contributor_name`, `event_type` (milestone_unlocked | streak_achieved | first_of_type | top_contributor), `label`, `timestamp`, `idea_id` (if applicable)
- [ ] Feed is sorted by `timestamp` descending
- [ ] Feed supports `?limit=` (default 20, max 100) and `?offset=` pagination
- [ ] Feed supports `?contributor_id=` filter to see only a given person's recognitions
- [ ] Feed does NOT include every individual contribution — only notable events (milestone unlocks, streak achievements, first-of-type)

### R5 — Contribution Type Enrichment
- [ ] When recording a contribution via `POST /api/contributions/record`, the payload MAY include a `contribution_type` field with one of the defined types
- [ ] If `contribution_type` is absent, the system infers it from existing `metadata` fields where possible (e.g. `commit_hash` → `code`, `spec_id` → `spec`)
- [ ] Type is stored in the graph node's `metadata` field as `contribution_type`
- [ ] Existing contributions without an explicit type default to `code` for backward compatibility

### R6 — Self-Visible Dashboard Data
- [ ] `GET /api/contributors/{contributor_id}/dashboard` returns a combined response suitable for a profile dashboard:
  - `contributor` (base profile fields)
  - `growth` (R2 data)
  - `milestones_unlocked` (count + top 3 most recent)
  - `timeline_recent` (last 5 contributions)
  - `recognition_recent` (last 3 recognition feed entries for this contributor)

---

## Open Questions Addressed

### How can we improve this idea?

1. **Make types explicit from day one** — The contribution type taxonomy (spec, test, impl, review, question, stake, etc.) mirrors the actual diversity of work on the network. If type is missing, value goes unseen. The enrichment requirement (R5) ensures even legacy records get classified.

2. **Growth rate as proof of working** — The `growth_rate_pct_30d` field in the growth summary gives a single number that can be tracked over time to answer "is the system being used more or less than last month?" A positive rate = adoption. This can be surfaced on the homepage.

3. **Milestones as proof that work lands** — Each milestone has a condition that can be verified against live data. If the milestone `idea_advanced` exists and is unlocked for contributors, it directly proves that contributions are moving ideas through the pipeline.

4. **Streaks as signal of retention** — A contributor streak (days with ≥1 contribution) is the clearest signal that the platform is habit-forming. If `streak_longest_days` > 7 for multiple contributors, the system is working. If all streaks are 1, it is not.

5. **Feed as social proof** — The community recognition feed makes growth visible to everyone. When someone sees "Alice unlocked Core Contributor" in the feed, the entire community gets evidence that the platform supports long-term contributors.

### Is it working yet?

Before this spec: there is no way to answer this question from the API.
After this spec: query `GET /api/contributors/{id}/growth` on any real contributor and check `total_contributions > 0` and `streak_current_days > 0`. Query `GET /api/recognition/feed` and verify it has entries. These are falsifiable, production-checkable signals.

### How do we make proof clearer over time?

- `cc_earned_30d` vs `cc_earned_90d` ratio shows acceleration or deceleration
- `growth_rate_pct_30d` directly compares this month vs last
- Milestone `unlocked_at` timestamps create an immutable record of when growth thresholds were crossed
- The recognition feed is an append-only event stream — it cannot be backdated

---

## API Contract

### `GET /api/contributors/{contributor_id}/timeline`

**Request**
- `contributor_id`: UUID (path)
- `since`: ISO8601 string (query, optional)
- `until`: ISO8601 string (query, optional)
- `type`: contribution_type string (query, optional)
- `limit`: int (query, default 50, max 200)
- `offset`: int (query, default 0)

**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "contributor_id": "uuid",
      "type": "spec",
      "label": "Spec 178: Contribution Recognition",
      "timestamp": "2026-03-28T14:00:00Z",
      "coherence_score": 0.87,
      "cc_value": 12.5,
      "idea_id": "uuid-or-null",
      "task_id": "task_abc123-or-null",
      "metadata": {}
    }
  ],
  "total": 47,
  "limit": 50,
  "offset": 0
}
```

**Response 404**
```json
{ "detail": "Contributor not found" }
```

---

### `GET /api/contributors/{contributor_id}/growth`

**Request**
- `contributor_id`: UUID (path)

**Response 200**
```json
{
  "contributor_id": "uuid",
  "total_contributions": 47,
  "contributions_by_type": {
    "spec": 12,
    "review": 8,
    "code": 15,
    "question": 5,
    "stake": 7
  },
  "cc_earned_total": 342.5,
  "cc_earned_30d": 87.0,
  "cc_earned_90d": 210.0,
  "coherence_score_avg": 0.74,
  "streak_current_days": 5,
  "streak_longest_days": 14,
  "first_contribution_at": "2025-11-01T09:00:00Z",
  "last_contribution_at": "2026-03-28T12:00:00Z",
  "growth_rate_pct_30d": 23.5
}
```

**Response 404**
```json
{ "detail": "Contributor not found" }
```

---

### `GET /api/contributors/{contributor_id}/milestones`

**Request**
- `contributor_id`: UUID (path)

**Response 200**
```json
{
  "contributor_id": "uuid",
  "unlocked": [
    {
      "id": "first_contribution",
      "label": "First Step",
      "unlocked_at": "2025-11-01T09:00:00Z",
      "description": "Made your first contribution to the network"
    }
  ],
  "locked": [
    {
      "id": "hundred_contributions",
      "label": "Core Contributor",
      "progress_pct": 47.0,
      "description": "Make 100 contributions of any type",
      "threshold": 100,
      "current": 47
    }
  ]
}
```

**Response 404**
```json
{ "detail": "Contributor not found" }
```

---

### `GET /api/recognition/feed`

**Request**
- `contributor_id`: UUID (query, optional — filter to one contributor)
- `limit`: int (query, default 20, max 100)
- `offset`: int (query, default 0)

**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "contributor_id": "uuid",
      "contributor_name": "alice",
      "event_type": "milestone_unlocked",
      "milestone_id": "ten_contributions",
      "label": "alice unlocked Tenacious (10 contributions)",
      "timestamp": "2026-03-28T11:00:00Z",
      "idea_id": null
    }
  ],
  "total": 8,
  "limit": 20,
  "offset": 0
}
```

---

### `GET /api/contributors/{contributor_id}/dashboard`

**Response 200**
```json
{
  "contributor": { "id": "uuid", "name": "alice", "type": "HUMAN" },
  "growth": { "...": "...as per growth endpoint..." },
  "milestones_unlocked_count": 5,
  "milestones_recent": [
    { "id": "week_streak", "label": "Week of Work", "unlocked_at": "2026-03-20T08:00:00Z" }
  ],
  "timeline_recent": [
    { "type": "spec", "label": "Spec 178", "timestamp": "2026-03-28T14:00:00Z" }
  ],
  "recognition_recent": [
    { "event_type": "milestone_unlocked", "label": "alice unlocked Week of Work", "timestamp": "2026-03-20T08:00:00Z" }
  ]
}
```

---

## Data Model

```yaml
ContributionTimelineEntry:
  properties:
    id: { type: uuid }
    contributor_id: { type: uuid }
    type: { type: string, enum: [spec, test, impl, review, question, answer, share, stake, belief, vote, comment, code] }
    label: { type: string }
    timestamp: { type: datetime, format: ISO8601 }
    coherence_score: { type: float, min: 0.0, max: 1.0 }
    cc_value: { type: float, min: 0.0 }
    idea_id: { type: uuid, nullable: true }
    task_id: { type: string, nullable: true }
    metadata: { type: object }

GrowthSummary:
  properties:
    contributor_id: { type: uuid }
    total_contributions: { type: int, min: 0 }
    contributions_by_type: { type: object, values: int }
    cc_earned_total: { type: float, min: 0.0 }
    cc_earned_30d: { type: float, min: 0.0 }
    cc_earned_90d: { type: float, min: 0.0 }
    coherence_score_avg: { type: float, min: 0.0, max: 1.0 }
    streak_current_days: { type: int, min: 0 }
    streak_longest_days: { type: int, min: 0 }
    first_contribution_at: { type: datetime, nullable: true }
    last_contribution_at: { type: datetime, nullable: true }
    growth_rate_pct_30d: { type: float, description: "Positive = growing, negative = shrinking" }

MilestoneDefinition:
  properties:
    id: { type: string }
    label: { type: string }
    description: { type: string }
    condition_type: { type: string, enum: [count_total, count_by_type, streak_days, cc_earned, idea_advanced] }
    threshold: { type: float }
    contribution_type_filter: { type: string, nullable: true }

UnlockedMilestone:
  extends: MilestoneDefinition
  properties:
    unlocked_at: { type: datetime }

LockedMilestone:
  extends: MilestoneDefinition
  properties:
    progress_pct: { type: float, min: 0.0, max: 100.0 }
    current: { type: float }

RecognitionEvent:
  properties:
    id: { type: uuid }
    contributor_id: { type: uuid }
    contributor_name: { type: string }
    event_type: { type: string, enum: [milestone_unlocked, streak_achieved, first_of_type, top_contributor] }
    milestone_id: { type: string, nullable: true }
    label: { type: string }
    timestamp: { type: datetime }
    idea_id: { type: uuid, nullable: true }
```

---

## Task Card

```yaml
goal: Surface contribution history, growth metrics, milestones, and community feed via 4 new API endpoints on top of existing graph data
files_allowed:
  - api/app/routers/contributor_recognition.py
  - api/app/services/contributor_growth_service.py
  - api/app/models/contributor_growth.py
  - api/app/routers/contributors.py
  - api/app/main.py
  - api/tests/test_contributor_recognition.py
done_when:
  - GET /api/contributors/{id}/timeline returns paginated contribution history
  - GET /api/contributors/{id}/growth returns streak, CC, and growth rate
  - GET /api/contributors/{id}/milestones returns unlocked/locked milestone split
  - GET /api/recognition/feed returns community recognition events
  - GET /api/contributors/{id}/dashboard returns combined summary
  - All 5 routes return 404 for unknown contributor_id
  - At least 15 passing pytest tests covering happy path + edge cases
commands:
  - cd api && python -m pytest tests/test_contributor_recognition.py -v
constraints:
  - Do NOT modify existing /api/contributions or /api/contributors/{id}/contributions routes
  - All computation happens at read time from graph data — no new write tables
  - Streak computation uses contribution timestamps only — no new date tracking fields
  - Milestones are computed, not persisted — re-evaluating is acceptable for MVP
  - Recognition feed events are derived from contribution timestamps + milestones — no separate event log required for MVP
```

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `api/app/models/contributor_growth.py` | CREATE | Pydantic models: GrowthSummary, MilestoneDefinition, UnlockedMilestone, LockedMilestone, RecognitionEvent, ContributionTimelineEntry |
| `api/app/services/contributor_growth_service.py` | CREATE | Business logic: compute growth metrics, evaluate milestones, build timeline, build recognition feed |
| `api/app/routers/contributor_recognition.py` | CREATE | Route handlers: /timeline, /growth, /milestones, /dashboard, /recognition/feed |
| `api/app/main.py` | MODIFY | Register new router with prefix `/api` |
| `api/tests/test_contributor_recognition.py` | CREATE | ≥15 pytest tests |

---

## Acceptance Tests

- `api/tests/test_contributor_recognition.py::test_timeline_empty_for_new_contributor`
- `api/tests/test_contributor_recognition.py::test_timeline_returns_contributions_in_reverse_order`
- `api/tests/test_contributor_recognition.py::test_timeline_filter_by_type`
- `api/tests/test_contributor_recognition.py::test_timeline_filter_by_date_range`
- `api/tests/test_contributor_recognition.py::test_timeline_404_unknown_contributor`
- `api/tests/test_contributor_recognition.py::test_growth_zero_for_new_contributor`
- `api/tests/test_contributor_recognition.py::test_growth_counts_by_type`
- `api/tests/test_contributor_recognition.py::test_growth_streak_single_day`
- `api/tests/test_contributor_recognition.py::test_growth_streak_consecutive_days`
- `api/tests/test_contributor_recognition.py::test_growth_rate_positive_when_growing`
- `api/tests/test_contributor_recognition.py::test_milestones_first_contribution_unlocked`
- `api/tests/test_contributor_recognition.py::test_milestones_locked_shows_progress_pct`
- `api/tests/test_contributor_recognition.py::test_milestones_404_unknown_contributor`
- `api/tests/test_contributor_recognition.py::test_recognition_feed_empty_initially`
- `api/tests/test_contributor_recognition.py::test_recognition_feed_returns_milestone_event`
- `api/tests/test_contributor_recognition.py::test_dashboard_combines_all_data`
- `api/tests/test_contributor_recognition.py::test_dashboard_404_unknown_contributor`

---

## Verification Scenarios

### Scenario 1: New contributor has empty but valid growth state

**Setup:** A fresh contributor exists in the system with no contributions recorded.
```bash
CONTRIBUTOR_ID=$(curl -s -X POST https://api.coherencycoin.com/api/contributors \
  -H "Content-Type: application/json" \
  -d '{"type":"HUMAN","name":"testuser178","email":"testuser178@example.com"}' | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
```
**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIBUTOR_ID/growth"
```
**Expected:** HTTP 200, `total_contributions=0`, `streak_current_days=0`, `cc_earned_total=0.0`, `growth_rate_pct_30d=0.0`, `first_contribution_at=null`

**Edge:** `curl -s "https://api.coherencycoin.com/api/contributors/00000000-0000-0000-0000-000000000000/growth"` → HTTP 404 `{"detail":"Contributor not found"}`

---

### Scenario 2: Contributor earns a milestone after their first contribution

**Setup:** Contributor from Scenario 1 exists with 0 contributions.
**Action:**
```bash
curl -s -X POST https://api.coherencycoin.com/api/contributions/record \
  -H "Content-Type: application/json" \
  -d "{\"contributor_id\":\"$CONTRIBUTOR_ID\",\"contribution_type\":\"spec\",\"label\":\"Test spec 178\",\"coherence_score\":0.8,\"cc_value\":5.0}"

curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIBUTOR_ID/milestones"
```
**Expected:** HTTP 200, response contains `unlocked` list with at least `{"id":"first_contribution","label":"First Step"}` and `{"id":"first_spec","label":"Spec Author"}`. The `locked` list contains `ten_contributions` with `progress_pct` between 1.0 and 99.9 (not 0, not 100).

**Edge:** Check `locked` milestone for `ten_contributions`: `current=1`, `threshold=10`, `progress_pct=10.0`.

---

### Scenario 3: Timeline pagination and type filtering

**Setup:** Contributor with 5 contributions of mixed types (`spec`, `review`, `code`).
**Action:**
```bash
# Get all contributions
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIBUTOR_ID/timeline?limit=10"

# Filter to spec only
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIBUTOR_ID/timeline?type=spec"
```
**Expected (all):** HTTP 200, `items` array with 5 entries, `total=5`, items sorted newest-first by `timestamp`.
**Expected (spec filter):** HTTP 200, `items` array containing only entries where `type=="spec"`, all other types excluded.

**Edge:** `?type=nonexistent_type` → HTTP 422 validation error (not 500).

---

### Scenario 4: Recognition feed shows milestone event

**Setup:** Contributor from Scenario 2 who has unlocked `first_contribution`.
**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/recognition/feed?contributor_id=$CONTRIBUTOR_ID"
```
**Expected:** HTTP 200, at least one item in `items` where `event_type=="milestone_unlocked"` and `milestone_id=="first_contribution"` and `contributor_id==$CONTRIBUTOR_ID`.

**Edge:** `curl -s "https://api.coherencycoin.com/api/recognition/feed?limit=0"` → HTTP 422 (limit must be ≥1).

---

### Scenario 5: Dashboard combines data correctly

**Setup:** Contributor with ≥1 contribution and ≥1 unlocked milestone.
**Action:**
```bash
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIBUTOR_ID/dashboard"
```
**Expected:** HTTP 200, response contains all five keys: `contributor`, `growth`, `milestones_unlocked_count`, `timeline_recent`, `recognition_recent`. The `milestones_unlocked_count` matches the count of items in `GET /api/contributors/$CONTRIBUTOR_ID/milestones` → `unlocked` array. The `timeline_recent` has at most 5 items. The `growth.total_contributions` matches `GET /api/contributors/$CONTRIBUTOR_ID/growth` → `total_contributions`.

**Edge:** Dashboard for unknown contributor returns HTTP 404 with `{"detail":"Contributor not found"}`, not a partial response.

---

## Concurrency Behavior

- **Read operations** (all endpoints in this spec): Safe for concurrent access; all data is computed from existing graph nodes at read time. No writes are performed.
- **Write operations**: The contribution recording endpoint (`POST /api/contributions/record`) is pre-existing; this spec adds no new write paths.
- **Streak computation**: Uses `timestamp` fields only. Concurrent reads of the same contributor's streak will return the same result as long as no contributions are being written simultaneously. Last-write-wins on concurrent contributions is acceptable for MVP.
- **Milestone evaluation**: Computed at read time from contribution counts. No locking required. Two concurrent milestone reads may return slightly different results if a contribution lands between them — this is acceptable and consistent within milliseconds.

---

## Verification Commands

```bash
# Run all tests
cd api && python -m pytest tests/test_contributor_recognition.py -v

# Verify routes are registered
curl -s https://api.coherencycoin.com/openapi.json | grep -o '"\/api\/contributors\/[^"]*"' | grep -E "timeline|growth|milestones|dashboard"
curl -s https://api.coherencycoin.com/openapi.json | grep '"\/api\/recognition\/feed"'

# Smoke test against production (requires a real contributor UUID)
# Replace UUID with any known contributor from GET /api/contributors
curl -s "https://api.coherencycoin.com/api/contributors/<UUID>/growth"
curl -s "https://api.coherencycoin.com/api/contributors/<UUID>/milestones"
curl -s "https://api.coherencycoin.com/api/recognition/feed"
```

---

## Out of Scope

- **Notification delivery** (email, Telegram, Discord) on milestone unlock — separate spec
- **Comparative ranking** (leaderboards, top-N) — deferred to reduce gaming risk
- **Retroactive type classification ML** — the type enrichment rule is heuristic only
- **Web UI** for the dashboard — this spec covers API only; web integration is a separate task
- **Persistent recognition event log** — MVP derives events from contribution data at read time; a persisted append-only event log can be added in a follow-up when performance requires it
- **Webhook triggers** on milestone unlock — follow-up once webhook infrastructure exists

---

## Risks and Assumptions

- **Risk: Graph query performance on large contribution sets.** The streak and growth rate computations require iterating all contributions for a contributor. If a contributor has thousands of contributions, this may be slow. Mitigation: add `?limit=` safety cap on internal graph queries; cache results if latency > 200ms.
- **Risk: `contribution_type` field missing for historical data.** All pre-existing contributions lack an explicit type field. The fallback rule (`commit_hash` → `code`) covers GitHub contributions but not all cases. Mitigation: `code` default is safe and honest; labeled unknown types can be re-classified later.
- **Assumption: Contributor IDs are stable UUIDs.** The timeline and growth endpoints use contributor UUID as the key. If a contributor is deleted and recreated, their history is lost. This is acceptable for MVP.
- **Assumption: Graph service is the authoritative data store.** All computation reads from `graph_service.list_nodes()` and edge queries. If the graph is inconsistent (hollow nodes, missing edges), computed metrics will be incomplete but not incorrect.
- **Risk: Milestone `idea_advanced` requires cross-entity join.** Checking whether a contributor's contributions advanced an idea requires traversing idea stage history. If that data is not available in graph metadata, this milestone will always show as locked. Mitigation: implement a simpler proxy condition (`total_contributions > 5 and stake > 0`) as a fallback if the full join is unavailable.

---

## Known Gaps and Follow-up Tasks

- **Follow-up: persistent recognition event log** — When read-time derivation becomes a performance bottleneck, add a `recognition_events` graph node type that is written on contribution record.
- **Follow-up: web dashboard UI** — Wire `GET /api/contributors/{id}/dashboard` into the Next.js profile page.
- **Follow-up: Telegram/Discord notification on milestone unlock** — Detect milestone changes on contribution record and push to subscriber channels.
- **Follow-up: growth chart data** — Add `GET /api/contributors/{id}/growth/history?window=weekly` returning time-series data for sparklines.
- **Gap: `contribution_type` enum not enforced at record time** — The existing `POST /api/contributions/record` endpoint does not validate `contribution_type`. Type enforcement should be added in a follow-up to prevent silent type drift.

---

## Failure/Retry Reflection

- **Failure mode:** Streak computed as 0 even though contributor is active daily.
  - **Blind spot:** Streak logic uses `date(timestamp)` grouping; if timestamps are in UTC and contributor works near midnight in their timezone, contributions may span two calendar days and break the streak count.
  - **Next action:** Use date bucketing by UTC day consistently; document that streaks are UTC-based. Consider timezone-aware streaks as a follow-up.

- **Failure mode:** Milestone `idea_advanced` always locked for all contributors.
  - **Blind spot:** The condition requires querying idea stage history, which may not be stored on graph nodes.
  - **Next action:** If `idea.stage_history` is absent, skip this milestone in evaluation and return it as `locked` with `progress_pct: 0` and a note in `description` that data is unavailable.

- **Failure mode:** Recognition feed is always empty even after many contributions.
  - **Blind spot:** Feed derivation logic looks for milestone-crossing events, which requires comparing before/after contribution counts. If computed at read time without baseline, no crossing is detected.
  - **Next action:** Simplify MVP: recognition feed shows the `first_contribution`, `first_spec`, `first_review`, `week_streak` milestones with `unlocked_at` as `timestamp` — no event-detection required, just milestone list filtered to notable IDs.

---

## Decision Gates

- [ ] **Confirm milestone list is final before implementation** — adding milestones post-deploy changes feed history retroactively (acceptable, but communicate to contributors that new milestones were added)
- [ ] **Confirm `recognition_feed` MVP scope** — implementing as read-time derivation (no persistent event log) is simpler but means the feed cannot include non-milestone events (e.g. "Alice answered 5 questions in one day") without significant added logic. If richer events are needed pre-launch, escalate.
