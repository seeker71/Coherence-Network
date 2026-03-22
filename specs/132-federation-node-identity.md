# Spec: Federation Node Identity and Registration

## Purpose

Federation nodes need a stable identity so the hub can track participating compute environments (Mac, Windows, VPS) across restarts and reconnects. This spec defines deterministic node identity derivation, local persistence, registration/heartbeat API contracts, and the hub storage model so federation health and node capability routing can be implemented reliably.

## Requirements

- [ ] Each node derives `node_id` as `sha256(hostname + mac_address).hexdigest()[:16]`.
- [ ] Each node persists `node_id` to `~/.coherence-network/node_id` and reuses it for future process runs.
- [ ] Node registration is performed via `POST /api/federation/nodes` with `node_id`, `hostname`, `os_type`, `providers`, and `capabilities`.
- [ ] Hub stores registrations in PostgreSQL table `federation_nodes` with columns: `node_id` (PK), `hostname`, `os_type`, `providers_json`, `capabilities_json`, `registered_at`, `last_seen_at`, `status`.
- [ ] Hub upserts on registration: first registration sets `registered_at`; repeat registration updates mutable fields and refreshes `last_seen_at`.
- [ ] Node heartbeat is performed via `POST /api/federation/nodes/{node_id}/heartbeat`.
- [ ] Heartbeat updates `last_seen_at` and can refresh `status` to `online`.
- [ ] Registration and heartbeat endpoints return deterministic JSON responses suitable for automation.

## Research Inputs (Required)

- `2026-03-21` - [Spec Template](specs/TEMPLATE.md) - required structure and quality gates for all specs.
- `2026-03-21` - [Spec 120: Minimum Federation Layer](specs/120-minimum-federation-layer.md) - baseline federation model and hub/node directionality.
- `2026-03-21` - [Spec 131: Federation Measurement Push](specs/131-federation-measurement-push.md) - adjacent federation transport and endpoint conventions to keep API consistent.

## Task Card (Required)

```yaml
goal: Implement stable node identity plus hub registration/heartbeat for federation nodes
files_allowed:
  - api/app/models/federation.py
  - api/app/routers/federation.py
  - api/app/services/federation_service.py
  - api/app/services/node_identity_service.py
  - api/app/db/migrations/add_federation_nodes.sql
  - api/tests/test_federation_node_identity.py
done_when:
  - node_id is deterministically derived and persisted to ~/.coherence-network/node_id
  - POST /api/federation/nodes registers or updates node record in federation_nodes
  - POST /api/federation/nodes/{node_id}/heartbeat updates last_seen_at and status
commands:
  - cd api && pytest -q tests/test_federation_node_identity.py
constraints:
  - do not add authentication in this spec; treat trust/auth as follow-up
  - preserve compatibility with existing federation endpoints
  - no scope creep outside node identity, registration, and heartbeat
```

## API Contract (if applicable)

### `POST /api/federation/nodes`

Registers a node with the federation hub.

**Request Body**
```json
{
  "node_id": "a1b2c3d4e5f60789",
  "hostname": "macbook-pro-dev",
  "os_type": "macos",
  "providers": ["openai", "openrouter"],
  "capabilities": {
    "python": true,
    "docker": true,
    "max_parallel_tasks": 2
  }
}
```

**Response 201**
```json
{
  "node_id": "a1b2c3d4e5f60789",
  "status": "online",
  "registered_at": "2026-03-21T15:00:00Z",
  "last_seen_at": "2026-03-21T15:00:00Z"
}
```

**Response 200** (existing node updated)
```json
{
  "node_id": "a1b2c3d4e5f60789",
  "status": "online",
  "registered_at": "2026-03-20T12:00:00Z",
  "last_seen_at": "2026-03-21T15:00:00Z"
}
```

### `POST /api/federation/nodes/{node_id}/heartbeat`

Refreshes liveness for a previously registered node.

**Request**
- `node_id`: string (path)

**Request Body**
```json
{
  "status": "online"
}
```

**Response 200**
```json
{
  "node_id": "a1b2c3d4e5f60789",
  "status": "online",
  "last_seen_at": "2026-03-21T15:05:00Z"
}
```

**Response 404**
```json
{
  "detail": "Node not found"
}
```

## Data Model (if applicable)

### Local node identity file

Path: `~/.coherence-network/node_id`

Contents:
```text
a1b2c3d4e5f60789
```

### PostgreSQL: `federation_nodes`

