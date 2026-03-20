# Spec 123: Transparent Audit Ledger -- Zero Hidden State

**Depends on**: Spec 119 (Coherence Credit), Spec 094 (Governance)
**Depended on by**: Spec 121 (OpenClaw Marketplace -- fork audit trail), Spec 122 (Treasury -- financial audit trail)

## Purpose

The Coherence Network handles CC-denominated value flows, governance decisions, idea valuations, and crypto treasury operations. Currently, these events are logged in service-specific stores with no unified audit trail and no tamper-evidence mechanism. This spec introduces an append-only audit ledger that records every CC transaction, governance vote, idea valuation change, and fund flow with cryptographic hash chaining for tamper detection. Any user can query the ledger and independently verify that no entries have been inserted, modified, or deleted. The principle is zero hidden state: if it affects value, reputation, or governance, it is in the ledger. Without this, users have no way to verify that the system operates honestly, which undermines the trust required for crypto-backed CC and cross-instance idea sharing.

## Requirements

- [ ] **R1: Append-only CC transaction ledger** -- Every CC transaction (mint, burn, transfer, attribution payout) is recorded with: `{entry_id, entry_type, timestamp, sender_id, receiver_id, amount_cc, reason, reference_id, hash, previous_hash}`. Entries are immutable once written. The ledger is stored in PostgreSQL with an `immutable` table policy (no UPDATE or DELETE allowed at the application layer).
- [ ] **R2: Hash chain integrity** -- Each ledger entry includes a SHA-256 hash computed over `(previous_hash + entry_type + timestamp + sender_id + receiver_id + amount_cc + reason + reference_id)`. The first entry uses a genesis hash (SHA-256 of "coherence-network-genesis"). Any tampering breaks the chain and is detectable by recomputing hashes from genesis.
- [ ] **R3: Governance vote audit** -- Every governance vote (ChangeRequestVote) is recorded in the ledger with entry_type `GOVERNANCE_VOTE`, including voter_id, decision, rationale, and the change_request_id as reference_id. The CC amount field is 0 for non-financial votes.
- [ ] **R4: Idea valuation change tracking** -- Every change to an idea's potential_value, actual_value, estimated_cost, or confidence is recorded with entry_type `VALUATION_CHANGE`. The entry includes the old value, new value, delta, field name, and the idea_id as reference_id.
- [ ] **R5: Treasury fund flow audit** -- Every deposit, withdrawal, minting, and burning operation from spec 122 is recorded with entry_type in `{DEPOSIT_INITIATED, DEPOSIT_CONFIRMED, CC_MINTED, WITHDRAWAL_REQUESTED, WITHDRAWAL_APPROVED, WITHDRAWAL_COMPLETED, CC_BURNED}`. The reference_id links to the deposit_id or withdrawal_id.
- [ ] **R6: Public query API** -- Three query endpoints:
  - `GET /api/audit/transactions` -- CC transactions with pagination, date range filter, user filter, entry_type filter
  - `GET /api/audit/governance` -- governance votes with pagination, change_request_id filter, voter_id filter
  - `GET /api/audit/treasury` -- treasury fund flows with pagination, currency filter, status filter
  All endpoints return entries with their hash and previous_hash for client-side verification.
- [ ] **R7: Hash chain verification endpoint** -- `GET /api/audit/verify` recomputes the hash chain from genesis (or from a given start entry_id) and returns `{verified: bool, entries_checked: int, first_invalid_entry_id: string | null, computed_head_hash: string}`. This allows any user to independently verify ledger integrity.
- [ ] **R8: Audit snapshots** -- Every 24 hours (configurable), the system produces a signed snapshot: `{snapshot_id, timestamp, entry_count, head_hash, head_entry_id, signature}`. The signature is produced using the instance's private key (same key infrastructure as federation). Snapshots are queryable via `GET /api/audit/snapshots`. Snapshots serve as checkpoints for efficient verification (verify from last snapshot instead of genesis).
- [ ] **R9: Entry metadata** -- Each ledger entry includes optional `metadata` dict for entry-type-specific data (e.g., old_value/new_value for valuation changes, tx_hash for treasury operations, tags for marketplace events). Metadata is stored as JSONB and is included in hash computation.
- [ ] **R10: Ledger export** -- `GET /api/audit/export` returns the full ledger (or a date range) as newline-delimited JSON for offline verification. Rate-limited to 1 export per user per hour.
- [ ] **R11: Write-only service interface** -- The audit ledger exposes an internal `append_entry()` function used by other services (treasury, marketplace, governance, idea service). This function is write-only: no service can read-then-modify. Each call returns the new entry's hash for caller confirmation.
- [ ] **R12: Tamper detection alert** -- If `GET /api/audit/verify` detects a broken hash chain, the system logs a CRITICAL alert, pauses all CC-affecting operations, and sets a system-wide `integrity_compromised` flag queryable via `GET /api/health`.

