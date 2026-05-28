# 41-chat — two cells exchanging free-form text over channel.fk

> Two mailbox files, one MESSAGE Blueprint, four turns of conversation.
> No registry, no router, no session layer — just two channels and a
> shape both cells know.

## What walked

```
$ ./validate.sh form-stdlib/core.fk form-stdlib/channel.fk \
                form-samples/cross-modal/41-chat/chat.fk
  ✓  core.fk+channel.fk+chat.fk
     → B-received-seq: 1
       B-body-hello-match: 1
       A-received-seq: 1
       A-body-hi-match: 1
       B-received-seq: 2
       B-body-name-match: 1
       A-received-seq: 2
       A-body-beta-match: 1
       4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran the same
four-turn conversation between Cell A and Cell B. Every body matched
on every kernel. **Verdict: 4** — one for each successful body round-trip.

## The envelope

```
MESSAGE (sender-string, body-string, sequence-int)
```

Every chat message is a Recipe whose Blueprint is `MESSAGE` and whose
ordered children are the sender's name, the body text, and a
per-direction sequence counter. The Blueprint NodeID is fixed by
`make_nodeid 1 2 99 1760` — both cells use the same call site, so
their `MESSAGE` Recipes content-address identically.

| Slot | Position | Accessor |
|------|---------:|----------|
| sender | 0 | `(node_value (head (node_children m)))` |
| body | 1 | `(node_value (head (tail (node_children m))))` |
| seq | 2 | `(node_value (head (tail (tail (node_children m)))))` |

`node_value` reads the underlying SubstrateString or int back out of
the trivial Recipe in each slot — no Blueprint negotiation needed for
the leaves, because they're already canonical leaf shapes.

## The topology

Cell A and Cell B each have their **own incoming channel** — a tiny
mailbox file on disk:

| Cell | Reads from | Writes to |
|------|------------|-----------|
| A | `/tmp/chat-a.fkb` | `/tmp/chat-b.fkb` |
| B | `/tmp/chat-b.fkb` | `/tmp/chat-a.fkb` |

A wants to talk to B → A appends a MESSAGE to `/tmp/chat-b.fkb`.
B wants to reply → B appends to `/tmp/chat-a.fkb`. Either side reads
its own mailbox to pick up what the other dropped off. The transport
is just `channel-append` and `channel-read` from
[`form-stdlib/channel.fk`](../../../form-stdlib/channel.fk).

## The conversation

| Turn | Direction | Body | Seq |
|-----:|-----------|------|----:|
| 1 | A → B | `hello` | 1 |
| 2 | B → A | `hi` | 1 |
| 3 | A → B | `what's your name` | 2 |
| 4 | B → A | `I am Beta` | 2 |
| 5 | A reads `/tmp/chat-a.fkb` again | — | — |

Each step is a `channel-append` on the recipient's mailbox immediately
followed by the recipient's `channel-read`. The reader extracts
`(sender, body, seq)` via the positional accessors and checks the body
with `str_eq`. Sequence numbers are per-direction — A's outgoing seq
and B's outgoing seq are independent counters.

## Why this shape

**Content-addressing is the wire format.** Both kernels intern
`(make_nodeid 1 2 99 1760)` to the same MESSAGE Blueprint NodeID;
`intern_trivial_string` and `intern_trivial_int` produce canonical
leaf NodeIDs across Go, Rust, and TypeScript. The `.fkb` file written
by one kernel deserializes to the same Recipe identity on any other.

**Raw NodeIDs stay off stdout.** Per-kernel inst counters can diverge
on freshly-minted nodes; `str_eq` results and the integer seq numbers
are canonical. The sample prints only the latter, so the three siblings
produce byte-identical output.

**No protocol layer beyond MESSAGE.** Two mailboxes, one envelope
shape, no correlation id, no session, no routing. Either cell can
poll its own channel whenever it wants. This is the smallest shape
that carries a multi-turn conversation, and the substrate already
gives us everything we need.

## What this is NOT yet

- **No durable log.** `channel-append` rewrites the whole file; an
  interrupted writer can truncate. For a multi-turn chat this is
  fine; for an audit log we'd want a real append-only structure.
- **No real-time delivery.** A polls by re-reading its mailbox.
  A daemon shape (see [37-pubsub](../37-pubsub)) would loop on
  `file_mtime` to wake up only when there's something new.
- **No turn-taking semantics.** Either cell can append at any time;
  the sample orchestrates the back-and-forth manually. A real chat
  daemon would interleave reads and writes in its own event loop.
- **No identity beyond the sender string.** "A" and "B" are just
  text. The next walk would key the channels off a registered
  identity via [23-cell-registry-osi](../23-cell-registry-osi)'s
  `register-cell` and route by NodeID rather than path.

## Cross-refs

- [`form-stdlib/channel.fk`](../../../form-stdlib/channel.fk) — the
  `CHANNEL-V0` / `CHANNEL-MSG` transport used by both cells.
- [`form-stdlib/tests/chat-band.fk`](../../../form-stdlib/tests/chat-band.fk)
  — the sibling-parity band test (verdict: 5).
- [25-end-to-end-channel](../25-end-to-end-channel) — full OSI walk
  with a registry, a query/response pair, and a typed item list.
- [37-pubsub](../37-pubsub) — polling pattern that the next chat
  daemon would adopt.
