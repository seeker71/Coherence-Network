# Spec: Ideas Prioritization API

## Purpose

Portfolio-based idea tracking and prioritization using free energy scoring. Enables data-driven decision making by ranking ideas based on potential value, confidence, cost, and resistance risk.

## Requirements

- [x] GET /api/ideas — List ideas ranked by free energy score with portfolio summary
- [x] GET /api/ideas/{id} — Retrieve individual idea with score (404 if not found)
- [x] PATCH /api/ideas/{id} — Update idea validation fields (404 if not found)
- [x] Filter support for unvalidated ideas only
- [x] Free energy scoring: (potential_value × confidence) / (estimated_cost + resistance_risk)
- [x] Value gap tracking: potential_value - actual_value
- [x] Manifestation status: none, partial, validated
- [x] Ideas stored in JSON file (api/logs/idea_portfolio.json)
- [x] Portfolio summary with aggregated metrics

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

---

### `GET /api/ideas/{idea_id}`

**Purpose**: Retrieve a specific idea by ID with score

**Request**:
- `idea_id`: String (path, required) — Unique idea identifier

**Response 200**:
```json
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
  "open_questions": [],
  "free_energy_score": 2.8636,
  "value_gap": 80.0
}
```

**Response 404**:
```json
{
  "detail": "Idea not found"
}
```

---

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

- **Location**: `api/logs/idea_portfolio.json`
- **Format**: JSON with `{"ideas": [...]}` structure
- **Initialization**: Auto-creates with default ideas if file missing
- **Environment**: Path configurable via `IDEA_PORTFOLIO_PATH` env var

## Files

- `api/app/routers/ideas.py` — Route handlers (implemented)
- `api/app/services/idea_service.py` — Portfolio service (implemented)
- `api/app/models/idea.py` — Pydantic models (implemented)
- `api/tests/test_ideas.py` — Test suite (implemented)
- `specs/053-ideas-prioritization.md` — This spec

## Acceptance Tests

See `api/tests/test_ideas.py`:
- [x] `test_list_ideas_returns_ranked_scores_and_summary` — List endpoint with ranking and summary
- [x] `test_get_idea_by_id_and_404` — Get endpoint with 404 handling
- [x] `test_patch_idea_updates_fields` — Update endpoint with persistence

All 3 tests passing.

## Out of Scope

- Multi-user portfolio isolation (single shared portfolio)
- Idea creation or deletion via API (manual JSON editing only)
- Idea versioning or history tracking
- Idea dependencies or relationships
- Real-time collaboration or locking
- Idea search or filtering beyond manifestation status
- Authentication or authorization

## Decision Gates

None — implementation already complete and tested.
