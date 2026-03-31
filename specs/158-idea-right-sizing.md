# Spec 158: Idea Right-Sizing — Automatic Granularity Management

**Spec ID**: 158-idea-right-sizing
**Idea ID**: task_118e91480bc5af70
**Status**: Draft
**Depends on**: Spec 053 (Portfolio Governance), Spec 126 (Idea Lifecycle Management), Spec 138 (Idea Lifecycle v2)
**Depended on by**: Spec 157 (Investment UX)

---

## Summary

Ideas in the Coherence Network portfolio become unwieldy at two extremes: bloated super-ideas that contain 10+ open questions and a dozen sub-tasks (too big to execute), and nano-ideas that duplicate 80% of an existing idea and have no independent activity (too small to justify tracking). Right-sizing is the discipline of keeping ideas at the right execution granularity — actionable enough to assign, distinct enough to track.

This spec introduces **automatic right-sizing analysis** as a backend service plus lightweight surfacing in the CLI (`cc ideas --right-size`) and REST API (`GET /api/ideas/right-sizing`). The service diagnoses each idea's granularity health, produces `split` or `merge` suggestions with rationale, and writes a `granularity_health` field back to each idea so dashboards and agents can act on it.

The proof of whether right-sizing is working is explicit and measurable: the number of ideas in the "over-large" or "overlap-duplicate" bands must decline week-over-week after suggestions are applied.

---

## Problem Statement

The current portfolio has no mechanism to detect or correct granularity drift:

- An idea accumulates 12 open questions and 8 linked tasks but never gets decomposed → it stays in the backlog forever, too big to act on.
- Two near-duplicate ideas are created independently → contributors split effort; coherence scores diverge for the same underlying work.
- Portfolio navigation degrades: 200+ ideas, many of which are either too vague or too redundant to usefully rank.

There is no feedback loop that says *"this idea needs to be split"* or *"these two ideas should become one"* before a human notices it themselves.

---

## Requirements

### R1 — Granularity Diagnosis

The system must compute a `granularity_signal` for each idea:

```
granularity_signal ∈ { "too_large", "too_small", "overlap", "healthy" }
```

Thresholds (configurable via `api/config/right_sizing.json`):

| Signal      | Condition                                                                 |
|-------------|---------------------------------------------------------------------------|
| `too_large` | open_questions ≥ 10 OR linked_task_count ≥ 8                              |
| `too_small` | open_questions == 0 AND linked_task_count == 0 AND age_days ≥ 14          |
| `overlap`   | semantic_overlap_score ≥ 0.80 with any other idea in portfolio            |
| `healthy`   | none of the above                                                         |

`semantic_overlap_score` is computed via a lightweight text similarity (TF-IDF cosine) over `name + description`. Full embedding-based similarity is a follow-up task.

### R2 — Split Suggestion

When `granularity_signal == "too_large"`, the service generates a `SplitSuggestion`:

```json
{
  "suggestion_type": "split",
  "idea_id": "my-big-idea",
  "rationale": "This idea has 12 open questions and 9 tasks. Consider splitting into: (1) core delivery tasks, (2) research sub-idea for unresolved questions.",
  "proposed_children": [
    { "name": "my-big-idea (core)", "description": "..." },
    { "name": "my-big-idea (research)", "description": "..." }
  ],
  "confidence": 0.82
}
```

Split suggestions are **advisory only**. The user must explicitly apply them via `POST /api/ideas/right-sizing/apply`.

### R3 — Merge Suggestion

When `granularity_signal == "overlap"`, the service generates a `MergeSuggestion`:

```json
{
  "suggestion_type": "merge",
  "idea_id": "my-small-idea",
  "overlap_with_id": "larger-idea",
  "overlap_score": 0.83,
  "rationale": "This idea overlaps 83% with 'larger-idea' by TF-IDF cosine similarity. It has no independent activity.",
  "proposed_action": "attach_as_child",
  "confidence": 0.76
}
```

`proposed_action` is one of:
- `attach_as_child` — set `my-small-idea.parent_idea_id = larger-idea.id` and `idea_type = CHILD`
- `merge_and_archive` — copy open questions into `larger-idea` and archive `my-small-idea`

### R4 — Right-Sizing API Endpoint

```
GET /api/ideas/right-sizing
```

Returns a full right-sizing report for the portfolio:

