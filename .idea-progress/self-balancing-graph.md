# Idea progress — self-balancing-graph

## Current task
- **Task ID**: task_6fc7d0ee3406bd17
- **Status**: Added `api/tests/test_self_balancing_graph.py` (5 tests) for spec 172 acceptance: graph health snapshot contract, empty graph, single-component orphan semantics, advisory-only invariant, dangling-edge resilience.

## Completed phases
### Self-balancing graph tests (task_6fc7d0ee3406bd17)
- New file only: `api/tests/test_self_balancing_graph.py` (no edits to existing tests/modules).

### Prior (task_1fa07d03691fd410)
- Earlier note referenced `test_self_balancing_graph.py`; this task delivers that file with full coverage.

## Key decisions
- Mirror `test_172_graph_health.py` patterns: minimal FastAPI app with `graph_health` router, `graph_health_repo.reset_for_tests()`, reset `_last_compute_time`.
- Edge cases chosen to match spec 172: empty baseline, no false orphan signals on one component, no mutation of `concept_service` lists, ignore invalid edge endpoints without 500.

## Blockers
- Automated pytest/DIF/git not run in agent shell (allowlist). Runner should execute verify steps and commit.
