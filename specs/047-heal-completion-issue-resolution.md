# Spec 047: Heal Completion → Issue Resolution

**Idea ID**: `047-heal-completion-issue-resolution`
**Status**: Ready for Implementation
**Related Specs**: 002, 007, 114, 115

---

## Summary

When the monitor pipeline runs and detects that a previously-reported condition has cleared, it must record that **resolution** to close the failure→heal→resolution loop. This spec makes that contract explicit, adds optional persistence of resolved entries into `monitor_issues.json`, and ensures the `GET /api/agent/monitor-issues` endpoint surfaces resolved entries when present.

The loop being closed: Spec 114 creates a `heal_task_id` when a condition fires → Spec 047 attributes that `heal_task_id` to the resolution when the condition clears → Spec 115 uses resolution data in the quality multiplier for grounded value measurement.

---

## Goal

1. **Resolution recording** (JSONL): When a condition that was present on the previous monitor run is no longer present on the current run, the monitor appends a record to `api/logs/monitor_resolutions.jsonl`. If the previous issue had a `heal_task_id`, the resolution record includes it so effectiveness can attribute heal success.

2. **Optional resolution persistence** (JSON): When `MONITOR_PERSIST_RESOLVED=1` (env var), the monitor also appends the resolution to a `resolved` array within `monitor_issues.json`. The array is capped to the last 50 entries. This provides audit visibility without changing the semantics of `issues` (which remains the current open-issue list).

3. **API pass-through**: `GET /api/agent/monitor-issues` returns the file content as-is. When `monitor_issues.json` contains a `resolved` array, it appears in the response. No stripping.

---

## Requirements

- [ ] **R1** — `_record_resolution(condition, log, heal_task_id=...)` is called for every condition that clears. If the previous issue had a `heal_task_id`, it must be present in the resolution record. *(Core loop — already partially implemented; spec makes it a named contract.)*

- [ ] **R2** — Resolution records in `monitor_resolutions.jsonl` have the shape:
  ```json
  { "condition": "<string>", "resolved_at": "<ISO8601 UTC>", "heal_task_id": "<string (optional)>" }
  ```

- [ ] **R3** — When `MONITOR_PERSIST_RESOLVED=1`, the monitor appends a resolution entry to `monitor_issues.json`'s `resolved` array (creating it if absent) after each condition clears. Entry shape:
  ```json
  { "condition": "<string>", "resolved_at": "<ISO8601 UTC>", "heal_task_id": "<string (optional)>", "issue_id": "<string (optional)>" }
  ```

- [ ] **R4** — The `resolved` array in `monitor_issues.json` is capped at 50 entries (newest last). Older entries are dropped silently.

- [ ] **R5** — Open `issues` in `monitor_issues.json` remain unchanged in semantics: the current firing conditions. Resolved entries are supplemental audit data only.

- [ ] **R6** — `GET /api/agent/monitor-issues` includes `resolved` in the response when the field is present in `monitor_issues.json`. When the field is absent, the response is unchanged (`{ "issues": [], "last_check": null, ... }`).

- [ ] **R7** — When `monitor_issues.json` is missing, unreadable, or stale, the derived fallback response does not include `resolved` (safe default).

- [ ] **R8** — All resolution writes are best-effort: if writing fails (disk full, permissions), the monitor logs a debug message and continues without crashing.

---

## API Contract

### `GET /api/agent/monitor-issues`

**Base response shape** (unchanged):

```json
{
  "issues": [
    {
      "id": "abc12345",
      "condition": "api_unreachable",
      "severity": "high",
      "priority": 1,
      "message": "API unreachable: ...",
      "suggested_action": "Restart API ...",
      "created_at": "2026-03-28T10:00:00Z",
      "resolved_at": null,
      "heal_task_id": "task_abc123"
    }
  ],
  "last_check": "2026-03-28T10:05:00Z",
  "history": [],
  "resolved_since_last": ["stale_version"]
}
```

**Extended response shape** (when `MONITOR_PERSIST_RESOLVED=1` and conditions have cleared):

```json
{
  "issues": [],
  "last_check": "2026-03-28T10:10:00Z",
  "history": [],
  "resolved_since_last": ["api_unreachable"],
  "resolved": [
    {
      "condition": "api_unreachable",
      "resolved_at": "2026-03-28T10:10:00Z",
      "heal_task_id": "task_abc123",
      "issue_id": "abc12345"
    }
  ]
}
```

