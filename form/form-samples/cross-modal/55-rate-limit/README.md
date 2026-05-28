# 55-rate-limit — token-bucket rate limiter in Form, sibling-verified

## What walked

```
$ ./validate.sh form-stdlib/rate-limit.fk \
                form-samples/cross-modal/55-rate-limit/rate-limit.fk
  ✓  rate-limit.fk+rate-limit.fk     → 1
                                       1
                                       1
                                       1
                                       1
                                       5
                                       5
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each built the same
token bucket, walked the same five admission decisions across
simulated wall-clock time, and produced the same verdict — using
**only** the canonical rate-limit Form recipe and the kernel's list +
int primitives. No rate-limit native exists in any kernel; the
recipe IS the implementation.

- bucket capacity = 10, refill-rate = 1 token / second
- t=0: consume 5 → admit (5 left); consume 5 → admit (0 left)
- t=500: consume 1 → reject (0.5s refills 0 tokens under integer ms math)
- t=1500: consume 1 → admit (1.5s refills 1 token)
- t=20000: consume 100 → reject (refill caps at capacity 10)
- Final verdict: **5** on every kernel

## The shape

```
   BUCKET ( capacity         : int (max tokens)
          , tokens-remaining : int (current count)
          , last-refill-time : int (caller-clock ms)
          , refill-rate      : int (tokens / second) )
```

A bucket is a 4-element list. Cells consume from a bucket by calling
`(bucket-consume bucket cost now-time)`; the recipe lazily refills
based on elapsed time since `last-refill`, capped at `capacity`. If
the refilled bucket holds enough tokens, the call returns a new
bucket carrying the debit and an advanced `last-refill`; otherwise
it returns the bucket unchanged.

The refill rule:

```
   new-tokens = min(capacity,
                    tokens-remaining + (now - last-refill) * refill-rate / 1000)
```

Refill is lazy — the bucket doesn't tick on its own. It catches up
at the moment of query. Integer division on the elapsed-window
keeps the recipe portable across kernels; fractional tokens are
dropped, which is the correct conservative behavior for a limiter.
A long-idle bucket can't burst beyond its declared ceiling because
the `min(capacity, ...)` clamp lives in the same expression.

The trust shape sits in the observer's clock, like `52-heartbeat`
and `49-token`: a caller that lies about `now` can be detected by
an observer running its own clock, but the bucket itself is honest
about how many tokens its math allows.

## The Form recipe shape

`form-stdlib/rate-limit.fk` carries:

```
(let BUCKET (make_nodeid 1 2 99 1840))

(defn bucket-new (capacity refill-rate))           → fresh bucket (full)
(defn bucket-consume (bucket cost now-time))       → new bucket OR same
(defn bucket-can-consume? (bucket cost now-time))  → 1 or 0
(defn bucket-capacity (b))                         → int
(defn bucket-tokens (b))                           → int (raw, unfilled)
(defn bucket-last-refill (b))                      → int
(defn bucket-refill-rate (b))                      → int
```

No rate-limit native opcode; no host timer dependency. The recipe is
the canonical authoring of "what a token bucket means" in this body
and composes directly with the kernel's list primitives.

The Blueprint NodeID `(make_nodeid 1 2 99 1840)` reserves the rate-
limit family's identity in the user-channel range, adjacent to the
tree-diff cluster at 1830 and the session cluster at 1860.

## The walk this sample runs

```
bucket-new(10, 1)                  → (10, 10, 0, 1)

consume 5 at t=0  → refill 0, 10 ≥ 5  →  ADMIT, bucket (10, 5, 0, 1)
consume 5 at t=0  → refill 0,  5 ≥ 5  →  ADMIT, bucket (10, 0, 0, 1)
consume 1 at t=500 → refill 500*1/1000 = 0, 0 < 1 → REJECT, unchanged
consume 1 at t=1500 → refill 1500*1/1000 = 1, 1 ≥ 1 → ADMIT,
                                                      bucket (10, 0, 1500, 1)
consume 100 at t=20000 → refill min(10, 0+18) = 10, 10 < 100 → REJECT

