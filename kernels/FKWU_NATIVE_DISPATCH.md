# fkwu native dispatch — the I/O boundary for the fourth kernel as a server

> The gap between "fkwu walks request-handling logic correctly" and "fkwu serves
> a real route" is one seam: a band being walked by the emitted fourth kernel
> (fkwu) must be able to reach a host I/O native — `pg_query_rows`, a socket
> read/write — and return its result into the walk. This scopes that seam.

Companion to [`KERNEL_AS_ROUTER.md`](KERNEL_AS_ROUTER.md) (the front-door
inversion) and [`API_KERNEL_READINESS.md`](API_KERNEL_READINESS.md) (the native
surface map). Those move the door onto the native kernel; this names how the
fourth kernel reaches the outside world without ceasing to be a universal walker.

## Why this is the unblocking piece

The HTTP/route *body* is already Form and already proven four-way on fkwu:
`kernel-http`, `bml-route-source-object`, `bml-route-choice-runtime`,
`native-route-goal-cells`, `recognition-router*` all sit in
[`form/fourth-arm-bands.txt`](../form/fourth-arm-bands.txt). Those bands are
**pure compute** — parse/route/render over byte-strings already in hand
([`http-parse.fk`](../form/form-stdlib/http-parse.fk),
[`http-render.fk`](../form/form-stdlib/http-render.fk): "a value in, a string
out; no I/O"). What no four-way band does today is touch Postgres or a live
socket. A DB-backed route like `/api/ideas` is ~55ms Postgres + ~87ms pure
tree-walk/emit (measured prod-internal, 2026-06-14). fkwu walks the 87ms in
milliseconds from a pre-flattened table — but only once it can make the DB call
that the other 55ms lives behind.

## How fkwu resolves an operation today (two pathways, one fenced seam)

When the emitted walker meets a call while walking a flattened node-table, the
operation resolves one of two ways — and **neither carries a generic host
callback**:

1. **Form mirror rows.** Pure operations (arithmetic folds, list ops, string
   stones, record fallbacks) are ordinary `defn` rows contributed by
   [`fourth-shim.fk`](../form/form-stdlib/fourth-shim.fk), prepended to every
   band. fkwu walks them as a normal CALL. No host needed, deterministic,
   four-way by construction.

2. **Emitted-C walker tags.** Primitives carry hard-coded tags in the emitted C
   ([`hati-os-kernel-emit.fk`](../form/form-stdlib/hati-os-kernel-emit.fk)): tag
   3 = ADD, tag 27 = `str_concat`, and so on. The flatten encoding
   ([`form-flatten.fk`](../form/form-stdlib/form-flatten.fk) `flt-ops`) makes a
   native call and a user call **indistinguishable in the table** — tag +
   children either way; the *walker's instruction set*, not the table, decides.

Crucially, **tags 55–63 already do real file I/O** (`open`/`read`/`write`/
`mkdir`/`unlink`…) inlined as syscalls in the emitted C, and socket primitives
exist as `extern` declarations. So the emitted fourth kernel *can* call the OS —
the mechanism is present. It is deliberately **fenced out of the four-way
manifest** ("host io family — blocked"): environmental I/O cannot be proven by
cross-kernel value-agreement, so any band that touches it stays 3-kernel-only.

The problem is therefore not "fkwu cannot do I/O." It is two things:
(a) the I/O seam is **per-op inlined** (baking `open`/`read` into the walker;
baking a Postgres driver in would betray "universal walker"), and
(b) there is **no discipline** that lets a route use I/O while keeping its pure
logic four-way.

## The seed that already crosses four-way

Both are already solved in miniature. The `substrate-core` band crosses four-way
on fkwu **with durable I/O**, by abstracting the carrier as a value and calling
it indirectly: `storage-put → (carrier-put carrier)` is a **first-class indirect
call** through a carrier passed in. The whole `channel-*` family
(`channel-interface`, `channel-flow`, `channel-loopback`, persistence) does the
same — I/O behind a port, proven with a **functional (deterministic) carrier**
so all four kernels agree. Both Go and Rust already expose every host native
through one uniform table (`registerNative` / `register_native`), including
`pg_connect`, `pg_query_rows`, `pg_close`, `http_get`, `fs_*`, `file_*`.

So the parts exist: first-class carrier dispatch (four-way), a functional-carrier
proof pattern (four-way), and a carrier-side native table (Go + Rust). Native
dispatch is **generalizing the per-op file-I/O seam into one carrier-served
vector**, then plugging a functional carrier for proof and a live carrier for
serve.

## The boundary: one host-native vector, not a driver per op

**Recommended shape.** The emitted walker gains a single host seam: a
host-native-call node dispatches through **one function pointer**
`host_native(name_id, argv, argc) -> value`. The walker stays universal — it
knows *that* a call is a host native and *which* (by interned name id), never
*how*. The carrier driving fkwu (the Go or Rust kernel, or a thin C host that
links a carrier's table) implements that one pointer by dispatching into its
existing `registerNative` table. The file-I/O tags 55–63 are the reference for
"what a host call looks like in the emitted C"; this replaces N inlined ops with
one indirection.

A route's I/O carrier then becomes a **host-native carrier value**: its
operations are host-native-call nodes. The route handler stays carrier-agnostic
(`(carrier-query carrier sql params)`), exactly the `substrate-core` indirect-call
shape — the value plugged in decides whether the call lands on a functional mock
or a live native.

**Rejected shape.** Inlining `pg_*`/socket as new walker tags (the tags-55–63
pattern extended) bakes libpq and a socket lifecycle into the universal walker.
Fast, but it couples the fourth kernel to a DB driver and grows the walker per
native. The vector keeps all I/O in the carrier where it already lives.

The one real cost the vector carries: a **shared Value marshalling** across the
fkwu-C ↔ carrier boundary (ints, floats, strings, lists, node ids). This is the
ABI to design first; the file-I/O tags already marshal strings/bytes across that
line, so the representation is partly proven.

## Proof discipline — keep the logic four-way, contract the boundary

- The route's **pure logic** (param shaping, SQL-string construction, response
  node-tree, json-emit) stays a four-way band, walked with a **functional
  carrier** that returns fixed fixture rows. Deterministic → Go/Rust/TS/fkwu
  agree → the band enters [`fourth-arm-bands.txt`](../form/fourth-arm-bands.txt).
- The **I/O boundary** (the host-native vector + the live carrier) is proven by
  **contract**, not value-agreement: the functional carrier and the live carrier
  satisfy the same carrier interface; the vector is integration-tested. It is
  named honestly as a 3-kernel/seam boundary, never claimed four-way.
- **Production serve swaps the carrier value only** — same flattened band, same
  walk, the indirect call now lands on `pg_query_rows`.

This is the existing `channel-*`/`substrate-core` discipline (functional carrier
for proof, real carrier for run) applied to the route handler.

## Build order

1. **Value ABI** across the fkwu-C ↔ carrier boundary (extend what tags 55–63
   already marshal). Smallest honest first step.
2. **Host-native vector** in [`hati-os-kernel-emit.fk`](../form/form-stdlib/hati-os-kernel-emit.fk):
   one `host_native(name_id, argv, argc)` seam; generalize the per-op file-I/O
   tags onto it.
3. **Carrier side**: the Go kernel (the chosen non-fourth carrier — its JIT
   subset already covers strings/lists) drives fkwu and serves the vector from
   its `registerNative` table. Rust parity follows.
4. **Functional-carrier proof**: one DB-shaped route handler authored against a
   carrier value; band crosses four-way with the functional carrier.
5. **Live serve**: swap to the host-native carrier behind `X-Form-Native-Preview`,
   in the kernel-router shadow lane — no front-door flip.

## First route targets

- **Pure-compute first** — a `/api/utils/*` handler (`shannon_entropy`,
  `softmax_weights`, `idea_score`): no I/O, so it proves the
  carrier→fkwu→response loop end-to-end before the vector exists. The seed of
  "route all requests to the fourth kernel."
- **DB-backed next** — `/api/ideas` once the vector + `pg_query_rows` binding
  land: the route whose ~87ms tree-walk becomes an fkwu flat-table walk, with the
  Postgres call delegated through the vector to the carrier.

Routing policy falls out for free: a handler band in
[`fourth-arm-bands.txt`](../form/fourth-arm-bands.txt) → fkwu; else → Go (its
existing JIT, no new features); else → Python fan-out. The manifest is already
the source of truth for "what the fourth kernel can serve."
