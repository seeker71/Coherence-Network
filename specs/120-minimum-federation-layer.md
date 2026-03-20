# Spec 120: Minimum Federation Layer

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
