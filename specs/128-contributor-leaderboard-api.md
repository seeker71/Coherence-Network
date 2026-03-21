# Spec: Contributor Leaderboard API

## Purpose

Provide a ranked leaderboard of contributors based on aggregated contribution metrics (total cost, contribution count, average coherence score). This enables transparent recognition of top contributors, supports gamification on the web UI, and provides data for governance and distribution decisions. Without this endpoint, clients must fetch all contributors and all contributions separately, then aggregate client-side — expensive and inconsistent.

## Requirements

- [ ] GET /api/leaderboard — Return a ranked list of contributors with aggregated stats
- [ ] Each entry includes: contributor_id, name, type, total_cost, contribution_count, avg_coherence_score, rank
- [ ] Default sort: total_cost descending (highest contributor first)
- [ ] Support `sort_by` query param: `total_cost` (default), `contribution_count`, `avg_coherence_score`
- [ ] Support `limit` (default 10, max 100) and `offset` (default 0) for pagination
- [ ] Contributors with zero contributions are excluded from the leaderboard
- [ ] Response uses PaginatedResponse wrapper with total count of ranked contributors
- [ ] All responses are Pydantic models (JSON-serialized)
- [ ] Coherence scores: 0.0–1.0; dates: ISO 8601 UTC

## Research Inputs (Required)

- `2026-02-15` - [Spec 048: Contributions API](specs/048-contributions-api.md) - defines the contribution data model and coherence scoring used for aggregation
- `2026-02-10` - [Spec 082: Landing Page Contributor Onboarding](specs/082-landing-page-contributor-onboarding.md) - defines contributor registration flow that feeds the leaderboard

## Task Card (Required)

```yaml
goal: Add GET /api/leaderboard endpoint returning ranked contributors by aggregated contribution metrics
files_allowed:
  - api/app/routers/leaderboard.py
  - api/app/models/leaderboard.py
  - api/app/services/leaderboard_service.py
  - api/app/main.py
  - api/app/adapters/graph_store.py
  - api/app/adapters/postgres_store.py
  - api/tests/test_leaderboard.py
  - specs/128-contributor-leaderboard-api.md
done_when:
  - GET /api/leaderboard returns ranked contributors with aggregated stats
  - Sorting by total_cost, contribution_count, avg_coherence_score works
  - Pagination via limit/offset works correctly
  - Contributors with zero contributions are excluded
  - All tests pass
commands:
  - python3 -m pytest api/tests/test_leaderboard.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations
  - aggregation performed server-side, not client-side
```

## API Contract

### `GET /api/leaderboard`

**Purpose**: Return a ranked leaderboard of contributors sorted by aggregated contribution metrics.

**Request**
- `sort_by`: string (query, optional) — one of `total_cost`, `contribution_count`, `avg_coherence_score`. Default: `total_cost`
- `limit`: int (query, optional) — max items to return, 1–100. Default: 10
- `offset`: int (query, optional) — items to skip, >= 0. Default: 0

**Response 200**
```json
{
  "items": [
    {
      "rank": 1,
      "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Alice",
      "type": "HUMAN",
      "total_cost": 1500.00,
      "contribution_count": 12,
      "avg_coherence_score": 0.85
    },
    {
      "rank": 2,
      "contributor_id": "660e8400-e29b-41d4-a716-446655440000",
      "name": "Bob",
      "type": "HUMAN",
      "total_cost": 1200.00,
      "contribution_count": 8,
      "avg_coherence_score": 0.72
    }
  ],
  "total": 25,
  "limit": 10,
  "offset": 0
}
```

**Field definitions:**
- `rank`: int — 1-indexed position in the sorted leaderboard (relative to full dataset, not page)
- `contributor_id`: UUID — contributor identifier
- `name`: string — contributor display name
- `type`: string — `HUMAN` or `SYSTEM`
- `total_cost`: Decimal — sum of all contribution cost_amounts
- `contribution_count`: int — number of contributions
- `avg_coherence_score`: float (0.0–1.0) — mean coherence score across contributions, rounded to 2 decimal places

