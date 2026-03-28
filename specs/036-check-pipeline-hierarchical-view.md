# Spec: Hierarchical View in check_pipeline (Goal → PM → Tasks → Artifacts)

**Spec ID**: 036
**Status**: Implemented
**Author**: agent/product-manager
**Related Specs**: 007-meta-pipeline-backlog, 026-pipeline-observability-and-auto-review, 032-attention-heuristics-pipeline-status

---

## Summary

Operators need a single command that shows pipeline health in a clear hierarchy: goal progress first, then orchestration (PM), then task execution, then artifact health. The `check_pipeline.py` script is extended with a four-layer hierarchical view so operators can immediately answer "are we on track?" without scrolling through undifferentiated status blocks.

---

## Goal

Replace the flat ad-hoc layout of `check_pipeline.py` human-readable output with a strictly ordered hierarchical view:

```
Goal (Layer 0)               <- Are we making progress toward the system goal?
PM / Orchestration (Layer 1) <- Is the project manager healthy and running?
Tasks (Layer 2)              <- What is running, pending, recently completed?
Artifacts (Layer 3)          <- What did recently-completed tasks produce?
```

The hierarchy is also exposed in `--json` output so scripting consumers get the same structure.

---

## Requirements

- [ ] When run without `--json`, `check_pipeline.py` prints a **hierarchical view** with four labeled sections in this exact order: Goal (Layer 0), PM/Orchestration (Layer 1), Tasks (Layer 2), Artifacts (Layer 3).
- [ ] **Goal section (Layer 0)**: Fetch `GET /api/agent/status-report`; display `layer_0_goal.status`, `goal_proximity`, `throughput`, and `success_rate`. If status-report is unavailable, fall back to `GET /api/agent/effectiveness` for the same fields. If both are unavailable, print `Goal: (report not yet generated)`.
- [ ] **PM / Orchestration section (Layer 1)**: Use `layer_1_orchestration` from status-report when available; otherwise derive from `GET /api/agent/pipeline-status` fields (`project_manager.state`, `backlog_index`, `phase`, `blocked`) plus OS-process detection for `agent_runner` workers and PM `--parallel` flag.
- [ ] **Tasks section (Layer 2)**: Show running tasks (with model, duration, direction), pending tasks (with wait time), and recent completed (with duration). Source: `GET /api/agent/pipeline-status`.
- [ ] **Artifacts section (Layer 3)**: Show recent completed tasks with `output_len` and optional `output_preview` (first ~80 chars) so operators can confirm artifacts were produced.
- [ ] Add `--hierarchical` flag to explicitly select hierarchical view. Default for human-readable output **is** hierarchical (`use_hierarchical = not args.flat`).
- [ ] Add `--flat` flag to preserve legacy output format (sections may appear in any order, no strict layering requirement).
- [ ] With `--json` and hierarchical view active (default or `--hierarchical`): response JSON includes a top-level `"hierarchical"` key containing `layer_0_goal`, `layer_1_orchestration`, `layer_2_execution`, `layer_3_attention` subobjects.
- [ ] With `--json --flat`: response JSON does **not** include `"hierarchical"` key; returns raw pipeline-status JSON only.

---

## API Contract

No new API endpoints. Uses existing read-only APIs:

| Endpoint | Purpose | Fallback |
|---|---|---|
| `GET /api/agent/status-report` | Full hierarchical report written by monitor | Falls back to effectiveness + pipeline-status |
| `GET /api/agent/pipeline-status` | Running/pending/completed tasks, PM state | Required — script fails gracefully if unreachable |
| `GET /api/agent/effectiveness` | goal_proximity, throughput, success_rate | Used when status-report unavailable |

### Response Shape for `--json` (hierarchical, default)

```json
{
  "running": [...],
  "pending": [...],
  "recent_completed": [...],
  "project_manager": {...},
  "hierarchical": {
    "layer_0_goal": {
      "status": "healthy",
      "goal_proximity": 0.72,
      "throughput": 3.1,
      "success_rate": 0.85,
      "summary": "Pipeline operating at steady state"
    },
    "layer_1_orchestration": {
      "status": "running",
      "state": "EXECUTING",
      "backlog_index": 12,
      "workers": 2,
      "parallel": true
    },
    "layer_2_execution": {
      "running_count": 1,
      "pending_count": 2,
      "recent_completed_count": 5
    },
    "layer_3_attention": {
      "flags": [],
      "artifact_count": 5,
      "total_output_bytes": 18340
    }
  }
}
```

---

## Data Model

No database schema changes. The script is a read-only aggregator that:

