---
idea_id: federation-and-nodes
status: done
source:
  - file: api/app/routers/federation.py
    symbols: [register_instance, list_instances, get_instance, receive_payload, list_sync_history]
  - file: api/app/services/federation_service.py
    symbols: [register_instance, list_instances, get_instance, receive_payload, list_sync_history, check_trust_level, _ensure_federation_sync_history_columns]
  - file: api/app/services/governance_service.py
    symbols: [_apply_change_request, create_change_request]
  - file: api/app/models/federation.py
    symbols: [FederatedInstance, FederatedPayload, FederationSyncResult]
requirements:
  - "POST /api/federation/instances registers a peer fork by instance_id, name, endpoint_url"
  - "GET /api/federation/instances lists registered peer instances"
  - "GET /api/federation/instances/{instance_id} returns a single peer record"
  - "POST /api/federation/sync receives a FederatedPayload carrying telemetry (lineage_links, usage_events) and substance (concept_proposals, spec_proposals, idea_proposals, teaching_proposals)"
  - "Every received item becomes a governance ChangeRequest of type FEDERATION_IMPORT"
  - "Telemetry items use auto_apply_on_approval=True — they land in the lineage graph once quorum approves"
  - "Substance items use auto_apply_on_approval=False — the proposal body is held in change_request.payload until a maintainer walks it into the repo as a PR"
  - "FEDERATION_IMPORT change requests enforce required_approvals ≥ 2"
  - "Payloads from unregistered peers are rejected; all items counted as rejected with no governance requests created"
  - "Peers with trust_level below 'pending' are rejected with ValueError"
  - "GET /api/federation/sync-history returns past sync operations with link / event / proposal counts"
done_when:
  - "POST /api/federation/instances returns 201 with the registered instance shape"
  - "POST /api/federation/sync with a 4-substance payload returns FederationSyncResult with proposals_received=4, accepted=4, governance_requests_created=4"
  - "Each substance ChangeRequest has required_approvals=2 and auto_apply_on_approval=False"
  - "Two YES votes on a substance ChangeRequest flip status to APPROVED but applied_result remains None until manual apply"
  - "Manual apply of a substance ChangeRequest returns kind=federation_{type}, action=stored, id=<proposal id>"
  - "POST /api/federation/sync with an unregistered source_instance_id returns FederationSyncResult with rejected = item count and governance_requests_created=0"
  - "federation_sync_history rows include the proposals_received column; ALTER TABLE migration applies in place on older snapshots"
  - "all federation + governance tests pass"
test: "cd api && python -m pytest tests/test_federation_substance.py tests/test_federation_layer.py -q"
constraints:
  - "The API never writes peer-authored substance into the deployed corpus on its own — substance is held by governance and walked into the repo by a maintainer"
  - "Do not add new ChangeRequestType enum values — discriminate by federation_type inside the payload (existing pattern)"
  - "Trust level required for sync is 'pending'; verified/trusted are reserved for stricter surfaces (measurements aggregation)"
  - "Substance proposal payloads carry the full markdown body in payload.data so a maintainer can author the file locally without re-fetching"
---

> **Parent idea**: [federation-and-nodes](../ideas/federation-and-nodes.md)
> **Source**: [`api/app/routers/federation.py`](../api/app/routers/federation.py) | [`api/app/services/federation_service.py`](../api/app/services/federation_service.py) | [`api/app/services/governance_service.py`](../api/app/services/governance_service.py) | [`api/app/models/federation.py`](../api/app/models/federation.py)
> **Walked practice**: [`docs/FEDERATING-INSTANCES.md`](../docs/FEDERATING-INSTANCES.md)

# Federation Instance Exchange — Telemetry and Substance Between Peer Forks

## Purpose

Two Coherence Network forks can peer with each other and exchange both **telemetry** (lineage links, usage events) and **substance** (concept, spec, idea, teaching proposals) through one governance-gated REST surface — without either fork having to give up sovereignty over its own body.

The companion `federation-network-layer` spec covers *compute nodes* (workers running `local_runner.py` against a hub). This spec covers *federated instances* (full forks of the repo each running their own API, web, and database, peering at the substance level).

## What's Built

Four surfaces compose the instance-exchange path:

1. **Peer registration** — `POST /api/federation/instances` records a remote instance with its `endpoint_url`, `public_key` (reserved for future signature verification), and a `trust_level` that starts at `pending`. Listing and lookup endpoints expose the registry.

