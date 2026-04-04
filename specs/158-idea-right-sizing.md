---
idea_id: idea-realization-engine
status: active
source: []  # not yet implemented
requirements:
  - Detect too_large, too_small, overlap granularity signals per idea
  - Generate split/merge suggestions with confidence and rationale
  - GET /api/ideas/right-sizing returns portfolio health counts and suggestions
  - POST /api/ideas/right-sizing/apply executes split or merge with dry_run support
  - GET /api/ideas/right-sizing/history returns time-series health snapshots
  - TF-IDF overlap detection with configurable score threshold (default 0.80)
  - Snapshot health counts on 6-hour sweep, retain 90 days
done_when:
  - Right-sizing report returns valid health counts for 10+ ideas
  - Dry-run apply previews changes without writing
  - pytest api/tests/test_right_sizing.py passes
---

> **Parent idea**: [idea-realization-engine](../ideas/idea-realization-engine.md)

# Spec 158: Idea Right-Sizing — Automatic Granularity Management

**Spec ID**: 158-idea-right-sizing
**Idea ID**: task_118e91480bc5af70
**Status**: Draft
**Depends on**: Spec 053 (Portfolio Governance), Spec 126 (Idea Lifecycle Management), Spec 138 (Idea Lifecycle v2)
**Depended on by**: Spec 157 (Investment UX)

## Problem Statement

The current portfolio has no mechanism to detect or correct granularity drift:

- An idea accumulates 12 open questions and 8 linked tasks but never gets decomposed → it stays in the backlog forever, too big to act on.
- Two near-duplicate ideas are created independently → contributors split effort; coherence scores diverge for the same underlying work.
- Portfolio navigation degrades: 200+ ideas, many of which are either too vague or too redundant to usefully rank.

There is no feedback loop that says *"this idea needs to be split"* or *"these two ideas should become one"* before a human notices it themselves.

## Data Model

### New: `GranularitySignal` enum

```python
class GranularitySignal(str, Enum):
    HEALTHY   = "healthy"
    TOO_LARGE = "too_large"
    TOO_SMALL = "too_small"
    OVERLAP   = "overlap"
```

### Updated: `Idea` model additions

```python
granularity_signal: GranularitySignal = GranularitySignal.HEALTHY
granularity_assessed_at: Optional[datetime] = None
overlap_with_idea_id: Optional[str] = None       # populated when signal == overlap
overlap_score: Optional[float] = None            # 0.0–1.0
```

### New: `RightSizingSuggestion` Pydantic model

```python
class SuggestionType(str, Enum):
    SPLIT = "split"
    MERGE = "merge"

class RightSizingSuggestion(BaseModel):
    suggestion_type: SuggestionType
    idea_id: str
    rationale: str
    confidence: float               # 0.0–1.0
    overlap_with_id: Optional[str] = None
    overlap_score: Optional[float] = None
    proposed_children: list[dict] = Field(default_factory=list)
    proposed_action: Optional[str] = None   # attach_as_child | merge_and_archive
```

### New: `RightSizingReport` response model

```python
class PortfolioHealthCounts(BaseModel):
    total: int
    healthy: int
    too_large: int
    too_small: int
    overlap: int

class TrendInfo(BaseModel):
    healthy_pct_now: float
    healthy_pct_7d_ago: Optional[float] = None
    direction: str                  # improving | stable | degrading

class RightSizingReport(BaseModel):
    generated_at: datetime
    portfolio_health: PortfolioHealthCounts
    suggestions: list[RightSizingSuggestion]
    trend: TrendInfo
```

### New: `right_sizing_snapshots` PostgreSQL table

```sql
CREATE TABLE right_sizing_snapshots (
    id          SERIAL PRIMARY KEY,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total       INTEGER NOT NULL,
    healthy     INTEGER NOT NULL,
    too_large   INTEGER NOT NULL,
    too_small   INTEGER NOT NULL,
    overlap     INTEGER NOT NULL,
    healthy_pct FLOAT NOT NULL
);

CREATE INDEX idx_rss_snapshot_at ON right_sizing_snapshots(snapshot_at);
```

### Config: `api/config/right_sizing.json`

```json
{
  "thresholds": {
    "too_large_questions": 10,
    "too_large_tasks": 8,
    "too_small_age_days": 14,
    "overlap_score_min": 0.80
  },
  "sweep_interval_hours": 6,
  "snapshot_retention_days": 90
}
```

### `POST /api/ideas/right-sizing/apply`

**Auth**: requires API key (`X-API-Key` header)

**Request body**
```json
{
  "suggestion_type": "split",
  "idea_id": "my-big-idea",
  "action": "split_into_children",
  "proposed_children": [
    { "name": "my-big-idea (core)", "description": "Core delivery tasks" },
    { "name": "my-big-idea (research)", "description": "Unresolved questions" }
  ],
  "dry_run": false
}
```

**Response 200**
```json
{
  "applied": true,
  "dry_run": false,
  "changes": [
    { "op": "create_idea", "idea_id": "my-big-idea-core" },
    { "op": "create_idea", "idea_id": "my-big-idea-research" },
    { "op": "update_idea", "idea_id": "my-big-idea", "set": { "idea_type": "super" } }
  ]
}
```