1. Fetches `status-report`, `pipeline-status`, and optionally `effectiveness` from the running API.
2. Merges responses into a `hierarchical` dict via `_build_hierarchical_from_data()`.
3. Prints (human-readable) or serializes (JSON) the result.

---

## Files to Create / Modify

| File | Change |
|---|---|
| `api/scripts/check_pipeline.py` | Add `--hierarchical` / `--flat` flags; implement four-section hierarchical human-readable output; extend `--json` to include `hierarchical` key; add `_fetch_status_report()`, `_fetch_effectiveness()`, `_build_hierarchical_from_data()` helpers. |
| `api/tests/test_check_pipeline_hierarchical.py` | Pytest suite (mocked HTTP) verifying section order, JSON shape, fallback behavior, and flag interactions. |

---

## Verification Scenarios

These scenarios are concrete and runnable. The reviewer will execute them against the actual script.

### Scenario 1 — Default human-readable output shows all four sections in order

**Setup**: API is reachable at `http://localhost:8000`. `GET /api/agent/pipeline-status` returns at least one running task.

**Action**:
```bash
cd api && python scripts/check_pipeline.py 2>&1
```

**Expected result**:
- Output contains section labels in this order (earlier lines first):
  1. A line matching `Goal` or `Goal (Layer 0)`
  2. A line matching `PM` or `Orchestration` or `Layer 1`
  3. A line matching `Task` or `Running` or `Layer 2`
  4. A line matching `Artifact` or `Layer 3`
- `Goal` section shows either a numeric `goal_proximity` value (e.g. `goal_proximity: 0.72`) or the literal string `report not yet generated`.
- Script exits with code 0.

**Edge case**: If the API is completely unreachable, output contains `[API unreachable]` or `Connection refused` message. Script exits with non-zero code without printing a Python traceback.

---

### Scenario 2 — `--json` output includes `hierarchical` key with four layers

**Setup**: API is reachable.

**Action**:
```bash
cd api && python scripts/check_pipeline.py --json | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'hierarchical' in d, 'missing top-level hierarchical key'
h = d['hierarchical']
for layer in ('layer_0_goal', 'layer_1_orchestration', 'layer_2_execution', 'layer_3_attention'):
    assert layer in h, f'missing {layer}'
print('OK - all four layers present')
"
```

**Expected result**: Prints `OK - all four layers present`. No assertion errors. Exit code 0.

**Edge case**: If `GET /api/agent/status-report` returns 404 (monitor not yet run), `hierarchical` key is still present — built from pipeline-status + effectiveness fallback. `layer_0_goal.summary` will contain `"Report not yet generated by monitor"` or `goal_proximity` from effectiveness.

---

### Scenario 3 — `--flat` flag disables hierarchical key in JSON and uses legacy layout

**Setup**: API is reachable.

**Action (JSON)**:
```bash
cd api && python scripts/check_pipeline.py --json --flat | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert 'hierarchical' not in d, f'hierarchical key should be absent with --flat, got keys: {list(d.keys())}'
print('OK - no hierarchical key with --flat')
"
```

**Expected result**: Prints `OK - no hierarchical key with --flat`.

**Action (human-readable)**:
```bash
cd api && python scripts/check_pipeline.py --flat 2>&1 | head -10
```

**Expected result**: Output does NOT begin with `Goal (Layer 0)`. Uses legacy section headers (e.g. `PIPELINE STATUS`, `PROJECT MANAGER`, `Running Tasks`).

**Edge case**: `--hierarchical` and `--flat` are mutually exclusive. Passing both raises an argparse error or `--flat` takes precedence (per documented behavior).

---

### Scenario 4 — Graceful fallback when `status-report` endpoint is unavailable

**Setup**: `GET /api/agent/status-report` returns HTTP 404. `GET /api/agent/pipeline-status` and `GET /api/agent/effectiveness` return valid data.

**Action**:
```bash
cd api && python scripts/check_pipeline.py 2>&1
```

**Expected result**:
- Script does not crash with a traceback.
- `Goal (Layer 0)` section is present.
- Shows fallback effectiveness data (e.g. `goal_proximity: 0.65`) **or** the literal text `report not yet generated` — one of the two must appear.
- `Tasks (Layer 2)` section is still populated from pipeline-status.
- `Artifacts (Layer 3)` section still lists recent completed tasks.
- Exit code 0 (partial data is not an error condition).

**Edge case**: If `GET /api/agent/pipeline-status` is also unavailable (both endpoints down), script exits with non-zero code and prints a user-facing error message (not a bare Python exception).