```json
{
  "generated_at": "2026-03-27T12:00:00Z",
  "portfolio_health": {
    "total": 210,
    "healthy": 172,
    "too_large": 14,
    "too_small": 9,
    "overlap": 15
  },
  "suggestions": [
    { "suggestion_type": "split", ... },
    { "suggestion_type": "merge", ... }
  ],
  "trend": {
    "healthy_pct_now": 0.819,
    "healthy_pct_7d_ago": 0.784,
    "direction": "improving"
  }
}
```

Query params:
- `?idea_id=<id>` — return right-sizing analysis for a single idea only
- `?signal=too_large|too_small|overlap|healthy` — filter by signal type
- `?limit=50&offset=0` — pagination for suggestions

### R5 — Apply Suggestion Endpoint

```
POST /api/ideas/right-sizing/apply
```

Body:
```json
{
  "suggestion_type": "split" | "merge",
  "idea_id": "my-big-idea",
  "action": "split_into_children" | "attach_as_child" | "merge_and_archive",
  "proposed_children": [...],   // required for split_into_children
  "overlap_with_id": "...",     // required for attach_as_child / merge_and_archive
  "dry_run": false
}
```

Response:
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

When `dry_run: true`, no writes occur; only `changes` is returned to preview the effect.

### R6 — `granularity_signal` Persisted on Idea

The `Idea` model must be extended with:

```python
granularity_signal: GranularitySignal = GranularitySignal.HEALTHY
granularity_assessed_at: Optional[datetime] = None
```

`GranularitySignal` enum: `healthy`, `too_large`, `too_small`, `overlap`.

The signal is re-computed on:
1. Any `POST /api/ideas` (new idea created)
2. Any `PATCH /api/ideas/<id>` that changes `open_questions`, `child_idea_ids`, or `description`
3. A background sweep via the runner every 6 hours (configurable)

### R7 — CLI: `cc ideas --right-size`

The `cc ideas` command gains a `--right-size` flag:

```
cc ideas --right-size
```

Output (abbreviated):
```
Portfolio Right-Sizing Report  (generated 2026-03-27T12:00Z)
─────────────────────────────────────────────────────────────
Healthy:    172 / 210  (82%)   ▲ +3% vs 7 days ago
Too large:   14        → run `cc ideas split <id>` to decompose
Too small:    9        → run `cc ideas merge <id> <target>` to consolidate
Overlap:     15        → run `cc ideas merge <id> <target>` to deduplicate

Top suggestions:
  SPLIT   my-big-idea         12 questions, 9 tasks  (confidence: 0.82)
  MERGE   my-small-idea   →  larger-idea   overlap: 83%  (confidence: 0.76)
  MERGE   duplicate-idea  →  canonical-idea  overlap: 91%  (confidence: 0.91)
```

Sub-commands:
- `cc ideas split <idea-id>` — applies the system-proposed split (dry-run by default; `--apply` to execute)
- `cc ideas merge <idea-id> <target-id>` — applies attach_as_child or merge_and_archive

### R8 — Proof that Right-Sizing is Working

The system must be able to answer: *"Is right-sizing improving portfolio navigability over time?"*

Proof mechanism:
1. `GET /api/ideas/right-sizing` returns a `trend` block comparing `healthy_pct` now vs 7 days ago.
2. A time-series table `right_sizing_snapshots` (PostgreSQL) records daily portfolio health counts.
3. `GET /api/ideas/right-sizing/history?days=30` returns the 30-day series so a chart can be rendered.
4. When the healthy percentage increases week-over-week, the trend `direction` is `"improving"`. When it falls, `"degrading"`. When stable (< 1% change), `"stable"`.

The web `/ideas` page displays a small health badge: `Portfolio health: 82% ✓` that links to the right-sizing report.

---

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

---

## API Contract

### `GET /api/ideas/right-sizing`

**Query params**
- `idea_id` (optional, string): filter to single idea
- `signal` (optional, enum): `too_large | too_small | overlap | healthy`
- `limit` (int, default 50, max 200)
- `offset` (int, default 0)

**Response 200** — `RightSizingReport`
```json
{
  "generated_at": "2026-03-27T12:00:00Z",
  "portfolio_health": {
    "total": 210,
    "healthy": 172,
    "too_large": 14,
    "too_small": 9,
    "overlap": 15
  },
  "suggestions": [...],
  "trend": {
    "healthy_pct_now": 0.819,
    "healthy_pct_7d_ago": 0.784,
    "direction": "improving"
  }
}
```

