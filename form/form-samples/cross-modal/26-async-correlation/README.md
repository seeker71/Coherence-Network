# 26-async-correlation — multiple in-flight queries, correlation routing

> *Reply order is not request order; the correlation field is what
> makes the difference safe.*

This walk pushes the L5 session layer of the prior end-to-end channel
walk into the open. Cell A sends THREE queries to Cell B without
waiting for any reply. B answers all three, but appends responses to
A's reply channel in an INTENTIONALLY jumbled order (q3, q1, q2). A
reads everything off the channel and routes each reply back to its
originating query by the correlation field on the RESPONSE.

The proof: arrival order is jumbled, pairing is correct anyway.

## What walked

```
$ ./validate.sh form-stdlib/core.fk form-stdlib/channel.fk \
                form-stdlib/cell-registry.fk form-stdlib/sha256.fk \
                form-stdlib/channel-query.fk form-stdlib/symbols.fk \
                form-samples/cross-modal/26-async-correlation/cell-query-async.fk
  ✓  → queries-sent: 3
       replies-received: 3
       correlations-distinct: 1
       arrival-order-was-jumbled: 1
       all-replies-matched-a-query: 1
       no-duplicate-or-missing-matches: 1
       matched-payload-carries-q1-verb: 1
       7
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels each ran the full seven-assertion protocol.
**Verdict: 7.**

The companion band `form-stdlib/tests/async-correlation-band.fk`
locks the same shape into the auto-validated suite with a five-
assertion verdict.

## The flow

```
                                  L3 REGISTRY              L2 CHANNEL                  L2 CHANNEL
                                  (e2e-async-registry.fkb) (e2e-async-cell-b.fkb)      (e2e-async-cell-a-reply.fkb)
                                       │                       │                            │
  CELL B                               │                       │                            │
  ──────                               │                       │                            │
  register-cell                        │                       │                            │
  (id=3003, path=/tmp/cell-b,          │                       │                            │
   verbs=["answer"])                   │                       │                            │
   ─────── REGISTRATION ──────────────▶                       │                            │
                                                                                            │
  CELL A                                                                                    │
  ──────                                                                                    │
  find-by-capability "answer"                                                               │
   ◀─── REG (id=3003, path=/tmp/cell-b, ["answer"]) ───                                     │
                                                                                            │
  q1 = (cq-query "about"      topic-a "what-is-the-shape")                                  │
  q2 = (cq-query "fetch"      topic-b "give-me-the-content")                                │
  q3 = (cq-query "introspect" topic-c "tell-me-your-state")                                 │
                                                                                            │
  A remembers (corr-1, corr-2, corr-3) where corr_i = (node_inst q_i)                       │
                                                                                            │
  channel-append b-channel q1   ──── QUERY q1 ─────▶                                        │
  channel-append b-channel q2   ──── QUERY q2 ─────▶                                        │
  channel-append b-channel q3   ──── QUERY q3 ─────▶                                        │
                                                                                            │
                                       CELL B HANDLER                                       │
                                       ──────────────                                       │
                                       channel-read its channel → [q1,q2,q3]                │
                                       build resp1 with correlation = (node_inst q1)        │
                                       build resp2 with correlation = (node_inst q2)        │
                                       build resp3 with correlation = (node_inst q3)        │
                                       ───── RESPONSE for q3 ───────────────────────────────▶
                                       ───── RESPONSE for q1 ───────────────────────────────▶
                                       ───── RESPONSE for q2 ───────────────────────────────▶
                                                                                            │
  CELL A                                                                                    │
  ──────                                                                                    │
  channel-read a-reply  → [r_arr_1, r_arr_2, r_arr_3]                                       │
  for each r:                                                                               │
    corr = (node_inst (head (node_children (channel-msg-payload r))))                       │
    find q in {q1,q2,q3} where (node_inst q) == corr                                        │
                                                                                            │
  ✓ r_arr_1.correlation == corr-3  → reply belongs to q3                                    │
  ✓ r_arr_2.correlation == corr-1  → reply belongs to q1                                    │
  ✓ r_arr_3.correlation == corr-2  → reply belongs to q2
