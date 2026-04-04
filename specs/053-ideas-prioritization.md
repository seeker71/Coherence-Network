---
idea_id: idea-realization-engine
status: done
source:
  - file: api/app/routers/ideas.py
    symbols: [list_ideas(), get_idea(), get_idea_tags_catalog()]
  - file: api/app/services/idea_service.py
    symbols: [list_ideas(), _score(), _with_score(), _build_cost_vector(), _build_value_vector()]
  - file: api/app/models/idea.py
    symbols: [Idea, IdeaWithScore, IdeaPortfolioResponse, IdeaSummary, CostVector, ValueVector]
requirements:
  - "GET /api/ideas — List ideas ranked by free energy score with portfolio summary"
  - "GET /api/ideas/{id} — Retrieve individual idea with score (404 if not found)"
  - "PATCH /api/ideas/{id} — Update idea validation fields (404 if not found)"
  - "GET /api/ideas/storage — Report structured storage backend and row counts"
  - "Filter support for unvalidated ideas only"
  - "Free energy scoring: (potential_value × confidence) / (estimated_cost + resistance_risk)"
  - "Value gap tracking: potential_value - actual_value"
  - "Manifestation status: none, partial, validated"
  - "Ideas stored in structured DB registry with machine-readable metadata"
  - "Portfolio summary with aggregated metrics"
done_when:
  - "GET /api/ideas — List ideas ranked by free energy score with portfolio summary"
  - "GET /api/ideas/{id} — Retrieve individual idea with score (404 if not found)"
  - "PATCH /api/ideas/{id} — Update idea validation fields (404 if not found)"
  - "GET /api/ideas/storage — Report structured storage backend and row counts"
  - "Filter support for unvalidated ideas only"
test: "| Ideas test suite | `cd api && pytest -q tests/test_ideas.py` | Exit code 0; \"passed\" in output | Non-zero exit; failures or errors listed |"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [idea-realization-engine](../ideas/idea-realization-engine.md)
> **Source**: [`api/app/routers/ideas.py`](../api/app/routers/ideas.py) | [`api/app/services/idea_service.py`](../api/app/services/idea_service.py) | [`api/app/models/idea.py`](../api/app/models/idea.py)

# Spec: Ideas Prioritization API

## Spec contract summary

