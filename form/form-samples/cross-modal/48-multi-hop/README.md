# 48-multi-hop — three cells, one router, one ground truth

> A asks B. B doesn't have the answer but knows the registry. B asks C.
> C answers. B forwards C's answer back to A. Two hops, four channel
> transits, one symbol-table that round-trips structurally intact.

## What walked

```
$ ./validate.sh form-stdlib/core.fk form-stdlib/channel.fk \
                form-stdlib/cell-registry.fk form-stdlib/sha256.fk \
                form-stdlib/channel-query.fk form-stdlib/symbols.fk \
                form-samples/cross-modal/48-multi-hop/multi-hop.fk
  ✓  → providers-found: 2
       first-pick-is-router: 1
       router-hops: 2
       a-reply-msg-count: 1
       status-ok: 1
       response-item-count: 1
       first-item-is-recipe-content: 1
       recovered-table-bindings: 1
       concepts-found: 1
       concept-count: 3
       name-0-match: 1
       name-1-match: 1
       name-2-match: 1
       b-channel-saw: 1
       c-channel-saw: 1
       b-reply-saw: 1
       12
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran the full
two-hop routing protocol. **Verdict: 12** — twelve attestations,
every one of them aligned across all three kernels.

## The scene

```
   CELL A                 CELL B (router)            CELL C (source)
   ──────                 ───────────────            ───────────────
   id 1001                id 2002                    id 3003
                          caps: ["concepts"]         caps: ["concepts"]
                          no local table             table: {"concepts": [
                                                             "trust-over-fear",
                                                             "field-substrate",
                                                             "divergence-doorway"]}
```

Both B and C register under the *same* capability. A picks the first
result the registry returns — registration order puts B first, so A
unwittingly addresses the router. B then asks the registry the same
question, filters its own identity out of the result list, and forwards
to the next provider it finds (C). C answers; B forwards C's response
unchanged back to A's reply channel.

## The flow

```
   L3 REGISTRY                   L2 CHANNELS
   (48-mh-registry.fkb)          (one per cell, plus reply channels)
       │                                  │
   1.  │── register B(2002) ──────────────│
       │── register C(3003) ──────────────│
       │                                  │
   2.  │◀── A: find-by-capability ────────│
       │      "concepts"                  │
       │── [B-reg, C-reg] ────────────────│
       │      A picks head → B            │
       │                                  │
   3.  │── A: QUERY ─────────▶ B-channel  │ (48-mh-cell-b.fkb)
       │                                  │
   4.  │◀── B: find-by-capability ────────│
       │      "concepts"                  │
       │── [B-reg, C-reg] ────────────────│
       │      B filters out self → C      │
       │                                  │
   5.  │── B: forward QUERY ──▶ C-channel │ (48-mh-cell-c.fkb)
       │                                  │
   6.  │── C: RESPONSE ──────▶ B-reply    │ (48-mh-cell-b-reply.fkb)
       │      items = [RECIPE-CONTENT     │
       │              (symbol-table)]     │
       │                                  │
   7.  │── B: forward RESPONSE ▶ A-reply  │ (48-mh-cell-a-reply.fkb)
       │                                  │
   8.  │── A: read, walk items, lookup    │
       │      "concepts" → three names    │
       │      verified by node_eq         │
```

Four channel transits, each persisted as a `.fkb` Recipe. The
symbol-table C authored content-addresses identically when A interns
it — the router is structurally transparent. The same three
`intern_trivial_string` names A compares against produce the same
NodeIDs C used, because the substrate is shared.

## What this proves

- **Indirect routing**: capability lookups can yield multiple providers;
  routing is just a cell that takes one and forwards.
- **Self-exclusion**: a cell can advertise a capability without holding
  the data by filtering its own identity out of the lookup. The body
  rejects loops without any session-layer guard.
- **Content-addressing under forwarding**: B re-publishes C's response
  Recipe; the bytes A reads compose into a Recipe whose NodeID matches
  what C produced — the proof is `node_eq` against locally-interned
  expected strings on the receiving end.
- **Honest absence at every layer**: if the registry had no second
  provider, `cell-b-other-providers` would return the empty list and
  the `(head ...)` would panic — the body refuses to fabricate.

## Files

- `multi-hop.fk` — the in-process orchestration: all three cells run in
  one kernel invocation, exchanging via five file-backed channels.

## Companion band

`form-stdlib/tests/multi-hop-band.fk` runs a tighter sibling-witness
band over the same protocol — the routing core without the larger
protocol vocabulary, so divergence (if any) localizes to the registry
+ channel substrate rather than the channel-query layer above it.