2. **Payload envelope** — `POST /api/federation/sync` accepts a `FederatedPayload` containing two layers. Telemetry layer: `lineage_links`, `usage_events`. Substance layer: `concept_proposals`, `spec_proposals`, `idea_proposals`, `teaching_proposals`. Each item in each list becomes a governance `ChangeRequest` of type `FEDERATION_IMPORT`.

3. **Governance applier** — `governance_service._apply_change_request` discriminates `FEDERATION_IMPORT` by the `federation_type` field inside the payload. `lineage_link` and `usage_event` apply directly into the local lineage graph via `value_lineage_service`. `concept_proposal`, `spec_proposal`, `idea_proposal`, `teaching_proposal` return `action=stored` — the proposal is held by governance; the API never writes peer-authored substance into the deployed corpus.

4. **Sync audit** — every received payload is recorded in `federation_sync_history` with counts of links, events, proposals, governance requests created, accepted, rejected, and any errors. The router exposes `GET /api/federation/sync-history` for inspection.

## Requirements

- [x] `POST /api/federation/instances` registers a peer fork by `instance_id`, `name`, `endpoint_url`.
- [x] `GET /api/federation/instances` lists registered peers; `GET /api/federation/instances/{id}` returns one.
- [x] `POST /api/federation/sync` accepts a `FederatedPayload` carrying both telemetry and substance layers.
- [x] Every received item becomes a governance `ChangeRequest` of type `FEDERATION_IMPORT` with `required_approvals >= 2`.
- [x] Telemetry items use `auto_apply_on_approval=True` — they land in the lineage graph once quorum approves.
- [x] Substance items use `auto_apply_on_approval=False` — held in `change_request.payload.data` until a maintainer authors the file in the repo.
- [x] Payloads from unregistered peers are rejected with no governance requests created.
- [x] Peers with `trust_level` below `pending` are rejected with `ValueError`.
- [x] `GET /api/federation/sync-history` returns past sync operations with link/event/proposal counts.
- [x] Schema migration `_ensure_federation_sync_history_columns` backfills `proposals_received` on older snapshots in place.

## Why two layers, two apply modes

Telemetry is small, structured, and verifiable on its face — a lineage link or a usage event is either valid in the local graph or rejected. Once two reviewers approve a telemetry item, the applier writes it automatically.

Substance is body-level material — markdown a peer would like this body to absorb. Auto-applying a peer's concept into the deployed corpus would mean the API writes peer-authored content into the body without a human walking it. That's not the gesture the body wants. Instead, the substance proposal is held: approved means *quorum agrees this should be considered*; applied requires a maintainer to read the body, author the file in the repo, run the relevant sync script (`sync_kb_to_db.py`, `generate_repo_indexes.py`), and merge a PR. Then the change request is marked `APPLIED`.

This keeps the gate where it belongs: peer instances can propose; the receiving body decides what to weave in.

## Trust levels

`trust_level` on a peer instance is one of `unknown` < `pending` < `verified` < `trusted`. Sync requires `pending` or higher; lower trust levels rejected with `ValueError`. Measurement aggregation (a separate surface, in `federation-aggregated-visibility`) requires `verified`. Upgrading trust is a manual operator gesture today; the trust handshake is a future breath.

## Substance proposal shape

A substance proposal dict carries the markdown body plus enough metadata for a maintainer to author the file locally. Suggested shape:

```json
{
  "id": "lc-some-concept",
  "title": "…",
  "body_markdown": "…",
  "frontmatter": { "...optional structured fields..." },
  "origin_url": "https://peer.example/vision/lc-some-concept",
  "license": "CC-BY-SA-4.0"
}
```

`id` becomes the maintainer's filename hint (`docs/vision-kb/concepts/{id}.md` for concept, `specs/{id}.md` for spec, etc.). `body_markdown` is the full file content. `origin_url` preserves attribution back to the source instance.

## Files to Modify

