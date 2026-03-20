# Spec 120: Minimum Federation Layer


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - All requirements implemented and tests pass
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Summary
Remote Coherence instances can register, send lineage links and usage events,
and have them integrated through governance approval. No trust required —
local instance re-computes all valuations from raw data.

## Endpoints
- POST /api/federation/instances
- GET /api/federation/instances
- GET /api/federation/instances/{instance_id}
- POST /api/federation/sync
- GET /api/federation/sync/history

## Data Flow
1. Remote instance registers with local instance
2. Remote sends FederatedPayload (links + events)
3. Each item becomes a governance ChangeRequest (type=FEDERATION_IMPORT)
4. Local operator approves/rejects
5. Approved items are integrated into local lineage
6. Valuations re-computed locally from raw data

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Acceptance Tests

See `api/tests/test_minimum_federation_layer.py` for test cases covering this spec's requirements.


## Verification
- [ ] Instance registration CRUD
- [ ] Payload → ChangeRequest conversion
- [ ] Governance approval → data integration
- [ ] Local valuation re-computation
- [ ] Unregistered instance rejection

## Risks and Assumptions
- Assumes honest timestamps (no clock skew protection yet)
- No signature verification in v1 (public_key field reserved)
- Single-threaded sync (no concurrent payload handling)

## Known Gaps and Follow-up Tasks
- Instance discovery (manual registration only)
- Signature verification
- Conflict resolution for duplicate lineage links
- Rate limiting for sync endpoint
