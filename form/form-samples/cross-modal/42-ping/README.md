# 42-ping — the smallest verb on the channel

The minimal heartbeat verb. A asks "are you there?", B answers "ok"
with a stamp. Built entirely on the existing channel-query
vocabulary — same QUERY/RESPONSE Blueprints, same correlation
discipline, same wire-optimized item kinds. Ping is the shape
every richer verb echoes.

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-stdlib/channel-query.fk \
                form-stdlib/ping.fk \
                form-samples/cross-modal/42-ping/ping.fk
  ✓  sha256.fk+channel-query.fk+ping.fk+ping.fk → real-ok: 1
                                                  correlation-matches: 1
                                                  tampered-ok: 0
                                                  3
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran the walk
end-to-end:

1. **`real-ok: 1`** — `ping-handler` returns a RESPONSE whose
   `status` field is `"ok"`, and `ping-ok?` reads that value.
2. **`correlation-matches: 1`** — the response's correlation field
   carries the originating QUERY's NodeID-inst, so a multi-in-flight
   ping fleet routes each reply back to its sender (same shape as
   `26-async-correlation`).
3. **`tampered-ok: 0`** — when the response is rebuilt with status
   `"error"`, `ping-ok?` returns 0. The predicate reads the value;
   it doesn't trust the shape blindly.

**Verdict: 3** — all three attestations hold across all three
kernels.

## The verb

`form-stdlib/ping.fk` is three definitions:

```
(ping-request)              → QUERY(verb="ping",
                                    address=PING-SELF,
                                    body=intern_trivial_string "")

(ping-handler query)        → RESPONSE(correlation=node_inst query,
                                       status="ok",
                                       items=[RECIPE-CONTENT(stamp)])

(ping-ok? response)         → 1 if status == "ok"
                              0 otherwise
```

The address slot is populated with `PING-SELF` — a well-known
NodeID at `(1, 2, 99, 1720)` just past the channel-query Blueprint
family. Ping isn't asking about anything in particular; the
sentinel address keeps the QUERY shape uniform without carving a
ping-specific exception into the vocabulary.

## The stamp — and the time-native gap

The response carries one item: a RECIPE-CONTENT wrapping a single
trivial-int that's meant to be the responder's current wall-clock
time.

**Today the stamp is hardcoded to `0`.** None of the three sibling
kernels currently expose a `(now)` or `(current_time)` native that
returns the same shape on every sibling-on-the-same-host. The
closest existing primitive is `file_mtime`, which reads an mtime
off disk — useful for caching, not for "right now".

The protocol shape is correct; the freshness signal is parked. The
proposed next walk: add a `now` native returning unix-seconds as
an int to all three kernels, then change one line in `ping.fk`:

```
(let stamp 0)               ; today
(let stamp (now))           ; once the native lands
```

Nothing else moves. The Blueprint, the RESPONSE shape, the
correlation field, the predicate — all carry forward.

## Why ping is load-bearing

A cell that can answer ping is a cell that has wired:

- The channel-query Blueprints (`QUERY`, `RESPONSE`, mixed-content
  item kinds) into its substrate.
- A handler dispatch — `verb-router` reads the QUERY's verb field
  and routes to `ping-handler`.
- The correlation discipline — every RESPONSE carries back the
  originating QUERY's NodeID-inst so an async fleet routes
  correctly.

Every richer verb (`about`, `fetch`, `compute`, `introspect`)
plugs into the same shape. If ping passes, the cell's
channel-query path is alive; if ping fails, no other verb is
worth trying.

## Cross-refs

- [`form-stdlib/ping.fk`](../../../form-stdlib/ping.fk) — the verb
- [`form-stdlib/channel-query.fk`](../../../form-stdlib/channel-query.fk) — the vocabulary
- [`form-stdlib/tests/ping-band.fk`](../../../form-stdlib/tests/ping-band.fk) — sibling-witness band (verdict 5)
- 21-cell-query-protocol — the first verb (`about`) on this vocabulary
- 26-async-correlation — the correlation discipline ping inherits
- 31-verb-router — the dispatch ping plugs into
