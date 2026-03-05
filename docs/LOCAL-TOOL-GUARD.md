# Local Tool Guard — Unblock Plan and Completion Criteria

This doc defines the stabilized local tool validation flow: baseline capture, tool order, gate vs canary executors, and completion criteria.

## Guards (no exceptions)

- **Local only:** `http://127.0.0.1:8000`; never call production.
- **AGENT_AUTO_EXECUTE=0** for all runs.
- **Never call:** `POST /api/inventory/gaps/sync-traceability`.
- **Process gaps:** never use `auto_sync=true`.
- **ROI sync:** always use `normalize_missing_roi=false`.
- **Internal ideas:** use `include_internal_ideas=false` where available.

## 1) Stabilize baseline

1. Start API with `AGENT_AUTO_EXECUTE=0`.
2. **Warm + capture baseline** (run from repo root):
   ```bash
   python3 api/scripts/capture_local_tool_baseline.py --base-url http://127.0.0.1:8000 --output api/logs/local_tool_guard_baseline.json
   ```
   This warms the idea registry with one `GET /api/ideas`, then captures counts and ID-level snapshots (`idea_ids`, `spec_ids`) so later diffs can show exactly what changed.
3. **ID-level diff after each tool** (optional but recommended):
   ```bash
   python3 api/scripts/capture_local_tool_baseline.py --base-url http://127.0.0.1:8000 --diff api/logs/local_tool_guard_baseline.json
   ```
   Exit 0 = invariant OK (counts unchanged, no forbidden patterns). Exit 1 = drift; inspect `idea_ids_added` / `spec_ids_added`.
   If you ran the executor flow matrix (Tool 2), it creates ideas with ID prefix `runtime-idea-cli-flow-`. To treat those as allowed when diffing:
   ```bash
   python3 api/scripts/capture_local_tool_baseline.py --base-url http://127.0.0.1:8000 --diff api/logs/local_tool_guard_baseline.json --allow-idea-id-prefix runtime-idea-cli-flow-
   ```

## 2) Tool 2 — Gate vs canary

- **Strict gate:** run the matrix with **cheap executors only** (e.g. `cursor`). Codex is treated as a **quarantined canary** (external runtime/state-db); its failures must not fail the local gate.
- **Strict gate run (recommended):**
  ```bash
  python3 api/scripts/run_cli_task_flow_matrix.py \
    --local-base-url http://127.0.0.1:8000 \
    --executors cursor \
    --attempts-per-executor 1 \
    --spawn-local-runner \
    --timeout-seconds 300 \
    --strict
  ```
- **Codex as non-blocking canary** (optional, run after gate passes):
  ```bash
  python3 api/scripts/run_cli_task_flow_matrix.py \
    --local-base-url http://127.0.0.1:8000 \
    --executors codex \
    --attempts-per-executor 1 \
    --spawn-local-runner \
    --timeout-seconds 300 \
    --non-blocking-executors codex \
    --strict
  ```
  With `--non-blocking-executors codex`, codex failures do not cause exit 2; they are logged as external canary issues.

## 3) Tool 4 — Deterministic once-drain

To get a clear exit code and avoid long runs from idle auto-generation:

```bash
cd api && AGENT_AUTO_GENERATE_IDLE_TASKS=0 AGENT_TASK_TIMEOUT=180 .venv/bin/python scripts/agent_runner.py --once --workers 1 --interval 1
```

- **Pass rule:** exit code 0; no repeated requeue loop.
- Must run from `api/` so `scripts/agent_runner.py` and repo path resolve correctly.

## 4) Tool order (validation sequence)

1. **Routing smoke:** `python api/scripts/test_routing.py http://127.0.0.1:8000`
2. **Executor flow matrix (gate):** `run_cli_task_flow_matrix.py ... --executors cursor --strict` (and optionally codex with `--non-blocking-executors codex`)
3. **Inventory (safe mode):** the six POSTs with guarded params (no sync-traceability, no auto_sync, normalize_missing_roi=false, include_internal_ideas=false where applicable).
4. **Agent runner once:** the deterministic command above.

After each tool, run the baseline diff to confirm invariant (or at least after tools 1 and 3).

## 5) Completion criteria

- **all_tools_green:** true when:
  - Routing smoke exits 0.
  - Matrix **gate** (e.g. `--executors cursor --strict`) exits 0.
  - All six inventory safe-mode POSTs return 200.
  - Agent runner `--once` exits 0 with the deterministic env (no idle task generation, single worker).
- **Invariant checks:** unchanged from warmed baseline (run `capture_local_tool_baseline.py --diff ...`; exit 0).
- **Codex:** any codex-only failures are treated as **external canary** issues (runtime/state-db); they do not block `all_tools_green` when using `--non-blocking-executors codex`.

## Optional: read-only guard for invariant checks

When calling `GET /api/ideas` for invariant/diff runs, you can pass `read_only_guard=true` so the idea service does not persist ensure logic (avoids extra idea count drift from list path):

```bash
curl "http://127.0.0.1:8000/api/ideas?limit=500&include_internal=true&read_only_guard=true"
```

The baseline capture script uses this for the capture pass after warm-up.
