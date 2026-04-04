---
idea_id: pipeline-optimization
status: partial
source:
  - file: api/app/services/task_activity_service.py
    symbols: [task outcome correlation]
---

# Spec 127: Cross-Task Outcome Correlation

**Idea**: `coherence-network-agent-pipeline`
**Depends on**: Spec 115 (grounded measurement), Spec 114 (auto-heal), Spec 113 (error classification)
**Advances open question**: Spec 115 Known Gap #1 — "Downstream value validation: did review pass? did tests pass after impl? Requires cross-task correlation (spec TBD)"

## Purpose

The grounded measurement service (spec 115) scores execution quality per task in isolation — it knows whether a single task succeeded and what it cost, but cannot answer whether the *work product* actually held up downstream. An implementation task that completes successfully is worthless if the follow-up review task rejects it or the test task fails. Without cross-task correlation, the pipeline optimizes for task-level success rate rather than end-to-end value delivery.

This spec adds a lightweight correlation layer that links related tasks into **task chains**, tracks downstream outcomes, and computes a `chain_effectiveness` score. This score feeds back into the grounded measurement service as a validated value signal, replacing the current assumption that task completion equals value.

## Requirements

- [ ] **R1: Task chain linkage** — When a task's `context` contains a `source_task_id` (set by heal tasks, review tasks, test tasks), record a `TaskChainLink` associating the upstream task to the downstream task with a `link_type` (one of: `heal`, `review`, `test`, `continuation`). Store in `api/logs/task_chain_links.json`.
- [ ] **R2: Chain resolution** — `resolve_chain(task_id: str) -> list[TaskChainLink]` returns the full ordered chain of tasks linked from a root task, following `source_task_id` references forward. Max depth 10 (prevent cycles).
- [ ] **R3: Chain effectiveness score** — `compute_chain_effectiveness(chain: list[TaskChainLink]) -> ChainEffectiveness` examines the terminal tasks in a chain and produces:
  - `chain_effectiveness`: 0.0–1.0 composite score
  - `downstream_pass_rate`: fraction of downstream tasks that completed successfully
  - `chain_length`: number of tasks in the chain
  - `terminal_status`: status of the final task in the chain
  - `value_validated`: bool — True only if at least one downstream `review` or `test` task completed successfully
- [ ] **R4: Effectiveness scoring rules** —
  - Root task failed → 0.0 (nothing downstream matters)
  - Root task succeeded, no downstream tasks → 0.5 (unvalidated — better than failure, worse than validated)
  - Root task succeeded, downstream review/test passed → 1.0 × quality_multiplier from spec 115
  - Root task succeeded, downstream review/test failed → 0.2 (work was done but rejected)
  - Root task succeeded, downstream heal was needed and succeeded → 0.6 (recovered, but fragile)
- [ ] **R5: Measurement enrichment** — When a downstream task completes, call `enrich_upstream_measurement(source_task_id)` to update the upstream task's grounded measurement record with `chain_effectiveness` and `value_validated` fields in `raw_signals`.
- [ ] **R6: Chain stats endpoint** — `GET /api/agent/task-chains/stats` returns aggregate chain metrics: `{total_chains, avg_chain_length, avg_effectiveness, validation_rate, by_link_type: {type: {count, pass_rate}}}`.

## Research Inputs (Required)

- `2026-03-18` - Spec 115 `record_grounded_measurement()` — measurement record structure and `raw_signals` schema
- `2026-03-18` - Spec 114 `auto_heal_service.py` — heal tasks set `context.source_task_id` for traceability
- `2026-03-18` - `agent_execution_completion.py` — `complete_success` / `complete_failure` integration points
- `2026-03-18` - Spec 113 `classify_error()` — error categories used in chain analysis
- `2026-03-21` - `agent_service_crud.py` — task creation and context schema

## Task Card (Required)

```yaml
goal: Link related tasks into chains and compute downstream-validated effectiveness scores
files_allowed:
  - api/app/services/task_chain_correlation_service.py
  - api/app/routers/agent_task_chain_routes.py
  - api/app/routers/agent.py
  - api/tests/test_task_chain_correlation.py
  - api/logs/task_chain_links.json
  - specs/127-cross-task-outcome-correlation.md
done_when:
  - TaskChainLink recorded when downstream task has source_task_id in context
  - resolve_chain returns ordered chain with cycle protection (max depth 10)
  - compute_chain_effectiveness returns correct scores per R4 rules
  - enrich_upstream_measurement updates raw_signals with chain_effectiveness
  - GET /api/agent/task-chains/stats returns valid JSON with aggregate metrics
  - all tests pass
commands:
  - cd api && python -m pytest tests/test_task_chain_correlation.py -q
constraints:
  - do not modify grounded_measurement_service.py internals (only call its public API)
  - do not modify agent_execution_completion.py (integration is a follow-up)
  - do not modify existing test files
  - JSON file store only (no database changes)
  - max chain depth capped at 10 to prevent runaway traversal
```

## API Contract

### `GET /api/agent/task-chains/stats`

