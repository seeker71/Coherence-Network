# 40-kv-store — a cell that holds state, answers questions about it, lets another cell mutate it

> The first reusable cell pattern. Not a one-shot protocol demo —
> a HABITABLE cell. Cell K exposes "kv-set" and "kv-get"; Cell A
> discovers K by capability and threads a sequence of mutations and
> reads through file-backed channels. K's state is the value passed
> between calls; the body of Form is functional, but state shows
> up as a value you keep.

## What walked

```
$ ./validate.sh form-stdlib/core.fk form-stdlib/channel.fk \
                form-stdlib/cell-registry.fk form-stdlib/sha256.fk \
                form-stdlib/channel-query.fk form-stdlib/symbols.fk \
                form-samples/cross-modal/40-kv-store/kv-store.fk
  ✓  ...+kv-store.fk
     → kv-cells-found: 1
       table-0-bindings: 0
       step1-set-name-status-ok: 1
       table-1-bindings: 1
       step2-set-color-status-ok: 1
       table-2-bindings: 2
       step3-get-name-status-ok: 1
       step3-get-name-value-ok: 1
       step4-get-color-status-ok: 1
       step4-get-color-value-ok: 1
       step5-get-unknown-status-not-known: 1
       7
  1 ok, 0 divergent — kernels agree on every sample.
```

**Verdict: 7** — two sets acknowledged, two gets with matching values,
one miss honest-absent. Sibling parity across Go, Rust, TypeScript.

## The shape

```
                    REGISTRY (.fkb)
                    ────────────────
                K registers as
                ["kv-set", "kv-get"]
                    │
                    ▼
                A finds-by-capability "kv-set"  ──┐
                    │                             │
                    │   k-channel ◄── kv-set/kv-get queries
                    ▼                             ▲
                    K (handler)                   │
                    │                             A
                    │   a-reply ──► kv responses ─┘
                    ▼
                table → table' → table'' → ...
                    (state threaded as value)
```

K is a cell, not a service. The handler is a Form function that takes
the current `(table, query)` and returns `(new-table, response)`. K
holds no mutable global; the orchestrator threads the table through
each step. In a long-lived daemon, K would persist the table back to
its own .fkb after each mutation; here the in-process thread IS the
persistence.

## The walk

| Step | A's ask | K's table after | A's response |
|-----:|---------|:---------------:|:-------------|
| 0 | (initial) | `{}` | — |
| 1 | `(kv-set "name" "alice")` | `{name: alice}` | status `ok` |
| 2 | `(kv-set "color" "blue")` | `{name: alice, color: blue}` | status `ok` |
| 3 | `(kv-get "name")` | unchanged | status `ok`, value `alice` |
| 4 | `(kv-get "color")` | unchanged | status `ok`, value `blue` |
| 5 | `(kv-get "unknown")` | unchanged | status `not-known` |

Every ask travels through a file-backed channel both directions:
A appends a `CHANNEL-MSG` carrying a `QUERY`; K reads, dispatches,
appends a `CHANNEL-MSG` carrying a `RESPONSE` to A's reply channel.
The orchestrator drives K once per ask — in a daemon this is the
poll loop.

## The query bodies

The two verbs share the channel-query envelope but carry different
body shapes — the verb tells K's handler what to expect.

```
;; kv-set body: a 2-child list of (key, value) substrate strings.
(cq-query "kv-set" topic-nid
    (intern_node (make_nodeid 1 1 14 0)
        (list (intern_trivial_string key)
              (intern_trivial_string value))))

;; kv-get body: the key, alone, as a substrate string.
(cq-query "kv-get" topic-nid
    (intern_trivial_string key))
```

K's handler peels each body in the shape its verb dictates: `kv-set`
takes `node_children` of the body to get key + value; `kv-get` takes
`node_value` to read the key directly. No shape negotiation, no
schema lookup — the verb IS the schema.

## Why this matters

**`symbols.fk` is functionally a KV store.** This walk doesn't
re-invent it; it lifts `symbol-table` and `symbol-bind` into the
channel-query protocol. The "store" is just a `SYMBOL-TABLE` value
threaded through the dispatch. Other cells already in the body can
do the same thing for any value-shape they care about.

**State without mutation.** Form is functional. A cell that "holds
state" holds it as a value — a recipe whose NodeID changes when its
contents change. The orchestrator (or a daemon's poll-loop) threads
the value forward. Two cells with the same table at the same step
intern to the same NodeID — the body recognizes structurally
identical states without negotiation.

**Honest absence is a protocol property.** A get of a key K never
set returns status `not-known`, not an empty value. Every layer
above sees the difference between "no binding" and "binding to
empty" without inference. Compare with `SYMBOL-NOT-FOUND` in
`symbols.fk` and the not-known walk in 31-verb-router.

## What this is NOT yet

- **No overwrite-shadowing.** Setting the same key twice appends a
  second binding. `symbol-lookup` returns the FIRST match (insertion
  order), so the original value still wins. A real KV store
  shadows; this demo doesn't because the symbol-table is "linear
  bindings" and the cleanup belongs in `symbols.fk`, not here.
- **No deletion.** No `kv-del` verb. The shape would be the same
  body-as-key; the handler would filter out the matching binding.
  Left for the next walk so this sample stays focused.
- **No iteration.** No `kv-list` verb returning all keys. Would
  be a single response with an items-list of substrate-refs to each
  bound name. Same pattern, more children.
- **No multi-step transactions.** Each step reads the LATEST
  message and writes ONE reply. A real KV store would correlate
  requests with responses by `cq-query-fingerprint`; here the
  in-process orchestration is the correlation.
- **No persistence across processes.** The table lives in the
  orchestrator's call-frame. A daemon would write the table back
  to a `.fkb` file after each mutation and reload on start; the
  shape is unchanged, just one more `write_form_binary` per step.

## Cross-refs

- [`form-stdlib/symbols.fk`](../../../form-stdlib/symbols.fk) — `symbol-table`, `symbol-bind`, `symbol-lookup`, `SYMBOL-NOT-FOUND`
- [`form-stdlib/channel-query.fk`](../../../form-stdlib/channel-query.fk) — `cq-query`, `cq-response`, `cq-recipe-content`
- [`form-stdlib/cell-registry.fk`](../../../form-stdlib/cell-registry.fk) — `register-cell`, `find-by-capability`
- [`form-stdlib/channel.fk`](../../../form-stdlib/channel.fk) — `channel-create`, `channel-append`, `channel-read`
- [21-cell-query-protocol](../21-cell-query-protocol) — the QUERY/RESPONSE shape this builds on
- [23-cell-registry-osi](../23-cell-registry-osi) — the capability addressing K uses
- [25-end-to-end-channel](../25-end-to-end-channel) — single-query walk through every OSI layer; this is its many-query habitable cousin
- [31-verb-router](../31-verb-router) — how the verb-table dispatch scales beyond two verbs; ready for kv-list / kv-del when this walk grows them
- [`form-stdlib/tests/kv-store-band.fk`](../../../form-stdlib/tests/kv-store-band.fk) — sibling-parity band test