## Research Inputs (Required)

- `2026-03-18` - Spec 119 Coherence Credit -- CC transaction types that must be audited
- `2026-03-18` - Spec 094 Governance -- ChangeRequestVote model providing vote data structure
- `2026-03-20` - Spec 122 Treasury -- deposit/withdrawal operations requiring financial audit trail
- `2026-03-20` - RFC 6962 Certificate Transparency -- Merkle tree append-only log design pattern
- `2026-03-20` - PostgreSQL row-level security -- mechanism for enforcing append-only at DB layer
- `2026-03-20` - RFC 7515 JSON Web Signature -- JWS format for signed audit snapshots

## Task Card (Required)

```yaml
goal: Implement append-only audit ledger with hash chaining, public query API, verification, and signed snapshots
files_allowed:
  - api/app/models/audit_ledger.py
  - api/app/services/audit_ledger_service.py
  - api/app/routers/audit.py
  - api/app/main.py
  - api/app/services/treasury_service.py
  - api/app/services/marketplace_service.py
  - api/app/services/governance_service.py
  - api/app/services/idea_service.py
  - api/app/routers/health.py
  - api/tests/test_audit_ledger.py
  - specs/123-transparent-audit-ledger.md
done_when:
  - append_entry() writes immutable entry with correct hash chain
  - GET /api/audit/transactions returns paginated CC transactions
  - GET /api/audit/governance returns paginated governance votes
  - GET /api/audit/treasury returns paginated fund flows
  - GET /api/audit/verify recomputes hash chain and reports integrity
  - GET /api/audit/snapshots returns signed daily snapshots
  - GET /api/audit/export streams NDJSON of ledger entries
  - Tamper detection sets integrity_compromised flag
  - All tests pass
commands:
  - python3 -m pytest api/tests/test_audit_ledger.py -x -v
  - python3 -m pytest api/tests/test_governance_api.py -x -q
constraints:
  - No UPDATE or DELETE on audit ledger table at application layer
  - Hash chain must be correct even under concurrent writes (sequential entry_id assignment)
  - Snapshot signing uses same key infrastructure as federation (spec 120)
  - Export endpoint rate-limited to 1 per user per hour
```

## API Contract

### `GET /api/audit/transactions`

Query CC transaction audit entries.

**Request (query params)**
- `page`: int (default 1)
- `page_size`: int (default 50, max 500)
- `entry_type`: string (optional, filter by specific CC transaction type)
- `user_id`: string (optional, matches sender_id or receiver_id)
- `from_date`: ISO 8601 datetime (optional)
- `to_date`: ISO 8601 datetime (optional)
- `min_amount`: float (optional)

**Response 200**
```json
{
  "entries": [
    {
      "entry_id": "aud_00001",
      "entry_type": "CC_MINTED",
      "timestamp": "2026-03-20T12:45:00Z",
      "sender_id": "SYSTEM",
      "receiver_id": "alice",
      "amount_cc": 833.33,
      "reason": "BTC deposit confirmed",
      "reference_id": "dep_abc123",
      "metadata": {
        "currency": "BTC",
        "crypto_amount": 0.05,
        "tx_hash": "abc123..."
      },
      "hash": "sha256:a1b2c3...",
      "previous_hash": "sha256:genesis..."
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "head_hash": "sha256:a1b2c3..."
}
```

