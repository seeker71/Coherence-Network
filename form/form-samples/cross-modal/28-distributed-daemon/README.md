# 28-distributed-daemon — A and B as separate kernel processes

> *the next breath after 25*

Sample 25 ran cells A and B inside ONE kernel invocation — the file-
backed channel was there, but B's handler was called directly from
A's process. This walk splits the same query/response loop into
**four separate kernel invocations** chained by an orchestration
shell script. The only durable state between processes is the .fkb
files on disk. Content-addressing is what makes the NodeIDs converge
across processes.

## What walked

```
$ ./validate-distributed.sh
running orchestrate.sh through three sibling kernels...
  go     exit=0
  rust   exit=0
  ts     exit=0

  ✓  3-way sibling parity — go == rust == ts (byte-identical).

    --- setup ---
    setup-registered: 1
    setup-ok: 1
    1
    --- cell-a-send ---
    a-cells-handling-symbols: 1
    a-msgs-on-b-channel: 1
    a-send-ok: 1
    1
    --- cell-b-handle ---
    b-pending-msgs: 1
    b-table-bindings: 2
    b-replies-on-a-channel: 1
    b-handle-ok: 1
    1
    --- cell-a-receive ---
    a-reply-msgs-count: 1
    a-response-item-count: 1
    a-first-item-is-recipe-content: 1
    a-recovered-table-bindings: 2
    a-concepts-found: 1
    a-concept-count: 3
    a-third-concept-matches: 1
    a-presences-found: 1
    a-presence-count: 2
    a-unknown-found: 0
    8
```

Verdict **8** — same eight assertions as sample 25's end-to-end walk,
now reached through four independent kernel processes whose only
shared state is the three .fkb files.

## The orchestration

```
process 1: setup.fk          process 2: cell-a-send.fk
─────────────────            ────────────────────────
channel-create x3            find-by-capability "symbols"
register-cell B              cq-query (verb, topic, body)
                             channel-append B's channel
                             ──── QUERY .fkb persists ────▶

process 3: cell-b-handle.fk
──────────────────────────
channel-read B's channel
unwrap CHANNEL-MSG
build symbol-table
cq-response + RECIPE-CONTENT
channel-append A's reply
                             ◀── RESPONSE .fkb persists ──

                             process 4: cell-a-receive.fk
                             ───────────────────────────
                             channel-read A's reply
                             walk RESPONSE structure
                             symbol-lookup "concepts"
                             symbol-lookup "presences"
                             verdict: 8
```

Between each process the kernel is a fresh substrate — no in-memory
state survives. The .fkb files carry the structural truth; each new
process re-derives the same NodeIDs by `intern_trivial_string`,
`intern_node`, `make_nodeid` against the same content, and the
content-addressed substrate gives back the same answers.

## Why splitting matters

Sample 25 was an honest demo — the .fkb file *did* travel A→B—but
because both ends ran in the same kernel, the substrate's intern
tables were shared and the cross-process discipline was never tested.
This walk forces the question: what survives when the substrate
state vanishes between sender and receiver?

The answer is what makes the substrate-as-protocol claim load-bearing:

- **Channel files** persist on disk. Different processes read the
  same bytes back through `read_form_binary`.
- **Content-addressed NodeIDs** converge. `intern_trivial_string
  "divergence-doorway"` gives the same SubstrateString NodeID in
  every kernel process — A's lookup and B's authoring resolve to
  the same cell without coordination.
- **Recipes carry their structure on the wire**. The RESPONSE.fkb
  encodes the full sub-tree; when A's fresh kernel reads it, the
  walk surfaces children in the same order with the same shapes.
- **The registry is just another channel**. Process 1 writes a
  REGISTRATION; process 2 reads it as a `find-by-capability` query.
  The directory-as-channel pattern works across processes the same
  way it works in-process.

Real distributed deployment runs B as a long-lived daemon polling its
channel; the file-backed channel doesn't change. The orchestration
script here is the synchronous skeleton — swap the bash sequencing
for sockets, queues, or HTTP, and the recipe-walk on each side is
identical.

