---
idea_id: pipeline-reliability
status: done
source:
  - file: api/app/services/failed_task_diagnostics_service.py
    symbols: [classify_error(), ensure_diagnostics()]
  - file: api/app/models/agent.py
    symbols: [error_summary, error_category fields]
  - file: api/app/services/agent_task_store_service.py
    symbols: [AgentTaskRecord.error_summary column]
requirements:
  - "Error fields on model: Add `error_summary: Optional[str]` and `error_category: Optional[str]` to `AgentTask`, `AgentTaskListItem`, `AgentTaskUp"
  - "Require diagnostics on failure: When a task transitions to `status=failed` via PATCH, require at least one of `error_summary` or `output` to be non-empt"
  - "Diagnostics service: `classify_error(output: str | None) -> tuple[str, str]` returns `(error_summary, error_category)` by pattern-matching th"
  - "Auto-classify on PATCH: When PATCH sets `status=failed` and `error_summary` is not provided, call `classify_error(output)` to auto-populate both"
  - "Diagnostics completeness endpoint: `GET /api/agent/diagnostics-completeness` returns `{\"total_failed\": N, \"with_diagnostics\": M, \"missing_pct\": float, \"by_"
done_when:
  - "AgentTask model has error_summary and error_category fields"
  - "AgentTaskRecord DB model has error_summary and error_category columns"
  - "PATCH to status=failed auto-populates error_summary when not provided"
  - "classify_error correctly categorizes timeout, crash, provider, validation patterns"
  - "GET /api/agent/diagnostics-completeness returns correct shape"
  - "all tests pass"
test: "cd api && python -m pytest tests/test_failed_task_diagnostics.py -q"
constraints:
  - "no changes to existing test files"
  - "backward compatible: existing tasks with null error fields remain valid"
  - "error_category must be one of the 5 defined categories"
---

> **Parent idea**: [pipeline-reliability](../ideas/pipeline-reliability.md)
> **Source**: [`api/app/services/failed_task_diagnostics_service.py`](../api/app/services/failed_task_diagnostics_service.py) | [`api/app/models/agent.py`](../api/app/models/agent.py) | [`api/app/services/agent_task_store_service.py`](../api/app/services/agent_task_store_service.py)

# Spec 113: Failed-Task Diagnostics Completeness Contract

**Idea**: `agent-failed-task-diagnostics` (sub-idea of `coherence-network-agent-pipeline`)
**Depends on**: Spec 007 meta-pipeline backlog (item 14)
**Depended on by**: Spec 114 (auto-heal uses classify_error)
**Cross-idea contribution**: `coherence-signal-depth` (replaces null error fields with classified diagnostics)

## Purpose

Require every failed agent task to persist a non-empty error summary and error category so that failures are immediately debuggable without manually inspecting logs. Baseline (2026-02-19): 16/16 failed tasks had null `error` and null `output`. Target: <5% of failed tasks missing diagnostics. This unblocks downstream heal-task generation, monitor condition classification, and paid-provider mitigation policies.

## Requirements

- [x] **R1: Error fields on model** — Add `error_summary: Optional[str]` and `error_category: Optional[str]` to `AgentTask`, `AgentTaskListItem`, `AgentTaskUpdate`, and `AgentTaskRecord` (DB column). Categories: `executor_crash`, `timeout`, `validation_failure`, `provider_error`, `unknown`.
- [x] **R2: Require diagnostics on failure** — When a task transitions to `status=failed` via PATCH, require at least one of `error_summary` or `output` to be non-empty. If both are null/empty, auto-populate `error_summary` with `"No diagnostics provided"` and `error_category` with `"unknown"`.
- [x] **R3: Diagnostics service** — `classify_error(output: str | None) -> tuple[str, str]` returns `(error_summary, error_category)` by pattern-matching the output text. Patterns: timeout keywords → `timeout`, exit code / crash / traceback → `executor_crash`, rate limit / billing / 429 → `provider_error`, assertion / validation → `validation_failure`, else → `unknown`.
- [x] **R4: Auto-classify on PATCH** — When PATCH sets `status=failed` and `error_summary` is not provided, call `classify_error(output)` to auto-populate both fields.
- [x] **R5: Diagnostics completeness endpoint** — `GET /api/agent/diagnostics-completeness` returns `{"total_failed": N, "with_diagnostics": M, "missing_pct": float, "by_category": {"timeout": 2, ...}}`.

## Research Inputs (Required)

- `2026-02-19` - Pipeline improvement snapshot (`docs/system_audit/pipeline_improvement_snapshot_2026-02-19.json`) — baseline: 16/16 failed tasks have null error/output
- `2026-03-05` - `api/app/models/agent.py` AgentTask/AgentTaskUpdate — existing model fields
- `2026-03-05` - `api/app/services/agent_task_store_service.py` AgentTaskRecord — DB schema
- `2026-03-18` - Spec 007 meta-pipeline backlog item 14 — requirement source