### `GET /api/audit/governance`

Query governance vote audit entries.

**Request (query params)**
- `page`: int (default 1)
- `page_size`: int (default 50, max 500)
- `change_request_id`: string (optional)
- `voter_id`: string (optional)
- `decision`: string (optional, "yes" or "no")
- `from_date`: ISO 8601 datetime (optional)
- `to_date`: ISO 8601 datetime (optional)

**Response 200**
```json
{
  "entries": [
    {
      "entry_id": "aud_00042",
      "entry_type": "GOVERNANCE_VOTE",
      "timestamp": "2026-03-20T15:30:00Z",
      "sender_id": "bob",
      "receiver_id": "GOVERNANCE",
      "amount_cc": 0.0,
      "reason": "Vote YES on withdrawal request",
      "reference_id": "cr_gov123",
      "metadata": {
        "decision": "yes",
        "rationale": "Legitimate withdrawal, identity verified",
        "change_request_type": "TREASURY_WITHDRAWAL"
      },
      "hash": "sha256:d4e5f6...",
      "previous_hash": "sha256:c3d4e5..."
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "head_hash": "sha256:d4e5f6..."
}
```

### `GET /api/audit/treasury`

Query treasury fund flow audit entries.

**Request (query params)**
- `page`: int (default 1)
- `page_size`: int (default 50, max 500)
- `entry_type`: string (optional, e.g. "DEPOSIT_CONFIRMED", "WITHDRAWAL_COMPLETED")
- `currency`: string (optional, "BTC" or "ETH")
- `from_date`: ISO 8601 datetime (optional)
- `to_date`: ISO 8601 datetime (optional)

**Response 200**
```json
{
  "entries": [
    {
      "entry_id": "aud_00001",
      "entry_type": "DEPOSIT_CONFIRMED",
      "timestamp": "2026-03-20T12:45:00Z",
      "sender_id": "EXTERNAL",
      "receiver_id": "alice",
      "amount_cc": 833.33,
      "reason": "BTC deposit 0.05 BTC confirmed at 6/6 confirmations",
      "reference_id": "dep_abc123",
      "metadata": {
        "currency": "BTC",
        "crypto_amount": 0.05,
        "tx_hash": "abc123...",
        "locked_rate_cc_per_btc": 16666.67
      },
      "hash": "sha256:a1b2c3...",
      "previous_hash": "sha256:genesis..."
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "head_hash": "sha256:a1b2c3..."
}
```

### `GET /api/audit/verify`

Verify hash chain integrity.

**Request (query params)**
- `from_entry_id`: string (optional, default: genesis)
- `to_entry_id`: string (optional, default: head)

**Response 200**
```json
{
  "verified": true,
  "entries_checked": 1042,
  "from_entry_id": "aud_00001",
  "to_entry_id": "aud_01042",
  "computed_head_hash": "sha256:f7g8h9...",
  "expected_head_hash": "sha256:f7g8h9...",
  "first_invalid_entry_id": null,
  "verification_duration_ms": 230,
  "verified_at": "2026-03-20T16:00:00Z"
}
```

**Response 200 (integrity failure)**
```json
{
  "verified": false,
  "entries_checked": 500,
  "from_entry_id": "aud_00001",
  "to_entry_id": "aud_01042",
  "computed_head_hash": "sha256:MISMATCH...",
  "expected_head_hash": "sha256:f7g8h9...",
  "first_invalid_entry_id": "aud_00501",
  "verification_duration_ms": 120,
  "verified_at": "2026-03-20T16:00:00Z"
}
```

### `GET /api/audit/snapshots`

List signed audit snapshots.

**Request (query params)**
- `page`: int (default 1)
- `page_size`: int (default 10, max 50)

**Response 200**
```json
{
  "snapshots": [
    {
      "snapshot_id": "snap_20260320",
      "timestamp": "2026-03-20T00:00:00Z",
      "entry_count": 1042,
      "head_hash": "sha256:f7g8h9...",
      "head_entry_id": "aud_01042",
      "signature": "jws:eyJhbGciOiJFZDI1NTE5In0...",
      "signer_instance_id": "instance-001"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 10
}
```

