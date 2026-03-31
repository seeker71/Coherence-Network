# Spec: Federation Measurement Push

## Purpose

Nodes push aggregated measurement summaries to the federation hub so operators gain fleet-wide visibility into slot performance without exposing raw per-request data. Without this, the hub has no operational telemetry from remote nodes, making it impossible to detect cross-node performance regressions, compare provider effectiveness, or trigger fleet-level remediation. Summaries are computed from local SlotSelector files, aggregated per `(decision_point, slot_id)` since the last push, and sent via a single POST. Local execution is never blocked by hub availability.

## Requirements

- [x] POST `/api/federation/nodes/{node_id}/measurements` accepts a batch of measurement summaries and stores them in `node_measurement_summaries`.
- [x] Each summary contains: `node_id`, `decision_point`, `slot_id`, `period_start`, `period_end`, `sample_count`, `successes`, `failures`, `mean_duration_s`, `mean_value_score`, `error_classes_json`, `pushed_at`.
- [x] Hub validates that `node_id` in the path matches every summary's `node_id`; rejects with 422 on mismatch.
- [x] Hub validates that `sample_count == successes + failures` for each summary; rejects with 422 on mismatch.
- [x] Hub rejects empty summary batches with 422.
- [x] Hub returns 201 with the count of stored summaries on success.
- [x] A client-side push function reads all SlotSelector JSON files from the local store directory, groups measurements by `(decision_point, slot_id)`, filters to only measurements recorded after `last_push` timestamp, computes aggregated summaries, and POSTs them to the hub.
- [x] `last_push` timestamp is persisted in `~/.coherence-network/last_push.json` as `{"last_push_utc": "<ISO 8601>"}` and updated only after a successful push.
- [x] If the hub is unreachable or returns a non-2xx status, the push function logs a warning and returns without raising — local execution continues uninterrupted.
- [x] `mean_value_score` is the arithmetic mean of `value_score` across filtered measurements for that `(decision_point, slot_id)` pair.
- [x] `mean_duration_s` is the arithmetic mean of `duration_s` values (only measurements that include `duration_s`); null if none have it.
- [x] `successes` counts measurements with `value_score > 0.0`; `failures` counts measurements with `value_score == 0.0`.
- [x] `error_classes_json` is a JSON object mapping each `error_class` string to its occurrence count (e.g. `{"timeout": 3, "rate_limit": 1}`); empty object `{}` if no errors.
- [x] `period_start` is the earliest measurement timestamp in the group; `period_end` is the latest.
- [x] GET `/api/federation/nodes/{node_id}/measurements` returns stored summaries for the given node, with optional `decision_point` query filter and `limit`/`offset` pagination (default limit 100).
- [x] PostgreSQL migration creates `node_measurement_summaries` table with appropriate indexes on `(node_id, decision_point)` and `pushed_at`.

## Research Inputs (Required)

- `2025-03-01` - [Spec 120: Minimum Federation Layer](specs/120-minimum-federation-layer.md) - establishes federation instance model, trust levels, and sync patterns that this spec extends with measurement telemetry.
- `2025-03-01` - [SlotSelector service](api/app/services/slot_selection_service.py) - source of truth for local measurement data format (slot_id, value_score, error_class, duration_s, timestamp fields).
- `2025-03-01` - [Spec 115: Grounded Cost & Value Measurement](specs/115-grounded-cost-value-measurement.md) - defines the measurement schema and value_score semantics used by SlotSelector.

## Task Card (Required)

```yaml
goal: Nodes push aggregated SlotSelector measurement summaries to hub via federation endpoint
files_allowed:
  - api/app/routers/federation.py
  - api/app/services/federation_service.py
  - api/app/services/federation_push_service.py
  - api/app/models/federation.py
  - api/app/db/migrations/add_node_measurement_summaries.sql
  - api/tests/test_federation_measurement_push.py
done_when:
  - POST /api/federation/nodes/{node_id}/measurements stores summaries and returns 201
  - GET /api/federation/nodes/{node_id}/measurements returns stored summaries with filtering
  - Push client reads SlotSelector files, computes aggregates, sends to hub
  - last_push.json tracks push timestamp and is updated only on success
  - Hub unreachable → warning logged, no exception raised
  - node_measurement_summaries table created with indexes
commands:
  - cd api && pytest -q tests/test_federation_measurement_push.py
constraints:
  - Never block local task execution on hub connectivity
  - Do not modify SlotSelector measurement file format
  - Summaries are one-way push; hub does not write back to nodes
```

## API Contract (if applicable)

### `POST /api/federation/nodes/{node_id}/measurements`

Accepts a batch of measurement summaries from a node.

**Request**
- `node_id`: string (path) — the pushing node's identifier

