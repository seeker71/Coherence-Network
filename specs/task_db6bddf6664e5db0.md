# Spec: Visible Contribution Recognition and Growth Tracking

## Summary

Contributors need a simple, visible way to understand whether their work is being recognized and whether participation is increasing or slowing down. The minimal requirement is not a leaderboard, badge system, or full analytics dashboard. It is a single read API that returns one contributor's lifetime recognition totals plus a basic recent-growth comparison. This keeps the scope small while giving the web UI or CLI enough data to show "your contributions so far" and "activity compared with the previous period" without client-side aggregation across multiple endpoints.

This spec intentionally reuses existing contributor and contribution records. It does not introduce write flows, reputation formulas, notifications, or configurable windows. The response should be stable, cheap to compute, and understandable by a first-time contributor.

## Purpose

Provide the smallest useful contract for visible contribution recognition and growth tracking so one contributor can see lifetime contribution totals and recent activity change without leaderboard logic, client-side aggregation, or new write paths.

## Requirements

- [ ] Add `GET /api/contributors/{contributor_id}/recognition`.
- [ ] The endpoint returns a contributor recognition snapshot with these lifetime fields:
  - `contributor_id`
  - `name`
  - `total_contributions`
  - `total_cost`
  - `average_coherence_score`
- [ ] The same response returns fixed-window growth fields for recent contribution activity:
  - `window_days`
  - `current_window_contributions`
  - `prior_window_contributions`
  - `delta_contributions`
- [ ] `window_days` is fixed at `30` for the MVP. No query parameter is added for custom windows.
- [ ] Growth is based on contribution timestamps using two contiguous UTC windows of equal length: the current 30-day window ending at request time, and the immediately preceding 30-day window.
- [ ] Unknown contributor IDs return `404`.
- [ ] Contributors with zero contributions still return `200` when the contributor exists, with all aggregate counts and sums set to zero.
- [ ] The endpoint is read-only and must not create or mutate contributor or contribution records.

## Research Inputs

- `2026-02-15` - [Spec 048: Contributions API](specs/048-contributions-api.md) - defines contribution fields, timestamps, cost, and coherence score inputs reused here.
- `2026-02-15` - [Spec 128: Contributor Leaderboard API](specs/128-contributor-leaderboard-api.md) - establishes related contributor aggregation patterns, but this spec stays per-contributor and does not include rank.
- `2026-03-28` - [Prior draft for same idea](specs/task_f576c873b5af86d3.md) - broader earlier draft; this retry narrows scope to the smallest useful read contract.

## Task Card

```yaml
goal: Add a minimal per-contributor recognition endpoint with fixed 30-day growth tracking.
files_allowed:
  - api/app/routers/contributor_recognition.py
  - api/app/models/contributor_recognition.py
  - api/app/services/contributor_recognition_service.py
  - api/app/adapters/graph_store.py
  - api/app/main.py
  - api/tests/test_contributor_recognition.py
  - specs/task_db6bddf6664e5db0.md
done_when:
  - GET /api/contributors/{contributor_id}/recognition returns lifetime recognition fields and 30-day growth fields.
  - Existing contributor with no contributions returns zeros instead of 404.
  - Missing contributor returns 404.
commands:
  - cd api && python -m pytest tests/test_contributor_recognition.py -x -v
constraints:
  - keep the scope read-only
  - no badges, ranks, streaks, notifications, or custom date windows
  - no schema migration unless the existing store cannot supply contribution timestamps
```

## Files to Create/Modify

- `api/app/routers/contributor_recognition.py` - route handler for `GET /api/contributors/{contributor_id}/recognition`
- `api/app/models/contributor_recognition.py` - response model for recognition snapshot fields
- `api/app/services/contributor_recognition_service.py` - aggregation and 30-day window computation
- `api/app/adapters/graph_store.py` - reuse or extend contributor contribution accessors if needed
- `api/app/main.py` - register the new router
- `api/tests/test_contributor_recognition.py` - endpoint and aggregation coverage
- `specs/task_db6bddf6664e5db0.md` - implementation contract

## API Changes

### `GET /api/contributors/{contributor_id}/recognition`

Purpose: Return one contributor's visible recognition totals and recent growth comparison.

**Request**
- `contributor_id`: UUID path parameter

