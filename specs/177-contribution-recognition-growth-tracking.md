# Spec 177: Visible Contribution Recognition and Growth Tracking

**Spec ID**: 177-contribution-recognition-growth-tracking
**Idea ID**: contribution-recognition-growth-tracking
**Task ID**: task_778b6cfa59c4d651
**Status**: Draft
**Depends on**: Spec 048 (Contributions API), Spec 128 (Contributor Leaderboard API), Spec 094 (Contributor Onboarding)
**Depended on by**: Spec 157 (Investment UX), Spec 162 (Meta Self-Discovery)

---

## Summary

Every contribution — a question asked, a spec written, a review completed, a share posted — is currently invisible to the contributor the moment after they make it. There is no feed showing what you just did, no timeline of your growth over weeks or months, no signal that the network noticed your effort.

This spec makes the invisible labor of thinking, connecting, and caring **visible and valued**. It does so through four concrete additions:

1. **Contribution activity feed** — `GET /api/contributors/{id}/activity` — chronological stream of all contribution events for a contributor, with type, target idea, coherence score, and CC earned.
2. **Growth metrics endpoint** — `GET /api/contributors/{id}/growth` — weekly/monthly aggregates showing trajectory: count, coherence trend, CC accumulated, rank movement.
3. **Recognition badge system** — `GET /api/contributors/{id}/badges` — milestone badges earned automatically (first spec, 10 reviews, 50 CC earned, top-10 leaderboard, etc.).
4. **Web: Contributor profile page** — `/contributors/{id}` — renders the activity feed, growth chart, and badge shelf. Linked from idea cards and the leaderboard.

The measure of success is simple: a contributor can open their profile, see exactly what they've done, how their influence has grown, and feel that the network has recorded their effort faithfully.

---

## Problem Statement

The current system records contributions in the graph (via `POST /api/contributions`) but surfaces nothing back to the contributor:

- No feed shows a contributor's recent activity across ideas.
- No trend data exists — a contributor cannot see if their coherence scores are improving.
- No milestone recognition is given — no moment when the system says "you've done 10 reviews."
- The web UI has no contributor profile page; clicking a contributor name goes nowhere.

The result: **contribution feels thankless**. Contributors deposit effort into a black box and receive no confirmation that it registered, no evidence of growth, and no community visibility.

This is also a measurement problem. We cannot prove the platform is working without per-contributor growth data. If this spec is implemented, we can show whether new contributors are returning (retention), whether coherence scores trend up over time (quality signal), and whether recognition moments correlate with increased contributions (engagement signal).

---

## Requirements

### R1 — Contribution Activity Feed API

**Endpoint**: `GET /api/contributors/{contributor_id}/activity`

Returns a reverse-chronological list of contribution events for a specific contributor.

Each event includes:
- `id`: contribution UUID
- `type`: one of `spec`, `review`, `question`, `share`, `implementation`, `test`, `deployment`, `other`
- `idea_id`: the idea this contribution belongs to (nullable)
- `idea_title`: denormalized title for display (nullable)
- `coherence_score`: float 0.0–1.0 (the score assigned to this contribution)
- `cc_earned`: float — CC credited for this contribution
- `created_at`: ISO 8601 UTC timestamp
- `summary`: short human-readable description (e.g., "Wrote spec for GraphQL caching layer")

Supports pagination: `limit` (default 20, max 100), `offset` (default 0).
Returns 404 if contributor not found.
Returns 200 with empty items list if contributor exists but has no contributions.

### R2 — Growth Metrics API

**Endpoint**: `GET /api/contributors/{contributor_id}/growth`

Returns aggregated growth data suitable for rendering a chart.

Query parameters:
- `period`: `week` | `month` (default: `week`)
- `window`: integer 1–52 (default: 12) — how many periods to include

Returns:
- `contributor_id`: string
- `period`: `week` | `month`
- `buckets`: array of period buckets, each containing:
  - `label`: ISO 8601 week (`2026-W12`) or month (`2026-03`) string
  - `contribution_count`: int
  - `avg_coherence_score`: float 0.0–1.0 (null if no contributions in period)
  - `cc_earned`: float
  - `rank`: int | null — leaderboard rank at end of period (null if not on leaderboard)