**Error cases**:

| Scenario | Response |
|---|---|
| `monitor_issues.json` missing | `{ "issues": [], "last_check": null }` derived fallback |
| `monitor_issues.json` stale | Derived fallback from `pipeline-status` |
| `monitor_issues.json` valid but no `resolved` field | Response as-is (no `resolved` key) |

---

## Data Model

### `monitor_issues.json` (persisted by monitor)

```yaml
issues:          array of Issue        # Currently-firing conditions
last_check:      string | null         # ISO8601 of last monitor run
history:         array of HistoryEntry # Rolling 100-entry log of all conditions ever seen
resolved_since_last: array of string   # Condition names cleared this run (ephemeral; single run)
resolved:        array of ResolvedEntry  # (optional) Capped at 50; newest last
```

**Issue** (unchanged):
```yaml
id:               string   # 8-char UUID fragment
condition:        string   # Machine-readable name (e.g. "api_unreachable")
severity:         string   # "high" | "medium" | "low"
priority:         integer  # 1=highest; derived from severity
message:          string
suggested_action: string
created_at:       string   # ISO8601 UTC
resolved_at:      null     # Always null for open issues
heal_task_id:     string?  # Set if Spec 114 created a heal task for this condition
```

**ResolvedEntry** (new, optional):
```yaml
condition:   string   # The condition name that cleared
resolved_at: string   # ISO8601 UTC
heal_task_id: string? # heal_task_id from previous issue, if present
issue_id:    string?  # id from previous issue, if retrievable
```

### `api/logs/monitor_resolutions.jsonl`

JSONL — one JSON object per line:

```json
{"condition": "stale_version", "resolved_at": "2026-03-28T10:10:00Z", "heal_task_id": "task_xyz"}
{"condition": "api_unreachable", "resolved_at": "2026-03-28T10:20:00Z"}
```

---

## Files to Create/Modify

| File | Change |
|---|---|
| `api/scripts/monitor_pipeline.py` | Ensure `_record_resolution()` always receives `heal_task_id` from `prev_condition_to_heal_task` map. Add optional `_persist_resolved_to_issues_file()` helper called when `MONITOR_PERSIST_RESOLVED=1`. |
| `docs/PIPELINE-MONITORING-AUTOMATED.md` | Document resolution recording, `MONITOR_PERSIST_RESOLVED` env var, `resolved` array semantics, and capping behavior. |
| `api/app/routers/agent_issues_routes.py` | No change required — already returns file content as-is; `resolved` field passes through automatically. |

---

## Verification Scenarios

These scenarios are runnable against a local instance or production. The reviewer MUST run them and confirm each expected result.

### Scenario 1 — Condition clears without heal_task_id, JSONL record written

**Setup**: Monitor has previously recorded an issue for `stale_version` (no `heal_task_id` because heal was not triggered). The condition now clears (pipeline is on current SHA).

**Action**:
```bash
# Simulate previous state with an open issue (no heal_task_id)
echo '{"issues":[{"id":"aaa11111","condition":"stale_version","severity":"high","priority":1,"message":"...","suggested_action":"...","created_at":"2026-03-28T09:00:00Z","resolved_at":null}],"last_check":"2026-03-28T09:00:00Z","history":[]}' \
  > api/logs/monitor_issues.json

# Run monitor check (single run)
python3 api/scripts/monitor_pipeline.py --once

# Check resolution was recorded
tail -1 api/logs/monitor_resolutions.jsonl
```

**Expected**: JSONL contains `{"condition": "stale_version", "resolved_at": "<ISO8601>"}` — no `heal_task_id` key (or key is null/absent), `resolved_at` is a valid ISO8601 UTC timestamp.

**Edge**: If `api/logs/` does not exist, the monitor creates it. Resolution write failure (e.g. permissions) must log a debug message but NOT raise an exception or crash the monitor.

---

### Scenario 2 — Condition clears WITH heal_task_id; heal attributed in JSONL

**Setup**: Monitor has a previous issue for `no_task_running` with `heal_task_id: "task_heal_abc"`.

