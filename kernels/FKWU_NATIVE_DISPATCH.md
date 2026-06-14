# fkwu native dispatch — the I/O boundary for the fourth kernel as a server

> The gap between "fkwu walks request-handling logic correctly" and "fkwu serves
> a real route" is one seam: a route must reach a host I/O operation —
> `pg_query_rows`, a socket — and return its result into the walk. This scopes
> that seam to its end, with every named gap closed, by assembling patterns the
> body already proves four-way rather than inventing new machinery.

Companion to [`KERNEL_AS_ROUTER.md`](KERNEL_AS_ROUTER.md) (the front-door
inversion) and [`API_KERNEL_READINESS.md`](API_KERNEL_READINESS.md) (the native
surface map). An independent review by Grok (2026-06-14, reading the emitter
internals directly) reshaped this scope: the primary path is *offload*, not a
mid-walk callback; the callback is a deferred facility; and the whole thing rides
the storage-port carrier the body already carries.

## The one abstraction: the carrier is the boundary

[`storage-port.fk`](../form/form-stdlib/storage-port.fk) already names the answer:
**"a Port = a capability-contract (the operation shape) bound to a carrier."** A
carrier is a record that *carries its bounded operation set as function values*
(`mk-carrier name init put get has`); the port pulls the op from the carrier and
calls it indirectly — `(storage-get carrier store key)` → `(let f (carrier-get
carrier)) (f store key)`. The call site never names a global host native. It can
only call the ops the carrier it was handed exposes.

Three facts make this load-bearing, each already four-way:

- **Capability-contract** — [`storage-port.fk`](../form/form-stdlib/storage-port.fk)
  is explicit that the carrier *is* the capability. The bounded vtable is the
  carrier record's `{init,put,get,has}`. A band holding a `db` carrier reaches
  exactly those ops on it — never `volatile_cell_*`, never `jit_*`, never another
  carrier.
- **Substitutability** — [`substrate-core.fk`](../form/form-stdlib/substrate-core.fk)
  runs over memory, file, and Postgres carriers *unchanged*; the memory carrier
  is functional (deterministic), the pg carrier is the live floor. The band is
  identical; only the carrier value differs. This is the proof discipline,
  already crossing four-way (`substrate-core` in
  [`fourth-arm-bands.txt`](../form/fourth-arm-bands.txt) via first-class indirect
  carrier dispatch).
- **Value serialization exists** — [`persistence.fk`](../form/form-stdlib/persistence.fk)
  round-trips a Recipe tree to bytes and back through `write_form_binary` /
  `read_form_binary`, the kernel's durable-persistence format. The marshalling ABI
  is not invented; it is the format the kernel already persists the lattice with.

So "native dispatch" is: **let fkwu run the storage-port carrier shape it almost
already walks, with the live carrier's ops bound to host natives.** The capability
scoping, the marshalling, and the proof discipline are properties of the carrier,
not new kernel surface.

## How fkwu resolves an operation today (two pathways, one fenced seam)

When the emitted walker meets a call while walking a flattened node-table, it
resolves one of two ways:

1. **Form mirror rows** — pure ops (arithmetic, list, string stones, record
   fallbacks) are ordinary `defn` rows from
   [`fourth-shim.fk`](../form/form-stdlib/fourth-shim.fk), prepended to every band.
   fkwu walks them as a normal CALL. Deterministic, four-way by construction.
2. **Emitted-C walker tags** — primitives are hard-coded tags in
   [`hati-os-kernel-emit.fk`](../form/form-stdlib/hati-os-kernel-emit.fk). Tags
   55–63 **already do real file I/O** (`open`/`read`/`write`) inlined as syscalls,
   with socket `extern`s present. The flatten encoding
   ([`form-flatten.fk`](../form/form-stdlib/form-flatten.fk) `flt-ops`) makes a
   native call and a user call indistinguishable by tag.

Those file-I/O tags are deliberately **fenced out of the four-way manifest** —
environmental I/O cannot be proven by cross-kernel value agreement. They are the
pragmatic per-op exception that proves the rule: extending that pattern with
`pg_*`/socket tags would bake a DB driver and socket lifecycle into the universal
walker. The seam exists; it must be *generalized and capability-scoped*, never
multiplied per op.

## Primary path — offload the pure slice, the carrier owns I/O

The first move keeps fkwu a **strictly pure evaluator** and gives the latency win
now. The carrier — the Go kernel today, which already owns the listener, the
`registerNative` table, request context, and `pg_query_rows` — owns the request
lifecycle and every live I/O call. It walks the handler band itself (Go can run
the live carrier op). When the walk reaches the heavy **pure slice** — the
`shape_tree` + `json_emit` that measured ~87 ms of a ~146 ms `/api/ideas`
handler (prod-internal, 2026-06-14) — Go **offloads that slice to fkwu**:

- Marshal the input (parsed request + DB rows) to bytes via `write_form_binary`.
- fkwu reads the bytes, walks the pre-flattened pure slice from its cached
  node-table in milliseconds, returns the response value (or the emitted JSON
  byte-string directly).
- Go writes the response.

fkwu makes **no host call** in this path. The ABI is one-shot — *value tree in,
value/string out* — with no mid-walk reentrancy, no cancellation into a C stack,
no capability surface. It harvests exactly the pure cost measured, and it is the
smallest honest step toward "the fourth kernel serves." This is how Go already
treats the kernel for pure compute; here the offloaded slice is the route's
shaping body.

