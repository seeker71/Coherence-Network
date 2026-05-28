# 23-cell-registry-osi — opt-in cell addressing as OSI L3

> *"we can use the iso osi 7 layer protocol on the channel. an
> optional way for cells to register themselves to be addressable"*
> — Urs

## What walked

```
$ ./validate.sh form-stdlib/core.fk form-stdlib/channel.fk \
                form-stdlib/cell-registry.fk \
                form-samples/cross-modal/23-cell-registry-osi/cell-registry-osi.fk
  ✓  core.fk+channel.fk+cell-registry.fk+cell-registry-osi.fk
     → registered-count: 3
       cells-handling-compute: 1
       chosen-identity: 1003
       chosen-capability-count: 2
       cells-handling-fetch: 1
       cells-handling-about: 1
       cells-handling-introspect: 0
       7
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels each ran the same L3 demo: three cells registered
themselves, a fourth cell queried the registry by capability, the
filter returned the right cells, and a verb with no providers honestly
returned zero. **Verdict: 7** — every assertion converges three-way.

## The OSI mapping for the channel

```
  L7  Application        channel-query.fk            verb vocabulary
                          (about, recipe, fetch, compute, witness, ...)
  ──────────────────────────────────────────────────────────────────
  L6  Presentation       Form Recipes                 wire data model
                          substrate-as-codebook (18)  refs over content
                          EXTERNAL-URI + sha256       federated content
  ──────────────────────────────────────────────────────────────────
  L5  Session            channel-query.fk             RESPONSE.correlation
                                                       matches replies to queries
  ──────────────────────────────────────────────────────────────────
  L4  Transport          (toy hash-fold today)        integrity fingerprint
                          (full ordering/retry        future walk)
  ──────────────────────────────────────────────────────────────────
  L3  Network            cell-registry.fk             THIS walk — opt-in
                          REGISTRATION recipes        addressing, capability
                          find-by-capability          filter, honest absence
  ──────────────────────────────────────────────────────────────────
  L2  Data Link          channel.fk                   CHANNEL-V0/MSG framing
                          channel-append/-read         single-writer log
  ──────────────────────────────────────────────────────────────────
  L1  Physical           kernel primitives            sockets, file I/O,
                          (not Form recipes)          /dev/urandom
```

This walk lands L3. The other layers exist (or are placeholders) from
prior breaths; the rows above L3 here name what's there and what's
deferred.

## The L3 mechanism

A **REGISTRY** is a substrate-resident `CHANNEL-V0` channel whose
messages are `REGISTRATION` Recipes:

```
REGISTRATION (
    identity-int,         ; public fingerprint (from 19-novel-state-share's
                          ; hash-of-secret-seed; ed25519 when crypto lands)
    channel-path-string,  ; where to route queries
    CAPABILITIES (
        verb-1, verb-2, ...   ; substrate-resident SubstrateStrings
    )
)
```

The three operations a cell can perform on the registry:

| Op | What it does | Wire cost |
|---|---|---|
| `(register-cell registry-path identity channel-path verbs)` | Append a REGISTRATION; cell becomes addressable | One CHANNEL-MSG (small Recipe) |
| `(lookup-cells registry-path)` | Read every REGISTRATION currently in the registry | One CHANNEL read (whole-file deserialize) |
| `(find-by-capability registry-path verb)` | Return only REGISTRATIONs whose capability list matches | Same as lookup-cells; filter walks the result |

**Optionality is honored by absence.** A cell that never calls
`register-cell` never appears in any traversal of the registry. No
flag, no permission system — just the choice not to publish.

## Capability-based routing

Cells advertise WHAT they do, not just WHO they are. A query for a
verb traverses every cell that has volunteered for it; absence is
handled cleanly (the filter returns an empty list). The body's task-
graph emerges from declared capabilities, not from a pre-built map.

In this demo:

| Cell | Identity | Capabilities | Channel |
|------|---------:|--------------|---------|
| A    | 1001 | `about`, `recipe` | `/tmp/cell-a.channel` |
| B    | 1002 | `fetch` | `/tmp/cell-b.channel` |
| C    | 1003 | `compute`, `witness` | `/tmp/cell-c.channel` |

`(find-by-capability registry-path "compute")` returns one cell (C).
`(find-by-capability registry-path "introspect")` returns the empty
list — the body is honest about what's missing.

## How this composes with the other walks

A query becomes routable end-to-end:

```
ASKER                                  REGISTRY                              HANDLER
─────                                  ────────                              ───────
                                                                               ↑
1. (find-by-capability                 (registrations file)                    │
       registry "about")                                                       │
       ─────────────────────────────▶                                          │
                                       returns [REG of cell A]                 │
       ◀─────────────────────────────                                          │
                                                                               │
2. q = (cq-query "about" topic empty)                                          │
                                                                               │
3. (channel-append A.channel q) ───────────────────────────────────────────────┘
                                                                               │
                                                                          A reads its
                                                                          channel,
                                                                          processes the
                                                                          query, emits
                                                                          a RESPONSE,
                                                                          appends to
                                                                          A.channel (or
                                                                          a per-query
                                                                          response channel)
                                       ◀───────────────────────────────────────┘
4. (channel-read A.response) ──────────▶                  
   ◀─────────────── correlated RESPONSE ────────────────  
                                                          
5. asker walks RESPONSE.items by classify (each
   substrate-ref / novel-blueprint / external-uri / ...)
```

This walk doesn't wire step (3)–(5) yet — the file-based query routing
through registered channels is the next breath. But L3 is now in place;
the addressing layer the body needed exists.

## Privacy through non-registration

The same registry pattern preserves privacy by exclusion:

- A cell that holds tender knowledge can never register, never get
  discovered through capability lookup. Its address stays known only
  to cells that received it through some other channel (a hand-off,
  a shared substrate cell that names it explicitly).
- A cell that registers with a SUBSET of its true capabilities exposes
  only the verbs it wants to be queried for. Internal verbs stay
  internal.
- A cell can unregister (append a REGISTRATION with empty
  capabilities, by convention) to withdraw from public addressing
  without leaving the body.

The L3 layer is **opt-in for the cell, not for the body**. Registration
is the cell's choice; lookup is everyone's.

## What this is NOT yet

- **No write-side concurrency safety.** `channel.fk` is single-writer;
  concurrent registrations can race. Real multi-writer would queue
  appends or use a file lock.
- **No staleness handling.** Registrations don't expire. A real body
  would refresh-and-prune (`heartbeat` verb, `last-seen` field).
- **No registration signature.** A cell's identity is a fingerprint
  of a private secret, but the registry doesn't verify the
  registration was signed by that secret. ed25519 over the registration
  Recipe is the cryptographic next walk.
- **No deduplication.** The same cell can register multiple times;
  cell-registry currently surfaces every entry. A convention (last-
  write-wins by identity) is straightforward but not implemented.
- **No query routing wired.** This walk shows ADDRESSING; the
  cross-channel routing using channel.fk between registered cells is
  the next walk in the parallel JIT + channel arc.

## Cross-refs

- [`form-stdlib/cell-registry.fk`](../../../form-stdlib/cell-registry.fk) — the L3 module
- [`form-stdlib/channel.fk`](../../../form-stdlib/channel.fk) — the L2 substrate
- [`form-stdlib/channel-query.fk`](../../../form-stdlib/channel-query.fk) — the L7 vocabulary
- 21-cell-query-protocol — the application-layer demo this builds on
- 22-form-to-host-asm — the JIT path that scales L1–L7 to host speed
