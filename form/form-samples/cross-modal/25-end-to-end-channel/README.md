# 25-end-to-end-channel — full L1→L7 channel walk

> *"next breath"*  — Urs

This walk wires every layer we've built into one query/response loop.
Cell A finds Cell B through the registry, asks a question over a
file-backed channel, B handles it, returns a symbol-table response,
A parses the items and looks up symbols.

## What walked

```
$ ./validate.sh form-stdlib/core.fk form-stdlib/channel.fk \
                form-stdlib/cell-registry.fk form-stdlib/sha256.fk \
                form-stdlib/channel-query.fk form-stdlib/symbols.fk \
                form-samples/cross-modal/25-end-to-end-channel/end-to-end.fk
  ✓  → cells-handling-symbols: 1
       reply-msgs-count: 1
       response-item-count: 1
       first-item-is-recipe-content: 1
       recovered-table-bindings: 2
       concepts-found: 1
       concept-count: 3
       third-concept-matches: 1
       presences-found: 1
       presence-count: 2
       unknown-found: 0
       8
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels each ran the full eight-assertion protocol.
**Verdict: 8.**

## The flow

```
                                  L3 REGISTRY          L2 CHANNEL              L2 CHANNEL
                                  (e2e-registry.fkb)   (e2e-cell-b.fkb)        (e2e-cell-a-reply.fkb)
                                       │                    │                       │
  CELL B                               │                    │                       │
  ──────                               │                    │                       │
  register-cell                        │                    │                       │
  (id=2002, path=/tmp/cell-b,          │                    │                       │
   verbs=["symbols"])                  │                    │                       │
   ─────── REGISTRATION ──────────────▶                    │                       │
                                                                                    │
  CELL A                                                                            │
  ──────                                                                            │
  find-by-capability "symbols"                                                      │
   ◀─── REG (id=2002, path=/tmp/cell-b, ["symbols"]) ───                            │
                                                                                    │
  q = (cq-query "symbols" topic empty)                                              │
  channel-append b-channel (channel-message q)                                      │
   ──────── QUERY recipe via .fkb ────────────▶                                     │
                                                                                    │
                                       CELL B HANDLER                               │
                                       ──────────────                               │
                                       channel-read its channel                     │
                                       unwrap CHANNEL-MSG                           │
                                       read query                                   │
                                       build symbol-table:                          │
                                         "concepts" → [3 strings]                   │
                                         "presences" → [2 strings]                  │
                                       wrap as RECIPE-CONTENT item                  │
                                       build RESPONSE(corr, "ok", [item])           │
                                       channel-append a-reply ───── RESPONSE ──────▶
                                                                                    │
  CELL A                                                                            │
  ──────                                                                            │
  channel-read a-reply                                                              │
  unwrap CHANNEL-MSG                                                                │
  walk RESPONSE: items[0]                                                           │
  classify by node_category → "recipe-content"                                      │
  unwrap → symbol-table                                                             │
  symbol-lookup "concepts" → [3 strings]                                            │
  symbol-lookup "presences" → [2 strings]                                           │
  symbol-lookup "unknown-key" → SYMBOL-NOT-FOUND ✓
```

## The OSI layers exercised

| Layer | What happened in this walk |
|---|---|
| L1 Physical | `write_form_binary` / `read_form_binary` persist the .fkb to disk |
| L2 Data Link | `channel.fk`'s CHANNEL-V0 / CHANNEL-MSG framing carried the QUERY and the RESPONSE |
| L3 Network | `cell-registry.fk`'s `find-by-capability "symbols"` resolved A's question to B's address |
| L6 Presentation | Form Recipes ARE the wire data; `cq-recipe-content` wrapped B's symbol-table; the substrate's content-addressing made cross-cell NodeID resolution sovereign |
| L7 Application | `channel-query.fk`'s QUERY/RESPONSE Blueprints + the verb "symbols"; `symbols.fk`'s `symbol-lookup` extracted the values A wanted |

L4 (transport integrity) and L5 (session correlation) are present in
the protocol's shape — the RESPONSE carries a correlation field; the
toy hash-fold in earlier walks is the transport fingerprint — but
this demo doesn't exercise them directly. Adding ed25519-signed
packets + correlation-keyed reply matching is its own next walk.

## What this proves

Cells in this body can now:

1. **Find each other** by declared capability (L3, opt-in addressing).
2. **Speak to each other** via a content-addressed channel format
   (L2 over L1).
3. **Carry rich responses** containing substrate-refs / novel
   blueprints / recipe content / external URIs / cell refs (L6).
4. **Use a shared verb vocabulary** (L7) where both ends understand
   the question without negotiating a schema.
5. **Share named content** (symbols) that converges across cells via
   substrate-resident strings — both sender and receiver intern the
   same name to the same NodeID.

All of this without any new kernel natives in this breath — the
building blocks from prior walks composed cleanly.

## What this is NOT yet

- **In-process orchestration.** B's handler is invoked directly
  rather than running as a daemon polling its channel. Real
  distributed deployment runs B in a separate process that loops
  on `channel-read`; the recipe-walk is identical, only the
  scheduling differs.
- **No correlation matching.** A's reply pulls the first response on
  its reply channel. With multiple in-flight queries, the correlation
  field would route replies to the right asker.
- **No signature on the wire bytes.** A tampered .fkb between
  channel-append and channel-read isn't detected. ed25519 over the
  packet is the cryptographic next walk.
- **Single-writer assumption.** `channel.fk` rewrites the whole .fkb
  on every append; concurrent appenders race. Real multi-writer needs
  file locking or a queue.

## A small fix that landed alongside this walk

`form-stdlib/cell-registry.fk`'s `reg-channel-path` and `reg-identity`
accessors switched from `node_inst` (returns the inst slot — a string-
table index for trivial-strings) to `node_value` (returns the actual
value — the path string content). Go happened to work coincidentally
with the wrong accessor; Rust + TS were strict and surfaced the bug
during this end-to-end walk. Pre-existing 23-cell-registry-osi sample
didn't print the channel-path so it never hit the bug. Fixed now.

## Cross-refs

- 21-cell-query-protocol — verb/response vocabulary (L7)
- 22-form-to-host-asm — JIT path to scale the recipe-walk to host speed
- 23-cell-registry-osi — L3 addressing
- 24-wire-binary-symbols — symbols + recipe_to_bytes (the wire layer)
- `form-stdlib/channel.fk` — L2 channel framing
- `form-stdlib/cell-registry.fk` — L3 directory
- `form-stdlib/channel-query.fk` — L7 vocabulary
- `form-stdlib/symbols.fk` — symbol-table over the wire
