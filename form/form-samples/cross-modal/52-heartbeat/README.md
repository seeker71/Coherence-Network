# 52-heartbeat — periodic liveness tracking in Form, sibling-verified

## What walked

```
$ ./validate.sh form-stdlib/heartbeat.fk \
                form-samples/cross-modal/52-heartbeat/heartbeat.fk
  ✓  heartbeat.fk+heartbeat.fk       → alive-3: 1
                                       alive-1: 0
                                       alive-count: 1
                                       pruned-len: 1
                                       verdict: 4
                                       4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each built the same liveness
table, asked the same freshness questions, pruned the same stale entries,
and produced the same verdict — using **only** the canonical heartbeat
Form recipe and the kernel's list + int primitives. No heartbeat native
exists in any kernel; the recipe IS the implementation.

- 3 cells emit heartbeats at t=100, t=200, t=300
- At now=350 with threshold=100: cell 3 alive, cells 1 and 2 stale
- `alive-count` → **1**, `pruned-len` → **1**
- Final verdict: **4** on every kernel

## The shape

```
   HEARTBEAT-ENTRY ( identity        : int
                  , last-seen-time   : int )

   HEARTBEAT-TABLE = ordered list of HEARTBEAT-ENTRYs
                     (each identity appears at most once)
```

A heartbeat table is a list of `(identity, last-seen-time)` pairs. Cells
emit heartbeats by calling `(heartbeat-record table identity now-time)`;
the recipe reads the prior table, removes any existing entry for the
identity, and appends a fresh one. The most recent recording wins.

The freshness rule sits in the observer's clock, not the emitter's:

```
   alive?(entry, now, threshold)  iff  entry.last-seen ≥ now - threshold
```

A cell that lies about its last-seen time can be detected by an observer
running its own clock; a cell that drops off the wire silently becomes
stale as soon as the observer's `now` advances past the threshold. Same
trust shape as the capability token in `49-token`.

## The Form recipe shape

`form-stdlib/heartbeat.fk` carries:

```
(let HEARTBEAT-ENTRY (make_nodeid 1 2 99 1820))
(let HEARTBEAT-TABLE (make_nodeid 1 2 99 1821))

(defn heartbeat-empty ())                                  → empty table
(defn heartbeat-record (table identity now-time))          → updated table
(defn heartbeat-alive? (table identity now-time threshold)) → 1 or 0
(defn heartbeat-prune  (table now-time threshold))          → fresh-only table
(defn heartbeat-alive-count (table now-time threshold))     → int count
(defn heartbeat-len (table))                                → int count
```

No heartbeat native opcode; no host wall-clock dependency. The recipe is
the canonical authoring of "what a liveness table means" in this body
and composes directly with the kernel's list primitives.

The Blueprint NodeIDs `(make_nodeid 1 2 99 1820)` and `1821` reserve the
heartbeat family's identity in the user-channel range, adjacent to the
triangle cluster at 1800/1801.

## The walk this sample runs

```
emit at t=100  → table = [(1,100)]
emit at t=200  → table = [(1,100), (2,200)]
emit at t=300  → table = [(1,100), (2,200), (3,300)]

ask alive?(cell=3, now=350, threshold=100)  →  300 ≥ 250  →  1
ask alive?(cell=1, now=350, threshold=100)  →  100 < 250  →  0
ask alive-count(now=350, threshold=100)     →  1 (only cell 3)
prune(now=350, threshold=100)               →  [(3,300)], length 1

verdict = 1 (fresh) + 1 (stale→0 correctly) + 1 (count is 1)
        + 1 (pruned length is 1) = 4
```

## Why this matters

Liveness tracking is the missing primitive for **observer-side trust
without a central health check**. Where a capability token (`49-token`)
binds *what a cell may do* under a deadline, a heartbeat table tracks
*which cells are still here* under a freshness threshold. Together they
let any cell decide locally whether to admit a peer's claim — no central
registry, no PKI, no out-of-band ping protocol.

What this opens:

- **Decentralized presence.** Each observer maintains its own table; no
  cell needs to be authoritative about who is alive. Two observers can
  reconcile their tables by exchanging entries — the recipient takes
  the entry with the higher `last-seen-time`.
- **Self-pruning sessions.** Long-running coordinators don't accumulate
  dead peers — `(heartbeat-prune)` composts entries the observer hasn't
  heard from within its threshold. Memory growth tracks active peers,
  not historical ones.
- **Cheap stale-detection.** The freshness check is one int comparison
  per query; the prune walks the table once. Composes naturally with
  the cell registry (`23-cell-registry-osi`) — registered cells that
  go silent fall out of the live set without an explicit deregister.
- **Composable with substrate refs.** Identities are ints in the
  recipe but the convention can carry any fingerprint — a cell-name
  hash, a NodeID, an HMAC tag. The recipe doesn't care; freshness is
  the only property it commits to.

The recipe is sovereign across all three sibling kernels — once a kernel
runs the core list + int primitives, liveness tracking comes for free.
No new natives, no new bindings.

## Cost

Every operation walks the table once. `heartbeat-record` walks twice
(remove existing entry, then append), so O(2n) per record. `alive?`
walks until found, O(n) worst case. `prune` walks once with an
accumulator, O(n). `alive-count` walks once without materializing the
pruned list, O(n). The table stays small in recipe-mode runs because
`heartbeat-prune` composts stale entries when called.

For the 3-entry demo here the total work is ~12 list traversals — well
inside the recursion budget. The same recipe lifts to host-asm speed
via the Form→host-JIT path (see `16-jit-registry`). The canonical
source in `heartbeat.fk` doesn't change; the cell chooses dispatch.

## What this is NOT yet

- **No persistence.** The table lives in process memory. Pairing with
  `channel.fk` (the substrate's append-only message channel) would
  give durable on-disk storage; pairing with `cell-registry.fk` would
  let one cell distribute its liveness view.
- **No signed heartbeats.** A cell that wants to emit on another's
  behalf can; the recipe doesn't check authenticity. Composing with
  HMAC-SHA-256 (`29-hmac-sha256`) over `(identity, now-time)` would
  bind each emit to a shared secret — a small layer above this one.
- **No clock-skew handling.** The freshness rule trusts the observer's
  clock absolutely. Pairing with a clock-sync recipe (Lamport,
  vector, or hybrid logical clocks) would let two observers agree on
  liveness across an unsynchronized network. Not yet in this recipe.
- **No native fast path.** Every record/query/prune walks the recipe.
  JIT lifts that to host speed without changing this source.

## Cross-refs

- [`form-stdlib/heartbeat.fk`](../../../form-stdlib/heartbeat.fk) — the canonical recipe
- [`form-stdlib/tests/heartbeat-band.fk`](../../../form-stdlib/tests/heartbeat-band.fk) — sibling-witness band, verdict locked at 5
- `42-ping` — sibling composition: single round-trip liveness check (this layer turns ping into history)
- `49-token` — sibling composition: observer-side trust shape, time-bounded
- `23-cell-registry-osi` — the cell registry this layer naturally pairs with for presence
- `16-jit-registry` — the future host-speed dispatch path
