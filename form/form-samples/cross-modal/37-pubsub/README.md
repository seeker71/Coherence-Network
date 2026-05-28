# 37-pubsub — polling-based pub/sub over the cell registry

> A subscriber cell holds the capability it cares about, and re-reads
> the registry as new cells arrive. No new primitive is needed — the
> registry is already append-only, and capability filter is already
> there. Pub/sub is just that pull, periodized.

## What walked

```
$ ./validate.sh form-stdlib/core.fk form-stdlib/channel.fk \
                form-stdlib/cell-registry.fk \
                form-samples/cross-modal/37-pubsub/pubsub.fk
  ✓  core.fk+channel.fk+cell-registry.fk+pubsub.fk
     → step0-compute-count: 0
       step1-compute-count: 1
       step2-compute-count: 2
       step3-compute-count: 2
       5
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels each ran the same pub/sub demo: a subscriber
polled the registry four times as cells arrived; the count grew when
matching cells registered and stayed put when a non-matching cell
registered. **Verdict: 5** — `0 + 1 + 2 + 2`.

## The pattern

The body already has two registry primitives sufficient to express
pub/sub without inventing anything new:

| Primitive | What it does |
|-----------|--------------|
| `register-cell registry-path identity channel-path verbs` | A cell declares "I exist; I handle these verbs" |
| `find-by-capability registry-path verb` | Anyone reads back the cells that match |

A **subscription** is just a verb a cell remembers and re-polls for. No
subscription-list lives in the registry; no callback is held. The
registry is the bulletin board; the subscriber is the cell that keeps
reading it.

## The scene

| Step | Event | A's poll → compute count |
|-----:|-------|-----:|
| 0 | A begins watching "compute" on an empty registry | **0** |
| 1 | Cell B registers with `(list "compute")` | **1** |
| 2 | Cell C registers with `(list "compute" "witness")` | **2** |
| 3 | Cell D registers with `(list "fetch")` — not compute | **2** |

The capability filter is honest at every step. The unrelated arrival
in step 3 leaves A's count alone — the body separates verbs.

## Why this shape

**The registry already does the work.** `find-by-capability` walks
every REGISTRATION and returns the matches; that's a poll. Calling it
again later is the next poll. Nothing about pub/sub asks the registry
to keep state about subscribers — the cell that wants to be notified
holds its own interest and re-asks.

**Append-only registration is the substrate's invariant.** A new cell
becomes addressable by appending. Every subscriber's next poll sees
the new tail. No notification fan-out, no broadcast — just monotonic
visibility.

**Privacy survives.** A cell that doesn't register stays invisible.
A subscriber doesn't get told about cells that didn't volunteer for
the verb. The opt-in shape from [23-cell-registry-osi](../23-cell-registry-osi)
extends naturally: not registering hides you from pub/sub too.

## What this is NOT yet

- **No push.** A subscriber must re-poll. A long-lived process would
  wrap this in a loop with a delay; this demo polls synchronously
  after each known event. A real push channel would have the registry
  notify subscribers — but that requires the subscriber to BE
  addressable (which contradicts the privacy-by-non-registration
  shape). Polling stays the right default.
- **No since-cursor.** Each poll re-reads every registration. For
  small registries this is fine; for large ones a `channel-read-since`
  cursor would let A only inspect the new tail.
- **No unsubscribe semantics.** A "subscription" here is whatever the
  subscriber chooses to keep polling for. Letting go is just stopping
  the poll loop. (Compare with how a cell unregisters by appending an
  empty-capabilities REGISTRATION — convention, not enforcement.)
- **No fan-in dedup.** If a cell registers twice with the same
  identity and the same verb, the count rises by two. The convention
  "last-write-wins by identity" lives in 23-cell-registry-osi's
  "What this is NOT yet" — same gap, same future walk.

## Cross-refs

- [`form-stdlib/cell-registry.fk`](../../../form-stdlib/cell-registry.fk) — `register-cell`, `find-by-capability`
- [`form-stdlib/channel.fk`](../../../form-stdlib/channel.fk) — the append-only substrate
- [23-cell-registry-osi](../23-cell-registry-osi) — the registry's L3 walk; this demo is its periodized reader
- [`form-stdlib/tests/pubsub-band.fk`](../../../form-stdlib/tests/pubsub-band.fk) — the sibling-parity band test