**Response 422** — invalid `action` for `suggestion_type`

**Response 404** — `idea_id` or `overlap_with_id` not found

## Files to Create/Modify

| File | Change |
|------|--------|
| `api/app/models/idea.py` | Add `GranularitySignal` enum; extend `Idea` with `granularity_signal`, `granularity_assessed_at`, `overlap_with_idea_id`, `overlap_score`; add `RightSizingSuggestion`, `RightSizingReport`, `PortfolioHealthCounts`, `TrendInfo` models |
| `api/app/services/right_sizing_service.py` | New service: `compute_granularity_signal()`, `generate_suggestions()`, `build_report()`, `apply_suggestion()`, `snapshot_health()`, `get_history()` |
| `api/app/routers/ideas.py` | Add `GET /ideas/right-sizing`, `POST /ideas/right-sizing/apply`, `GET /ideas/right-sizing/history` routes |
| `api/config/right_sizing.json` | New config file with thresholds and sweep settings |
| `api/alembic/versions/<hash>_add_right_sizing_fields.py` | Migration: add columns to `ideas` table; create `right_sizing_snapshots` table |
| `api/tests/test_right_sizing.py` | Full test suite (see Acceptance Tests) |

## Verification Scenarios

These scenarios must pass in production against `https://api.coherencycoin.com`.

### Scenario 1 — Portfolio right-sizing report is readable and has sensible structure

**Setup**: At least 10 ideas exist in the portfolio (production baseline).

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/ideas/right-sizing | jq '{
  total: .portfolio_health.total,
  healthy: .portfolio_health.healthy,
  direction: .trend.direction,
  suggestion_count: (.suggestions | length)
}'
```

**Expected result**:
- HTTP 200
- `portfolio_health.total` >= 10
- `portfolio_health.healthy` >= 0 and <= `portfolio_health.total`
- `trend.direction` in `["improving", "stable", "degrading"]`
- `suggestions` is an array (may be empty if all ideas are healthy)

**Edge case**: No ideas exist → returns `portfolio_health.total == 0`, `suggestions == []`, `trend.direction == "stable"` (not 500).

### Scenario 3 — Apply split (dry run previews changes without writing)

**Setup**: Idea `test-too-large-001` from Scenario 2 exists with `granularity_signal == "too_large"`.

**Action**:
```bash
curl -s -X POST https://api.coherencycoin.com/api/ideas/right-sizing/apply \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "suggestion_type": "split",
    "idea_id": "test-too-large-001",
    "action": "split_into_children",
    "proposed_children": [
      {"name": "Test Over-Large (core)", "description": "Core delivery"},
      {"name": "Test Over-Large (research)", "description": "Unresolved questions"}
    ],
    "dry_run": true
  }'
```

**Expected result**:
- HTTP 200
- `applied == false` (dry run)
- `dry_run == true`
- `changes` contains `{"op": "create_idea", ...}` entries for both proposed children
- `changes` contains `{"op": "update_idea", "idea_id": "test-too-large-001", "set": {"idea_type": "super"}}`
- No new ideas actually created (verify with `GET /api/ideas/test-too-large-001-core` → 404)

**Edge case**: Invalid `action` value → HTTP 422 with validation error.

### Scenario 5 — Trend history shows time series

**Setup**: At least one right-sizing snapshot has been taken (occurs automatically on API startup or 6-hour sweep).

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/ideas/right-sizing/history?days=7" | jq '{
  count: (.series | length),
  first: .series[0],
  last: .series[-1]
}'
```

**Expected result**:
- HTTP 200
- `series` is an array with ≥ 1 entry
- Each entry has `date` (ISO 8601), `healthy` (int), `healthy_pct` (float 0–1)
- `healthy_pct` values are consistent with portfolio size (`healthy / total`)

**Edge case**: `?days=0` → HTTP 422 (`days must be >= 1`). `?days=366` → HTTP 422 (`days must be <= 365`).

## Out of Scope

- Embedding-based semantic similarity (TF-IDF only for MVP; embeddings are a follow-up)
- Automatic application of suggestions without human confirmation
- Right-sizing for tasks (only ideas in this spec)
- Mobile or email notifications for right-sizing alerts
- ML-based split point detection (rule-based threshold logic only)

## Known Gaps and Follow-up Tasks

- **Follow-up**: Replace TF-IDF overlap with sentence-embedding similarity (e.g., via `sentence-transformers` or OpenAI embeddings) once the overlap false-positive rate is measured.
- **Follow-up**: Surface the portfolio health badge (`82% healthy`) on the web `/ideas` page (requires web changes outside this spec's scope).
- **Follow-up**: Add `cc ideas --right-size` CLI subcommand (requires `cc` CLI changes; this spec defines the API contract only).
- **Follow-up**: Alerting when `healthy_pct` drops > 5% week-over-week (spec 159 candidate).

## Decision Gates

- **Threshold values** (too_large_questions=10, too_large_tasks=8, overlap_score_min=0.80) must be reviewed with the portfolio owner before the first background sweep runs. These are configurable in `right_sizing.json` but the defaults ship with this spec.
- **`merge_and_archive` action** is irreversible (soft-delete only). A human must confirm via the API explicitly; there is no "undo" endpoint in this spec.