verdict = 5 correct admit/reject decisions
```

## Why this matters

Rate limiting is the missing primitive for **request admission
without a central scheduler**. Where a heartbeat table (`52-heartbeat`)
tracks *which cells are still here* and a capability token
(`49-token`) binds *what a cell may do under a deadline*, a token
bucket controls *how often a cell may act*. Together they let any
cell decide locally whether to admit a peer's request — no central
gateway, no global counter, no out-of-band quota service.

What this opens:

- **Decentralized fair-share.** Each observer maintains its own
  bucket per peer; no cell needs to be authoritative about who has
  spent how much. Two observers seeing the same emitter can disagree
  on its instantaneous bucket level (clock skew, message ordering)
  without disagreeing on the admit/reject decision over a window.
- **Burst tolerance with a ceiling.** A long-idle bucket can answer
  a burst up to `capacity` instantly — desirable for interactive
  use — but never exceeds it, so a quiet hour doesn't unlock an hour
  of saved-up rate at once. The `min(capacity, ...)` clamp is what
  makes the bucket robust to long pauses.
- **Lazy O(1) bookkeeping.** No timer fires; no background sweep.
  The bucket carries only its last-refill stamp and current token
  count. A query computes the refill at the moment of asking, in
  one arithmetic step. Composes naturally with the cell registry
  (`23-cell-registry-osi`) — registered cells each carry their own
  bucket, queried at admission time.
- **Composable with substrate refs.** The bucket is a plain list of
  ints. A cell can stamp it with a NodeID for cross-cell recognition,
  serialize it through `channel.fk` for hand-off, or sign its state
  with HMAC (`29-hmac-sha256`) so two peers reconcile honestly. The
  recipe doesn't care; refill arithmetic is the only property it
  commits to.

The recipe is sovereign across all three sibling kernels — once a
kernel runs the core list + int primitives, rate limiting comes for
free. No new natives, no new bindings.

## Cost

`bucket-new` is O(1) — one 4-element list cons. `bucket-consume`
and `bucket-can-consume?` are each O(1) — one subtraction, one
multiplication, one integer division, one min, one comparison, one
list cons on admission (or zero on rejection). No history is kept;
the bucket carries only its current state and the last-refill
timestamp. For the 5-step walk here the total work is ~10 list
operations and ~25 arithmetic ops — well inside the recursion
budget. The same recipe lifts to host-asm speed via the Form→host-
JIT path (see `16-jit-registry`). The canonical source in
`rate-limit.fk` doesn't change; the cell chooses dispatch.

## What this is NOT yet

- **No persistence.** The bucket lives in the caller's hands as a
  plain list. Pairing with `channel.fk` (the substrate's append-only
  message channel) would give durable on-disk bucket state across
  process restarts; pairing with `cell-registry.fk` would let one
  cell distribute its rate-limit view.
- **No fractional tokens.** Integer arithmetic means a refill rate
  of 1 token/second under a 999ms window contributes zero. For
  sub-second precision, scale the refill-rate (e.g. 1000 → tokens
  per millisecond) and the cost together; the recipe doesn't change.
- **No multi-bucket coordination.** Each bucket is a single
  one-dimensional limiter. Hierarchical rate limiting (per-user AND
  global) wants a small layer above this one that consults two
  buckets per request. Not yet in this recipe.
- **No clock-skew handling.** The refill rule trusts the caller's
  `now-time` absolutely. A caller running backwards (`now` <
  `last-refill`) would produce a negative `elapsed` and a negative
  refill — the recipe doesn't currently floor at zero. Pairing with
  a clock-sync recipe (Lamport, vector, or hybrid logical clocks)
  would harden the limiter against backward-jumping callers.
- **No native fast path.** Every consume/can-consume walks the
  recipe. JIT lifts that to host speed without changing this source.

## Cross-refs

- [`form-stdlib/rate-limit.fk`](../../../form-stdlib/rate-limit.fk) — the canonical recipe
- [`form-stdlib/tests/rate-limit-band.fk`](../../../form-stdlib/tests/rate-limit-band.fk) — sibling-witness band, verdict locked at 6
- `52-heartbeat` — sibling composition: liveness window over the same observer-clock trust shape
- `49-token` — sibling composition: time-bounded capability (deadline) vs. time-bounded throughput (rate)
- `42-ping` — sibling composition: single liveness reading at one moment
- `53-now-unix-ms` — the host clock the caller passes in as `now-time`
- `16-jit-registry` — the future host-speed dispatch path