## Deferred facility — the host-bound carrier (whole handler on fkwu)

When we want the *entire* handler walked on fkwu (not the host orchestrating the
I/O), the carrier abstraction extends with zero new dispatch shape: a **host-bound
carrier** is a normal storage-port carrier whose op functions, instead of pure
Form (the memory carrier) or emitted-C tags (the file carrier), resolve through
**one host seam** — `host_carrier_op(carrier_handle, op_id, argv) -> value` — that
the driving carrier serves from its `registerNative` table. Every named gap closes
as a property of this shape:

- **Capability scoping (the gap Grok named).** Closed by construction. The seam
  dispatches *through a carrier handle the host minted and injected into the
  band's root frame*, never by global native name. The band has no constructor
  for a host-bound carrier — it only receives one. The reachable op set is the
  carrier's bounded vtable. A band handed a `db` carrier cannot reach
  `volatile_cell_*` or another carrier's ops; there is no node-shape in the table
  that addresses a global native. The flattener emits only carrier-op nodes for
  the carriers a handler declares it requires.
- **Marshalling ABI.** The existing `write_form_binary`/`read_form_binary` format.
  argv and the return value cross the seam in the kernel's own persistence
  encoding; the task is giving the emitted walker a read/write arm for that
  format, not inventing one.
- **Reentrancy.** A host-bound op is a **leaf** in the walk — it cannot re-enter
  the walker. The host runs the op, allocates the result as a serialized value,
  and the walker interns it into its arena *after the call returns*. No host code
  writes into the arena; `melt` relocates nothing the host holds, because the host
  holds a serialized value, not arena pointers. This is exactly the discipline the
  fs tags 55–63 already follow (read into a fixed buffer, then `fk_sbuf`).
- **Cancellation / timeout.** The host enforces the deadline (carried on the
  carrier capability or as the per-request budget) and returns an **error-value** —
  the same `-1`/`"ERR"`/error-cell convention the Go and Rust `pg_*` natives use —
  into the walk. The band handles it as an ordinary Form value (the
  persistence-error branch). The walk never blocks in C beyond the host-enforced
  deadline.
- **Determinism.** The functional carrier (proof) and the live carrier (serve)
  satisfy the same bounded contract — already substrate-core's proven
  substitutability. The contract forbids observing connection state and requires
  the handler's SQL to be ordered (`ORDER BY`), so the live carrier is value-
  substitutable for the functional one over every shape the band feeds it.
- **Re-emit blast radius.** The seam is one walker arm and one stable carrier-op
  encoding; an ABI change re-clangs the standing fkwu and invalidates the
  fourth-arm cache, so the carrier-op encoding is frozen early and the seam kept
  minimal. Named honestly as a cost, bounded to one arm.

The host-bound carrier is the same storage-port shape as the functional and file
carriers — the fourth binding time. It is built only when a route genuinely needs
its whole body four-way on fkwu; the offload path serves the latency goal first.

## Why not "route all requests to the fourth kernel" literally

fkwu is a **table evaluator**, not a listener. The emitter *can* produce a server
main (its own socket/fork loop), but baking net-organ lifecycle, pooling, and
graceful drain into the universal binary is the coupling this scope avoids. The
durable shape is **Go owns the front door + fkwu as accelerator** — Go keeps the
listener, the pg handle table, headers, and context; fkwu walks the pure slices
(offload) and, later, whole handler bands over host-bound carriers. "Route all
*coverable* requests to the fourth kernel" means: every handler whose pure heart
is in [`fourth-arm-bands.txt`](../form/fourth-arm-bands.txt), with its I/O boundary
carried by the storage-port carrier — functional for proof, live for serve.

## Build order

1. **Pure-slice offload** — Go invokes fkwu on the `/api/ideas` `shape_tree` +
   `json_emit` slice with a `write_form_binary` bundle; fkwu returns the JSON.
   Needs: fkwu reads the form-binary input format; the slice flattened as a band.
   Smallest honest step, harvests the measured ~87 ms.
2. **Value-binary ABI parity** — confirm/seat `read_form_binary`/`write_form_binary`
   on the emitted walker so the bundle round-trips bit-for-bit with Go and Rust.
3. **Host-bound carrier seam** — `host_carrier_op(handle, op_id, argv)` in
   [`hati-os-kernel-emit.fk`](../form/form-stdlib/hati-os-kernel-emit.fk), one arm,
   capability-scoped through the injected carrier handle; Go serves it from
   `registerNative`.
4. **Functional-carrier four-way band** — one DB-shaped handler authored against a
   storage-port carrier, crossing four-way with the memory/functional carrier.
5. **Live serve** — swap the injected carrier to the host-bound pg carrier behind
   `X-Form-Native-Preview` in the kernel-router shadow lane. No front-door flip.

First route targets: a pure-compute `/api/utils/*` handler proves the loop with no
I/O; `/api/ideas` is the first DB-backed route — offload first (step 1), whole-band
host-bound carrier later (steps 3–5). Routing policy falls out of
[`fourth-arm-bands.txt`](../form/fourth-arm-bands.txt): handler band in the manifest
→ fkwu; else → Go (its existing JIT, no new features); else → Python fan-out.