**Action**:
```bash
echo '{"issues":[{"id":"bbb22222","condition":"no_task_running","severity":"high","priority":1,"message":"No task running","suggested_action":"Check pipeline","created_at":"2026-03-28T09:00:00Z","resolved_at":null,"heal_task_id":"task_heal_abc"}],"last_check":"2026-03-28T09:00:00Z","history":[]}' \
  > api/logs/monitor_issues.json

python3 api/scripts/monitor_pipeline.py --once

grep '"condition": "no_task_running"' api/logs/monitor_resolutions.jsonl | tail -1
```

**Expected**: Resolution record contains both `"condition": "no_task_running"` AND `"heal_task_id": "task_heal_abc"`. This is the core attribution contract.

**Edge**: If `heal_task_id` was absent from the previous issue, `heal_task_id` must not appear in the resolution record (no null/empty key leakage).

---

### Scenario 3 — `GET /api/agent/monitor-issues` with no `resolved` field (backward compat)

**Setup**: `monitor_issues.json` has a valid fresh payload with no `resolved` key (existing behavior before this spec).

**Action**:
```bash
API=http://localhost:8000
curl -s "$API/api/agent/monitor-issues" | python3 -c "import json,sys; d=json.load(sys.stdin); print('has_resolved:', 'resolved' in d); print('has_issues:', 'issues' in d)"
```

**Expected**:
```
has_resolved: False
has_issues: True
```

Response must not include a `resolved` key when the field is absent from the file. No 500 error.

**Edge**: `monitor_issues.json` missing entirely → response is `{"issues": [], "last_check": null}` derived fallback. Must return HTTP 200 (not 404 or 500).

---

### Scenario 4 — `MONITOR_PERSIST_RESOLVED=1` persists `resolved` array in JSON; capped at 50

**Setup**: `MONITOR_PERSIST_RESOLVED=1` env var set. Previous `monitor_issues.json` has 50 existing resolved entries and one open issue for `api_error` with `heal_task_id: "task_fix_api"`. The condition clears on this run.

**Action**:
```bash
# Build file with 50 existing resolved entries + 1 open issue
python3 - <<'EOF'
import json, datetime, pathlib
entries = [{"condition": f"old_cond_{i}", "resolved_at": "2026-03-01T00:00:00Z"} for i in range(50)]
data = {
    "issues": [{"id": "ccc33333", "condition": "api_error", "severity": "high", "priority": 1,
                "message": "API error", "suggested_action": "Check logs",
                "created_at": "2026-03-28T09:00:00Z", "resolved_at": None,
                "heal_task_id": "task_fix_api"}],
    "last_check": "2026-03-28T09:00:00Z", "history": [],
    "resolved": entries
}
pathlib.Path("api/logs/monitor_issues.json").write_text(json.dumps(data))
EOF

MONITOR_PERSIST_RESOLVED=1 python3 api/scripts/monitor_pipeline.py --once

python3 -c "
import json
d = json.load(open('api/logs/monitor_issues.json'))
r = d.get('resolved', [])
print('resolved_count:', len(r))
print('last_entry_condition:', r[-1].get('condition') if r else 'none')
print('last_entry_has_heal_task_id:', 'heal_task_id' in (r[-1] if r else {}))
"
```

**Expected**:
```
resolved_count: 50        # capped; oldest entry dropped, new entry appended
last_entry_condition: api_error
last_entry_has_heal_task_id: True
```

The cap ensures the array never exceeds 50 entries regardless of how many conditions resolve over time.

**Edge**: `MONITOR_PERSIST_RESOLVED` not set (or `=0`) → `monitor_issues.json` must NOT contain a `resolved` key after the run (no silent write).

---

### Scenario 5 — Full create-read-update cycle via API: issue fires, heal created, condition clears, resolution visible

**Setup**: Fresh environment, no issues. API running locally.

**Action**:
```bash
API=http://localhost:8000

# Step 1: Verify no issues
curl -s "$API/api/agent/monitor-issues" | python3 -c "import json,sys; print(json.load(sys.stdin).get('issues', []))"
# Expected: []

# Step 2: Inject an issue with a heal_task_id (simulating Spec 114 flow)
echo '{"issues":[{"id":"ddd44444","condition":"stale_version","severity":"high","priority":1,
"message":"Old SHA","suggested_action":"Restart","created_at":"2026-03-28T10:00:00Z",
"resolved_at":null,"heal_task_id":"task_stale_heal_001"}],
"last_check":"2026-03-28T10:00:00Z","history":[]}' > api/logs/monitor_issues.json

# Step 3: Run monitor (condition now gone = resolved)
python3 api/scripts/monitor_pipeline.py --once

# Step 4: Check resolution attributed to heal_task_id
grep "stale_version" api/logs/monitor_resolutions.jsonl | tail -1

# Step 5: Confirm open issues are now empty
curl -s "$API/api/agent/monitor-issues" | python3 -c "import json,sys; d=json.load(sys.stdin); print('open_issues:', len(d['issues'])); print('resolved_since_last:', d.get('resolved_since_last', []))"
```