- `summary`: object with all-time totals:
  - `total_contributions`: int
  - `total_cc_earned`: float
  - `avg_coherence_score`: float
  - `current_rank`: int | null
  - `first_contribution_at`: ISO 8601 UTC | null
  - `streak_days`: int — consecutive days with at least one contribution

Returns 404 if contributor not found.
Returns 200 with empty `buckets` and zero `summary` if contributor has no contributions.

### R3 — Badge System API

**Endpoint**: `GET /api/contributors/{contributor_id}/badges`

Returns all badges earned by a contributor. Badges are computed on-the-fly from contribution data (no separate badge store needed for MVP).

Each badge:
- `id`: slug string (e.g., `first-contribution`, `ten-reviews`, `top-ten`)
- `name`: display name (e.g., "First Contribution")
- `description`: short explanation of how it was earned
- `category`: `milestone` | `quality` | `community` | `streak`
- `earned_at`: ISO 8601 UTC — date the milestone was first crossed
- `icon`: one of a fixed icon slug set (see §Data Model)

Badge definitions (MVP set):

| id | name | trigger |
|----|------|---------|
| `first-contribution` | First Step | Made first contribution of any type |
| `spec-author` | Spec Author | Authored first spec (type=spec) |
| `ten-contributions` | Ten Strong | Reached 10 total contributions |
| `fifty-contributions` | Fifty Strong | Reached 50 total contributions |
| `ten-reviews` | Thoughtful Reviewer | Completed 10 review contributions |
| `quality-streak` | Quality Streak | 5 consecutive contributions with coherence ≥ 0.7 |
| `cc-earner-10` | Early Earner | Accumulated 10 CC |
| `cc-earner-100` | Century Mark | Accumulated 100 CC |
| `top-ten` | Top Ten | Appeared in top-10 leaderboard |
| `seven-day-streak` | Week of Work | 7-day contribution streak |

Returns 404 if contributor not found.
Returns 200 with empty list if no badges earned yet.

### R4 — Web Contributor Profile Page

**Route**: `/contributors/[id]` in Next.js web app.

Renders:
1. **Header**: contributor name, type badge (HUMAN/AGENT), member since date, current rank
2. **Badge shelf**: all earned badges rendered as icon+name chips; unearned badges shown as greyed-out "locked" chips for the next 3 milestones
3. **Activity feed**: last 20 contributions as a card list (type icon, idea title, coherence score chip, CC earned, timestamp)
4. **Growth chart**: weekly contribution count + coherence score trend line, last 12 weeks
5. **Summary stats**: total contributions, total CC earned, avg coherence score, streak

The page must:
- Load in under 2 seconds on a cold cache (3G network simulation)
- Work without JavaScript (SSR via Next.js `getServerSideProps` or equivalent)
- Link each activity item to its idea detail page `/ideas/{idea_id}`
- Be linked from: leaderboard rows, idea card contributor attributions, `cc profile` CLI output

### R5 — CLI: `cc profile [contributor-id]`

Show a contributor's growth summary in the terminal.

```
$ cc profile alice@coherence.network

alice@coherence.network  (HUMAN)  Rank #7 / 42 contributors
Member since: 2026-01-15  |  Streak: 4 days

Badges (6):  First Step  ·  Spec Author  ·  Ten Strong  ·  Quality Streak  ·  Early Earner  ·  Thoughtful Reviewer

Growth (last 12 weeks):
  Week     Contributions  Avg Coherence  CC Earned
  2026-W03     3             0.71          4.2
  2026-W04     1             0.68          1.1
  ...
  2026-W14     5             0.82          7.8  ← this week

All time: 47 contributions  ·  68.4 CC earned  ·  avg coherence 0.74
```

If no `contributor-id` given, uses the identity from `cc whoami`.

---

## How This Proves the Idea Is Working

The primary question posed by this idea is: *"How can we show whether it is working yet, and make that proof clearer over time?"*

