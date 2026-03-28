# Spec: Hierarchical view in check_pipeline (goal → PM → tasks → artifacts)

## Summary

Operators need a single command that shows pipeline health in a clear hierarchy: goal progress first, then orchestration (PM), then task execution, then artifact health. This makes it easy to see "are we on track?" before drilling into running/pending tasks and recent outputs.

The feature adds a structured four-layer view to `api/scripts/check_pipeline.py`, controlled via `--hierarchical` (default) and `--flat` flags. When run without `--json`, output is sectioned as:

```
Pipeline Status (hierarchical)
============================================================
Goal (Layer 0)
  status: ok
  goal_proximity=0.78, 12 tasks (7d), 91% success
  ...

PM / Orchestration (Layer 1)
  item 5, phase=impl; agent_runner workers=5 (ok); PM parallel=true (ok)
  PROJECT MANAGER: item 5, phase=impl

Tasks (Layer 2)
  RUNNING: abc123 (impl) | model: claude-sonnet-4-6 | duration: 1m 23s
  PENDING: 3 tasks
  RECENT COMPLETED: 5

Artifacts (Layer 3)
  • abc120 | output: 4200 chars | preview: Implemented feature X...
```

---

## Requirements

- [ ] When run without `--json`, `check_pipeline.py` prints a **hierarchical view**: Goal → PM/Orchestration → Tasks → Artifacts (in that order).
- [ ] **Goal** section (Layer 0): Use `GET /api/agent/status-report` when available; show `layer_0_goal.status` and `layer_0_goal.summary` (e.g. goal_proximity, throughput, success rate). If status-report is missing or not yet generated, fall back to `GET /api/agent/effectiveness` and show `goal_proximity` and a one-line summary. If both unavailable, print `(report not yet generated)`.
- [ ] **PM / Orchestration** section (Layer 1): Show `layer_1_orchestration` from status-report when available; otherwise derive from `GET /api/agent/pipeline-status` (project_manager state: backlog_index, phase, blocked) and process detection (agent_runner workers, PM --parallel). Label as "Layer 1".
- [ ] **Tasks** section (Layer 2): Running task (id, task_type, model, duration), pending count with wait times for first 8, recent completed count and brief list with duration. Label as "Layer 2".
- [ ] **Artifacts** section (Layer 3): Recent completed tasks listed with `output_len` (chars) and optional one-line `output_preview`. Label as "Layer 3".
- [ ] `--hierarchical` flag explicitly selects hierarchical view; human-readable default is hierarchical.
- [ ] `--flat` flag preserves legacy flat output (sections not strictly layered; backward-compatible).
- [ ] With `--json`, when hierarchical view is requested (default or `--hierarchical`), the JSON includes a top-level `"hierarchical"` key containing `layer_0_goal`, `layer_1_orchestration`, `layer_2_execution`, `layer_3_attention`. When status-report is available, those fields come from it; otherwise built from pipeline-status + effectiveness.

---

## API Contract

No new API endpoints. Uses existing read-only endpoints:

| Endpoint | Purpose | Fallback |
|---|---|---|
| `GET /api/agent/status-report` | Full hierarchical report (layers 0–3) | Falls back to next row |
| `GET /api/agent/pipeline-status` | Running/pending/completed tasks, PM state | Required (no further fallback) |
| `GET /api/agent/effectiveness` | goal_proximity, throughput, success_rate | Used when status-report missing |

All endpoints return JSON. All are read-only (GET). No mutations needed.

---

## Data Model

Script aggregates existing API responses and prints (or emits JSON) in hierarchical order. No new database schema.

**Output JSON shape (with `--json` and hierarchical mode)**:

```json
{
  "running": [...],
  "pending": [...],
  "recent_completed": [...],
  "project_manager": {...},
  "hierarchical": {
    "layer_0_goal": {
      "status": "ok",
      "goal_proximity": 0.78,
      "summary": "goal_proximity=0.78, 12 tasks (7d), 91% success"
    },
    "layer_1_orchestration": {
      "status": "ok",
      "summary": "item 5, phase=impl; workers=5; parallel=true"
    },
    "layer_2_execution": {
      "running": 1,
      "pending": 3,
      "recent_completed": 5
    },
    "layer_3_attention": {
      "flags": []
    }
  }
}
```

---

## Files to Create/Modify

- `api/scripts/check_pipeline.py` — add `--hierarchical` / `--flat` argument; fetch status-report and effectiveness; build and print four-layer hierarchy; extend `--json` output to include `hierarchical` key.

No other files. No migrations. No new API routes.

---

## Acceptance Tests

- Run `python scripts/check_pipeline.py` (no flags): output begins with `Pipeline Status (hierarchical)`, contains sections `Goal (Layer 0)`, `PM / Orchestration (Layer 1)`, `Tasks (Layer 2)`, `Artifacts (Layer 3)` in that order.
- Run with `--json`: JSON response includes top-level key `"hierarchical"` containing `layer_0_goal`, `layer_1_orchestration`, `layer_2_execution`, `layer_3_attention`.
- Run with `--flat`: output begins with `Pipeline Status` (no "hierarchical" in header), shows sections in legacy format (RUNNING, PENDING, RECENT COMPLETED, PROJECT MANAGER, PROCESSES).
- Run with `--hierarchical` explicitly: same output as default (no `--flat`).
- When API is down or status-report not yet generated: Goal section shows `(report not yet generated)` or effectiveness-derived fallback; script exits cleanly (exit 0 or 1 only, no unhandled exception).

---

