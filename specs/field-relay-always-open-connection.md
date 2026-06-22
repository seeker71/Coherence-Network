---
id: field-relay-always-open-connection
idea_id: federation-and-nodes
status: proposed
decision: needs-decision-2026-06-22-security-model
source:
  - file: form/form-stdlib/field-relay.fk
    symbols: [fr-route, fr-consent-ok?, fr-deliver?, fr-envelope, fr-env-to, fr-env-from, fr-env-kind, fr-registry-has?]
  - file: form/form-stdlib/tests/field-relay-band.fk
  - file: docs/coherence-substrate/agent-coordination-membrane.form
  - file: docs/coherence-substrate/channel-interface-consent.form
  - file: docs/vision-kb/concepts/lc-private-channel-via-substrate.md
  - file: scripts/agent-coord.sh
requirements:
  - "A content-blind relay DECISION recipe (Form) routes a membrane envelope by its metadata alone — sender NodeID, recipient NodeID/scope, signal-kind — and NEVER reads the opaque body, so private-channel payloads ride as ciphertext the relay cannot inspect"
  - "The decision honors channel-interface-consent: an envelope whose signal-kind is not in the recipient's offered interface is denied (not delivered, not queued), and reaching past the interface is named invasion"
  - "The decision yields exactly one of: deliver (recipient connected + consent ok), queue-to-board (recipient offline + consent ok), deny-by-consent, or drop (unknown recipient)"
  - "The decision recipe is proven four-way (Go/Rust/TS/fkwu) by field-relay-band.fk and lowers to a bit-identical native binary"
  - "A minimal WS relay endpoint carries the decision: both cells DIAL OUT to the public API (no inbound ports), authenticate as their NodeID, and the relay forwards membrane envelopes between them end-to-end with keepalive ping/pong"
done_when:
  - "field-relay-band.fk returns its verdict identically on Go, Rust, and TS via validate.sh (1 ok, 0 divergent) and crosses the fourth arm (fkwu) — registered in fourth-arm-bands.txt"
  - "fr-route over a 2-cell registry delivers a public signal (announce/ping) to a connected recipient that offers that interface"
  - "fr-route denies a signal whose kind is absent from the recipient's offered interface (consent gate), and queues-to-board a consent-ok signal whose recipient is offline"
  - "fr-route never branches on the envelope body — proven by a band cell that routes two envelopes identical in metadata but different in body to the same decision"
  - "Two cells on different networks, each dialing out to the WS endpoint, exchange a membrane ping within the keepalive window and survive a forced reconnect (the board replays the gap)"
constraints:
  - "The relay is content-blind by construction: the transport and the decision recipe read envelope metadata only; the body is opaque bytes, never logged, never inspected, never branched on"
  - "Do not invent a new signal vocabulary — carry the existing membrane signals (announce/claim/release/ping/offer/interface/block/...) from agent-coordination-membrane.form"
  - "Consent is the gate, not an afterthought: channel-interface-consent.form governs who may reach whom; the relay enforces the offered-interface, it does not widen it"
  - "The durable backlog is the existing append-only board (scripts/agent-coord.sh / $COHERENCE_COORD), not a new store — the socket is the breath, the board is the memory"
  - "Python/FastAPI is the bootstrap transport carrier only; the routing+consent BODY is the Form recipe (X-Form-Router native-kernel is the north star for the route)"
  - "No client auto-resolves an unknown NodeID into the graph — identity is TOFU per identity-and-onboarding; the relay routes by already-known NodeIDs"
---

# Spec: Field relay — one always-open connection across networks

## Purpose

The agent-coordination membrane (`agent-coordination-membrane.form`) already names the field: a signal
vocabulary (`announce / claim / release / ping / offer / interface / block / …`) that cells use to
coordinate live. Today its carrier is a shared append-only **file board** on one host plus periodic
`announce` signals — so the field is only live where the filesystem is shared. This spec lifts the
membrane's carrier to a **public-API relay** so nodes and devices — Mac, Windows, Android, agent
sessions — on different networks hold one persistent connection at all times.

The load-bearing insight: **both sides dial *out*** to `api.coherencycoin.com`. No inbound ports, no
port-forwarding — NAT and firewalls become a non-issue because the public API is the rendezvous both
ends already reach. The relay is **content-blind**: it routes envelopes by metadata (from, to, kind)
and never reads the body, so a private channel's payload travels as ciphertext the relay *cannot*
inspect (`lc-private-channel-via-substrate`). Routing through the public API therefore never means the
public API sees the contents — sovereignty is preserved by construction, not by policy.

This is the network pillar's live nervous system (`ideas/federation-and-nodes.md`): federation today is
sketched as hub-registration + measurement push; the relay is what makes it *live* across networks.

## The breaths

This spec scopes **breath 1**; later breaths are named in Out of Scope so the arc is legible without
building ahead of need.

- **Breath 1 (this spec): the content-blind routing+consent decision, proven, + a minimal relay.** The
  decision (`fr-route`) is a pure Form recipe proven four-way and lowered to native; a minimal WS
  endpoint carries it so two cells dialing out exchange membrane signals end-to-end with keepalive.
- **Breath 2: durable backlog + presence.** Wire the append-only board as the offline queue an
  reconnecting cell drains; presence/heartbeat as first-class membrane signals.