**Response 422**
```json
{
  "detail": [
    {
      "loc": ["query", "sort_by"],
      "msg": "Input should be 'total_cost', 'contribution_count' or 'avg_coherence_score'",
      "type": "enum"
    }
  ]
}
```

## Data Model

```yaml
LeaderboardEntry:
  properties:
    rank: { type: int, description: "1-indexed position" }
    contributor_id: { type: UUID }
    name: { type: string }
    type: { type: ContributorType }
    total_cost: { type: Decimal }
    contribution_count: { type: int }
    avg_coherence_score: { type: float, min: 0.0, max: 1.0 }

LeaderboardSortField:
  enum: [total_cost, contribution_count, avg_coherence_score]
```

## Files to Create/Modify

- `api/app/routers/leaderboard.py` — route handler for GET /api/leaderboard
- `api/app/models/leaderboard.py` — LeaderboardEntry and LeaderboardSortField Pydantic models
- `api/app/services/leaderboard_service.py` — aggregation logic (iterate contributors, sum contributions, rank)
- `api/app/main.py` — register leaderboard router
- `api/app/adapters/graph_store.py` — no new methods needed (uses existing list_contributors + get_contributor_contributions)
- `api/tests/test_leaderboard.py` — test suite

## Acceptance Tests

- `api/tests/test_leaderboard.py::test_leaderboard_default_sort` — returns entries sorted by total_cost desc
- `api/tests/test_leaderboard.py::test_leaderboard_sort_by_contribution_count` — sort by contribution_count works
- `api/tests/test_leaderboard.py::test_leaderboard_sort_by_avg_coherence` — sort by avg_coherence_score works
- `api/tests/test_leaderboard.py::test_leaderboard_pagination` — limit and offset correctly paginate results
- `api/tests/test_leaderboard.py::test_leaderboard_excludes_zero_contributions` — contributors with no contributions are excluded
- `api/tests/test_leaderboard.py::test_leaderboard_empty` — returns empty items when no contributions exist
- `api/tests/test_leaderboard.py::test_leaderboard_invalid_sort_by` — returns 422 for invalid sort_by value

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: N/A — this is a read-only endpoint.
- **Recommendation**: Leaderboard data is eventually consistent with contribution writes; no transactional guarantees needed for MVP.

## Verification

```bash
cd api && python3 -m pytest tests/test_leaderboard.py -x -v
```

## Out of Scope

- Time-windowed leaderboards (e.g., "top contributors this week") — deferred to follow-up
- Leaderboard caching/materialized views — optimize only if performance becomes an issue
- WebSocket real-time leaderboard updates
- Contributor avatars or profile enrichment
- Tie-breaking rules (contributors with identical scores share the same rank position)

## Risks and Assumptions

- **Performance risk**: Aggregation iterates all contributors and their contributions in-memory. Mitigation: acceptable for MVP scale (< 1000 contributors); add PostgreSQL aggregation query or caching if scale demands it.
- **Assumption**: Existing `list_contributors` and `get_contributor_contributions` store methods provide sufficient data without new store methods.
- **Assumption**: `avg_coherence_score` rounding to 2 decimal places is sufficient precision for display and sorting.

## Known Gaps and Follow-up Tasks

- Follow-up: Add time-windowed leaderboards (weekly, monthly) once contribution volume warrants it.
- Follow-up: Add PostgreSQL-native aggregation query to replace in-memory aggregation at scale.
- Follow-up: Add leaderboard entry to web UI dashboard.

## Failure/Retry Reflection

- Failure mode: Store returns incomplete contributor list due to pagination in underlying query
- Blind spot: `list_contributors` has an internal limit; leaderboard service must request sufficient records
- Next action: Pass a high limit to `list_contributors` or add an unbounded variant for internal aggregation

## Decision Gates (if any)

- None — straightforward read-only aggregation endpoint with no security or architecture implications beyond existing patterns.