**Response 200**
```json
{
  "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Alice",
  "total_contributions": 12,
  "total_cost": 1500.0,
  "average_coherence_score": 0.84,
  "window_days": 30,
  "current_window_contributions": 4,
  "prior_window_contributions": 2,
  "delta_contributions": 2
}
```

**Response 404**
```json
{
  "detail": "Contributor not found"
}
```

Notes:
- `delta_contributions = current_window_contributions - prior_window_contributions`.
- No percentage-growth field is included in MVP. That avoids divide-by-zero edge cases and keeps the response simple.
- No leaderboard rank is returned. Recognition here is personal summary data only.

## Data Model

```yaml
ContributorRecognitionSnapshot:
  type: object
  required:
    - contributor_id
    - name
    - total_contributions
    - total_cost
    - average_coherence_score
    - window_days
    - current_window_contributions
    - prior_window_contributions
    - delta_contributions
  properties:
    contributor_id: { type: UUID }
    name: { type: string }
    total_contributions: { type: integer, minimum: 0 }
    total_cost: { type: number, minimum: 0 }
    average_coherence_score: { type: number, minimum: 0, maximum: 1 }
    window_days: { type: integer, enum: [30] }
    current_window_contributions: { type: integer, minimum: 0 }
    prior_window_contributions: { type: integer, minimum: 0 }
    delta_contributions: { type: integer }
```

Data sourcing rules:
- Lifetime aggregates are computed from all contribution records linked to the contributor.
- Growth counts are computed from the same contribution set using contribution timestamps.
- If no contributions exist, `total_contributions`, `total_cost`, `average_coherence_score`, `current_window_contributions`, `prior_window_contributions`, and `delta_contributions` are all `0`.

## Acceptance Tests

- `api/tests/test_contributor_recognition.py::test_get_recognition_snapshot_returns_lifetime_totals`
- `api/tests/test_contributor_recognition.py::test_get_recognition_snapshot_returns_window_growth_counts`
- `api/tests/test_contributor_recognition.py::test_get_recognition_snapshot_returns_zero_metrics_for_existing_contributor_without_contributions`
- `api/tests/test_contributor_recognition.py::test_get_recognition_snapshot_returns_404_for_missing_contributor`
- Manual validation is acceptable during implementation if seeded test data is used to verify the 30-day and prior-30-day buckets.

## Verification

- `GET /api/contributors/{known_id}/recognition` returns `200` with all required fields.
- A contributor with known seeded contributions returns correct lifetime totals.
- A contributor with contributions split across current and prior windows returns correct `current_window_contributions`, `prior_window_contributions`, and `delta_contributions`.
- A contributor record that exists but has no contributions returns zeroed metrics and `200`.
- `GET /api/contributors/{unknown_id}/recognition` returns `404`.
- Validation command for implementation phase:

```bash
cd api && python -m pytest tests/test_contributor_recognition.py -x -v
```

Manual verification for implementation phase:
1. Create or identify a contributor with dated contributions in both recent windows.
2. Call `GET /api/contributors/{contributor_id}/recognition`.
3. Confirm the lifetime totals match the stored contributions and the 30-day counts match the expected date buckets.

## Out of Scope

- Global rank or leaderboard placement
- Badges, streaks, milestones, or achievement labels
- Configurable date windows or historical charts
- Web UI implementation
- Notification, email, or feed surfacing
- Cross-contributor comparisons

## Risks

- **Timestamp quality**: Growth tracking is only as accurate as contribution timestamps. If some legacy contributions are missing timestamps or use inconsistent formats, window counts may be wrong. Mitigation: treat timestamp normalization as an implementation precondition and fail tests on malformed records.
- **Average score semantics**: `average_coherence_score` may overweight old low-volume data for long-lived contributors. That is acceptable for MVP because the goal is visible recognition, not ranking fairness.
- **Scope confusion with leaderboard**: Product or UI code may try to use this endpoint as a substitute for rank. Mitigation: keep the response intentionally personal and omit comparative fields.
- **Window-boundary ambiguity**: UTC boundaries must be used consistently in code and tests to avoid off-by-one-day errors around local time zones.

## Known Gaps and Follow-up Tasks

- None for this minimal spec. Future enhancements should be separate follow-up tasks for rank, badges, charts, or configurable windows.