---

### Scenario 5 — Full test suite passes without a live API server

**Setup**: No live API server. Tests use `unittest.mock.patch` to mock `httpx` responses.

**Action**:
```bash
cd api && python3 -m pytest tests/test_check_pipeline_hierarchical.py -x -v 2>&1 | tail -25
```

**Expected result**:
```
PASSED tests/test_check_pipeline_hierarchical.py::test_hierarchical_view_default_output_order
PASSED tests/test_check_pipeline_hierarchical.py::test_hierarchical_flag_explicit
PASSED tests/test_check_pipeline_hierarchical.py::test_flat_flag_legacy_output
PASSED tests/test_check_pipeline_hierarchical.py::test_json_output_includes_hierarchical_data
PASSED tests/test_check_pipeline_hierarchical.py::test_json_flat_output_no_hierarchical
PASSED tests/test_check_pipeline_hierarchical.py::test_goal_section_displays_status
PASSED tests/test_check_pipeline_hierarchical.py::test_pm_orchestration_section_displays
PASSED tests/test_check_pipeline_hierarchical.py::test_tasks_section_displays
PASSED tests/test_check_pipeline_hierarchical.py::test_artifacts_section_displays
PASSED tests/test_check_pipeline_hierarchical.py::test_script_handles_api_unreachable
...
X passed, 0 failed, 0 errors
```

Exit code 0. No `FAILED` or `ERROR` lines.

**Edge case**: If `check_pipeline` module cannot be imported (missing dependency), all tests fail with `ImportError`. The spec requires no new third-party dependencies beyond `httpx` and `argparse` (both already present in the project).

---

## Acceptance Tests

- `python scripts/check_pipeline.py` (no flags): output shows four sections in order — Goal, PM/Orchestration, Tasks, Artifacts.
- `python scripts/check_pipeline.py --json`: response includes `"hierarchical"` key with four layer subobjects.
- `python scripts/check_pipeline.py --json --flat`: response does NOT include `"hierarchical"` key.
- `python scripts/check_pipeline.py --flat`: uses legacy flat layout (no `Goal (Layer 0)` header).
- When status-report is missing (API up): Goal section shows fallback from effectiveness or "report not yet generated"; other sections still populated.
- Full test suite: `python3 -m pytest api/tests/test_check_pipeline_hierarchical.py -x -v` — all tests pass.

---

## Out of Scope

- Changing `GET /api/agent/status-report` or `GET /api/agent/pipeline-status` API contracts.
- Modifying `monitor_pipeline.py` (monitor continues to write status-report as-is).
- New API endpoints or files beyond `check_pipeline.py` and its test.
- Authentication / authorization on the existing read-only endpoints.

---

## Risks and Known Gaps

| Risk | Mitigation |
|---|---|
| `status-report` not yet written by monitor (fresh deploy) | Fallback to `effectiveness` + `pipeline-status`; never crash |
| `ps aux` process detection fails on non-Unix hosts (Windows, Docker) | Wrap in `try/except`; return `None` for process counts |
| `--hierarchical` and `--flat` both passed | `argparse` mutual exclusion group or `--flat` takes precedence |
| API timeouts during script execution | `httpx` client uses `timeout=10`; script continues with partial data |
| No auth gate on endpoints | Acceptable for MVP (local/VPS internal network); defer to C1 auth milestone |
| `ps aux` parsing brittle across OS flavors | Return best-effort; log warning on parse failure |

---

## Concurrency Behavior

- **Read operations**: All API calls are GET (read-only); safe for concurrent access — no locking required.
- **No writes**: Script does not mutate any API state.

---

## Failure and Retry Behavior

- Script makes a single attempt per endpoint with `timeout=10s`.
- No retry logic — script is intended for interactive operator use; re-run manually if needed.
- On connection failure: print human-friendly error and exit non-zero.
- On partial API failure (status-report missing, effectiveness missing): continue with available data and note missing sections.

---

## See Also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — item 5.
- [026-pipeline-observability-and-auto-review.md](026-pipeline-observability-and-auto-review.md) — goal status and dashboard.
- [032-attention-heuristics-pipeline-status.md](032-attention-heuristics-pipeline-status.md) — attention flags.
- [docs/PIPELINE-EFFICIENCY-PLAN.md](../docs/PIPELINE-EFFICIENCY-PLAN.md) — §4.3 Hierarchical view, §7 Phase 3.

---

## Verification Command

```bash
python3 -m pytest api/tests/test_check_pipeline_hierarchical.py -x -v
```
