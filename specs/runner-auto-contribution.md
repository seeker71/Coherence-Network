---
idea_id: pipeline-optimization
status: partial
source:
  - file: api/app/services/agent_runner_registry_service.py
    symbols: [runner registry, auto-contribution]
  - file: api/app/services/contribution_ledger_service.py
    symbols: [contribution tracking]
requirements:
  - "`_auto_record_contribution` must embed a stable `task_id`-scoped idempotency key in"
  - "On `POST /api/contributions/record` failure, the runner must persist the failed"
  - "Partial contributions must be recorded for failed or timed-out tasks when the output"
  - "`GET /api/contributions/ledger/{contributor_id}` must accept an optional"
  - "`GET /api/contributions/ledger/{contributor_id}` must accept an optional"
  - "`amount_cc` must incorporate the task's DIF score if present in"
  - "`_NODE_ID` must appear verbatim in `metadata.node_id` of every auto-recorded"
---

> **Parent idea**: [pipeline-optimization](../ideas/pipeline-optimization.md)
> **Source**: [`api/app/services/agent_runner_registry_service.py`](../api/app/services/agent_runner_registry_service.py) | [`api/app/services/contribution_ledger_service.py`](../api/app/services/contribution_ledger_service.py)

# Spec: Runner Auto-Contribution

## Purpose

Every completed task in the Coherence Network runner should generate an automatic attribution
record in the contribution ledger without any manual step from the operator. This closes the
loop between execution work and value tracking: task output becomes CC credit, providing
full traceability from idea → task → contributor → reward. Without this automation, agents
doing real work go unattributed and the value-lineage graph develops gaps that undermine
payout correctness and ROI reporting.

## Current Implementation

`_auto_record_contribution(task, provider, duration)` is defined at line 1148 of
`api/scripts/local_runner.py`. It is called from the task completion path at line 3348,
inside the guard `if success and reported and len(output_stripped) >= min_chars`.

The function:
- Derives `contribution_type` from `task_type` via a static map
  (`spec→docs`, `test→code`, `impl→code`, `review→review`, `heal→code`).
- Computes `amount_cc = base_cc[task_type] + min(duration_seconds / 60, 5)`.
  Base values: `spec=3`, `test=5`, `impl=8`, `review=2`, `heal=3`, default=2.
- Sets `contributor_id` to the module-level constant `_NODE_ID` (a stable node identifier
  derived at startup).
- Resolves `idea_id` via `_idea_id_from_task(task)` (line 1193), which walks
  `context["idea_id"]`, `context["origin_idea_id"]`, `context["primary_idea_id"]`,
  `context["tracking_idea_id"]`, and list variants.
- Posts `POST /api/contributions/record` (`OpenContributionRequest` schema).
- Logs `AUTO_CONTRIBUTION recorded` on success and `AUTO_CONTRIBUTION failed` on API
  non-response; swallows all exceptions with a `log.warning`.

`_worker_loop(worker_id, dry_run)` is defined at line 5228 and spawns per-worker threads
that iterate the claim/execute/report cycle. Each completed task passes through the
completion block at line 3344 before `_auto_record_contribution` is reached.

## Identified Gaps

1. **Partial contributions on failure**: `_auto_record_contribution` is only called on
   `success=True`. Tasks that fail after significant LLM work (e.g. timed out after 5 min
   of generation) produce no attribution record, losing provenance for partial outputs.

2. **No deduplication guard**: If a task is retried and succeeds on a second attempt, both
   successful completions call `_auto_record_contribution` independently. The ledger receives
   two entries for the same task without any idempotency key, inflating CC totals.

3. **Flat quality-blind amount formula**: `amount_cc` is purely duration-based. It does not
   incorporate output quality signals (DIF score, test pass rate, reviewer approval) that
   are already available in the task context. A 1-minute spec task that scores 0.95 DIF
   earns the same as one that scores 0.20.

4. **No session-scoped query surface**: There is no API endpoint to list contributions that
   were auto-recorded during a given runner session or time window. Operators must inspect
   raw ledger history to audit what the runner claimed.