This spec answers it with three observable metrics:

1. **Retention rate**: percentage of contributors who make a second contribution within 7 days of their first. Tracked via `growth` endpoint. Target: ≥ 40% within 60 days of launch.
2. **Coherence trend**: average `avg_coherence_score` across all contributors' `growth` buckets trending upward over successive months. Tracked via aggregate of `/growth` responses. Target: +0.05 over 90 days.
3. **Badge unlock velocity**: rate at which the network earns new badges per week. A healthy network should show exponential early growth then steady-state. Tracked via `GET /api/badges/network-stats` (see §API Contract).

These metrics are surfaced on a public `/stats` page (out of scope for this spec; see §Known Gaps) and reported in the weekly `cc broadcast` digest.

---

## API Contract

### `GET /api/contributors/{contributor_id}/activity`

**Request**
- `contributor_id`: UUID (path)
- `limit`: int (query, optional, default 20, max 100)
- `offset`: int (query, optional, default 0)

**Response 200**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "type": "spec",
      "idea_id": "graphql-caching",
      "idea_title": "GraphQL Caching Layer",
      "coherence_score": 0.82,
      "cc_earned": 5.5,
      "created_at": "2026-03-20T10:14:00Z",
      "summary": "Wrote spec for GraphQL caching layer"
    }
  ],
  "total": 47,
  "limit": 20,
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
- `period`: `week` | `month` (query, optional, default `week`)
- `window`: int 1–52 (query, optional, default 12)

**Response 200**
```json
{
  "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
  "period": "week",
  "buckets": [
    {
      "label": "2026-W03",
      "contribution_count": 3,
      "avg_coherence_score": 0.71,
      "cc_earned": 4.2,
      "rank": 9
    }
  ],
  "summary": {
    "total_contributions": 47,
    "total_cc_earned": 68.4,
    "avg_coherence_score": 0.74,
    "current_rank": 7,
    "first_contribution_at": "2026-01-15T09:00:00Z",
    "streak_days": 4
  }
}
```

**Response 404**
```json
{ "detail": "Contributor not found" }
```

---

### `GET /api/contributors/{contributor_id}/badges`

**Request**
- `contributor_id`: UUID (path)

**Response 200**
```json
{
  "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
  "badges": [
    {
      "id": "first-contribution",
      "name": "First Step",
      "description": "Made your first contribution to the network",
      "category": "milestone",
      "earned_at": "2026-01-15T09:00:00Z",
      "icon": "star"
    }
  ]
}
```

**Response 404**
```json
{ "detail": "Contributor not found" }
```

---

### `GET /api/badges/network-stats`

**Purpose**: Aggregate badge statistics for the network health dashboard.

**Response 200**
```json
{
  "total_badges_earned": 142,
  "unique_badge_holders": 28,
  "badges_earned_this_week": 12,
  "most_common_badge": "first-contribution",
  "rarest_badge": "top-ten",
  "weekly_velocity": [3, 4, 7, 12]
}
```

---

## Data Model

### ContributionActivity (new Pydantic model)

```yaml
ContributionActivity:
  properties:
    id: { type: UUID }
    type: { type: string, enum: [spec, review, question, share, implementation, test, deployment, other] }
    idea_id: { type: string, nullable: true }
    idea_title: { type: string, nullable: true }
    coherence_score: { type: float, minimum: 0.0, maximum: 1.0 }
    cc_earned: { type: float, minimum: 0.0 }
    created_at: { type: datetime }
    summary: { type: string }
```

### GrowthBucket (new Pydantic model)

```yaml
GrowthBucket:
  properties:
    label: { type: string, description: "ISO week (2026-W12) or month (2026-03)" }
    contribution_count: { type: int }
    avg_coherence_score: { type: float, nullable: true }
    cc_earned: { type: float }
    rank: { type: int, nullable: true }
```

### Badge (new Pydantic model)

```yaml
Badge:
  properties:
    id: { type: string, description: "slug" }
    name: { type: string }
    description: { type: string }
    category: { type: string, enum: [milestone, quality, community, streak] }
    earned_at: { type: datetime }
    icon: { type: string, enum: [star, shield, flame, bolt, trophy, heart, eye, leaf] }
```