## Task Card (Required)

```yaml
goal: Ensure every failed task has non-empty error diagnostics with auto-classification
files_allowed:
  - api/app/models/agent.py
  - api/app/services/agent_task_store_service.py
  - api/app/services/failed_task_diagnostics_service.py
  - api/app/routers/agent_diagnostics_routes.py
  - api/app/routers/agent.py
  - api/tests/test_failed_task_diagnostics.py
  - specs/113-failed-task-diagnostics-contract.md
done_when:
  - AgentTask model has error_summary and error_category fields
  - AgentTaskRecord DB model has error_summary and error_category columns
  - PATCH to status=failed auto-populates error_summary when not provided
  - classify_error correctly categorizes timeout, crash, provider, validation patterns
  - GET /api/agent/diagnostics-completeness returns correct shape
  - all tests pass
commands:
  - cd api && python -m pytest tests/test_failed_task_diagnostics.py -q
constraints:
  - no changes to existing test files
  - backward compatible: existing tasks with null error fields remain valid
  - error_category must be one of the 5 defined categories
```

## API Contract

### `PATCH /api/agent/tasks/{task_id}` (modified behavior)

When `status` is set to `failed`:
- If `error_summary` is not provided, auto-classify from `output` field
- If both `error_summary` and `output` are null/empty, set `error_summary` to `"No diagnostics provided"` and `error_category` to `"unknown"`

### `GET /api/agent/diagnostics-completeness`

**Response 200**
```json
{
  "total_failed": 16,
  "with_diagnostics": 14,
  "missing_pct": 12.5,
  "by_category": {
    "timeout": 3,
    "executor_crash": 5,
    "provider_error": 4,
    "validation_failure": 2,
    "unknown": 2
  }
}
```

## Data Model

```yaml
# New fields on AgentTask / AgentTaskRecord
error_summary: Optional[str]    # Human-readable error description (max 500 chars)
error_category: Optional[str]   # One of: executor_crash, timeout, validation_failure, provider_error, unknown
```

## Files to Create/Modify

- `api/app/models/agent.py` — Add `error_summary` and `error_category` to `AgentTask`, `AgentTaskListItem`, `AgentTaskUpdate`
- `api/app/services/agent_task_store_service.py` — Add columns to `AgentTaskRecord`
- `api/app/services/failed_task_diagnostics_service.py` — `classify_error()` and `compute_diagnostics_completeness()`
- `api/app/routers/agent_diagnostics_routes.py` — `GET /api/agent/diagnostics-completeness`
- `api/app/routers/agent.py` — Include diagnostics router
- `api/tests/test_failed_task_diagnostics.py` — Unit tests

## Acceptance Tests

- `api/tests/test_failed_task_diagnostics.py::test_classify_error_timeout`
- `api/tests/test_failed_task_diagnostics.py::test_classify_error_crash`
- `api/tests/test_failed_task_diagnostics.py::test_classify_error_provider`
- `api/tests/test_failed_task_diagnostics.py::test_classify_error_validation`
- `api/tests/test_failed_task_diagnostics.py::test_classify_error_unknown`
- `api/tests/test_failed_task_diagnostics.py::test_auto_populate_on_missing_diagnostics`
- `api/tests/test_failed_task_diagnostics.py::test_diagnostics_completeness_shape`
- `api/tests/test_failed_task_diagnostics.py::test_model_fields_present`

## Verification

```bash
cd api && python -m pytest tests/test_failed_task_diagnostics.py -q
python3 scripts/validate_spec_quality.py --file specs/113-failed-task-diagnostics-contract.md
```

## Out of Scope

- Modifying existing PATCH endpoint logic (integration wiring is a follow-up)
- Backfilling historical failed tasks with error classifications
- UI for diagnostics dashboard
- Alert/notification on failure patterns

## Risks and Assumptions

- **Risk**: Adding columns to AgentTaskRecord requires DB migration for PostgreSQL deployments. Mitigation: columns are nullable, so existing rows remain valid.
- **Assumption**: The `output` field contains enough signal for pattern-based classification. If output is always null (current baseline), auto-classify falls back to `unknown` with `"No diagnostics provided"`.
- **Assumption**: 5 error categories are sufficient for initial classification. Can be extended later.

## Known Gaps and Follow-up Tasks

- Follow-up: Wire `classify_error` into the actual PATCH `/api/agent/tasks/{id}` handler when status transitions to `failed`.
- Follow-up: Backfill existing failed tasks by re-reading task logs and classifying.
- Follow-up: Add monitor rule that alerts when `missing_pct > 5%`.

## Failure/Retry Reflection

- Failure mode: Pattern matching misclassifies errors (e.g. "timeout" in a variable name)
- Blind spot: Patterns too broad or too narrow for real-world output
- Next action: Add test cases from actual failed task outputs once available

## Decision Gates (if any)

- None — nullable columns are backward compatible and classification is non-destructive.
