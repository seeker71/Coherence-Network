---
idea_id: mesh-federation-ingress-healing
status: active
source:
  - file: api/app/routers/federation.py
    symbols: [get_messages()]
  - file: scripts/mesh_command_receiver.sh
    symbols: [fetch_inbox(), cycle()]
  - file: scripts/install_mesh_command_receiver.sh
    symbols: []
requirements:
  - "Federation inbox observation can be explicitly non-consuming."
  - "The device receiver defaults to the canonical local NodeID file before a legacy alias."
  - "Transient federation API failures receive bounded retries without losing queued work."
done_when:
  - "Focused API and receiver tests pass."
  - "The receiver prints the canonical NodeID from an isolated local identity file."
  - 'pytest_passes("api/tests/test_federation_message_readback.py")'
  - 'pytest_passes("api/tests/test_mesh_command_receiver.py")'
test: "cd api && python3 -m pytest tests/test_federation_message_readback.py tests/test_mesh_command_receiver.py -q"
constraints:
  - "Preserve consuming reads as the backward-compatible default."
  - "Do not add a second message service or identity registry."
  - "Only change files listed in this spec."
---

# Spec: Mesh Federation Ingress Healing

## Purpose

A live federation attempt exposed three coupled carrier wounds: observing a
recipient inbox marked messages as read, the Mac receiver polled a legacy alias
instead of its registered NodeID, and one transient API restart ended a poll
without retry. Heal those seams in their existing homes.

## Requirements

- [ ] **R1:** `GET /api/federation/nodes/{node_id}/messages` accepts
  `mark_read=false`; returned messages remain unread until a consuming read.
- [ ] **R2:** Existing callers retain `mark_read=true` by default.
- [ ] **R3:** The receiver resolves identity in this order: `MR_NODE_ID`, the
  first non-empty line of `~/.coherence-network/node_id`, then `sema-macos`.
- [ ] **R4:** The installer uses the same identity order.
- [ ] **R5:** Inbox polling retries transient empty/failed reads a bounded four
  times before recording one strained-edge failure.
- [ ] **R6:** `--identity` exposes the receiver's enacted identity without
  polling or executing work.

## Files

- `api/app/routers/federation.py`
- `api/tests/test_federation_message_readback.py`
- `api/tests/test_mesh_command_receiver.py`
- `scripts/mesh_command_receiver.sh`
- `scripts/install_mesh_command_receiver.sh`
- `specs/mesh-federation-ingress-healing.md`
- `docs/system_audit/commit_evidence_2026-07-21_mesh-federation-ingress-healing.json`

## Verification

```bash
cd api && python3 -m pytest tests/test_federation_message_readback.py tests/test_mesh_command_receiver.py -q
python3 scripts/validate_spec_quality.py --file specs/mesh-federation-ingress-healing.md
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-07-21_mesh-federation-ingress-healing.json
```

## Acceptance

- A non-consuming inbox read returns the offered message twice without adding
  the recipient to `read_by`; the default consuming read then removes it from
  the unread set.
- With no environment override, the receiver reports the NodeID held in the
  local identity file. `MR_NODE_ID` remains the explicit highest-priority
  override, and `sema-macos` remains only the compatibility fallback.
- A receiver whose first two inbox requests fail and whose third succeeds exits
  cleanly after exactly three attempts and records no terminal bus failure.

## Risks

- Existing diagnostic readers may rely on GET marking messages read. The
  default remains consuming; observation becomes non-consuming only when the
  caller explicitly sends `mark_read=false`.
- A stale local NodeID file could redirect a receiver. The environment override
  remains available for deliberate carrier identity, and the `--identity`
  probe makes the enacted value inspectable before launch.
- Retries may delay a genuinely unavailable bus. Attempts are capped at four
  with short bounded backoff; queued work remains durable in PostgreSQL.

## Gaps

- Delivery and `read_by` remain transport observations, not application-level
  acknowledgements. The `nothing | 0 | 1 | node` response belongs to the
  recipient protocol and is not fabricated here.
- Already-installed launch agents need one installer refresh to inherit the
  canonical NodeID. The source fix does not silently rewrite a running process.
- Public deployment observation freshness is a separate deployment-witness
  concern and is not claimed by this ingress repair.

## Out of Scope

- Executing remote commands.
- Replacing the PostgreSQL message store.
- Treating transport delivery as an application acknowledgement.