**Request Body**
```json
{
  "summaries": [
    {
      "node_id": "node-alpha",
      "decision_point": "provider_code_gen",
      "slot_id": "openrouter/deepseek-v3",
      "period_start": "2026-03-20T10:00:00Z",
      "period_end": "2026-03-20T18:00:00Z",
      "sample_count": 42,
      "successes": 38,
      "failures": 4,
      "mean_duration_s": 2.35,
      "mean_value_score": 0.82,
      "error_classes_json": {"timeout": 2, "rate_limit": 2}
    }
  ]
}
```

**Response 201**
```json
{
  "stored": 1,
  "node_id": "node-alpha"
}
```

**Response 422** (validation failure)
```json
{
  "detail": "node_id mismatch: path='node-alpha', summary='node-beta'"
}
```

### `GET /api/federation/nodes/{node_id}/measurements`

Returns stored measurement summaries for a node.

**Request**
- `node_id`: string (path)
- `decision_point`: string (query, optional) — filter by decision point
- `limit`: int (query, default 100, max 500)
- `offset`: int (query, default 0)

**Response 200**
```json
{
  "node_id": "node-alpha",
  "summaries": [
    {
      "id": 1,
      "node_id": "node-alpha",
      "decision_point": "provider_code_gen",
      "slot_id": "openrouter/deepseek-v3",
      "period_start": "2026-03-20T10:00:00Z",
      "period_end": "2026-03-20T18:00:00Z",
      "sample_count": 42,
      "successes": 38,
      "failures": 4,
      "mean_duration_s": 2.35,
      "mean_value_score": 0.82,
      "error_classes_json": {"timeout": 2, "rate_limit": 2},
      "pushed_at": "2026-03-20T18:05:00Z"
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

## Data Model (if applicable)

### PostgreSQL: `node_measurement_summaries`

```sql
CREATE TABLE node_measurement_summaries (
    id              SERIAL PRIMARY KEY,
    node_id         TEXT NOT NULL,
    decision_point  TEXT NOT NULL,
    slot_id         TEXT NOT NULL,
    period_start    TIMESTAMPTZ NOT NULL,
    period_end      TIMESTAMPTZ NOT NULL,
    sample_count    INTEGER NOT NULL CHECK (sample_count > 0),
    successes       INTEGER NOT NULL CHECK (successes >= 0),
    failures        INTEGER NOT NULL CHECK (failures >= 0),
    mean_duration_s DOUBLE PRECISION,
    mean_value_score DOUBLE PRECISION NOT NULL CHECK (mean_value_score >= 0.0 AND mean_value_score <= 1.0),
    error_classes_json JSONB NOT NULL DEFAULT '{}',
    pushed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_sample_count CHECK (sample_count = successes + failures)
);

CREATE INDEX idx_nms_node_dp ON node_measurement_summaries (node_id, decision_point);
CREATE INDEX idx_nms_pushed_at ON node_measurement_summaries (pushed_at);
```

### Pydantic Models

```yaml
MeasurementSummary:
  properties:
    node_id: { type: string }
    decision_point: { type: string }
    slot_id: { type: string }
    period_start: { type: datetime }
    period_end: { type: datetime }
    sample_count: { type: integer, minimum: 1 }
    successes: { type: integer, minimum: 0 }
    failures: { type: integer, minimum: 0 }
    mean_duration_s: { type: float, nullable: true }
    mean_value_score: { type: float, minimum: 0.0, maximum: 1.0 }
    error_classes_json: { type: dict, default: {} }

MeasurementPushRequest:
  properties:
    summaries: { type: list[MeasurementSummary], min_items: 1 }

MeasurementPushResponse:
  properties:
    stored: { type: integer }
    node_id: { type: string }

MeasurementSummaryStored:
  extends: MeasurementSummary
  properties:
    id: { type: integer }
    pushed_at: { type: datetime }

MeasurementListResponse:
  properties:
    node_id: { type: string }
    summaries: { type: list[MeasurementSummaryStored] }
    total: { type: integer }
    limit: { type: integer }
    offset: { type: integer }