5. **Silent contribution loss on API failure**: When `POST /api/contributions/record` returns
   a falsy result (`None` or `{}`), the runner logs a warning and continues. The
   contribution is permanently lost — there is no retry queue, dead-letter store, or
   alerting.

## Requirements

- [ ] `_auto_record_contribution` must embed a stable `task_id`-scoped idempotency key in
  the `metadata` payload so the ledger service can detect and skip duplicate submissions.
- [ ] On `POST /api/contributions/record` failure, the runner must persist the failed
  payload to a local retry queue (in-memory list capped at 100 entries) and attempt
  re-submission on the next worker loop iteration, before claiming a new task.
- [ ] Partial contributions must be recorded for failed or timed-out tasks when the output
  exceeds a minimum threshold (configurable; default 200 characters). The `amount_cc`
  for a partial contribution must be capped at 50 % of the full computed value, and
  `metadata.partial=True` must be set.
- [ ] `GET /api/contributions/ledger/{contributor_id}` must accept an optional
  `auto_only=true` query parameter that filters history to entries where
  `metadata.auto_recorded=true`.
- [ ] `GET /api/contributions/ledger/{contributor_id}` must accept an optional
  `since` query parameter (ISO 8601 UTC) to constrain history to contributions recorded
  after that timestamp.
- [ ] `amount_cc` must incorporate the task's DIF score if present in
  `context["dif_score"]` or `task["dif_score"]`: `amount_cc *= (0.5 + 0.5 * dif_score)`,
  applied before rounding, so a DIF of 1.0 leaves the amount unchanged and DIF of 0.0
  halves it.
- [ ] `_NODE_ID` must appear verbatim in `metadata.node_id` of every auto-recorded
  contribution so consumers can filter by worker node without parsing
  `metadata.description`.

## API Contract

### `POST /api/contributions/record`

No new fields on the request. The `metadata` object must include the following keys when
called from the runner (enforced by the caller, not the API):

```json
{
  "contributor_id": "<_NODE_ID>",
  "type": "docs | code | review | other",
  "amount_cc": 9.3,
  "idea_id": "<idea_id or omitted>",
  "metadata": {
    "task_id": "<uuid>",
    "task_type": "spec | test | impl | review | heal",
    "provider": "<provider name>",
    "duration_s": 112.4,
    "auto_recorded": true,
    "node_id": "<_NODE_ID>",
    "partial": false,
    "idempotency_key": "auto:<task_id>:<attempt_number>",
    "dif_score": 0.87
  }
}
```

**Response 201**
```json
{
  "id": "<contribution_record_id>",
  "contributor_id": "<string>",
  "type": "docs",
  "amount_cc": 9.3,
  "idea_id": "<string or null>",
  "created_at": "2026-03-28T14:00:00Z",
  "metadata": {}
}
```

**Response 422** — missing `contributor_id` and no `provider`+`provider_id` combination.

---

### `GET /api/contributions/ledger/{contributor_id}`

Extended with two new optional query parameters:

| Parameter   | Type    | Description                                           |
|-------------|---------|-------------------------------------------------------|
| `auto_only` | boolean | If true, return only entries with `metadata.auto_recorded=true` |
| `since`     | string  | ISO 8601 UTC; return only entries created at or after this time |

**Response 200** (unchanged envelope, history array filtered)
```json
{
  "balance": { "total_cc": 42.1, "by_type": { "docs": 12.0, "code": 30.1 } },
  "history": [
    {
      "id": "<string>",
      "type": "docs",
      "amount_cc": 3.5,
      "idea_id": "<string>",
      "created_at": "2026-03-28T14:00:00Z",
      "metadata": { "auto_recorded": true, "node_id": "<string>", "task_id": "<string>" }
    }
  ]
}
```

## Data Model

