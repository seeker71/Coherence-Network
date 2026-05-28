# 56-dns — DNS-like name resolution in Form, sibling-verified

## What walked

```
$ ./validate.sh form-stdlib/dns.fk \
                form-samples/cross-modal/56-dns/dns.fk
  ✓  dns.fk+dns.fk                  → resolve-a: 1
                                       missing-is-not-found: 1
                                       prefix-count: 2
                                       verdict: 3
                                       3
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each built the same
DNS-style name table, resolved the same name, looked up the same
missing name, and walked the same zone-prefix — using **only** the
canonical DNS Form recipe and the kernel's list + int + string
primitives. No DNS native exists in any kernel; the recipe IS the
implementation.

- 3 cells register names under two zones
- `resolve("a.cells.local")` → bound trivial-int **1**
- `resolve("missing.cells.local")` → **DNS-NOT-FOUND** sentinel
- `resolve-prefix("cells.local")` → **2** matching records
- Final verdict: **3** on every kernel

## The shape

```
   NAME-RECORD ( name  : string  (dot-separated)
              , value  : Recipe  (substrate-ref / trivial / …) )

   DNS-TABLE = ordered list of NAME-RECORDs
               (insertion order; first match wins on resolve)
```

A DNS table is a list of `(name, value)` records. Cells register
names by appending records; observers ask `(dns-resolve table name)`
and the recipe walks until it finds the matching name or runs out.
Missing names return the `DNS-NOT-FOUND` Blueprint NodeID — callers
distinguish "found" from "absent" via `node_eq`.

The prefix walk reads the table as a zone directory:

```
   (dns-resolve-prefix table "cells.local")
     → every record whose name carries "cells.local" somewhere
       — "a.cells.local" and "b.cells.local" both qualify
       because str_find returns 2 (the prefix sits at offset 2),
       not -1.
```

`str_find` returns 0 when the prefix is at the very start of the
name, a positive index when it sits further in (e.g. as a parent
label), and -1 when absent. Any non-negative return is a match —
that's what makes DNS-style zone lookup work: a record at
`a.cells.local` belongs to the `cells.local` zone even though the
zone string sits at offset 2, not offset 0.

## The Form recipe shape

`form-stdlib/dns.fk` carries:

```
(let NAME-RECORD      (make_nodeid 1 2 99 1850))
(let DNS-TABLE        (make_nodeid 1 2 99 1851))
(let DNS-NOT-FOUND    (make_nodeid 1 2 99 1852))
(let DNS-PREFIX-MATCH (make_nodeid 1 2 99 1853))

(defn dns-record (name value))                → NAME-RECORD Recipe
(defn dns-table  (records))                   → DNS-TABLE Recipe
(defn dns-resolve         (table name))       → value Recipe or DNS-NOT-FOUND
(defn dns-resolve-prefix  (table prefix))     → list of NAME-RECORDs
```

No DNS native opcode; no host resolver dependency. The recipe is
the canonical authoring of "what a name directory means" in this
body and composes directly with the kernel's list + string
primitives.

The Blueprint NodeIDs `(make_nodeid 1 2 99 1850..1853)` reserve the
DNS family's identity in the user-channel range, sitting between
tree-diff at 1830-1832 and session at 1860-1862.

## The walk this sample runs

```
register "a.cells.local"   → trivial-int 1
register "b.cells.local"   → trivial-int 2
register "c.peers.remote"  → trivial-int 3

resolve "a.cells.local"        → trivial-int 1   (node_value → 1)
resolve "missing.cells.local"  → DNS-NOT-FOUND   (node_eq → 1)
resolve-prefix "cells.local"   → [r1, r2]        (len → 2)

verdict = 1 (resolve found) + 1 (missing → NOT-FOUND)
        + 1 (prefix count is 2) = 3
```

## Why this matters

Name resolution is the missing primitive for **cell-graph addressing
under a hierarchical namespace**. Where the cell registry
(`23-cell-registry-osi`) binds *capabilities* to channel paths, a
DNS table binds *names* to value recipes — substrate-refs, channel
paths, capability tokens, anything the recipe can hold. The two
compose: a registry of cells, named under zones, looked up by either
verb or hierarchical name.

What this opens:

- **Federated naming.** Each cell maintains its own DNS table; two
  cells exchanging tables can reconcile by appending each other's
  records. The recipe stays naive about uniqueness so callers
  choose resolution semantics (first-match-wins, latest-wins,
  consensus).
- **Zone walks.** `resolve-prefix` reads the table as a zone
  directory — "give me every record under `cells.local`" returns
  exactly the cells that named themselves under that zone, in
  insertion order.
- **Composable with substrate-refs.** Values are arbitrary Recipes
  — a trivial-int here, a substrate-ref pointing at a Blueprint
  cell in production, a channel-path string for L3 routing, a
  capability token for `49-token`-style trust delegation.
- **No central authority.** The recipe is the entire protocol; no
  root server, no out-of-band registry. Sibling kernels answer the
  same lookups from the same table.

The recipe is sovereign across all three sibling kernels — once a
kernel runs the core list + int + string primitives, name
resolution comes for free. No new natives, no new bindings.

## Cost

Every operation walks the table once. `dns-resolve` short-circuits
on the first match — best case O(1), worst case O(n).
`dns-resolve-prefix` walks the whole table calling `str_find` once
per record — O(n) traversals each calling the host's `indexOf` for
the substring search.

For the 3-entry demo here the total work is ~5 list traversals
plus 3 `str_find` calls — well inside the recursion budget. The
same recipe lifts to host-asm speed via the Form→host-JIT path (see
`16-jit-registry`). The canonical source in `dns.fk` doesn't
change; the cell chooses dispatch.

## What this is NOT yet

- **No persistence.** The table lives in process memory. Pairing
  with `channel.fk` (the substrate's append-only message channel)
  would give durable on-disk storage; pairing with
  `cell-registry.fk` would let one cell distribute its name view.
- **No TTL / staleness.** Records sit forever once added. Pairing
  with `heartbeat.fk` would let observers prune records whose
  bound cells have gone silent.
- **No glue between zones.** A record at `a.cells.local` doesn't
  imply a parent record at `cells.local`. Zone walks find names
  by substring containment, not by tree traversal. A future layer
  could split names on `.` and walk the label tree explicitly.
- **No signed records.** Any cell can register any name; the
  recipe doesn't check authority. Composing with HMAC-SHA-256
  (`29-hmac-sha256`) over `(name, value)` would bind each record
  to an emitter — a small layer above this one.
- **No native fast path.** Every resolve walks the recipe. JIT
  lifts that to host speed without changing this source.

## Cross-refs

- [`form-stdlib/dns.fk`](../../../form-stdlib/dns.fk) — the canonical recipe
- [`form-stdlib/tests/dns-band.fk`](../../../form-stdlib/tests/dns-band.fk) — sibling-witness band
- `23-cell-registry-osi` — the capability registry this layer naturally pairs with for name + verb routing
- `40-kv-store` — sibling primitive: string-keyed lookup over channels (this layer is hierarchical naming, not flat KV)
- `52-heartbeat` — sibling primitive: liveness; the future TTL layer for DNS records
- `16-jit-registry` — the future host-speed dispatch path