```

### Local State: `~/.coherence-network/last_push.json`

```json
{
  "last_push_utc": "2026-03-20T18:05:00Z"
}
```

## Files to Create/Modify

- `api/app/routers/federation.py` — add POST and GET measurement endpoints
- `api/app/services/federation_service.py` — add `store_measurement_summaries()` and `list_measurement_summaries()` methods
- `api/app/services/federation_push_service.py` — **new** client-side push logic: read SlotSelector files, compute aggregates, POST to hub, update last_push.json
- `api/app/models/federation.py` — add Pydantic models for measurement summaries
- `api/app/db/migrations/add_node_measurement_summaries.sql` — **new** PostgreSQL migration
- `api/tests/test_federation_measurement_push.py` — **new** tests for both hub endpoints and client push logic

## Acceptance Tests

- `api/tests/test_federation_measurement_push.py::test_post_summaries_201` — valid batch returns 201 with stored count.
- `api/tests/test_federation_measurement_push.py::test_post_node_id_mismatch_422` — path vs summary node_id mismatch returns 422.
- `api/tests/test_federation_measurement_push.py::test_post_sample_count_mismatch_422` — `sample_count != successes + failures` returns 422.
- `api/tests/test_federation_measurement_push.py::test_post_empty_batch_422` — empty summaries list returns 422.
- `api/tests/test_federation_measurement_push.py::test_get_summaries_returns_stored` — GET returns previously POSTed summaries.
- `api/tests/test_federation_measurement_push.py::test_get_summaries_filter_by_decision_point` — decision_point query param filters results.
- `api/tests/test_federation_measurement_push.py::test_get_summaries_pagination` — limit/offset pagination works correctly.
- `api/tests/test_federation_measurement_push.py::test_push_aggregates_measurements_correctly` — push client computes correct mean_value_score, mean_duration_s, successes, failures, error_classes_json from raw SlotSelector data.
- `api/tests/test_federation_measurement_push.py::test_push_respects_last_push_timestamp` — only measurements after last_push are included.
- `api/tests/test_federation_measurement_push.py::test_push_updates_last_push_on_success` — last_push.json updated after successful push.
- `api/tests/test_federation_measurement_push.py::test_push_no_update_on_failure` — last_push.json unchanged when hub returns error.
- `api/tests/test_federation_measurement_push.py::test_push_hub_unreachable_no_exception` — connection error logged as warning, no exception raised.

## Concurrency Behavior

- **Read operations** (GET summaries): Safe for concurrent access; standard PostgreSQL read isolation.
- **Write operations** (POST summaries): Each push inserts new rows; no update conflicts. Multiple nodes can push concurrently without contention since rows are partitioned by `node_id`.
- **Client-side push**: Reads SlotSelector files (append-only JSON) without locking. Race with concurrent `record()` calls is benign — at worst, a measurement recorded during push is included in the next push cycle.
- **last_push.json**: Single-writer (the push function); no concurrent access expected on a single node.

## Verification

```bash
cd api && pytest -q tests/test_federation_measurement_push.py
cd api && python -c "
from app.services.federation_push_service import compute_summaries
from pathlib import Path
# Smoke test: compute_summaries with empty dir returns []
assert compute_summaries(Path('/tmp/empty_slot_dir'), None) == []
print('smoke OK')
"
```

## Out of Scope

- Authentication/authorization on the push endpoint (deferred to federation auth spec).
- Hub-to-node feedback or remediation commands based on summaries.
- Real-time streaming of measurements (this is batch push only).
- Compression or delta encoding of summary payloads.
- Retention policies or automatic cleanup of old summaries.
- Aggregation across nodes on the hub side (fleet dashboards).

## Risks and Assumptions

- **Risk**: Large measurement files could cause slow push cycles. *Mitigation*: Summaries are aggregated before sending, reducing payload to one row per `(decision_point, slot_id)` pair per push.
- **Risk**: Clock skew between node and hub could cause `period_start`/`period_end` to look inconsistent. *Mitigation*: All timestamps are UTC ISO 8601; hub stores `pushed_at` from its own clock.
- **Assumption**: SlotSelector measurement files follow the current JSON array format with `slot_id`, `value_score`, `timestamp`, `error_class`, and `duration_s` fields. If the format changes, `federation_push_service.py` must be updated.
- **Assumption**: `~/.coherence-network/` directory exists (created by keystore spec 485). If not, push service creates it.
- **Assumption**: `node_id` is a stable identifier configured per node instance. This spec does not define how node_id is assigned.

## Known Gaps and Follow-up Tasks

- Follow-up task: Add authentication to federation measurement endpoints (bearer token or mTLS).
- Follow-up task: Fleet-level aggregation dashboard that queries `node_measurement_summaries` across all nodes.
- Follow-up task: Retention policy to prune summaries older than N days.
- Follow-up task: Define node_id assignment and registration flow for new nodes.

## Failure/Retry Reflection

- Failure mode: Hub returns 5xx during push.
  - Blind spot: Repeated failures could cause unbounded growth of unpushed measurements.
  - Next action: Log warning with retry-after hint; measurements accumulate locally and are included in the next successful push. Consider adding a `max_measurement_age` filter in a follow-up.

- Failure mode: Corrupted SlotSelector JSON file.
  - Blind spot: One bad file could prevent all summaries from being computed.
  - Next action: Catch `JSONDecodeError` per file, log the error, skip that decision point, and continue with remaining files.

- Failure mode: `last_push.json` is deleted or corrupted.
  - Blind spot: Without last_push, the next push would re-send all historical measurements.
  - Next action: If `last_push.json` is missing or unparseable, default to pushing only the last 24 hours of measurements to avoid a massive initial push.

## Decision Gates (if any)

- Node identity: How is `node_id` assigned? For MVP, assume it is a config value in `.env` or `~/.coherence-network/node.json`. Full registration flow is out of scope.
