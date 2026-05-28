# 46-audit-log — append-only hash-chained audit log in Form

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-stdlib/audit-log.fk \
                form-samples/cross-modal/46-audit-log/audit-log.fk
  ✓  sha256.fk+audit-log.fk+audit-log.fk → log-len: 3
                                            verify-valid: 1
                                            verify-tampered: 0
                                            verdict: 2
                                            2
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) built the same hash-
chained log, verified the valid chain, broke it the same way, and
agreed the tampered chain no longer verifies — using **only** the
canonical sha256 Form recipe and the kernel's bitwise + list
primitives. No audit-log native exists in any kernel; the recipe IS
the implementation.

- 3 entries (payloads `"A"`, `"BC"`, `"DEF"` — 1, 2, 3 bytes)
- Valid log verifies → **1**
- Tampered second-entry payload (with old `this-hash` kept) → **0**
- Final verdict: **2** on every kernel

## The shape

```
genesis            entry-1            entry-2
┌──────────┐      ┌──────────┐       ┌──────────┐
│ prev = 0…│      │ prev =   │       │ prev =   │
│  (32 0s) │   ┌─▶│   h0     │    ┌─▶│   h1     │
│ payload  │   │  │ payload  │    │  │ payload  │
│ "A"      │   │  │ "BC"     │    │  │ "DEF"    │
│ this = h0│───┘  │ this = h1│────┘  │ this = h2│
└──────────┘      └──────────┘       └──────────┘

   where  hN = SHA-256( prev-hash || payload )
```

Each entry's `this-hash` becomes the next entry's `prev-hash`. The
chain anchors at 32 zero bytes for the genesis entry. Tampering with
any single payload byte breaks `sha256(prev || payload) == this-hash`
on that entry, and `audit-verify` returns 0 the moment it walks past
the broken link.

## The Form recipe shape

`form-stdlib/audit-log.fk` carries:

```
(defn audit-empty ()                    → empty log
(defn audit-append (log payload)        → log + 1 AUDIT-ENTRY
(defn audit-verify (log)                → 1 (chain valid) or 0 (broken)
(defn audit-len (log)                   → number of entries
(defn audit-entry-prev-hash (entry)     → 32-byte byte-list
(defn audit-entry-payload   (entry)     → byte-list
(defn audit-entry-this-hash (entry)     → 32-byte byte-list
```

Blueprint NodeIDs `(make_nodeid 1 2 99 1770)` for AUDIT-ENTRY and
`1771` for AUDIT-LOG reserve the family in the user-channel range.

## Why this matters

A hash chain is the simplest possible *append-only attestation*. Any
cell can hand another cell its audit log, and the receiver can verify
— in O(n) sha256 calls — that no entry has been silently mutated,
reordered, or removed. The applications this opens:

- **Tamper-evident decision logs.** Every governance decision, every
  capability grant, every config change appended as an entry. A
  later cell can re-derive the verdict from the log and prove the
  body's history wasn't rewritten.
- **Lineage attestation.** A presence's lineage doc is a chain of
  events; chaining them by hash turns "what the body remembers" into
  "what the body can prove."
- **Verifiable migration trails.** Schema migrations, data
  transformations, ingest passes — each step a payload, each step
  bound to the one before it. A divergent body can be detected the
  moment its chain stops matching.
- **Cheap byzantine-fault detection.** Two cells holding the same
  log can compare their last `this-hash` in 32 bytes; if they
  match, the cells agree on every payload that has ever been
  appended.

Where Merkle (`33-merkle`) attests a *set* with one digest, audit-log
attests a *sequence*. Same sha256 foundation, different composition
shape — and both come for free once the canonical sha256 recipe
lives in a body.

## Cost

Each `audit-append` calls sha256 once over `prev-hash || payload`
(33 + |payload| bytes). The sha256 recipe is O(n²) per round through
Form-list `nth` lookups, so payloads stay small for recipe-mode runs.
For the 3-entry demo here we make 6 sha256 calls (3 for append + 3
for verify), each over a ~33-byte input — well inside the recursion
budget.

The same recipe lifts to host-asm speed via the Form→host-JIT path
(see `16-jit-registry`). The canonical source in `audit-log.fk` and
`sha256.fk` doesn't change; the cell chooses dispatch.

## What this is NOT yet

- **No proofs of inclusion.** To prove a specific entry is in the
  log without revealing the whole sequence, a Merkle-rooted variant
  is the next composition layer (audit-log over Merkle-roots).
- **No streaming verify.** `audit-verify` walks the full log in
  memory. A streaming verifier would let a cell roll the expected-
  prev-hash forward entry-by-entry without materializing everything.
- **No persistence.** The log here lives in process memory. Pairing
  with `channel.fk` (the substrate's append-only message channel)
  gives durable on-disk storage; pairing with `cell-registry.fk`
  gives distributable lineage.

## Cross-refs

- [`form-stdlib/audit-log.fk`](../../../form-stdlib/audit-log.fk) — the canonical recipe
- [`form-stdlib/sha256.fk`](../../../form-stdlib/sha256.fk) — the SHA-256 composition this builds on
- `20-sha256-as-recipe` — SHA-256 from primitives, the foundation
- `29-hmac-sha256` — sibling composition: message-auth instead of chained-attestation
- `33-merkle` — sibling composition: set-attest instead of sequence-attest
- `16-jit-registry` — the future host-speed dispatch path