**Response 404** (when `?idea_id=` is given and the idea does not exist)
```json
{ "detail": "Idea not found: <id>" }
```

---

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

---

### `GET /api/ideas/right-sizing/history`

**Query params**
- `days` (int, default 30, max 365)

**Response 200**
```json
{
  "series": [
    { "date": "2026-03-21", "healthy": 165, "too_large": 18, "too_small": 12, "overlap": 17, "healthy_pct": 0.757 },
    ...
  ]
}
```

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `api/app/models/idea.py` | Add `GranularitySignal` enum; extend `Idea` with `granularity_signal`, `granularity_assessed_at`, `overlap_with_idea_id`, `overlap_score`; add `RightSizingSuggestion`, `RightSizingReport`, `PortfolioHealthCounts`, `TrendInfo` models |
| `api/app/services/right_sizing_service.py` | New service: `compute_granularity_signal()`, `generate_suggestions()`, `build_report()`, `apply_suggestion()`, `snapshot_health()`, `get_history()` |
| `api/app/routers/ideas.py` | Add `GET /ideas/right-sizing`, `POST /ideas/right-sizing/apply`, `GET /ideas/right-sizing/history` routes |
| `api/config/right_sizing.json` | New config file with thresholds and sweep settings |
| `api/alembic/versions/<hash>_add_right_sizing_fields.py` | Migration: add columns to `ideas` table; create `right_sizing_snapshots` table |
| `api/tests/test_right_sizing.py` | Full test suite (see Acceptance Tests) |

---

## Acceptance Tests

- `api/tests/test_right_sizing.py::test_signal_too_large_by_questions`
- `api/tests/test_right_sizing.py::test_signal_too_large_by_tasks`
- `api/tests/test_right_sizing.py::test_signal_too_small`
- `api/tests/test_right_sizing.py::test_signal_overlap_detected`
- `api/tests/test_right_sizing.py::test_signal_healthy`
- `api/tests/test_right_sizing.py::test_get_report_200`
- `api/tests/test_right_sizing.py::test_get_report_idea_not_found_404`
- `api/tests/test_right_sizing.py::test_apply_split_dry_run`
- `api/tests/test_right_sizing.py::test_apply_split_creates_children`
- `api/tests/test_right_sizing.py::test_apply_merge_attach_as_child`
- `api/tests/test_right_sizing.py::test_apply_merge_and_archive`
- `api/tests/test_right_sizing.py::test_history_returns_series`
- `api/tests/test_right_sizing.py::test_trend_improving`
- `api/tests/test_right_sizing.py::test_invalid_action_422`

---

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

---

### Scenario 2 — Single-idea diagnosis returns granularity signal

**Setup**: Create an idea with 10 open questions.

**Action**:
```bash
# Create an over-large idea
curl -s -X POST https://api.coherencycoin.com/api/ideas \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-too-large-001",
    "name": "Test Over-Large Idea",
    "description": "An idea with too many questions to be actionable",
    "potential_value": 10.0,
    "estimated_cost": 5.0,
    "open_questions": [
      {"question": "Q1", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q2", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q3", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q4", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q5", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q6", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q7", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q8", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q9", "value_to_whole": 1.0, "estimated_cost": 0.5},
      {"question": "Q10", "value_to_whole": 1.0, "estimated_cost": 0.5}
    ]
  }'

# Query right-sizing for that specific idea
curl -s "https://api.coherencycoin.com/api/ideas/right-sizing?idea_id=test-too-large-001" | jq '.suggestions[0]'
```

**Expected result**:
- First request: HTTP 201, idea created
- Second request: HTTP 200, `suggestions[0].suggestion_type == "split"`, `suggestions[0].idea_id == "test-too-large-001"`, `suggestions[0].confidence > 0.0`

**Edge case**: `?idea_id=nonexistent-000` → HTTP 404 with `{"detail": "Idea not found: nonexistent-000"}` (not 500).

---

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

---

### Scenario 4 — Overlap detection between near-duplicate ideas

**Setup**: Create two ideas with very similar names and descriptions.