```yaml
ContributionLedgerRecord:
  properties:
    id: { type: string }
    contributor_id: { type: string }
    type: { type: string, enum: [docs, code, review, other] }
    amount_cc: { type: number, minimum: 0 }
    idea_id: { type: string, nullable: true }
    created_at: { type: string, format: date-time }
    metadata:
      type: object
      properties:
        task_id: { type: string }
        task_type: { type: string }
        provider: { type: string }
        duration_s: { type: number }
        auto_recorded: { type: boolean }
        node_id: { type: string }
        partial: { type: boolean }
        idempotency_key: { type: string }
        dif_score: { type: number, minimum: 0.0, maximum: 1.0, nullable: true }
```

## Files to Create/Modify

- `api/scripts/local_runner.py` — modify `_auto_record_contribution` (line 1148):
  add `node_id`, `idempotency_key`, `partial`, and `dif_score` fields to the metadata
  payload; apply DIF multiplier; add partial-contribution branch for failed tasks;
  add local retry queue flush at the top of the worker loop.
- `api/scripts/local_runner.py` — modify `_worker_loop` (line 5228): flush the
  pending retry queue before each task claim attempt.
- `api/app/routers/contributions.py` — extend `get_contributor_ledger` to accept and
  apply `auto_only` and `since` query parameters against `metadata.auto_recorded` and
  `created_at` respectively.
- `api/app/services/contribution_ledger_service.py` — extend `get_contributor_history`
  signature to accept `auto_only: bool = False` and `since: str | None = None`;
  apply filters in the SQL query before returning.

## Acceptance Tests

- `cd api && pytest -q tests/test_contributions.py -k "auto_contribution_spec_task"`
- `cd api && pytest -q tests/test_contributions.py -k "auto_contribution_duration_bonus"`
- `cd api && pytest -q tests/test_contributions.py -k "auto_contribution_failed_task_no_record"`
- `cd api && pytest -q tests/test_contributions.py -k "auto_contribution_node_id_in_metadata"`
- `cd api && pytest -q tests/test_contributions.py -k "auto_contribution_idempotency_key"`
- `cd api && pytest -q tests/test_contributions.py -k "auto_contribution_partial_on_failure"`
- `cd api && pytest -q tests/test_contributions.py -k "auto_contribution_dif_multiplier"`
- `cd api && pytest -q tests/test_contributions.py -k "ledger_auto_only_filter"`
- `cd api && pytest -q tests/test_contributions.py -k "ledger_since_filter"`

## Concurrency Behavior

- **Read operations**: `GET /api/contributions/ledger/{contributor_id}` is safe for
  concurrent access; no locking required.
- **Write operations** (retry queue flush): The in-memory retry queue must be protected
  by a `threading.Lock` because multiple worker threads share the same queue. Last-write-wins
  semantics are not sufficient; all queued entries must eventually be flushed.
- **Idempotency**: The `idempotency_key` field in metadata is informational at the API
  level. The ledger service does not enforce uniqueness on it in this spec (see Known Gaps).

## Verification

Four concrete scenarios that can be run against a live or test environment:

**Scenario 1 — Spec task produces docs contribution**
```bash
# Trigger or simulate a completed spec task for NODE_ID
TASK_ID="<test-task-id>"
NODE_ID="<runner-node-id>"
curl -s "https://api.coherencycoin.com/api/contributions/ledger/${NODE_ID}?auto_only=true" \
  | jq '[.history[] | select(.metadata.task_id == "'${TASK_ID}'")] | .[0].type'
# Expected: "docs"
```

**Scenario 2 — Amount scales with duration**
```bash
# impl task, duration = 8 minutes (480 s): base=8, bonus=min(480/60,5)=5 => 13.0 CC
# With DIF score 1.0: 13.0 * (0.5 + 0.5*1.0) = 13.0
# With DIF score 0.6: 13.0 * (0.5 + 0.5*0.6) = 13.0 * 0.8 = 10.4
curl -s "https://api.coherencycoin.com/api/contributions/ledger/${NODE_ID}?auto_only=true" \
  | jq '[.history[] | select(.metadata.task_type == "impl" and .metadata.duration_s >= 480)] | .[0].amount_cc'
# Expected: value >= 8.0 and <= 13.0 depending on DIF
```