```

## The OSI layers exercised

| Layer | What happened in this walk |
|---|---|
| L1 Physical | `write_form_binary` / `read_form_binary` persist the .fkb to disk |
| L2 Data Link | `channel.fk`'s CHANNEL-V0 / CHANNEL-MSG framing carried three QUERY recipes one way and three RESPONSE recipes back |
| L3 Network | `cell-registry.fk`'s `find-by-capability "answer"` resolved A's lookup to B's address |
| **L5 Session** | `cq-response`'s correlation field made it safe for the three RESPONSE messages to arrive in any order. A's correlation map (corr → original query) is the session table |
| L6 Presentation | Form Recipes ARE the wire data; `cq-recipe-content` wraps the verb+topic structural item B sends back |
| L7 Application | The three verbs ("about", "fetch", "introspect") are L7 vocabulary; each query is distinguishable to a reader looking only at the verb |

L5 is the layer this walk makes concrete. Prior walks (21, 25) named
the correlation field but only exercised it through a single
query/response pair, where there was nothing for the field to
correlate against. With three queries in flight, correlation routing
either works or doesn't — and the verdict shows it does, across all
three kernel implementations.

L4 (transport integrity) is still toy — no signing on the wire, no
truncation detection. ed25519 over the packet bytes is the next walk.

## What this proves

1. **Many-in-flight is safe.** Cells can interleave queries without
   blocking on each reply. The channel just accumulates.
2. **Routing is content-addressed.** The correlation seed is
   `(node_inst query-recipe)` — a per-query unique value derived from
   the query's structural identity. Two cells with the same intern
   history compute the same correlation; cross-cell pairing converges.
3. **Arrival order is irrelevant.** B replies in (q3, q1, q2); A
   pairs them back to (q1, q2, q3) by checking the correlation field
   only. No timestamps, no sequence numbers, no shared clock.
4. **Honest absence still works.** A fabricated correlation that
   doesn't match any sent query routes to nothing — the band test
   asserts this in its `bogus-corr` case.

The kernel signal is unchanged from 25 — no new natives needed. This
is composition on top of `channel.fk` + `channel-query.fk`.

## What this is NOT yet

- **Cryptographic correlation.** Today the correlation is the inst
  slot of the query's NodeID — deterministic per kernel because all
  three intern the same query Recipe to NodeIDs whose insts converge
  given the same intern history. A real protocol uses a cryptographic
  fingerprint (e.g. sha256 of the serialized query bytes) so a
  malicious B can't forge a response that A would route to a query B
  never saw. The shape of A's lookup is identical; only the
  fingerprint function changes.
- **In-process orchestration of B.** B's handler is still invoked
  directly. A daemon polling the request channel would loop on
  `channel-read-since`; the recipe-walk is identical, only the
  scheduling differs.
- **No timeout.** If B never replies to one of A's queries, A's map
  entry for that correlation lives forever. Real session layers age
  out unmatched correlations after a deadline.
- **Single writer.** Same caveat as channel.fk — concurrent appenders
  to the same .fkb race on the whole-file rewrite. v0 channels are
  point-to-point.
- **No backpressure.** A can flood B's channel. The channel grows
  unboundedly until something consumes it.

## A small detail this walk makes visible

`cq-response`'s first child is `(intern_trivial_int correlation)`,
and `node_inst` on a trivial-int returns its value. So `(node_inst
(head (node_children response)))` round-trips A's send-time correlation
seed directly. Other callers reaching for the correlation may prefer
`node_value` for the same field — both work for trivial-ints; the
prompt and this sample use `node_inst` because it's what the prior
walks adopted. If a future walk packs correlation as a richer Recipe
(e.g. a sha256 list of bytes), `node_value` becomes the right accessor
and that's a small isolated change.

## Cross-refs

- 21-cell-query-protocol — verb/response vocabulary (L7) and the
  correlation field's first appearance
- 23-cell-registry-osi — L3 addressing
- 24-wire-binary-symbols — wire serialization of recipes
- 25-end-to-end-channel — the prior single-query/single-response
  end-to-end walk this one extends
- `form-stdlib/channel.fk` — L2 channel framing
- `form-stdlib/cell-registry.fk` — L3 directory
- `form-stdlib/channel-query.fk` — L7 vocabulary, correlation field
- `form-stdlib/tests/async-correlation-band.fk` — companion band test