### `GET /api/audit/export`

Export ledger as newline-delimited JSON.

**Request (query params)**
- `from_date`: ISO 8601 datetime (optional)
- `to_date`: ISO 8601 datetime (optional)

**Response 200** (Content-Type: application/x-ndjson)
```
{"entry_id":"aud_00001","entry_type":"CC_MINTED","timestamp":"2026-03-20T12:45:00Z","sender_id":"SYSTEM","receiver_id":"alice","amount_cc":833.33,"reason":"BTC deposit confirmed","reference_id":"dep_abc123","metadata":{},"hash":"sha256:a1b2c3...","previous_hash":"sha256:genesis..."}
{"entry_id":"aud_00002",...}
```

**Response 429**
```json
{ "detail": "Export rate limit exceeded. Try again in 42 minutes." }
```

## Data Model

```yaml
AuditEntry:
  properties:
    entry_id: { type: string, format: "aud_{sequential_int}", description: "Monotonically increasing, gap-free" }
    entry_type: { type: string, enum: [
      "CC_MINTED", "CC_BURNED", "CC_TRANSFER", "CC_ATTRIBUTION",
      "GOVERNANCE_VOTE", "GOVERNANCE_DECISION",
      "VALUATION_CHANGE",
      "DEPOSIT_INITIATED", "DEPOSIT_CONFIRMED",
      "WITHDRAWAL_REQUESTED", "WITHDRAWAL_APPROVED", "WITHDRAWAL_COMPLETED", "WITHDRAWAL_REJECTED",
      "MARKETPLACE_PUBLISH", "MARKETPLACE_FORK",
      "SNAPSHOT_CREATED"
    ]}
    timestamp: { type: datetime, description: "UTC, set by server" }
    sender_id: { type: string, min_length: 1, description: "Originator (user, SYSTEM, or EXTERNAL)" }
    receiver_id: { type: string, min_length: 1, description: "Recipient (user, GOVERNANCE, TREASURY, or SYSTEM)" }
    amount_cc: { type: float, ge: 0, description: "CC amount (0.0 for non-financial entries)" }
    reason: { type: string, min_length: 1, max_length: 1000 }
    reference_id: { type: string, description: "Links to source record (deposit_id, withdrawal_id, idea_id, etc.)" }
    metadata: { type: "dict[str, Any]", default: {}, description: "Entry-type-specific structured data" }
    hash: { type: string, format: "sha256:{hex}" }
    previous_hash: { type: string, format: "sha256:{hex}" }

AuditSnapshot:
  properties:
    snapshot_id: { type: string, format: "snap_{date}" }
    timestamp: { type: datetime }
    entry_count: { type: int, ge: 0 }
    head_hash: { type: string }
    head_entry_id: { type: string }
    signature: { type: string, format: "jws:{payload}" }
    signer_instance_id: { type: string }

VerificationResult:
  properties:
    verified: { type: bool }
    entries_checked: { type: int, ge: 0 }
    from_entry_id: { type: string }
    to_entry_id: { type: string }
    computed_head_hash: { type: string }
    expected_head_hash: { type: string }
    first_invalid_entry_id: { type: "string | null" }
    verification_duration_ms: { type: int }
    verified_at: { type: datetime }
```

## Files to Create/Modify

- `api/app/models/audit_ledger.py` -- Pydantic models: AuditEntry, AuditSnapshot, VerificationResult, AuditEntryCreate (internal)
- `api/app/services/audit_ledger_service.py` -- append_entry(), verify_chain(), create_snapshot(), query helpers, export stream, tamper detection alert
- `api/app/routers/audit.py` -- route handlers for all audit endpoints
- `api/app/main.py` -- wire audit router
- `api/app/services/treasury_service.py` -- call append_entry() on deposit/withdrawal/mint/burn events
- `api/app/services/marketplace_service.py` -- call append_entry() on publish/fork events
- `api/app/services/governance_service.py` -- call append_entry() on vote/decision events
- `api/app/services/idea_service.py` -- call append_entry() on valuation changes
- `api/app/routers/health.py` -- add integrity_compromised flag to health check
- `api/tests/test_audit_ledger.py` -- contract tests for all requirements