### Contribution type inference

The `type` field on `ContributionActivity` is derived from the existing `metadata` on a contribution node:
- `metadata.type` if present and valid → use directly
- `metadata.has_tests == true` and no type → `test`
- `metadata.has_docs == true` and no type → `spec`
- `metadata.commit_hash` present → `implementation`
- otherwise → `other`

No schema migration required — this is computed at read time.

---

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `api/app/routers/contributor_growth.py` | Create | Routes for `/activity`, `/growth`, `/badges` |
| `api/app/models/contributor_growth.py` | Create | Pydantic models: ContributionActivity, GrowthBucket, GrowthResponse, Badge, BadgeResponse |
| `api/app/services/contributor_growth_service.py` | Create | Business logic: activity fetch, growth aggregation, badge computation |
| `api/app/routers/badges.py` | Create | `GET /api/badges/network-stats` route |
| `api/app/main.py` | Modify | Register new routers |
| `api/tests/test_contributor_growth.py` | Create | All acceptance tests |
| `web/app/contributors/[id]/page.tsx` | Create | Contributor profile page |
| `web/components/ContributionFeed.tsx` | Create | Activity feed component |
| `web/components/GrowthChart.tsx` | Create | Weekly/monthly chart component |
| `web/components/BadgeShelf.tsx` | Create | Badge display component |
| `specs/177-contribution-recognition-growth-tracking.md` | Create | This spec |

---

## Acceptance Tests

All located in `api/tests/test_contributor_growth.py`:

- `test_activity_returns_200_with_contributions` — contributor with 3 contributions returns 3 items
- `test_activity_returns_empty_for_no_contributions` — contributor with zero contributions returns 200 with empty items
- `test_activity_returns_404_unknown_contributor` — unknown UUID returns 404
- `test_activity_pagination_limit_offset` — limit=1, offset=1 returns second item only
- `test_growth_returns_weekly_buckets` — 12 weekly buckets returned by default
- `test_growth_returns_monthly_buckets` — `period=month` returns monthly buckets
- `test_growth_summary_totals_correct` — summary totals match sum of all contributions
- `test_growth_returns_404_unknown_contributor` — unknown UUID returns 404
- `test_badges_first_contribution_earned` — contributor with 1 contribution has `first-contribution` badge
- `test_badges_spec_author_only_for_spec_type` — badge requires at least one contribution with type=spec
- `test_badges_quality_streak_requires_five_consecutive_high_coherence` — 4 high + 1 low does not earn badge
- `test_badges_returns_404_unknown_contributor` — unknown UUID returns 404
- `test_network_stats_returns_aggregate` — badge network stats endpoint returns valid structure

---

## Verification Scenarios

These scenarios must pass when run against the live API at `https://api.coherencycoin.com`.

### Scenario 1 — Activity Feed: Contributor with contributions

**Setup**: Contributor `alice@coherence.network` exists in the graph with at least 3 contributions.

**Action**:
```bash
CONTRIB_ID=$(curl -s https://api.coherencycoin.com/api/contributors?limit=100 | python3 -c "import sys,json; cs=[c for c in json.load(sys.stdin)['items'] if 'alice' in c.get('email','')]; print(cs[0]['id'] if cs else 'none')")
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/activity"
```

**Expected**: HTTP 200, `items` array with at least 1 entry, each entry has `id`, `type`, `coherence_score` (float 0.0–1.0), `created_at` (ISO 8601), `cc_earned` (non-negative float).

**Edge — unknown contributor**:
```bash
curl -s "https://api.coherencycoin.com/api/contributors/00000000-0000-0000-0000-000000000000/activity"
```
Expected: HTTP 404, `{"detail": "Contributor not found"}`.

---

### Scenario 2 — Growth Metrics: Weekly buckets

**Setup**: Any contributor with at least 5 contributions exists.

**Action**:
```bash
CONTRIB_ID=<valid-contributor-uuid>
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/growth?period=week&window=4"
```