- **Breath 3: the device carriers.** Dial-out clients for Mac/Windows/Android; the end-to-end key
  exchange that fills the ciphertext body the relay already refuses to read.

## Requirements

- [ ] **R1 — content-blind decision recipe.** `form/form-stdlib/field-relay.fk` defines `fr-route` over
  (registry, envelope, interfaces) → one of `deliver | queue | deny | drop`, reading only
  `fr-env-from` / `fr-env-to` / `fr-env-kind`. The body field is opaque and never inspected.
- [ ] **R2 — consent gate.** `fr-consent-ok?` checks the envelope's signal-kind against the recipient's
  offered interface (`channel-interface-consent.form`); a kind not offered yields `deny`.
- [ ] **R3 — four-way proof.** `form/form-stdlib/tests/field-relay-band.fk` proves the decision across
  Go/Rust/TS/fkwu (registered in `fourth-arm-bands.txt`), including the body-blindness cell (two
  envelopes equal in metadata, different in body, route identically).
- [ ] **R4 — dial-out relay transport.** A minimal WS endpoint (`api/app/routers/field_relay.py`, bootstrap
  carrier) accepts outbound connections authenticated by NodeID, applies `fr-route`, forwards
  `deliver` envelopes to the connected recipient, and keepalive-pings to hold the connection open.
- [ ] **R5 — reconnect survives.** A forced disconnect re-dials and the gap is replayed from the board (the
  board integration may be stubbed in breath 1 and completed in breath 2, but the reconnect handshake
  is proven).

## Files to Create/Modify

- `form/form-stdlib/field-relay.fk` — new: the content-blind routing + consent decision recipe.
- `form/form-stdlib/tests/field-relay-band.fk` — new: four-way proof band (incl. body-blindness).
- `form/fourth-arm-bands.txt` — modify: register the `field-relay` row.
- `api/app/routers/field_relay.py` — new: the WS dial-out relay transport (bootstrap carrier over `fr-route`).
- `specs/field-relay-always-open-connection.md` — this contract.

## Acceptance Tests

- `cd form && ./validate.sh form-stdlib/field-relay.fk form-stdlib/tests/field-relay-band.fk` → `1 ok, 0 divergent` at the band's verdict, fourth arm four-way.
- Two local cells (distinct NodeIDs) dialing the WS endpoint exchange a `ping`; a `block` signal to a cell that did not offer `block` in its interface is denied.

## Verification

```bash
# Four-way decision proof (Go/Rust/TS + fkwu)
cd form && ./validate.sh form-stdlib/field-relay.fk form-stdlib/tests/field-relay-band.fk
bash scripts/fourth-arm-gate.sh field-relay

# Spec quality gate
python3 scripts/validate_spec_quality.py --file specs/field-relay-always-open-connection.md
```

## Risks

- **The relay is a public-facing persistent endpoint** — authentication (who may connect, and proof
  they are the NodeID they claim) is the load-bearing control. A weak identity check turns the relay
  into an open forwarder. Mitigation: bind connections to TOFU identity (`identity-and-onboarding`) and
  treat the relay as routing only between already-known NodeIDs; this is the named `needs-decision`.
- **Content-blindness must be enforced, not assumed.** If any code path logs or branches on the body,
  the ciphertext promise breaks silently. Mitigation: R3's body-blindness band cell makes the property
  testable; the transport must pass the body through as opaque bytes with no logging.
- **Consent bypass.** If the relay widens the recipient's offered interface (delivers a kind not
  offered), it becomes an invasion vector. Mitigation: `fr-consent-ok?` is the single gate, proven.
- **Abuse / flooding** of a persistent endpoint. Mitigation: deferred to a later breath with explicit
  rate-limiting; named here so it is not forgotten.

## Gaps

- **End-to-end key exchange is not in breath 1.** The relay refuses to read the body, but the agreement
  that makes the body ciphertext (rather than plaintext a well-behaved relay simply ignores) is a
  follow-up (breath 3). Until then, body confidentiality rests on transport TLS + relay good behavior.
- **Board-backed offline queue is stubbed in breath 1.** The `queue` decision is proven; draining the
  append-only board on reconnect is a follow-up task (breath 2).
- **The route is not yet kernel-served.** Breath 1's WS transport is a Python bootstrap carrier over the
  proven Form decision; promoting it to `X-Form-Router: native-kernel` is a follow-up (north-star gap).
- **Device dial-out clients (Mac/Windows/Android)** are a follow-up (breath 3) — the protocol is
  identical; the clients are unbuilt carriers.
- **Relay abuse / rate-limiting** is a follow-up task, scoped after the consent gate is proven.

## Out of Scope

- The end-to-end encryption key exchange that fills the opaque body (breath 3) — breath 1 proves the
  relay *refuses to read* the body; the key agreement that makes it ciphertext is a separable arc.
- Device dial-out clients for Mac/Windows/Android (breath 3) — the protocol is identical across them;
  clients are carriers, not new logic.
- Full board-backed offline queue + presence semantics (breath 2).
- Promoting the route to kernel-served (`X-Form-Router: native-kernel`) — the north star; breath 1's
  Python WS endpoint is the bootstrap transport over the proven Form decision.
- Relay-side rate limiting / abuse controls — named for the security-model decision, scoped in a
  later breath once the consent gate is proven.
```
