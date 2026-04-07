---
idea_id: pipeline-optimization
status: done
source:
  - file: api/app/services/prompt_ab_roi_service.py
    symbols: [record_prompt_outcome(), select_variant(), get_variant_stats()]
  - file: api/app/services/slot_selection_service.py
    symbols: [SlotSelector]
  - file: api/app/routers/agent_prompt_ab_routes.py
    symbols: [A/B testing endpoints]
requirements:
  - "Outcome recording — persist measurement record per task completion"
  - "ROI computation — sum(value_score)/sum(resource_cost) per variant with stats"
  - "Variant selection — Thompson Sampling with exploration priority for < 5 samples, block after 3 zeros"
  - "Stats endpoint — GET /api/agent/prompt-ab/stats returns per-variant ROI and selection probability"
  - "Integration hook — record_prompt_outcome() callable from task execution flow"
done_when:
  - "record_prompt_outcome writes valid measurement to JSON store"
  - "select_variant returns variant respecting exploration/exploitation rules"
  - "blocked variants (3 consecutive zeros) are never selected"
  - "new variants get exploration priority until 5 samples"
  - "GET /api/agent/prompt-ab/stats returns valid JSON with per-variant ROI"
  - "all tests pass"
test: "cd api && python -m pytest tests/test_prompt_ab_roi.py -q"
constraints:
  - "no database changes (JSON file store only)"
  - "no modifications to existing prompt_templates.json format"
  - "must be callable from existing task execution flow without breaking it"
---

> **Parent idea**: [pipeline-optimization](../ideas/pipeline-optimization.md)
> **Source**: [`api/app/services/prompt_ab_roi_service.py`](../api/app/services/prompt_ab_roi_service.py) | [`api/app/services/slot_selection_service.py`](../api/app/services/slot_selection_service.py) | [`api/app/routers/agent_prompt_ab_routes.py`](../api/app/routers/agent_prompt_ab_routes.py)

# Spec 112: Prompt A/B ROI Measurement

**Idea**: `agent-prompt-ab-roi` (sub-idea of `coherence-network-agent-pipeline`)
**Depends on**: Spec 026 Phase 2 (orchestrator_policy.json)
**Depended on by**: Spec 115 (grounded measurement)
**Cross-idea contribution**: `coherence-signal-depth` (replaces placeholder prompt selection with measured ROI)

## Purpose

Enable data-driven prompt selection by measuring the ROI (value generated per resource consumed) of each prompt variant. The system records per-task outcomes tagged with prompt variant IDs, computes ROI metrics, and selects variants using a Thompson Sampling–inspired policy with exploration guarantees: new prompts get at least 5 measurements unless the first 3 produce zero value, and proven high-ROI variants are favored proportionally to their measured performance.

This closes the spec 026 Phase 2 gap — prompt variant names exist in `orchestrator_policy.json` but no content routing, outcome tracking, or ROI-based selection is implemented.

## Requirements

- [x] **R1: Outcome recording** — When a task completes, persist a measurement record: `{variant_id, task_type, value_score (0.0–1.0), resource_cost (tokens or duration proxy), timestamp}` to `api/logs/prompt_ab_measurements.json`.
- [x] **R2: ROI computation** — ROI per variant = `sum(value_score) / sum(resource_cost)`. Expose per-variant stats: sample count, mean value, mean cost, ROI, and 95% CI when samples >= 5.
- [x] **R3: Variant selection policy** — Given a task type, select a prompt variant using:
  - Variants with < 5 measurements get exploration priority (probability boost).
  - Variants whose first 3 measurements are ALL zero value are blocked from further exploration.
  - Among measured variants, selection probability is proportional to ROI (Thompson Sampling approximation using Beta distribution on normalized value).
- [x] **R4: Stats endpoint** — `GET /api/agent/prompt-ab/stats` returns per-variant ROI, sample count, selection probability, and blocked status.
- [x] **R5: Integration hook** — `record_prompt_outcome(variant_id, task_type, value_score, resource_cost)` callable from task execution flow.

## Research Inputs (Required)

- `2026-03-05` - `orchestrator_policy.json` prompt_variants config — existing variant name infrastructure
- `2026-03-06` - `prompt_templates.json` direction_templates — existing prompt content definitions
- `2026-03-05` - Spec 026 Phase 2 requirements — A/B testing for prompts, skills, models
- `2025-01-15` - Thompson Sampling for A/B testing (Chapelle & Li, 2011) — principled exploration/exploitation balance

## Task Card (Required)

