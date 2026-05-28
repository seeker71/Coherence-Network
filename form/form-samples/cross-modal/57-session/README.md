# 57-session — multi-request session state in Form, sibling-verified

## What walked

```
$ ./validate.sh form-stdlib/session.fk \
                form-samples/cross-modal/57-session/session.fk
  ✓  session.fk+session.fk           → id-ok: 1
                                       counter0-ok: 1
                                       counter1-ok: 1
                                       miss-ok: 1
                                       verdict: 4
                                       4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each built the same session
table, opened the same session id=42 with counter=0, threaded the
counter through one update across simulated requests, and refused the
same unknown id — using **only** the canonical session Form recipe and
the kernel's list + int primitives. No session native exists in any
kernel; the recipe IS the implementation.

- Session id=42 opens with counter=0
- Bump to 1 in a later "request"; state survives because the table is
  the authority
- Probe for id=99 returns SESSION-NOT-FOUND
- Final verdict: **4** on every kernel

## The shape

```
   SESSION ( id    : int
           , state : Recipe )       ; whatever the server hangs off here

   SESSION-TABLE = ordered list of SESSIONs
                   (each id appears at most once)
```

A session table is a list of `(id, state)` pairs. Clients open a
session by calling `(session-create id init-state)`; the server
installs it with `(session-table-set table session)`. Each subsequent
request carries only the id; the server uses
`(session-table-get table id)` to recover the bound state, processes
the request against it, and may thread a new SESSION back into the
table with another `session-table-set` (which overwrites in place
because each id appears at most once).

The trust shape sits in the table, not the wire:

```
   what the client carries across requests  =  session-id only
   what the server holds                    =  the SESSION's state
```

A client cannot fabricate state because `(session-table-get)` returns
the server's stored SESSION, not anything the client sent. A request
carrying an unknown id lands on the `SESSION-NOT-FOUND` sentinel — the
server doesn't auto-create. Same trust shape as the capability token
in `49-token`: the holder presents an opaque handle, the authority
decides what it means.

## The Form recipe shape

`form-stdlib/session.fk` carries:

```
(let SESSION           (make_nodeid 1 2 99 1860))
(let SESSION-TABLE     (make_nodeid 1 2 99 1861))
(let SESSION-NOT-FOUND (make_nodeid 1 2 99 1862))

(defn session-create      (id init-state))     → SESSION
(defn session-id          (session))           → int
(defn session-state       (session))           → state Recipe
(defn session-update      (session new-state)) → SESSION (same id)
(defn session-table-new   ())                  → empty table
(defn session-table-set   (table session))     → table with session
                                                  inserted or overwritten
(defn session-table-get   (table id))          → SESSION or SESSION-NOT-FOUND
```

No session native opcode. The recipe is the canonical authoring of
"what a per-connection binding means" in this body and composes
directly with the kernel's list primitives — same convention as
heartbeat (`52-heartbeat`).

The Blueprint NodeIDs `(make_nodeid 1 2 99 1860/1861/1862)` reserve the
session family's identity in the user-channel range — the next free
decade after tree-diff at 1830-1832 (1840-1859 left open for adjacent
session-shaped recipes like session-table-drop and session-table-len
without breaking the contiguous family).

## The walk this sample runs

```
open  id=42, state=0   → table = [(42, 0)]

retrieve id=42         → SESSION (42, 0)
read counter           → 0
bump to 1, put back    → table = [(42, 1)]

retrieve id=42 again   → SESSION (42, 1)   ← state survived the round-trip
read counter           → 1

retrieve id=99         → SESSION-NOT-FOUND  ← server is the authority

verdict = 1 (id round-trip) + 1 (initial counter 0)
        + 1 (post-update counter 1) + 1 (missing-id sentinel) = 4
```

## Why this matters

Multi-request session state is the missing primitive for **stateful
conversations on a stateless wire**. HTTP, the channel recipe (`25-end-
to-end-channel`), the cell registry (`23-cell-registry-osi`) — every
transport in this body delivers one request at a time. A SESSION is
how a server binds many requests into one conversation without trusting
the wire to carry the state.

What this opens:

- **Stateful chat.** `41-chat` carries per-message context; pairing
  with this recipe gives each connected client a stable conversation
  thread, scoped by session-id, that survives reconnect.
- **Cart-shaped accumulation.** Any flow that builds up state across
  requests — shopping cart, multi-page form, query cursor — drops
  into the `state` slot of a SESSION without changing the surface.
  The state Recipe can be a counter (this sample), a list, a full
  document, an embedding.
- **Auth claims at session granularity.** Bind the result of a token
  validation (`49-token`) once at session-open; later requests don't
  re-validate, they just retrieve. Logout is `session-table-set` with
  a fresh (unbound) state, or — when it lands — a `session-table-drop`.
- **Composable with heartbeat.** Pairing with `52-heartbeat` gives
  presence-aware sessions: a session whose id hasn't been heard from
  inside the freshness threshold can be composted without an explicit
  logout. Memory growth tracks active conversations, not historical
  ones.

The recipe is sovereign across all three sibling kernels — once a
kernel runs the core list + int primitives, multi-request session
state comes for free. No new natives, no new bindings.

## Cost

Every operation is O(n) over the table. `session-table-set` walks the
list once to filter out any prior session for the id, then prepends a
fresh entry — so the most recent write wins and sits at the head.
`session-table-get` walks until found. The table stays small in
recipe-mode runs because sessions are added on connect and (eventually)
removed when the client signs off.

For the 4-attestation demo here the total work is ~8 list traversals
— well inside the recursion budget. The same recipe lifts to host-asm
speed via the Form→host-JIT path (`16-jit-registry`). The canonical
source in `session.fk` doesn't change; the cell chooses dispatch.

## What this is NOT yet

- **No `session-table-drop`.** Sessions never leave the table except
  by being overwritten. A drop verb is the natural next breath — and
  pairs with heartbeat to compost silent sessions automatically.
- **No expiry clock.** Sessions don't carry an expiration timestamp.
  Pairing with `(now_unix_ms)` (`53-now-unix-ms`) and a freshness
  threshold lifts this into the same shape as `52-heartbeat` —
  session liveness becomes observer-clock liveness.
- **No signed session ids.** A cell that wants to forge a session-id
  can; the recipe doesn't check authenticity. Composing with
  HMAC-SHA-256 (`29-hmac-sha256`) over the id binds each handle to
  a server secret — a small layer above this one.
- **No persistence.** The table lives in process memory. Pairing with
  `channel.fk` (the substrate's append-only message channel) would
  give durable on-disk storage across server restarts.
- **No native fast path.** Every set/get walks the recipe. JIT lifts
  that to host speed without changing this source.

## Cross-refs

- [`form-stdlib/session.fk`](../../../form-stdlib/session.fk) — the canonical recipe
- [`form-stdlib/tests/session-band.fk`](../../../form-stdlib/tests/session-band.fk) — sibling-witness band, verdict locked at 9
- `25-end-to-end-channel` — the stateless wire this layer carries state across
- `41-chat` — sibling composition: per-message context that wants a stable conversation thread
- `49-token` — sibling composition: opaque handle the holder presents, the authority decides what it means
- `52-heartbeat` — the freshness check that composts silent sessions
- `53-now-unix-ms` — the clock that lifts session state into time-bound state
- `16-jit-registry` — the future host-speed dispatch path
