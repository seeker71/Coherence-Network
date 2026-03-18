# Spec: Auto-Heal from Diagnostics

## Purpose

Automatically generate targeted heal tasks when a task fails, using the error category from `classify_error` (spec 113) to select a heal strategy. This closes the failure→recovery loop: instead of failures sitting inert until a human triages them, each failure immediately produces a scoped heal task with the right executor and direction. Baseline: 0% of failures auto-healed. Target: >40% of failures produce a heal task that resolves the root cause.

## Requirements

- [x] **R1: Heal strategy map** — Define a mapping from each error category to a heal strategy: `{category: {direction_template, executor_hint, max_retries, cooldown_seconds}}`. Categories: `timeout` → retry with extended window, `executor_crash` → retry on different executor, `provider_error` → route to fallback provider, `validation_failure` → fix validation with spec context, `unknown` → escalate with diagnostic dump.
- [x] **R2: Auto-heal trigger** — `maybe_create_heal_task(failed_task: dict) -> dict | None` inspects a failed task, classifies its error, checks cooldown/retry limits, and creates a heal task via `AgentTaskCreate(task_type=TaskType.HEAL)` if eligible. Returns the heal task dict or None if suppressed.
- [x] **R3: Cooldown & retry guard** — Do not create a heal task if: (a) the failed task already has a heal task (check `context.heal_task_id`), (b) the original task has been retried >= `max_retries` times (check `context.retry_count`), or (c) a heal task for the same error category was created within `cooldown_seconds`.
- [x] **R4: Heal task context** — Created heal tasks include in `context`: `{source_task_id, error_category, error_summary, retry_count, strategy_name}` for traceability.
- [x] **R5: Auto-heal stats endpoint** — `GET /api/agent/auto-heal/stats` returns `{total_failed, heals_created, heal_rate, by_category: {category: {failed, healed, suppressed}}}`.

## Research Inputs (Required)

- `2026-03-18` - Spec 113 `classify_error()` — provides error_category for routing
- `2026-03-18` - `agent_service_crud.py` `create_task()` — task creation interface
- `2026-03-18` - `runner_orphan_recovery_service.py` — existing recovery pattern (context tagging, status transitions)
- `2026-03-18` - `agent_service_executor.py` — HEAL task type routing (`dev-engineer` agent, `_COMMAND_HEAL` template)
- `2026-03-18` - Spec 007 meta-pipeline backlog item 19 — requirement source

## Task Card (Required)

```yaml
goal: Auto-generate heal tasks from failed task error classifications
files_allowed:
  - api/app/services/auto_heal_service.py
  - api/app/routers/agent_auto_heal_routes.py
  - api/app/routers/agent.py
  - api/tests/test_auto_heal_service.py
  - specs/114-auto-heal-from-diagnostics.md
done_when:
  - HEAL_STRATEGIES maps all 5 error categories to strategies
  - maybe_create_heal_task returns heal task dict for eligible failures
  - cooldown guard prevents duplicate heals within window
  - retry guard prevents infinite heal loops
  - heal task context includes source_task_id, error_category, retry_count
  - GET /api/agent/auto-heal/stats returns correct shape
  - all tests pass
commands:
  - cd api && python -m pytest tests/test_auto_heal_service.py -q
constraints:
  - do not modify agent_service_crud.py or existing task creation logic
  - do not modify existing test files
  - heal tasks must use TaskType.HEAL
  - max_retries per category capped at 3
```

## API Contract

### `GET /api/agent/auto-heal/stats`

**Response 200**
```json
{
  "total_failed": 20,
  "heals_created": 12,
  "heal_rate": 0.6,
  "by_category": {
    "timeout": {"failed": 5, "healed": 4, "suppressed": 1},
    "executor_crash": {"failed": 8, "healed": 5, "suppressed": 3},
    "provider_error": {"failed": 3, "healed": 2, "suppressed": 1},
    "validation_failure": {"failed": 2, "healed": 1, "suppressed": 1},
    "unknown": {"failed": 2, "healed": 0, "suppressed": 2}
  }
}
```

## Data Model

```yaml
HealStrategy:
  direction_template: str    # Prompt template with {error_summary}, {source_task_id} placeholders
  executor_hint: str | None  # Preferred executor override, or None for default routing
  max_retries: int           # Max heal attempts per source task (1-3)
  cooldown_seconds: int      # Min seconds between heals for same error category

AutoHealRecord:
  source_task_id: str
  heal_task_id: str
  error_category: str
  strategy_name: str
  created_at: str            # ISO 8601 UTC
```

## Files to Create/Modify

- `api/app/services/auto_heal_service.py` — Strategy map, trigger logic, cooldown, stats
- `api/app/routers/agent_auto_heal_routes.py` — `GET /api/agent/auto-heal/stats`
- `api/app/routers/agent.py` — Include auto-heal router
- `api/tests/test_auto_heal_service.py` — Unit tests

## Acceptance Tests

- `api/tests/test_auto_heal_service.py::test_heal_strategies_cover_all_categories`
- `api/tests/test_auto_heal_service.py::test_maybe_create_heal_task_eligible`
- `api/tests/test_auto_heal_service.py::test_maybe_create_heal_task_cooldown_suppressed`
- `api/tests/test_auto_heal_service.py::test_maybe_create_heal_task_retry_limit`
- `api/tests/test_auto_heal_service.py::test_maybe_create_heal_task_already_healed`
- `api/tests/test_auto_heal_service.py::test_heal_task_context_fields`
- `api/tests/test_auto_heal_service.py::test_auto_heal_stats_shape`

## Verification

```bash
cd api && python -m pytest tests/test_auto_heal_service.py -q
python3 scripts/validate_spec_quality.py --file specs/114-auto-heal-from-diagnostics.md
```

## Out of Scope

- Actually wiring into the PATCH status=failed handler (follow-up integration)
- Monitoring heal task outcomes and attributing resolution
- Adaptive strategy tuning based on heal success rates
- UI for auto-heal dashboard

## Risks and Assumptions

- **Risk**: Heal loops — a heal task could itself fail, triggering another heal. Mitigation: retry_count tracking + max_retries cap at 3.
- **Assumption**: `classify_error` categories are stable enough for strategy mapping. If categories change, strategies must be updated.
- **Assumption**: Creating a heal task via `AgentTaskCreate` is safe to call from a service without side effects beyond task creation.

## Known Gaps and Follow-up Tasks

- Follow-up: Wire `maybe_create_heal_task` into PATCH `/api/agent/tasks/{id}` when status transitions to `failed`.
- Follow-up: Track heal task outcomes and compute `heal_success_rate` per category.
- Follow-up: Adaptive cooldown — increase cooldown when heals repeatedly fail for same category.

## Failure/Retry Reflection

- Failure mode: Heal task created but never executed (no runner picks it up)
- Blind spot: Assuming heal tasks run promptly; may need TTL or expiry
- Next action: Add `observation_window_sec` to heal tasks so stale ones can be detected

## Decision Gates (if any)

- None — uses existing task creation API with no schema changes.