## Acceptance Tests

- `api/tests/test_audit_ledger.py::test_append_entry_returns_hash` -- append produces entry with valid SHA-256 hash
- `api/tests/test_audit_ledger.py::test_hash_chain_links_correctly` -- each entry's previous_hash matches prior entry's hash
- `api/tests/test_audit_ledger.py::test_genesis_entry_uses_genesis_hash` -- first entry chains from known genesis hash
- `api/tests/test_audit_ledger.py::test_entry_immutable` -- attempting to update or delete entry raises error
- `api/tests/test_audit_ledger.py::test_tamper_detection` -- modifying an entry mid-chain causes verify to return verified=false
- `api/tests/test_audit_ledger.py::test_tamper_detection_sets_integrity_flag` -- broken chain sets integrity_compromised on health endpoint
- `api/tests/test_audit_ledger.py::test_query_transactions_pagination` -- page/page_size work correctly
- `api/tests/test_audit_ledger.py::test_query_transactions_date_filter` -- from_date/to_date filter correctly
- `api/tests/test_audit_ledger.py::test_query_transactions_user_filter` -- user_id matches sender or receiver
- `api/tests/test_audit_ledger.py::test_query_governance_votes` -- governance entries returned with correct metadata
- `api/tests/test_audit_ledger.py::test_query_treasury_flows` -- treasury entries returned with correct metadata
- `api/tests/test_audit_ledger.py::test_verify_full_chain` -- verify from genesis returns verified=true for clean ledger
- `api/tests/test_audit_ledger.py::test_verify_partial_chain` -- verify from snapshot checkpoint works
- `api/tests/test_audit_ledger.py::test_snapshot_creation` -- snapshot includes correct head_hash and signature
- `api/tests/test_audit_ledger.py::test_snapshot_signature_verifiable` -- JWS signature can be verified with instance public key
- `api/tests/test_audit_ledger.py::test_export_ndjson_format` -- export returns valid NDJSON with all fields
- `api/tests/test_audit_ledger.py::test_export_rate_limit` -- second export within 1 hour returns 429
- `api/tests/test_audit_ledger.py::test_metadata_included_in_hash` -- metadata is part of hash computation
- `api/tests/test_audit_ledger.py::test_concurrent_appends_sequential` -- concurrent appends produce gap-free sequential IDs
- `api/tests/test_audit_ledger.py::test_cc_mint_creates_audit_entry` -- minting CC via treasury produces CC_MINTED audit entry
- `api/tests/test_audit_ledger.py::test_governance_vote_creates_audit_entry` -- voting creates GOVERNANCE_VOTE audit entry
- `api/tests/test_audit_ledger.py::test_valuation_change_creates_audit_entry` -- idea value update creates VALUATION_CHANGE entry

## Concurrency Behavior

- **Append operations**: Must be serialized to maintain gap-free sequential entry_ids and correct hash chaining. Implementation uses a database-level serial sequence and row-level advisory lock on the head entry. This is a strict requirement -- broken ordering invalidates the hash chain.
- **Read operations**: Safe for concurrent access; reads may see slightly stale data during concurrent appends (acceptable).
- **Verification**: Read-only; can run concurrently with appends. Verification result may not include entries appended during verification (acceptable -- re-verify if needed).
- **Snapshot creation**: Acquires read lock on head entry, computes snapshot, releases. Concurrent appends block briefly during snapshot creation.

## Failure and Retry Behavior

- **Append failure (DB unavailable)**: The calling service receives an error and must decide whether to proceed without audit (NOT recommended for financial operations). Treasury and withdrawal operations MUST abort if append fails.
- **Append failure (hash computation error)**: Should never happen (SHA-256 is deterministic). If it does, log CRITICAL error, abort the operation.
- **Verification timeout**: Large ledgers may take time to verify. Timeout at 5 minutes, return partial result with entries_checked count. Client can resume from last checked entry.
- **Snapshot signing failure**: If signing key unavailable, create unsigned snapshot with signature="UNSIGNED" and log warning. Unsigned snapshots are not trusted for verification checkpoints.
- **Export timeout**: Stream response so partial exports are usable. Client can resume with from_date set to last received entry timestamp.