**Scenario 3 — Failed task produces no full contribution**
```bash
curl -s "https://api.coherencycoin.com/api/contributions/ledger/${NODE_ID}?auto_only=true" \
  | jq '[.history[] | select(.metadata.task_id == "'${FAILED_TASK_ID}'" and .metadata.partial != true)]'
# Expected: empty array (no full contribution recorded for a failed task)
```

**Scenario 4 — Node ID in metadata matches runner**
```bash
curl -s "https://api.coherencycoin.com/api/contributions/ledger/${NODE_ID}?auto_only=true&limit=1" \
  | jq '.history[0].metadata.node_id'
# Expected: exact string matching NODE_ID of the worker that executed the task
```

## Out of Scope

- Server-side enforcement of `idempotency_key` uniqueness (database unique constraint).
  Deduplication in this spec is left to the caller; a follow-up task can add a DB index.
- UI dashboard changes to surface auto-contribution history.
- Adjusting the base CC values themselves (the numeric constants in `_auto_record_contribution`).
- Retroactively back-filling contributions for tasks completed before this spec is implemented.
- DIF score computation — this spec consumes an existing score from task context; it does
  not define how DIF is computed.
- Payout or distribution logic changes triggered by contribution records.

## Risks and Assumptions

- **Risk**: The retry queue grows unboundedly if the API is down for an extended period.
  Mitigation: cap the queue at 100 entries; log a warning and drop oldest entries when
  the cap is reached.
- **Risk**: Adding a DIF multiplier changes the CC amounts nodes have historically been
  earning, which may surprise operators on first deployment.
  Mitigation: document the formula change prominently in the PR description; the effect
  only applies to new completions.
- **Assumption**: `_NODE_ID` is stable across runner restarts within a session. If it
  changes on restart, `auto_only` history queries scoped to a single node ID will miss
  entries from prior sessions. This is an existing property of `_stable_node_id()` and
  is not changed by this spec.
- **Assumption**: `contribution_ledger_service.get_contributor_history` returns a
  consistent `created_at` field on each record. If any record omits `created_at`, the
  `since` filter will silently exclude it.
- **Assumption**: The `partial` task completion path (failed or timed-out tasks with
  sufficient output) is identifiable by checking `success=False` in the existing
  completion guard; no additional status codes need to be introduced.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_contrib_idempotency_db_unique_001` — add a database unique
  constraint on `idempotency_key` in `contribution_ledger_service` to prevent double-
  counting if the retry queue re-submits an already-recorded entry.
- Follow-up task: `task_contrib_dif_weighting_v2_001` — refine DIF multiplier to also
  incorporate reviewer approval and test pass rate, not just raw DIF score.
- Follow-up task: `task_contrib_partial_threshold_config_001` — expose the 200-character
  partial contribution threshold as a runner config key (`contributions.partial_min_chars`)
  rather than a hardcoded default.
- Follow-up task: `task_contrib_web_auto_history_001` — add a web UI panel on the
  contributor portfolio page to display auto-recorded contributions filtered by session.

## Failure/Retry Reflection

- **Failure mode**: API returns 422 because `contributor_id` format is rejected (e.g.,
  node ID contains characters the ledger service does not accept).
  **Blind spot**: Node IDs are MAC-address-derived hex strings; the ledger service
  currently accepts arbitrary strings, so this is low-risk but unverified.
  **Next action**: Add an integration test that posts a node-ID-formatted string to
  `POST /api/contributions/record` and asserts 201.

- **Failure mode**: Retry queue never drains if the API returns non-200 consistently
  (bad network partition); queue cap is reached and new contributions are silently dropped.
  **Blind spot**: There is no alerting today on dropped contributions.
  **Next action**: Emit a structured log line at `ERROR` level when an entry is evicted
  from the capped queue so it appears in monitoring dashboards.

## Decision Gates

- Confirm whether partial contributions (failed tasks) should be gated on a minimum
  output length (current proposal: 200 chars) or a minimum duration threshold. The
  choice affects how many partial records appear in production.
- Confirm whether `idempotency_key` should be enforced at the DB level in this spec
  or deferred to the follow-up task. Deferring is lower risk but leaves a short window
  for double-counting during the retry flush.