```sql
CREATE TABLE federation_nodes (
    node_id           TEXT PRIMARY KEY,
    hostname          TEXT NOT NULL,
    os_type           TEXT NOT NULL,
    providers_json    JSONB NOT NULL DEFAULT '[]'::jsonb,
    capabilities_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    registered_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status            TEXT NOT NULL DEFAULT 'online'
);

CREATE INDEX idx_federation_nodes_status ON federation_nodes (status);
CREATE INDEX idx_federation_nodes_last_seen_at ON federation_nodes (last_seen_at);
```

### Pydantic model shape

```yaml
FederationNodeRegisterRequest:
  properties:
    node_id: { type: string, min_length: 16, max_length: 16 }
    hostname: { type: string }
    os_type: { type: string, enum: [macos, windows, linux, vps] }
    providers: { type: list[string] }
    capabilities: { type: dict }

FederationNodeRegisterResponse:
  properties:
    node_id: { type: string }
    status: { type: string }
    registered_at: { type: datetime }
    last_seen_at: { type: datetime }

FederationNodeHeartbeatRequest:
  properties:
    status: { type: string, default: online }
```

## Files to Create/Modify

- `api/app/services/node_identity_service.py` - new helper for identity derivation and local persistence.
- `api/app/models/federation.py` - request/response models for registration and heartbeat.
- `api/app/routers/federation.py` - add registration and heartbeat endpoints.
- `api/app/services/federation_service.py` - add upsert and heartbeat persistence logic.
- `api/app/db/migrations/add_federation_nodes.sql` - migration for `federation_nodes` table.
- `api/tests/test_federation_node_identity.py` - endpoint and identity persistence tests.

## Acceptance Tests

- `api/tests/test_federation_node_identity.py::test_node_id_is_stable_for_same_host_and_mac`
- `api/tests/test_federation_node_identity.py::test_node_id_persisted_and_reused`
- `api/tests/test_federation_node_identity.py::test_register_node_creates_new_record`
- `api/tests/test_federation_node_identity.py::test_register_node_updates_existing_record`
- `api/tests/test_federation_node_identity.py::test_heartbeat_updates_last_seen`
- `api/tests/test_federation_node_identity.py::test_heartbeat_unknown_node_404`

## Concurrency Behavior

- **Identity creation**: single-writer local file behavior; if two local processes race on first write, both derive the same value so eventual consistency is stable.
- **Registration writes**: upsert semantics on `node_id` primary key prevent duplicate logical node rows.
- **Heartbeat writes**: last-write-wins on `last_seen_at`/`status`; concurrent heartbeats are safe and monotonic in normal clock conditions.

## Verification

```bash
python3 scripts/validate_spec_quality.py
```

## Out of Scope

- Mutual TLS, API key, or signed registration payload authentication.
- Node capability negotiation protocol beyond initial static payload.
- Automatic stale-node pruning/offline detection scheduler.
- Hub-to-node command channel or job dispatching.

## Risks and Assumptions

- Risk: MAC address access can vary by runtime/container context. Mitigation: abstract MAC retrieval in one service and fail with explicit error when unavailable.
- Risk: Hostname changes can alter derived identity if persistence is bypassed. Mitigation: always prefer persisted `~/.coherence-network/node_id` over re-derivation when file exists.
- Assumption: Node environments can write to `~/.coherence-network/`.
- Assumption: `providers` and `capabilities` are small JSON payloads suitable for direct `jsonb` storage.

## Known Gaps and Follow-up Tasks

- Follow-up: add authenticated registration/heartbeat trust model.
- Follow-up: define offline transition policy (e.g., mark offline when `last_seen_at` exceeds threshold).
- Follow-up: add fleet query endpoints for listing and filtering nodes by status/provider/capability.

## Failure/Retry Reflection

- Failure mode: inability to read MAC address.
  - Blind spot: node starts without stable identity in restricted environment.
  - Next action: return explicit startup error and operator guidance to configure fallback identifier source.

- Failure mode: registration endpoint unreachable.
  - Blind spot: node continues local execution but is invisible to hub.
  - Next action: keep node running, log warning, retry registration with bounded backoff.

- Failure mode: heartbeat for unknown `node_id`.
  - Blind spot: node_id file deleted or hub state reset.
  - Next action: client falls back to registration flow, then resumes heartbeat cadence.

## Decision Gates (if any)

- Confirm whether `os_type` should remain free-form string or be strictly enumerated at API level.
- Confirm canonical heartbeat interval and stale-node timeout for `online` to `offline` transition policy.
