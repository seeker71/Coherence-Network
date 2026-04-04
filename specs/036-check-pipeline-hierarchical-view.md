# Spec: Hierarchical view in check_pipeline (goal → PM → tasks → artifacts)

## Purpose

Operators need a single command that shows pipeline health in a clear hierarchy: goal progress first, then orchestration (PM), then task execution, then artifact health. This makes it easy to see "are we on track?" before drilling into running/pending tasks and recent outputs.

## Requirements

- [ ] When run without `--json`, `check_pipeline.py` prints a **hierarchical view**: Goal → PM/Orchestration → Tasks → Artifacts (in that order).
- [ ] **Goal** section: Use `GET /api/agent/status-report` when available (from monitor-written file); show layer_0_goal status and summary (e.g. goal_proximity, throughput, success rate). If status-report is missing, show "Goal: (report not yet generated)" or fetch `GET /api/agent/effectiveness` and show goal_proximity and a one-line summary.
- [ ] **PM / Orchestration** section: Show layer_1_orchestration from status-report when available; else derive from pipeline-status (project_manager state, backlog_index, phase, blocked) and process detection (agent_runner workers, PM --parallel). Same information as current "PROJECT MANAGER" and "PROCESSES" blocks, but labeled as Layer 1.
- [ ] **Tasks** section: Running, pending (with wait times), recent completed (with duration) — current pipeline-status content, labeled as Layer 2 / Tasks.
- [ ] **Artifacts** section: Recent task outputs / artifact health — e.g. recent_completed tasks with output_len and optional one-line output_preview; optionally mention spec/STATUS artifact health if effectiveness or status-report exposes it. At minimum: list recent completed with output size so operator can see "artifacts produced."
- [ ] Add optional flag `--hierarchical` to explicitly enable this view; default human-readable output is hierarchical. Add `--flat` to preserve legacy flat output (Goal/PM/Tasks/Artifacts order still allowed but sections not strictly layered).
- [ ] With `--json`, when hierarchical view is requested (default or `--hierarchical`), include in the JSON a top-level key `hierarchical` (or merge layer_0_goal, layer_1_orchestration, layer_2_execution, layer_3_attention from status-report when available) so script consumers get the same structure.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 007, 026, 032

## Task Card

```yaml
goal: Operators need a single command that shows pipeline health in a clear hierarchy: goal progress first, then orchestration (PM), then task execution, then artifact health.
files_allowed:
  - api/scripts/check_pipeline.py
done_when:
  - When run without `--json`, `check_pipeline.py` prints a hierarchical view: Goal → PM/Orchestration → Tasks → Artifact...
  - Goal section: Use `GET /api/agent/status-report` when available (from monitor-written file); show layer_0_goal status...
  - PM / Orchestration section: Show layer_1_orchestration from status-report when available; else derive from pipeline-s...
  - Tasks section: Running, pending (with wait times), recent completed (with duration) — current pipeline-status content...
  - Artifacts section: Recent task outputs / artifact health — e.g. recent_completed tasks with output_len and optional o...
commands:
  - python3 -m pytest api/tests/test_check_pipeline_hierarchical.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

No new API. Uses existing:

- `GET /api/agent/status-report` — hierarchical report (layer_0_goal … layer_3_attention) when monitor has written it.
- `GET /api/agent/pipeline-status` — running, pending, recent_completed, project_manager, attention, etc.
- `GET /api/agent/effectiveness` — goal_proximity, throughput, success_rate (fallback when status-report missing).


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

N/A. Script aggregates existing API responses and prints (or emits JSON) in hierarchical order.

## Files to Create/Modify

- `api/scripts/check_pipeline.py` — add hierarchical view: fetch status-report (and optionally effectiveness), merge with pipeline-status; print Goal → PM → Tasks → Artifacts; add `--hierarchical` / `--flat`; extend `--json` to include hierarchical structure when available.

## Acceptance Tests

- Run `python scripts/check_pipeline.py` (no `--json`): output shows four sections in order — Goal, PM/Orchestration, Tasks, Artifacts.
- Run with `--json`: response includes hierarchical data (e.g. from status-report or built from pipeline-status + effectiveness).
- Run with `--flat`: output is legacy flat format (no requirement to change section order for `--flat` beyond preserving previous behavior).
- When status-report file is missing and API is up: Goal section shows fallback from effectiveness or "report not yet generated"; Tasks and Artifacts still from pipeline-status.

## Out of Scope

- Changing `GET /api/agent/status-report` or `GET /api/agent/pipeline-status` contracts.
- Modifying `monitor_pipeline.py` (monitor continues to write status-report as today).
- New API endpoints or new files beyond the single script change.

## See also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — item 5.
- [PIPELINE-EFFICIENCY-PLAN.md](../docs/PIPELINE-EFFICIENCY-PLAN.md) — §4.3 Hierarchical view, §7 Phase 3.
- [032-attention-heuristics-pipeline-status.md](032-attention-heuristics-pipeline-status.md) — attention flags.
- [026-pipeline-observability-and-auto-review.md](026-pipeline-observability-and-auto-review.md) — goal status and dashboard.

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

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add distributed locking for multi-worker pipelines.


## Verification Scenarios

These scenarios must be run against the API (local or production) to confirm the feature works end-to-end. Each is concrete and runnable.

---

### Scenario 1: Default (hierarchical) human-readable output shows four sections in order

**Setup:** API is running at `$BASE` (e.g. `http://localhost:8000`). At least one task exists in the pipeline.