## Verification Scenarios

### Scenario 1: Default hierarchical output structure

**Setup**: API is running (`GET /api/agent/pipeline-status` responds 200). Status-report may or may not be available.

**Action**:
```bash
cd api && .venv/bin/python scripts/check_pipeline.py
```

**Expected result**:
- Exit code 0
- stdout contains the string `Pipeline Status (hierarchical)`
- stdout contains `Goal (Layer 0)` before `PM / Orchestration (Layer 1)`
- stdout contains `PM / Orchestration (Layer 1)` before `Tasks (Layer 2)`
- stdout contains `Tasks (Layer 2)` before `Artifacts (Layer 3)`
- All four section headers appear exactly once

**Edge case**: If `GET /api/agent/status-report` returns 404, the Goal section shows either effectiveness-based fallback or `(report not yet generated)` — it does NOT crash or print a Python traceback.

---

### Scenario 2: `--flat` flag produces legacy output

**Setup**: API is running.

**Action**:
```bash
cd api && .venv/bin/python scripts/check_pipeline.py --flat
```

**Expected result**:
- Exit code 0
- stdout starts with `Pipeline Status` (NOT `Pipeline Status (hierarchical)`)
- stdout does NOT contain `Goal (Layer 0)`, `Tasks (Layer 2)`, or `Artifacts (Layer 3)`
- stdout contains legacy sections `RUNNING:`, `PENDING:`, `RECENT COMPLETED:`

**Edge case**: Running with both `--flat` and `--hierarchical` at once should fail with an argparse error (mutually exclusive group) or clearly print an error and exit non-zero.

---

### Scenario 3: `--json` output includes `hierarchical` key

**Setup**: API is running.

**Action**:
```bash
cd api && .venv/bin/python scripts/check_pipeline.py --json
```

**Expected result**:
- Exit code 0
- Output is valid JSON (parseable with `python3 -c "import sys,json; json.load(sys.stdin)"`)
- The JSON object contains a top-level key `"hierarchical"`
- `hierarchical["layer_0_goal"]` is an object with at least the keys `"status"` and `"summary"`
- `hierarchical["layer_1_orchestration"]` is present
- `hierarchical["layer_2_execution"]` is present
- `hierarchical["layer_3_attention"]` is present

**Edge case**: If `GET /api/agent/effectiveness` returns 500, the `layer_0_goal` key is still present in JSON output, with a degraded summary (e.g. `"status": "unknown"` or `"summary": "report not yet generated"`) — not absent or null.

---

### Scenario 4: `--json --flat` produces JSON WITHOUT `hierarchical` key

**Setup**: API is running.

**Action**:
```bash
cd api && .venv/bin/python scripts/check_pipeline.py --json --flat
```

**Expected result**:
- Exit code 0
- Output is valid JSON
- The JSON object does NOT contain `"hierarchical"` as a top-level key (legacy flat JSON output)
- Keys present: `"running"`, `"pending"`, `"recent_completed"` (standard pipeline-status fields)

**Edge case**: Consumers relying on flat JSON (CI scripts, monitors) continue to work without modification when `--flat` is passed.

---

### Scenario 5: Graceful degradation when API is unreachable

**Setup**: API is NOT running (or `AGENT_API_BASE` points to a non-responding host).

**Action**:
```bash
cd api && AGENT_API_BASE=http://localhost:19999 .venv/bin/python scripts/check_pipeline.py
```

**Expected result**:
- Script exits with a non-zero exit code OR prints an error message indicating the API is not reachable
- No unhandled Python exception / traceback in stdout (stderr stacktrace acceptable if handled cleanly)
- Script does not hang indefinitely (timeouts are applied to HTTP requests, default ≤ 10 seconds)

**Edge case**: With `--json` and unreachable API, output may be empty or a JSON error object, but the script must not hang.

---

## Out of Scope

- Changing `GET /api/agent/status-report` or `GET /api/agent/pipeline-status` response contracts.
- Modifying `monitor_pipeline.py` (monitor continues to write status-report independently).
- New API endpoints or files beyond `api/scripts/check_pipeline.py`.
- Authentication or authorization changes.

---

## Risks and Assumptions

- **status-report availability**: The feature degrades gracefully when `GET /api/agent/status-report` is absent. Effectiveness fallback provides minimal Layer 0 data. This is an assumption — confirmed in implementation review.
- **No auth gate**: Script endpoints are unprotected in current deployment; acceptable for internal tooling.
- **Output contract**: The `--flat` mode preserves existing output format exactly to avoid breaking downstream CI/bash consumers.
- **Existing tests**: Any tests referencing `Pipeline Status\n` (without "hierarchical") must pass `--flat` to preserve coverage.

---

## Known Gaps and Follow-up Tasks

- **Layer 3 depth**: Currently only lists recent completed tasks with output size. Future: parse artifact files from `specs/` or `STATUS.md` for richer health signals.
- **Interactive refresh**: No `--watch` / auto-refresh. Operators must re-run manually. Could be added as a follow-up.
- **Attention flags in Layer 3**: `layer_3_attention` flags (from spec 032) could surface more prominently in the hierarchical view.

---

## See also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — item 5.
- [032-attention-heuristics-pipeline-status.md](032-attention-heuristics-pipeline-status.md) — attention flags.
- [026-pipeline-observability-and-auto-review.md](026-pipeline-observability-and-auto-review.md) — goal status and dashboard.

---

## Verification (automated tests)

```bash
python3 -m pytest api/tests/test_check_pipeline_hierarchical.py -x -v
```