**Expected**: HTTP 200, `buckets` array with exactly 4 entries, each with `label` matching pattern `\d{4}-W\d{2}`, `contribution_count` >= 0, `cc_earned` >= 0. `summary.total_contributions` equals the sum of all `contribution_count` values for the contributor's lifetime (not just the windowed buckets).

**Edge — bad period value**:
```bash
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/growth?period=decade"
```
Expected: HTTP 422, validation error (not 500).

---

### Scenario 3 — Badges: First contribution badge

**Setup**: Create a fresh contributor and record one contribution.

**Action**:
```bash
# Create contributor
CONTRIB=$(curl -s -X POST https://api.coherencycoin.com/api/contributors \
  -H "Content-Type: application/json" \
  -d '{"name":"badge-test-user","type":"HUMAN","email":"badge-test-'$RANDOM'@test.coherence.network"}')
CONTRIB_ID=$(echo $CONTRIB | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Create an asset and record a contribution
ASSET=$(curl -s -X POST https://api.coherencycoin.com/api/assets \
  -H "Content-Type: application/json" \
  -d '{"name":"test-idea-badge","type":"IDEA","owner_id":"'$CONTRIB_ID'"}')
ASSET_ID=$(echo $ASSET | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST https://api.coherencycoin.com/api/contributions \
  -H "Content-Type: application/json" \
  -d "{\"contributor_id\":\"$CONTRIB_ID\",\"asset_id\":\"$ASSET_ID\",\"cost_amount\":1.0}"

# Now check badges
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/badges"
```

**Expected**: HTTP 200, `badges` array contains one entry with `id` = `"first-contribution"` and `earned_at` set to a valid ISO 8601 timestamp.

**Edge — contributor with zero contributions**:
```bash
EMPTY_CONTRIB_ID=$(curl -s -X POST https://api.coherencycoin.com/api/contributors \
  -H "Content-Type: application/json" \
  -d '{"name":"empty-badge-test","type":"HUMAN","email":"emptybadge-'$RANDOM'@test.coherence.network"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
curl -s "https://api.coherencycoin.com/api/contributors/$EMPTY_CONTRIB_ID/badges"
```
Expected: HTTP 200, `badges` = `[]` (empty list, not 404).

---

### Scenario 4 — Network Badge Stats

**Setup**: At least one badge has been earned by any contributor (prerequisite: Scenario 3 passed).

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/badges/network-stats
```

**Expected**: HTTP 200, response contains `total_badges_earned` (int >= 1), `unique_badge_holders` (int >= 1), `most_common_badge` (non-empty string), `weekly_velocity` (array of ints).

**Edge — no badges in system** (fresh deploy):
Expected: HTTP 200, `total_badges_earned` = 0, `badges_earned_this_week` = 0, `most_common_badge` = null, `weekly_velocity` = `[]`.

---

### Scenario 5 — Growth Trend Proves Engagement

**Setup**: Two snapshots of `growth` data taken 1 week apart. (This scenario documents the observability contract.)

**Action** (week 1):
```bash
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/growth?period=week&window=1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['summary']['total_contributions'])"
```

**Action** (week 2, same contributor):
```bash
# Same command, run 7 days later
```

**Expected**: `total_contributions` in week 2 is >= week 1 (contributions are never lost; growth is monotonically non-decreasing over time).

**Edge — window=0**:
```bash
curl -s "https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/growth?window=0"
```
Expected: HTTP 422 validation error (window must be >= 1).

---

## Concurrency Behavior

- **Read operations** (activity, growth, badges): Safe for concurrent access. All three endpoints are read-only aggregations over existing contribution data. No locking required.
- **Write operations**: This spec adds no write endpoints. Badge computation is on-the-fly from existing data — no badge store to contend over.
- **Stale data**: Growth buckets and badge status may lag by up to 60 seconds on high-write days if caching is added in a follow-up. For MVP, all data is computed fresh per request.

---

## Verification

```bash
# Run all unit tests
cd api && python3 -m pytest api/tests/test_contributor_growth.py -x -v