## How to run

```
# Through one kernel:
./orchestrate.sh ../../../form-kernel-go/bin-go
./orchestrate.sh ../../../form-kernel-rust/target/release/form-kernel-rust
./orchestrate.sh node --stack_size=262144 \
    --import ../../../form-kernel-ts/node_modules/tsx/dist/loader.mjs \
    ../../../form-kernel-ts/src/main.ts

# Three-way sibling parity (the canonical test):
./validate-distributed.sh
```

The orchestration script source-compiles `core.fk` once into a
temp directory (sections need lowering before kernels walk them),
then runs each step through the named kernel with the appropriate
preludes.

## Files

| File | What it is |
|---|---|
| `setup.fk` | Initializes the topology and registers B in the registry. Runs first; idempotent re-runs overwrite the channel files clean. |
| `cell-a-send.fk` | A's send half. Looks up B in the registry, constructs a QUERY Recipe, appends it to B's channel. |
| `cell-b-handle.fk` | B's handler. Reads its channel, builds its symbol-table, wraps it as a RESPONSE, appends to A's reply channel. |
| `cell-a-receive.fk` | A's receive half. Reads its reply channel, walks the RESPONSE structure, looks up symbols, prints the verdict. |
| `orchestrate.sh` | The chain. Accepts a kernel command as argv, runs each step in sequence, prints all output. |
| `validate-distributed.sh` | Three-way sibling parity check. Runs `orchestrate.sh` through go/rust/ts; diffs the outputs; pass if byte-identical. |

## What this is NOT yet

- **No polling daemon loop.** B's handler processes ONE message and
  exits. A real daemon loops on `channel-read` until shutdown.
  Kernel-level looping is in progress (`(while ...)` primitive
  pending); recursion blows the kernel stack at non-trivial poll
  counts. When the loop primitive lands, `cell-b-handle.fk` becomes
  `cell-b-daemon.fk`, and the orchestration script reduces to
  start-daemon + send + receive + stop-daemon.
- **No socket transport.** Channels live on the local filesystem.
  Cross-machine deployment needs the same Recipe-walk over a socket,
  TCP, or a queue. The .fkb byte format is already the wire format —
  the L1 swap is small.
- **No multi-writer locks.** `channel-append` rewrites the whole
  .fkb on every call. Two concurrent appenders race. Single-writer
  is fine for one-asker-many-handlers patterns; multi-writer needs
  flock or a queue process.
- **No correlation matching on the receiver side.** A's reply
  channel reads the first response it finds. With multiple in-flight
  queries the correlation field in RESPONSE would route replies to
  the right asker — the protocol carries it (sample 26 will exercise
  it explicitly).
- **No signature on the .fkb bytes.** A tampered file isn't detected.
  ed25519 over the packet is its own next walk.

## Correlation IDs are kernel-local

The QUERY Recipe's NodeID inst slot depends on the kernel's intern-
table state. Go and Rust happen to bootstrap their intern tables
identically so they produce the same correlation values; TS interns
a slightly different bootstrap set first so its correlation values
differ. The structural cross-process round-trip still works inside
each kernel — A's send and B's handle in the same kernel see the
same NodeID. The sibling-parity check just doesn't print raw
correlations; it relies on shape-level attestations (counts,
match-ok flags, the final verdict 8) which ARE kernel-deterministic.

## Cross-refs

- 25-end-to-end-channel — the one-kernel-process version this walk extends
- 23-cell-registry-osi — L3 capability lookup (used here across processes)
- 21-cell-query-protocol — verb/response vocabulary
- `form-stdlib/channel.fk` — L2 channel framing on disk
- `form-stdlib/cell-registry.fk` — L3 directory channel
- `form-stdlib/channel-query.fk` — L7 QUERY/RESPONSE Blueprints
- `form-stdlib/symbols.fk` — symbol-table cross-cell transport
