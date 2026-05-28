# 17-novel-nodes — sharing novel substrate nodes between cells

> *"please continue the work on real time communication between cells
> with sharing cell novel nodes privately or publically."*  — Urs

## What walked

```
$ ./validate.sh form-samples/cross-modal/17-novel-nodes/novel-nodes.fk
  ✓  novel-nodes.fk → public-share-converged: 1
                      private-commit-verified: 1
                      2
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran both halves of
both protocols. Each kernel built a novel composite from primitives and
verified the other half's reconstruction. The byte-level entropy
(`random_bytes`) diverged per kernel; the verification result converged.

## The shape

A novel node is, by definition, something cell A holds that cell B
doesn't yet. Pure substrate-lookup can't transmit it because B has no
structural anchor for the new identity. What works is **content-
addressed reconstruction**: A transmits the structural recipe (atoms +
category); B re-interns the same shape locally; the substrate's
content-addressing gives B the *same* NodeID A computed. The novel node
is born in both cells from the same primitives.

Two paths cross the channel differently:

```
  PUBLIC SHARE                                  PRIVATE COMMIT
  ────────────                                  ──────────────

  A:  builds composite                          A:  builds composite
      from atoms                                    from atoms
                                                    nonce = random_bytes(8)
  packet =                                          fp = fingerprint(nonce,
    (category-tuple,                                              novel-inst)
     atom-strings,
     A's-claimed-nid)                            packet = (nonce, fp)

  ──── packet ────▶                              ──── packet ────▶

                B:  re-interns atoms                          B:  records (nonce, fp)
                    rebuilds composite                            doesn't know what it
                    node_eq(rebuilt,                              refers to yet
                            claimed) → 1

                                                ──── reveal ────▶
                                                (atom-strings)

                                                              B:  rebuilds composite
                                                                  fp' = fingerprint(nonce,
                                                                                    rebuilt-inst)
                                                                  fp' == fp → verified
```

### Public share

A transmits the **structural recipe** for the novel node — category
NodeID + atom strings + A's claimed final NodeID. B reconstructs by
running the same intern operations:

```
(let s1 (intern_trivial_string "circle"))
(let s2 (intern_trivial_string "blue"))
(let s3 (intern_trivial_string "large"))
(let cat (make_nodeid 1 1 14 0))                ; Basic / LIST
(let novel (intern_node cat (list s1 s2 s3)))
```

Because the substrate is content-addressed, B's `novel` NodeID **is**
A's `novel` NodeID. `node_eq` attests the convergence. The novel node
crossed the channel as a recipe, not as a NodeID-pointer — pointers
across substrates are meaningless, but recipes reconstruct sovereignly.

### Private commit-then-reveal

A doesn't transmit the structure. Instead, A commits to it via a
fingerprint over the substrate's instance index — the bookkeeping
counter the substrate assigned the new composite when A interned it.
The transmission is only `(nonce, fingerprint(nonce, novel-inst))`.

B has no way to decode what A invented. Later, when A reveals the
structural primitives, B rebuilds locally and confirms the fingerprint
matches A's earlier commitment. This is **Merkle-style content
binding**: A bound the value at commit time; the value is verifiable at
reveal time; B cannot forge a different reveal that fingerprints to the
same commit.

## Why content-addressing makes this work

The substrate's promise is that **same shape ⇒ same NodeID**. Three
kernels independently interning `intern_trivial_string("circle")` arrive
at the same NodeID for "circle" because the string table is built
deterministically. Three kernels independently interning
`intern_node(cat, [s1, s2, s3])` arrive at the same NodeID for the
composite because `(category, children)` is the content-address.

A and B don't need to negotiate the NodeID. They negotiate the
**recipe**. The substrate gives them the NodeID for free.

## Real-time communication shape

This demo runs sender and receiver in the same Form file (like
15-private-channel). The boundary is conceptual — only the packet
crosses; the cell-internal state stays private. A real two-process
channel keeps the same protocol shape; the I/O wiring swaps the
list-passing for `socket_send` / `socket_recv` (already in the kernel
across Go, Rust, TS).

Three sibling kernels each running their own copy of A + B is the
three-way validate.sh test. The same protocol could run with three
separate kernel *processes* over sockets:

```
Cell-A (Go kernel)   ──packet──▶   Cell-B (Rust kernel)
                                          │
                                          │  rebuilds with content-
                                          │  addressed intern
                                          ▼
                                   node_eq(rebuilt, claimed) → 1
```

The NodeID values themselves are NOT identical across two kernel
*processes* with different intern histories — the `inst` counter is
local. But the **structural identity** (the recipe) IS identical. Two
processes that agree on the recipe arrive at structurally identical
nodes within their own substrates; equality is by recipe-walk, not by
raw NodeID-tuple-match.

## What this is NOT yet

- **Not adversary-tolerant.** The fingerprint is a multiplicative hash
  for demonstration; a production protocol uses HMAC, BLAKE3, or similar
  PRFs. lc-private-channel-via-substrate names this constraint.
- **Not multi-cell broadcast.** This is one-to-one. Multicast would
  require either a shared bus (each cell pulls packets) or
  fingerprint-over-set semantics so a single commit covers many
  reveal-claims.
- **Not signed.** No cryptographic proof that the cell sending was
  the cell who created the novel node. A signature primitive (ed25519
  or similar, composable as a Form recipe over byte arithmetic) is the
  next walk.
- **Not auto-shared.** A cell that discovers a novel useful structure
  doesn't yet broadcast it without explicit code. A future walk would
  add substrate-side broadcast: any cell binding a new high-coherence
  composite emits its recipe to the collective bus.

## Cross-refs

- [`lc-substrate-two-modes`](../../../docs/vision-kb/concepts/lc-substrate-two-modes.md) — recipe is lossless transport
- [`lc-private-channel-via-substrate`](../../../docs/vision-kb/concepts/lc-private-channel-via-substrate.md) — meaning travels, symbols don't
- [`lc-cross-modal-unity`](../../../docs/vision-kb/concepts/lc-cross-modal-unity.md) — canonical Blueprints; the shared substrate
- 15-private-channel — the protocol this builds on
- 16-jit-registry — Form recipes as canonical truth across cells