**Response 200**
```json
{
  "total_chains": 45,
  "avg_chain_length": 2.3,
  "avg_effectiveness": 0.72,
  "validation_rate": 0.58,
  "by_link_type": {
    "heal": {"count": 12, "pass_rate": 0.67},
    "review": {"count": 18, "pass_rate": 0.83},
    "test": {"count": 10, "pass_rate": 0.70},
    "continuation": {"count": 5, "pass_rate": 0.80}
  }
}
```

**Response 200 (empty)**
```json
{
  "total_chains": 0,
  "avg_chain_length": 0.0,
  "avg_effectiveness": 0.0,
  "validation_rate": 0.0,
  "by_link_type": {}
}
```

## Data Model

```yaml
TaskChainLink:
  properties:
    upstream_task_id: { type: string }
    downstream_task_id: { type: string }
    link_type: { type: string, enum: [heal, review, test, continuation] }
    downstream_status: { type: string, enum: [pending, running, completed, failed] }
    created_at: { type: string, format: date-time }

ChainEffectiveness:
  properties:
    root_task_id: { type: string }
    chain_effectiveness: { type: float, minimum: 0.0, maximum: 1.0 }
    downstream_pass_rate: { type: float, minimum: 0.0, maximum: 1.0 }
    chain_length: { type: integer, minimum: 1 }
    terminal_status: { type: string }
    value_validated: { type: boolean }
    links: { type: array, items: TaskChainLink }
```

## Files to Create/Modify

- `api/app/services/task_chain_correlation_service.py` — Chain linkage, resolution, effectiveness scoring, measurement enrichment
- `api/app/routers/agent_task_chain_routes.py` — `GET /api/agent/task-chains/stats`
- `api/app/routers/agent.py` — Include task-chain router
- `api/tests/test_task_chain_correlation.py` — Unit tests for all requirements

## Acceptance Tests

- `api/tests/test_task_chain_correlation.py::test_record_chain_link`
- `api/tests/test_task_chain_correlation.py::test_resolve_chain_ordered`
- `api/tests/test_task_chain_correlation.py::test_resolve_chain_cycle_protection`
- `api/tests/test_task_chain_correlation.py::test_effectiveness_root_failed`
- `api/tests/test_task_chain_correlation.py::test_effectiveness_unvalidated`
- `api/tests/test_task_chain_correlation.py::test_effectiveness_review_passed`
- `api/tests/test_task_chain_correlation.py::test_effectiveness_review_failed`
- `api/tests/test_task_chain_correlation.py::test_effectiveness_heal_succeeded`
- `api/tests/test_task_chain_correlation.py::test_enrich_upstream_measurement`
- `api/tests/test_task_chain_correlation.py::test_chain_stats_shape`
- `api/tests/test_task_chain_correlation.py::test_chain_stats_empty`

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: JSON file store uses `fcntl.flock` for write safety (same pattern as spec 112).
- **Enrichment**: Last-write-wins for `raw_signals` updates; acceptable because enrichment is append-only (adds fields, never removes).

## Verification

```bash
cd api && python -m pytest tests/test_task_chain_correlation.py -q
python3 scripts/validate_spec_quality.py --file specs/127-cross-task-outcome-correlation.md
```

## Out of Scope

- Wiring `record_chain_link` into `complete_success`/`complete_failure` (follow-up integration task)
- UI visualization of task chains
- Cross-chain analysis (comparing effectiveness across different prompt variants)
- Automatic re-weighting of grounded measurement formula based on chain data
- Chain-aware variant selection in the A/B system

## Risks and Assumptions

- **Risk**: Chain resolution may be slow for deeply linked tasks. Mitigation: max depth 10 cap, and chains are typically 2-3 tasks deep.
- **Risk**: `source_task_id` is not consistently set across all task types today. Mitigation: only record links when the field is present; stats reflect actual correlation coverage via `validation_rate`.
- **Assumption**: Heal tasks (spec 114) and future review/test tasks will set `source_task_id` in their context. This is already the pattern for heal tasks.
- **Assumption**: JSON file store is sufficient for chain link volume (same assumption as spec 112 for measurements).

## Known Gaps and Follow-up Tasks

- Follow-up: Wire `record_chain_link` into `agent_execution_completion.py` `complete_success`/`complete_failure` when `context.source_task_id` is present.
- Follow-up: Feed `chain_effectiveness` back into Thompson Sampling variant selection (spec 112) as a stronger value signal than single-task outcome.
- Follow-up: Add `review` and `test` as standard task types with automatic `source_task_id` linking in the orchestrator.
- Follow-up: Calibrate R4 scoring rules from real chain outcome data once sufficient volume exists.

## Failure/Retry Reflection

- Failure mode: Chain link recorded but upstream measurement not found (task completed before measurement service existed)
- Blind spot: Assuming all upstream tasks have grounded measurements; older tasks may not
- Next action: `enrich_upstream_measurement` should no-op gracefully when upstream measurement is missing, logging a warning

## Decision Gates (if any)

- **Scoring weights in R4**: The 0.5 (unvalidated) and 0.2 (rejected) thresholds are initial estimates. Review after 50+ chains have real data; adjust if the distribution is too flat or too bimodal.