**Expected (Step 4)**: `{"condition": "stale_version", "resolved_at": "...", "heal_task_id": "task_stale_heal_001"}`

**Expected (Step 5)**:
```
open_issues: 0
resolved_since_last: ['stale_version']
```

**Edge**: If monitor runs twice in a row with no conditions, `resolved_since_last` is `[]` on the second run (no duplicate resolutions).

---

## Out of Scope

- How heal tasks are created or how monitor conditions are detected — unchanged.
- Webhook or push callback when a heal task completes — resolution is poll-detected only.
- Changing `heal_resolved_count` formula in `GET /api/agent/effectiveness` — tracked in Spec 115.
- Database persistence of resolutions — JSONL + optional JSON array is the storage tier for this spec.

---

## Risks and Assumptions

| Risk | Mitigation |
|---|---|
| `MONITOR_PERSIST_RESOLVED=1` not set in production | Document in RUNBOOK; opt-in env var so production behavior is unchanged until explicitly enabled |
| JSONL grows without bound | Out of scope for this spec; a rotation/truncation spec may follow |
| Concurrent monitor instances both writing resolved entries | Unlikely (single monitor process); file append is not atomic — document as single-node only |
| `resolved` array deserialization breaks existing clients | Array is additive; existing clients that parse `issues` are unaffected |

---

## Upstream Dependencies

- **Spec 114** ([114-auto-heal-from-diagnostics.md](114-auto-heal-from-diagnostics.md)) — Creates `heal_task_id` that this spec attributes in resolution records.
- **Spec 115** ([115-grounded-cost-value-measurement.md](115-grounded-cost-value-measurement.md)) — Consumes resolution data for `heal_resolved_count` and quality multiplier.

---

## See Also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — Item 2 (this spec); Item 5 (heal effectiveness tracking).
- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — `GET /api/agent/monitor-issues`, `GET /api/agent/effectiveness`.
- [docs/PIPELINE-MONITORING-AUTOMATED.md](../docs/PIPELINE-MONITORING-AUTOMATED.md) — Monitor flow, resolution tracking, issue shape.

---

## Known Gaps and Follow-up Tasks

- **JSONL rotation**: `monitor_resolutions.jsonl` grows indefinitely; a separate spec should add rotation (e.g. keep last 1000 lines or by date).
- **API endpoint for resolutions**: `GET /api/agent/monitor-resolutions` (paginated JSONL reader) would allow dashboards to query resolved history without reading raw files.
- **Distributed-safe writes**: For multi-worker setups, file-level locking or a DB-backed store replaces JSONL + JSON array.
- **Retention window**: The `resolved` cap (50) is an MVP choice; a time-window retention policy may be preferable long-term.

---

## Concurrency Behavior

- **Read operations**: `GET /api/agent/monitor-issues` is safe for concurrent access.
- **Write operations**: Monitor runs as a single process; file append for JSONL and read-modify-write for JSON are single-threaded within a monitor run. Last-write-wins if two monitor instances somehow run simultaneously.
- **Recommendation**: Do not run multiple monitor processes against the same `logs/` directory.

---

## Failure and Retry Behavior

- **Resolution write failure**: Logged at DEBUG; monitor continues. No crash, no retry.
- **`monitor_issues.json` write failure after persist-resolved**: Monitor logs warning; existing issue resolution still recorded in JSONL.
- **Partial completion**: Monitor state is checkpointed in `monitor_issues.json` after each run; a crashed run leaves the previous valid state.

---

## Verification

```bash
# Core tests
python3 -m pytest api/tests/test_auto_heal_service.py -x -v

# Integration (if monitor resolution test added)
python3 -m pytest api/tests/test_monitor_resolution.py -x -v
```

All tests must pass without modifying test assertions to force passing behavior.