# Smoke test against live API (requires valid contributor UUID)
CONTRIB_ID=<real-contributor-uuid>
curl -sf https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/activity | python3 -m json.tool
curl -sf https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/growth | python3 -m json.tool
curl -sf https://api.coherencycoin.com/api/contributors/$CONTRIB_ID/badges | python3 -m json.tool
curl -sf https://api.coherencycoin.com/api/badges/network-stats | python3 -m json.tool
```

---

## Evidence This Feature Is Live

Once deployed, the following are independently verifiable:

1. **API smoke test**: `curl -s https://api.coherencycoin.com/api/badges/network-stats` returns JSON with `total_badges_earned` field.
2. **Web profile page**: `https://coherencycoin.com/contributors/<id>` loads a profile with badge shelf and growth chart visible (no JS required for SSR render).
3. **CLI check**: `cc profile` outputs growth table and badge list without error.
4. **Retention metric**: `/api/contributors/{id}/growth?period=week&window=8` for any contributor who joined > 8 weeks ago shows non-zero `contribution_count` in at least 2 of the 8 buckets.

---

## Out of Scope

- Push notifications or email when a badge is earned (follow-up: Spec 178)
- Comparative analytics ("your coherence score is higher than 80% of contributors") — future
- Custom badge creation by contributors — future governance question
- `/stats` public network health page — referenced in §How This Proves the Idea, spec to follow
- Exporting contribution history as CSV — CLI enhancement, future

---

## Risks and Assumptions

- **Assumption**: Existing contribution nodes in the graph have a `created_at` timestamp. If timestamps are missing, growth buckets will collapse incorrectly. Mitigation: query must handle null `created_at` by placing in the oldest bucket.
- **Risk**: Computing badges on-the-fly for contributors with thousands of contributions could be slow (>500ms). Mitigation: add Redis cache keyed by `contributor_id` with 60s TTL, activated only when contribution count > 100. Badge cache invalidation on new contribution write.
- **Assumption**: Contribution `type` can be reliably inferred from metadata. If metadata is sparse (common for early contributions), most will fall into `other`. Acceptable for MVP. Mitigation: add a migration task to backfill type from commit messages (follow-up).
- **Risk**: Leaderboard rank is expensive to compute per-request if contributor count exceeds 1000. For MVP, rank is computed using the existing `GET /api/leaderboard` endpoint (single call, in-memory sort). Threshold to re-evaluate: 500+ contributors.

---

## Known Gaps and Follow-up Tasks

- Badge notifications (push/email) on milestone crossing: `Follow-up: Spec 178`
- Public network health `/stats` page showing system-wide growth: `Follow-up: Spec 179`
- Backfill contribution `type` from git history: `Follow-up task: task_contrib_type_backfill`
- `cc profile` CLI implementation requires updates to `cc` CLI codebase (separate PR)
- Comparative percentile display ("you're in the top 20%") deferred to post-launch analytics

---

## Failure/Retry Reflection

- **Failure mode**: Contributor ID not found in graph (UUID format mismatch between postgres and graph store).
  - **Blind spot**: The contributor router uses `legacy_id` mapping; the growth endpoints must use the same lookup pattern.
  - **Next action**: Reuse `_find_contributor_node()` helper from `contributions.py` rather than direct graph node lookup.

- **Failure mode**: Growth chart shows all zeros because `created_at` is stored as a string without timezone.
  - **Blind spot**: ISO 8601 parsing with and without `Z` suffix must both work.
  - **Next action**: Normalize to UTC on read using `dateutil.parser.parse(...).astimezone(timezone.utc)`.

---

## Decision Gates

- **Badge persistence**: MVP computes badges on-the-fly. If response time exceeds 300ms for p95, a badge cache or materialized view must be added. Decision owner: platform lead.
- **CC earned field**: `cc_earned` on contributions is not currently a first-class field. MVP derives it from `cost_amount` × exchange rate. If `exchange_rates.json` changes, historical CC figures will shift. Needs decision: should we snapshot CC at contribution time?