| Contract | Content |
|----------|---------|
| **IDEA** | Portfolio-governance: track and prioritize ideas via free energy scoring and a structured API. |
| **SPEC_SCOPE** | Ideas prioritization API (list, get, patch, storage), scoring algorithm, data model, and registry storage. Out of scope: multi-user isolation, CRUD beyond PATCH, versioning, dependencies, auth. |
| **ACCEPTANCE_CRITERIA** | GET /api/ideas returns ranked ideas and summary; GET /api/ideas/{id} and 404; PATCH updates and persists; GET /api/ideas/storage reports backend and counts. All four tests in `api/tests/test_ideas.py` pass. |
| **VERIFICATION_PLAN** | See [Verification](#verification) below: pytest for test pass; curl for live list; explicit pass/fail criteria per check. |

## Purpose

Portfolio-based idea tracking and prioritization using free energy scoring. Enables data-driven decision making by ranking ideas based on potential value, confidence, cost, and resistance risk.

## Requirements

- [x] GET /api/ideas — List ideas ranked by free energy score with portfolio summary
- [x] GET /api/ideas/{id} — Retrieve individual idea with score (404 if not found)
- [x] PATCH /api/ideas/{id} — Update idea validation fields (404 if not found)
- [x] GET /api/ideas/storage — Report structured storage backend and row counts
- [x] Filter support for unvalidated ideas only
- [x] Free energy scoring: (potential_value × confidence) / (estimated_cost + resistance_risk)
- [x] Value gap tracking: potential_value - actual_value
- [x] Manifestation status: none, partial, validated
- [x] Ideas stored in structured DB registry with machine-readable metadata
- [x] Portfolio summary with aggregated metrics


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Portfolio-based idea tracking and prioritization using free energy scoring.
files_allowed:
  - api/app/routers/ideas.py
  - api/app/services/idea_service.py
  - api/app/services/idea_registry_service.py
  - api/app/models/idea.py
  - api/tests/test_ideas.py
  - specs/053-ideas-prioritization.md
done_when:
  - GET /api/ideas — List ideas ranked by free energy score with portfolio summary
  - GET /api/ideas/{id} — Retrieve individual idea with score (404 if not found)
  - PATCH /api/ideas/{id} — Update idea validation fields (404 if not found)
  - GET /api/ideas/storage — Report structured storage backend and row counts
  - Filter support for unvalidated ideas only
commands:
  - | Ideas test suite | `cd api && pytest -q tests/test_ideas.py` | Exit code 0; "passed" in output | Non-zero exit; failures or errors listed |
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `GET /api/ideas`

**Purpose**: List all ideas ranked by free energy score with portfolio summary

**Request**:
- `only_unvalidated`: Boolean (query, default: false) — Filter to exclude validated ideas

**Response 200**:
```json
{
  "ideas": [
    {
      "id": "oss-interface-alignment",
      "name": "Align OSS intelligence interfaces with runtime",
      "description": "Expose and validate declared API routes used by web and scripts.",
      "potential_value": 90.0,
      "actual_value": 10.0,
      "estimated_cost": 18.0,
      "actual_cost": 0.0,
      "resistance_risk": 4.0,
      "confidence": 0.7,
      "manifestation_status": "partial",
      "interfaces": ["machine:api", "human:web", "ai:automation"],
      "open_questions": [
        {
          "question": "Which route set is canonical for current milestone?",
          "value_to_whole": 30.0,
          "estimated_cost": 1.0,
          "answer": null,
          "measured_delta": null
        }
      ],
      "free_energy_score": 2.8636,
      "value_gap": 80.0
    }
  ],
  "summary": {
    "total_ideas": 3,
    "unvalidated_ideas": 2,
    "validated_ideas": 1,
    "total_potential_value": 250.0,
    "total_actual_value": 30.0,
    "total_value_gap": 220.0
  }
}
```

- `ideas`: List sorted by `free_energy_score` descending (highest value first)
- `free_energy_score`: Float — Calculated as (potential_value × confidence) / (estimated_cost + resistance_risk)
- `value_gap`: Float — Calculated as max(potential_value - actual_value, 0.0)
- `summary`: Portfolio-wide aggregated metrics

### `PATCH /api/ideas/{idea_id}`

**Purpose**: Update idea validation fields after implementation or measurement

**Request**:
- `idea_id`: String (path, required) — Unique idea identifier

**Body** (at least one field required):
```json
{
  "actual_value": 34.5,
  "actual_cost": 8.0,
  "confidence": 0.75,
  "manifestation_status": "validated"
}
```

- `actual_value`: Float (optional, ≥ 0.0) — Measured value delivered
- `actual_cost`: Float (optional, ≥ 0.0) — Actual cost incurred
- `confidence`: Float (optional, 0.0–1.0) — Confidence level in estimates
- `manifestation_status`: String (optional) — One of: "none", "partial", "validated"

**Response 200**:
```json
{
  "id": "oss-interface-alignment",
  "name": "Align OSS intelligence interfaces with runtime",
  "description": "Expose and validate declared API routes used by web and scripts.",
  "potential_value": 90.0,
  "actual_value": 34.5,
  "estimated_cost": 18.0,
  "actual_cost": 8.0,
  "resistance_risk": 4.0,
  "confidence": 0.75,
  "manifestation_status": "validated",
  "interfaces": ["machine:api", "human:web", "ai:automation"],
  "open_questions": [],
  "free_energy_score": 3.0682,
  "value_gap": 55.5
}
```

**Response 400**:
```json
{
  "detail": "At least one field required"
}
```

**Response 404**:
```json
{
  "detail": "Idea not found"
}
```

**Response 422**:
```json
{
  "detail": [
    {
      "loc": ["body", "confidence"],
      "msg": "Input should be less than or equal to 1.0",
      "type": "less_than_equal"
    }
  ]
}
```

---

### `GET /api/ideas/storage`

**Purpose**: Expose current idea registry backend and counts for operator and machine inspection

**Response 200**:
```json
{
  "backend": "sqlite",
  "database_url": "sqlite+pysqlite:////.../idea_portfolio.db",
  "idea_count": 12,
  "question_count": 26,
  "bootstrap_source": "legacy_json+derived+standing_question"
}
```


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Scoring Algorithm

### Free Energy Score

Prioritizes ideas with high potential value and confidence, low cost and resistance:

```
free_energy_score = (potential_value × confidence) / (estimated_cost + resistance_risk)
```

- Higher scores indicate better value-to-cost ratio
- Confidence weights potential value (0.0–1.0)
- Denominator minimum 0.0001 to prevent division by zero
- Rounded to 4 decimal places

### Value Gap

Tracks unrealized potential:

```
value_gap = max(potential_value - actual_value, 0.0)
```

- Indicates how much value remains to be captured
- Never negative (capped at 0.0)
- Rounded to 4 decimal places

## Data Model

```yaml
ManifestationStatus: enum
  - none       # Not yet implemented
  - partial    # In progress or partially implemented
  - validated  # Fully implemented and validated

IdeaQuestion:
  question: String (min 1 char)
  value_to_whole: Float (≥ 0.0)
  estimated_cost: Float (≥ 0.0)
  answer: String | null
  measured_delta: Float | null

Idea:
  id: String (min 1 char, unique)
  name: String (min 1 char)
  description: String (min 1 char)
  potential_value: Float (≥ 0.0)
  actual_value: Float (≥ 0.0, default: 0.0)
  estimated_cost: Float (≥ 0.0)
  actual_cost: Float (≥ 0.0, default: 0.0)
  resistance_risk: Float (≥ 0.0, default: 1.0)
  confidence: Float (0.0–1.0, default: 0.5)
  manifestation_status: ManifestationStatus (default: none)
  interfaces: List[String] (default: [])
  open_questions: List[IdeaQuestion] (default: [])

IdeaWithScore: Idea + computed fields
  free_energy_score: Float (≥ 0.0)
  value_gap: Float (≥ 0.0)

IdeaSummary:
  total_ideas: Integer (≥ 0)
  unvalidated_ideas: Integer (≥ 0)
  validated_ideas: Integer (≥ 0)
  total_potential_value: Float (≥ 0.0)
  total_actual_value: Float (≥ 0.0)
  total_value_gap: Float (≥ 0.0)

IdeaPortfolioResponse:
  ideas: List[IdeaWithScore]
  summary: IdeaSummary

IdeaUpdate:
  actual_value: Float | null (≥ 0.0)
  actual_cost: Float | null (≥ 0.0)
  confidence: Float | null (0.0–1.0)
  manifestation_status: ManifestationStatus | null
```

## Storage

- **Primary**: Structured SQL registry tables (`idea_registry_ideas`, `idea_registry_questions`, `idea_registry_meta`)
- **Default backend**: SQLite file derived from `IDEA_PORTFOLIO_PATH` (`.db` suffix)
- **Production backend**: Postgres when `DATABASE_URL` (or `IDEA_REGISTRY_DATABASE_URL`) is configured
- **Bootstrap**: Imports from legacy JSON file if present, otherwise uses defaults
- **Compatibility**: Writes `api/logs/idea_portfolio.json` snapshot for existing tooling

## Files to Create/Modify

- `api/app/routers/ideas.py` — Route handlers (implemented)
- `api/app/services/idea_service.py` — Portfolio service (implemented)
- `api/app/services/idea_registry_service.py` — DB-backed structured persistence (implemented)
- `api/app/models/idea.py` — Pydantic models (implemented)
- `api/tests/test_ideas.py` — Test suite (implemented)
- `specs/053-ideas-prioritization.md` — This spec

## Acceptance Tests

See `api/tests/test_ideas.py`:
- [x] `test_list_ideas_returns_ranked_scores_and_summary` — List endpoint with ranking and summary
- [x] `test_get_idea_by_id_and_404` — Get endpoint with 404 handling
- [x] `test_patch_idea_updates_fields` — Update endpoint with persistence
- [x] `test_ideas_storage_endpoint_reports_structured_backend` — Storage metadata endpoint and DB bootstrap validation

All 4 tests passing.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.


## Verification

Verification plan: executable checks and pass/fail evidence.

| Check | Command | Pass | Fail |
|-------|---------|------|------|
| Ideas test suite | `cd api && pytest -q tests/test_ideas.py` | Exit code 0; "passed" in output | Non-zero exit; failures or errors listed |
| List endpoint (live) | `curl -sS -o /dev/null -w "%{http_code}" http://localhost:8000/api/ideas` | HTTP 200 | Any other status code |
| List with filter | `curl -sS http://localhost:8000/api/ideas?only_unvalidated=true \| head -c 500` | JSON with `ideas` and `summary` keys | Empty or non-JSON response |

Run the following to validate this spec before marking the idea as accepted:

```bash
cd api && pytest -q tests/test_ideas.py
curl -sS http://localhost:8000/api/ideas?only_unvalidated=true | head -c 500
```

Manual acceptance for the **portfolio-governance** idea: set an idea to `manifestation_status: validated` via `PATCH /api/ideas/{id}` only after all acceptance tests pass and the pipeline has run spec → impl → test → review for this idea.

## Out of Scope

- Multi-user portfolio isolation (single shared portfolio)
- Idea creation or deletion via API (manual JSON editing only)
- Idea versioning or history tracking
- Idea dependencies or relationships
- Real-time collaboration or locking
- Idea search or filtering beyond manifestation status
- Authentication or authorization

## Risks and Assumptions

- **Risk:** SQLite default backend may not scale for many concurrent writers; mitigation: use Postgres in production via `DATABASE_URL`.
- **Assumption:** Idea IDs and manifestation status are the single source of truth for "acceptance"; if inventory/flow derives acceptance from elsewhere, keep them in sync.

## Known Gaps and Follow-up Tasks

- None at spec time. Follow-up: extend portfolio-governance to include flow/inventory acceptance evidence (spec process, implementation, validation) when that contract is stable.

## Decision Gates

None — implementation already complete and tested.
