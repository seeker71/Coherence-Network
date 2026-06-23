---
id: field-queue-drain
idea_id: federation-and-nodes
status: active
decision: approved-2026-06-23-board-is-the-memory
source:
  - file: form/form-stdlib/field-queue.fk
    symbols: [fq-drain, fq-count, fq-cursor, fq-match?]
  - file: form/form-stdlib/tests/field-queue-band.fk
  - file: specs/field-relay-always-open-connection.md
  - file: scripts/agent-coord.sh
requirements:
  - "A four-way-proven drain recipe selects, on reconnect, exactly the backlog entries a cell missed: addressed to it, unseen (seq > last_seen), and consent-ok (kind in its offered interface), preserving board order"
  - "It is content-blind: the drain reads seq/to/kind only, never the body — the board holds bodies the relay and the drain never inspect"
  - "It yields the drained entries, a count, and a new high-water cursor (max drained seq, else last_seen unchanged) so a re-reconnect does not re-deliver"
  - "Consent stays the gate even in the backlog: an entry whose kind is not offered is never drained"
done_when:
  - "field-queue-band.fk returns 127 on Go, Rust, TS (1 ok, 0 divergent) AND crosses the fourth arm (fkwu) — registered in fourth-arm-bands.txt"
  - "field-queue-band.fk verdict 127 also holds on the native binary lane, bit-identical"
  - "fq-drain preserves order, fq-cursor is the drained high-water, and an un-offered kind is excluded (the band proves count rises only when the interface includes that kind)"
constraints:
  - "Decision only: the recipe performs no I/O; reading/writing the append-only board (scripts/agent-coord.sh / $COHERENCE_COORD) is the carrier"
  - "The board is the memory; do not introduce a new store — the QUEUE verdict (field-relay.fk) already routes offline-consent-ok envelopes to it"
  - "Content-blind: drain selection never reads the envelope body"
  - "Consent (channel-interface-consent) is honored on drain exactly as on live routing — the backlog is not a consent bypass"
---

# Spec: Field queue drain — what a reconnecting cell missed (breath 2)

## Purpose

The relay's QUEUE verdict (`field-relay.fk`) accepts a consent-ok envelope for a known-but-offline cell;
the append-only board is where it rests (the socket is the breath, the board is the memory). When that
cell reconnects it must drain **exactly** what it missed — addressed to it, unseen, still consent-gated,
in order — and advance a cursor so it never re-drains. This spec delivers that selection as a four-way +
native decision body; the board read/write is the carrier (breath 4 wires it into the client's
reconnect handshake).

## Requirements

- [x] **R1 — drain selection, four-way + native.** `form/form-stdlib/field-queue.fk` defines `fq-drain`
  / `fq-count` / `fq-cursor` over (backlog, to, last_seen, iface): select entries to `to`, seq >
  last_seen, kind in iface, preserving order; cursor = drained high-water. Proven 127 four-way + native.
- [x] **R2 — content-blind + consent-gated.** The drain reads seq/to/kind only (never the body), and an
  un-offered kind is never drained — proven in the band (count rises only when the interface admits it).
- [ ] **R3 — board carrier.** Read the append-only board into the backlog shape and persist the cursor
  per cell; the relay's QUEUE verdict appends. (Follow-up — board I/O carrier.)
- [ ] **R4 — client reconnect integration.** On reconnect the client calls `fq-drain` with its last
  cursor and replays the gap, then advances the cursor. (Breath 4 follow-up.)

## Files to Create/Modify

- `form/form-stdlib/field-queue.fk` — new: the drain selection decision recipe.
- `form/form-stdlib/tests/field-queue-band.fk` — new: four-way + native proof band (127).
- `form/fourth-arm-bands.txt` — modify: register the `field-queue` row.
- `specs/field-queue-drain.md` — this contract.

## Acceptance Tests

- `cd form && ./validate.sh form-stdlib/field-queue.fk form-stdlib/tests/field-queue-band.fk` → `1 ok, 0 divergent` → 127, fourth arm four-way.
- `cd form && ./validate.sh --binary ...` → 127, bit-identical.

## Verification

```bash
cd form && ./validate.sh form-stdlib/field-queue.fk form-stdlib/tests/field-queue-band.fk
cd form && ./validate.sh --binary form-stdlib/field-queue.fk form-stdlib/tests/field-queue-band.fk
python3 scripts/validate_spec_quality.py --file specs/field-queue-drain.md
```

## Risks

- **Cursor monotonicity.** Dedup rests on the board assigning a monotonic `seq`; if offsets are not
  monotonic, "unseen" misjudges. Mitigation: the board carrier (R3) assigns append-order offsets; the
  recipe treats seq as an opaque monotonic key.
- **Order depends on board order.** `fq-drain` preserves the backlog's order, so the board must store in
  delivery order. Mitigation: append-only by construction is already in delivery order.
- **A consent narrowing between queue-time and drain-time.** If a cell stops offering a kind after an
  envelope was queued, the drain (using the *current* interface) correctly withholds it — consent is
  evaluated at drain, not frozen at enqueue. This is intended, named here so it is not a surprise.

## Gaps

- **Board read/write carrier is not built** (follow-up task) — `fq-drain` operates on an in-memory
  backlog shape today; the carrier reads the append-only board into it and persists per-cell cursors.
- **Client reconnect integration** (follow-up task, breath 4) — calling `fq-drain` on reconnect and
  replaying the gap lands with the device carriers.

## Out of Scope

- The board storage itself (`scripts/agent-coord.sh` / `$COHERENCE_COORD`) — it already exists; this
  spec is the drain *decision*, not the store.
- Presence/heartbeat semantics — a sibling of breath 2, specced separately if taken.
- The relay routing decision (`field-relay.fk`) and identity verdict (`field-identity.fk`) — kin, not
  this contract.
```