- `api/app/routers/federation.py` — exposes `/federation/instances`, `/federation/sync`, `/federation/sync-history` routes.
- `api/app/services/federation_service.py` — implements `register_instance`, `receive_payload`, sync history, in-place column backfill.
- `api/app/services/governance_service.py` — applier branches on `federation_type`; substance returns `action=stored`.
- `api/app/models/federation.py` — `FederatedInstance`, `FederatedPayload` (two layers), `FederationSyncResult`.
- `api/tests/test_federation_substance.py` — round-trip proof of the substance contract.
- `api/tests/test_federation_layer.py` — node-level federation surface (separate but adjacent).
- `docs/FEDERATING-INSTANCES.md` — walked practice for two operators.

## Acceptance Tests

- `api/tests/test_federation_substance.py::test_substance_payload_creates_governance_proposals` — a 4-substance payload returns `proposals_received=4`, `governance_requests_created=4`, all `auto_apply_on_approval=False` with `required_approvals >= 2`.
- `api/tests/test_federation_substance.py::test_substance_proposal_approves_but_does_not_auto_apply` — two YES votes flip status to APPROVED with `applied_result=None`.
- `api/tests/test_federation_substance.py::test_substance_applier_records_stored_with_proposal_id` — manual apply returns `kind=federation_{type}, action=stored, id=<proposal id>`.
- `api/tests/test_federation_substance.py::test_substance_payload_from_unknown_instance_is_rejected` — unregistered peers reject substance with zero governance requests.

## Verification

```bash
cd api && python -m pytest tests/test_federation_substance.py tests/test_federation_layer.py -q
python3 scripts/validate_spec_quality.py --file specs/federation-instance-exchange.md
```

## Out of Scope

- `.well-known/coherence-federation` auto-discovery (future breath).
- Mutual trust handshake (future breath).
- Scheduled push-pull sync deltas (future breath).
- MCP tools for agent-driven peering (future breath).
- Signature verification of incoming payloads — the `signature` field is reserved on the envelope but not yet enforced.

Each is its own breath. None is rushed.

## Risks and Assumptions

- **Risk: peer payload spoofing.** Today the `signature` field is reserved but not verified. A malicious actor could forge a payload claiming to come from a registered peer. Mitigation today: `required_approvals >= 2` on every FEDERATION_IMPORT plus the substance `auto_apply=False` gate. Mitigation tomorrow: HMAC verification of the payload envelope before the governance request is created.
- **Risk: substance proposal staleness.** A proposal can sit in APPROVED status indefinitely if no maintainer walks it into the repo. Mitigation: surface APPROVED-not-APPLIED counts on the governance dashboard; let body presence (not bureaucracy) clear the queue.
- **Risk: telemetry auto-apply on bad data.** Lineage links and usage events auto-apply once approved. A bug in the applier or in the peer's data could corrupt the local lineage graph. Mitigation: applier wraps each apply in a try/except; failures are logged to the change request and surfaced in `sync_history.errors`.
- **Assumption: peers operate in good faith.** The substance gate (human-walked PR) means even a compromised peer cannot directly write to this body's corpus. Telemetry is more exposed but its damage radius is limited to the lineage graph.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_federation_well_known_discovery_001` — operators today must know each other's URLs and explicitly register. A `.well-known/coherence-federation` manifest endpoint would let agents propose peering through one gesture.
- Follow-up task: `task_federation_trust_handshake_002` — trust upgrade is one-sided today. A mutual handshake (peer A proposes, peer B accepts, both upgrade atomically) is the next breath.
- Follow-up task: `task_federation_signature_verification_003` — the `signature` field on `FederatedPayload` is reserved but not enforced. HMAC-SHA256 (already in `verify_payload_signature`) wants wiring into `receive_payload` once peer keys are exchanged.
- Follow-up task: `task_federation_mcp_peering_tools_004` — agents today do federation work via shell + curl. First-class MCP tools (`coherence_federation_propose_peer`, `coherence_federation_send_substance`) would let agents offer peering as a real action.
- Follow-up task: `task_federation_substance_pr_drafter_005` — a maintainer surface on `/governance` showing substance proposals waiting to be walked into the repo, with a one-click "draft PR" affordance.

## Companions

- [`specs/federation-network-layer.md`](federation-network-layer.md) — compute-node surfaces (registration, heartbeat, measurements, strategy propagation, inter-node messaging)
- [`specs/federation-aggregated-visibility.md`](federation-aggregated-visibility.md) — network-wide stats surfacing
- [`docs/FEDERATING-INSTANCES.md`](../docs/FEDERATING-INSTANCES.md) — walked practice for two operators