**Action:**
```bash
BASE=http://localhost:8000 python3 api/scripts/check_pipeline.py
```

**Expected result:**
- Output printed to stdout.
- Sections appear in order: Goal (layer 0), PM/Orchestration (layer 1), Tasks (layer 2), Artifacts/Attention (layer 3).
- The header line includes "hierarchical" (e.g. `Pipeline Status (hierarchical)`).
- Goal section shows `goal_proximity`, throughput, and success rate (or fallback message `"report not yet generated"`).
- Tasks section shows running, pending, and recent completed tasks.

**Edge case — API unreachable:**
```bash
BASE=http://localhost:19999 python3 api/scripts/check_pipeline.py
```
Expected: non-zero exit code, error message printed to stderr. No Python traceback exposed to user.

---

### Scenario 2: `--json` output includes `hierarchical` top-level key

**Setup:** API running, at least one task exists.

**Action:**
```bash
BASE=http://localhost:8000 python3 api/scripts/check_pipeline.py --json | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'hierarchical' in d, 'Missing hierarchical key'; print('OK')"
```

**Expected result:**
- Exit 0, prints `OK`.
- `hierarchical` key contains at minimum `layer_0_goal`, `layer_1_orchestration`, `layer_2_execution`.

**Edge case — `--flat --json`:**
```bash
BASE=http://localhost:8000 python3 api/scripts/check_pipeline.py --flat --json | python3 -c "import sys,json; d=json.load(sys.stdin); print('hierarchical' in d)"
```
Expected: Prints `False` (flat mode omits hierarchical wrapper) or includes it but clearly labelled flat — either behaviour is acceptable; must not crash.

---

### Scenario 3: `--flat` flag produces legacy flat output without hierarchical header

**Setup:** API running.

**Action:**
```bash
BASE=http://localhost:8000 python3 api/scripts/check_pipeline.py --flat | grep -i "hierarchical"
```

**Expected result:**
- Grep returns empty (exit 1) — i.e. the word "hierarchical" does not appear in the flat output header.
- Command itself exits 0 (pipeline output was produced without error).

**Edge case — mutually exclusive flags:**
```bash
BASE=http://localhost:8000 python3 api/scripts/check_pipeline.py --hierarchical --flat
```
Expected: Either an `argparse` error (`error: argument --flat: not allowed with argument --hierarchical`) with exit code 2, or one flag silently takes precedence. Must not crash with an unhandled exception.

---

### Scenario 4: Goal section graceful fallback when `GET /api/agent/status-report` returns 404

**Setup:** Status-report endpoint is not available (returns 404). `GET /api/agent/effectiveness` is available and returns `{"goal_proximity": 0.7, "throughput": {"tasks_per_hour": 4}, "success_rate": 0.85}`.

**Action:**
```bash
BASE=http://localhost:8000 python3 api/scripts/check_pipeline.py 2>&1 | head -30
```

**Expected result:**
- Output still prints all four sections.
- Goal section shows values derived from effectiveness endpoint (proximity ≥ 0.7, throughput ≥ 4 tasks/hr, success rate ≥ 85%).
- No Python traceback visible; any fallback message is human-readable.

**Edge case — both status-report and effectiveness unreachable:**
- Goal section prints `"Goal: (report not yet generated)"` or equivalent placeholder.
- Remaining sections (Tasks, Artifacts) still render from `pipeline-status`.

---

### Scenario 5: `--json` output passes full create-read cycle for scripting consumers

**Setup:** API running. Assign `OUT` to captured JSON output.

**Action:**
```bash
OUT=$(BASE=http://localhost:8000 python3 api/scripts/check_pipeline.py --json)
echo "$OUT" | python3 - <<'EOF'
import sys, json
d = json.loads(sys.stdin.read())
# Must have standard pipeline-status keys
assert "running" in d or "tasks" in d or "project_manager" in d, "Missing pipeline-status fields"
h = d.get("hierarchical", {})
assert "layer_0_goal" in h, f"Missing layer_0_goal: {list(h.keys())}"
assert "layer_1_orchestration" in h, f"Missing layer_1_orchestration"
assert "layer_2_execution" in h, f"Missing layer_2_execution"
print("ALL ASSERTIONS PASSED")
EOF
```

**Expected result:**
- Prints `ALL ASSERTIONS PASSED`, exit 0.

**Edge case — malformed JSON from upstream:**
- Script must not crash; should print error and exit non-zero rather than propagating a json.JSONDecodeError traceback.

---

## Verification (automated)

```bash
python3 -m pytest api/tests/test_check_pipeline_hierarchical.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
