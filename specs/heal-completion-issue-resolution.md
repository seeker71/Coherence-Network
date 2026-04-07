---
idea_id: pipeline-reliability
status: partial
source:
  - file: api/app/services/auto_heal_service.py
    symbols: [heal completion tracking]
  - file: api/app/services/pipeline_advance_service.py
    symbols: [completion issue detection]
requirements:
  - Record resolution to JSONL when a monitor condition clears
  - Include heal_task_id in resolution record for effectiveness attribution
  - Omit heal_task_id from resolution when absent on previous issue
  - Persist resolved array in monitor_issues.json when MONITOR_PERSIST_RESOLVED=1
  - Cap resolved array at 50 entries, dropping oldest on overflow
  - Do not write resolved key when MONITOR_PERSIST_RESOLVED is unset
  - GET /api/agent/monitor-issues returns file content as-is including resolved
done_when:
  - Resolution JSONL contains heal_task_id when present on prior issue
  - Resolved array capped at 50 with correct FIFO eviction
  - pytest api/tests/test_monitor_resolution.py passes
---

> **Parent idea**: [pipeline-reliability](../ideas/pipeline-reliability.md)
> **Source**: [`api/app/services/auto_heal_service.py`](../api/app/services/auto_heal_service.py) | [`api/app/services/pipeline_advance_service.py`](../api/app/services/pipeline_advance_service.py)

# Spec 047: Heal Completion → Issue Resolution

**Idea ID**: `047-heal-completion-issue-resolution`
**Status**: Ready for Implementation
**Related Specs**: 002, 007, 114, 115

## Goal

1. **Resolution recording** (JSONL): When a condition that was present on the previous monitor run is no longer present on the current run, the monitor appends a record to `api/logs/monitor_resolutions.jsonl`. If the previous issue had a `heal_task_id`, the resolution record includes it so effectiveness can attribute heal success.

2. **Optional resolution persistence** (JSON): When `MONITOR_PERSIST_RESOLVED=1` (env var), the monitor also appends the resolution to a `resolved` array within `monitor_issues.json`. The array is capped to the last 50 entries. This provides audit visibility without changing the semantics of `issues` (which remains the current open-issue list).

3. **API pass-through**: `GET /api/agent/monitor-issues` returns the file content as-is. When `monitor_issues.json` contains a `resolved` array, it appears in the response. No stripping.

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

## Files to Create/Modify

| File | Change |
|---|---|
| `api/scripts/monitor_pipeline.py` | Ensure `_record_resolution()` always receives `heal_task_id` from `prev_condition_to_heal_task` map. Add optional `_persist_resolved_to_issues_file()` helper called when `MONITOR_PERSIST_RESOLVED=1`. |
| `docs/PIPELINE-MONITORING-AUTOMATED.md` | Document resolution recording, `MONITOR_PERSIST_RESOLVED` env var, `resolved` array semantics, and capping behavior. |
| `api/app/routers/agent_issues_routes.py` | No change required — already returns file content as-is; `resolved` field passes through automatically. |

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

## Out of Scope

- How heal tasks are created or how monitor conditions are detected — unchanged.
- Webhook or push callback when a heal task completes — resolution is poll-detected only.
- Changing `heal_resolved_count` formula in `GET /api/agent/effectiveness` — tracked in Spec 115.
- Database persistence of resolutions — JSONL + optional JSON array is the storage tier for this spec.

## Upstream Dependencies

- **Spec 114** ([114-auto-heal-from-diagnostics.md](114-auto-heal-from-diagnostics.md)) — Creates `heal_task_id` that this spec attributes in resolution records.
- **Spec 115** ([115-grounded-cost-value-measurement.md](115-grounded-cost-value-measurement.md)) — Consumes resolution data for `heal_resolved_count` and quality multiplier.

## Known Gaps and Follow-up Tasks

- **JSONL rotation**: `monitor_resolutions.jsonl` grows indefinitely; a separate spec should add rotation (e.g. keep last 1000 lines or by date).
- **API endpoint for resolutions**: `GET /api/agent/monitor-resolutions` (paginated JSONL reader) would allow dashboards to query resolved history without reading raw files.
- **Distributed-safe writes**: For multi-worker setups, file-level locking or a DB-backed store replaces JSONL + JSON array.
- **Retention window**: The `resolved` cap (50) is an MVP choice; a time-window retention policy may be preferable long-term.

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