## Verification

```bash
python3 -m pytest api/tests/test_audit_ledger.py -x -v
python3 -m pytest api/tests/test_governance_api.py -x -q
python3 scripts/validate_spec_quality.py --file specs/123-transparent-audit-ledger.md
```

Manual verification:
- Append 100 entries, run verify, confirm verified=true.
- Manually corrupt one entry in the database, run verify, confirm verified=false with correct first_invalid_entry_id.
- Trigger a CC mint (via treasury deposit test), confirm audit entry appears in `GET /api/audit/transactions`.
- Export ledger as NDJSON, recompute hashes offline, confirm chain integrity.
- Create snapshot, verify JWS signature with instance public key.

## Out of Scope

- Merkle tree (using linear hash chain for simplicity; Merkle tree is a future optimization for log(n) proofs)
- Cross-instance audit federation (each instance has its own ledger; cross-verification is future work)
- Automated regulatory compliance reporting
- Audit entry deletion or archival (append-only means forever, storage growth is a known trade-off)
- Real-time streaming of audit events via WebSocket
- Client-side verification library (users use the API or export + offline tools)

## Risks and Assumptions

- **Risk: Storage growth** -- Append-only ledger grows unboundedly. At 1000 entries/day with ~1KB per entry, that is ~365MB/year. Acceptable for years. If needed, old entries can be archived to cold storage with only the hash chain preserved in the active DB.
- **Risk: Hash chain performance** -- Full chain verification is O(n). At 1M entries, verification takes ~30 seconds. Mitigation: snapshots provide checkpoints; verify from last snapshot instead of genesis.
- **Risk: Serialization bottleneck** -- Sequential append with advisory lock limits write throughput. At expected volume (<100 writes/second), this is not a concern. If volume grows, batch appends with a write-ahead buffer.
- **Risk: Clock skew** -- Entries use server-generated timestamps. If the server clock skews, timestamps may be non-monotonic. Mitigation: entry_id is the authoritative ordering, not timestamp.
- **Risk: Database admin bypass** -- A database administrator could directly modify rows, bypassing application-layer immutability. Mitigation: PostgreSQL row-level security policies prevent UPDATE/DELETE even for admin roles. Snapshots provide external checkpoints. Long-term: anchor snapshot hashes on a public blockchain.
- **Assumption**: PostgreSQL is available and reliable. The audit ledger is not designed for a distributed/partitioned database scenario.
- **Assumption**: SHA-256 is collision-resistant for the foreseeable future. If SHA-256 is broken, migrate to SHA-3 with a new genesis entry referencing the old chain's head.
- **Assumption**: The JWS signing key is the same as the federation instance key from spec 120. If federation key management changes, snapshot signing must be updated.

## Known Gaps and Follow-up Tasks

- Follow-up task: Merkle tree optimization for O(log n) inclusion proofs
- Follow-up task: Cross-instance audit comparison (compare head hashes between federated instances)
- Follow-up task: Public blockchain anchoring (publish daily snapshot hash to Bitcoin or Ethereum)
- Follow-up task: Client-side verification CLI tool for offline audit
- Follow-up task: Audit entry archival strategy for multi-year storage
- Follow-up task: Write-ahead buffer for high-throughput append scenarios
- Follow-up task: Automated daily snapshot scheduling (cron job or background task)

## Failure/Retry Reflection

- Failure mode: Concurrent high-volume appends cause advisory lock contention, slowing all audited operations
- Blind spot: Advisory lock hold time depends on hash computation + DB write; under load this could cascade
- Next action: Profile append latency under load (target <5ms per entry); if exceeded, implement batch append with 100ms collection window

## Decision Gates

- **DG1**: PostgreSQL row-level security policy for immutability -- needs DBA approval for production deployment
- **DG2**: Snapshot signing key management -- reuse federation key or separate audit key? Needs security review
- **DG3**: Public blockchain anchoring timeline -- not required for MVP but should be on the roadmap