```yaml
goal: Implement prompt A/B ROI measurement with Thompson Sampling selection
files_allowed:
  - api/app/services/prompt_ab_roi_service.py
  - api/app/routers/agent.py
  - api/app/routers/agent_prompt_ab_routes.py
  - api/tests/test_prompt_ab_roi.py
  - api/logs/prompt_ab_measurements.json
  - specs/prompt-ab-roi-measurement.md
done_when:
  - record_prompt_outcome writes valid measurement to JSON store
  - select_variant returns variant respecting exploration/exploitation rules
  - blocked variants (3 consecutive zeros) are never selected
  - new variants get exploration priority until 5 samples
  - GET /api/agent/prompt-ab/stats returns valid JSON with per-variant ROI
  - all tests pass
commands:
  - cd api && python -m pytest tests/test_prompt_ab_roi.py -q
constraints:
  - no database changes (JSON file store only)
  - no modifications to existing prompt_templates.json format
  - must be callable from existing task execution flow without breaking it
```

## API Contract

### `GET /api/agent/prompt-ab/stats`

**Response 200**
```json
{
  "variants": {
    "baseline_v1": {
      "sample_count": 12,
      "mean_value": 0.75,
      "mean_cost": 1.2,
      "roi": 0.625,
      "blocked": false,
      "selection_probability": 0.45
    },
    "spec_structure_v2": {
      "sample_count": 3,
      "mean_value": 0.0,
      "mean_cost": 1.5,
      "roi": 0.0,
      "blocked": true,
      "selection_probability": 0.0
    }
  },
  "total_measurements": 15,
  "active_variants": 4,
  "blocked_variants": 1
}
```

## Data Model

```yaml
PromptMeasurement:
  variant_id: string
  task_type: string
  value_score: float  # 0.0–1.0
  resource_cost: float  # tokens/duration proxy, >0
  timestamp: string  # ISO 8601 UTC

VariantStats:
  sample_count: int
  mean_value: float
  mean_cost: float
  roi: float
  blocked: bool
  selection_probability: float
```

## Files to Create/Modify

- `api/app/services/prompt_ab_roi_service.py` — Core service: recording, ROI computation, variant selection
- `api/app/routers/agent.py` — Wire `GET /api/agent/prompt-ab/stats` endpoint
- `api/tests/test_prompt_ab_roi.py` — Unit tests covering all requirements
- `api/logs/prompt_ab_measurements.json` — Measurement store (created at runtime)

## Acceptance Tests

- `api/tests/test_prompt_ab_roi.py::test_record_and_retrieve_measurement`
- `api/tests/test_prompt_ab_roi.py::test_roi_computation`
- `api/tests/test_prompt_ab_roi.py::test_variant_blocked_after_three_zeros`
- `api/tests/test_prompt_ab_roi.py::test_new_variant_exploration_priority`
- `api/tests/test_prompt_ab_roi.py::test_selection_favors_high_roi`
- `api/tests/test_prompt_ab_roi.py::test_stats_endpoint_shape`

## Verification

```bash
cd api && python -m pytest tests/test_prompt_ab_roi.py -q
python3 scripts/validate_spec_quality.py --file specs/prompt-ab-roi-measurement.md
```

## Out of Scope

- Skill variant A/B testing (spec 026 Phase 2, separate item)
- Model variant A/B testing (spec 026 Phase 2, separate item)
- Persistent database storage (JSON file is sufficient for MVP)
- UI dashboard for A/B stats (future work)

## Risks and Assumptions

- **Risk**: JSON file store may have concurrency issues under parallel task execution. Mitigation: use file locking via `fcntl`.
- **Assumption**: `value_score` can be derived from task outcome (1.0 = pass, 0.0 = fail, partial = intermediate). If scoring is more nuanced, the recording interface supports it.
- **Assumption**: Thompson Sampling approximation via Beta distribution is sufficient; full Bayesian inference is not needed.

## Known Gaps and Follow-up Tasks

- Follow-up: Wire `record_prompt_outcome` into `agent_execution_service.py` task completion flow.
- Follow-up: Add prompt content A/B (different template text per variant ID) once measurement is proven.
- Follow-up: Migrate JSON store to SQLite/PostgreSQL when measurement volume warrants it.

## Failure/Retry Reflection

- Failure mode: JSON file corruption from concurrent writes
- Blind spot: Multiple agents writing simultaneously
- Next action: Add `fcntl.flock` file locking on write operations

## Decision Gates (if any)

- None — this is a self-contained measurement layer with no external dependencies.