**Action**:
```bash
# Create canonical idea
curl -s -X POST https://api.coherencycoin.com/api/ideas \
  -H "Content-Type: application/json" \
  -d '{"id":"canonical-caching","name":"GraphQL response caching","description":"Cache GraphQL responses at the API layer to reduce latency","potential_value":8.0,"estimated_cost":3.0}'

# Create near-duplicate
curl -s -X POST https://api.coherencycoin.com/api/ideas \
  -H "Content-Type: application/json" \
  -d '{"id":"duplicate-caching","name":"GraphQL API caching layer","description":"Add caching to GraphQL API responses for lower latency","potential_value":7.0,"estimated_cost":3.0}'

# Get right-sizing report filtered to overlap
curl -s "https://api.coherencycoin.com/api/ideas/right-sizing?signal=overlap" | jq '.suggestions[] | select(.idea_id == "duplicate-caching")'
```

**Expected result**:
- HTTP 200 on report
- At least one suggestion with `suggestion_type == "merge"`, `idea_id == "duplicate-caching"`, `overlap_with_id == "canonical-caching"`, `overlap_score >= 0.80`

**Edge case**: Creating a clearly unrelated idea (e.g., `{"name": "Mobile push notifications", ...}`) must NOT appear as an overlap suggestion against the caching ideas.

---

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

---

## Verification

```bash
# Run unit tests
cd api && pytest -q tests/test_right_sizing.py -v

# Check report endpoint
curl -s https://api.coherencycoin.com/api/ideas/right-sizing | jq .portfolio_health

# Check history endpoint
curl -s "https://api.coherencycoin.com/api/ideas/right-sizing/history?days=30" | jq '.series | length'
```

---

## Out of Scope

- Embedding-based semantic similarity (TF-IDF only for MVP; embeddings are a follow-up)
- Automatic application of suggestions without human confirmation
- Right-sizing for tasks (only ideas in this spec)
- Mobile or email notifications for right-sizing alerts
- ML-based split point detection (rule-based threshold logic only)

---

## Risks and Assumptions

- **Assumption**: TF-IDF cosine similarity is sufficient to catch obvious duplicates. If false, precision will be low (too many false-positive merge suggestions). Mitigation: configurable `overlap_score_min` threshold; start at 0.80 and tune.
- **Risk**: Re-computing overlap pairwise across 200+ ideas on every write event is O(n²). Mitigation: run overlap analysis only during the 6-hour background sweep, not on every individual idea write.
- **Risk**: Applying a split suggestion without human review could create orphaned ideas. Mitigation: `dry_run: true` is the default; `--apply` must be explicit.
- **Assumption**: The PostgreSQL `right_sizing_snapshots` table can be created via Alembic migration without data loss to existing ideas.

---

## Known Gaps and Follow-up Tasks

- **Follow-up**: Replace TF-IDF overlap with sentence-embedding similarity (e.g., via `sentence-transformers` or OpenAI embeddings) once the overlap false-positive rate is measured.
- **Follow-up**: Surface the portfolio health badge (`82% healthy`) on the web `/ideas` page (requires web changes outside this spec's scope).
- **Follow-up**: Add `cc ideas --right-size` CLI subcommand (requires `cc` CLI changes; this spec defines the API contract only).
- **Follow-up**: Alerting when `healthy_pct` drops > 5% week-over-week (spec 159 candidate).

---

## Failure/Retry Reflection

- **Failure mode**: Overlap detection produces false positives (ideas flagged as duplicates that are genuinely distinct).
  - **Blind spot**: TF-IDF is lexical, not semantic — two ideas using the same vocabulary for different purposes will score high.
  - **Next action**: Tune threshold upward (0.85+) and add a `rationale` field that shows which keywords drove the overlap score, so humans can judge quickly.

- **Failure mode**: The right-sizing sweep runs on every API call and causes latency spikes.
  - **Blind spot**: Initial implementation naively computes on every write.
  - **Next action**: Move to background task with cached results; only invalidate cache when `open_questions` or description changes.

---

## Decision Gates

- **Threshold values** (too_large_questions=10, too_large_tasks=8, overlap_score_min=0.80) must be reviewed with the portfolio owner before the first background sweep runs. These are configurable in `right_sizing.json` but the defaults ship with this spec.
- **`merge_and_archive` action** is irreversible (soft-delete only). A human must confirm via the API explicitly; there is no "undo" endpoint in this spec.
