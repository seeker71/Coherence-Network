# 24-wire-binary-symbols — Form binary on the wire, NodeID resolution, shared symbols

> *"form native binary and node id resolution over the wire, and cell
> constr over the wire makes sense and a way to reference and share
> symbols"*  — Urs

## What walked

```
$ ./validate.sh form-stdlib/symbols.fk form-samples/cross-modal/24-wire-binary-symbols/wire-binary-symbols.fk
  ✓  symbols.fk+wire-binary-symbols.fk → table-a-binding-count: 3
                                          wire-bytes-nonempty: 1
                                          table-b-binding-count: 3
                                          alpha-found: 1
                                          beta-found: 1
                                          gamma-found: 1
                                          miss-found: 0
                                          alpha-structure-matches: 1
                                          beta-structure-matches: 1
                                          gamma-structure-matches: 1
                                          beta-child-count: 3
                                          beta-first-inst: 100
                                          8
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each:
- Constructed a symbol-table with three heterogeneous bindings.
- Serialized it to .fkb wire bytes (no file).
- Reconstructed a structurally-identical table from those bytes.
- Looked up each symbol by name; structures matched A's originals.
- Traversed a novel composite it had never seen before.

**Verdict: 8** — every attestation converges three-way.

## The four pieces

### 1. `recipe_to_bytes` / `bytes_to_recipe` — Form binary over any channel

Two new kernel natives (three-way sibling) expose the `.fkb` artifact
serialization to Form code without a file detour:

```
(recipe_to_bytes nid)   → list-of-bytes (or null on error)
(bytes_to_recipe bytes) → local nid    (or null on parse error)
```

The bytes are the canonical artifact format (string table + content-
addressed tree) that already powered `write_form_binary` /
`read_form_binary` for file transport. Now they ride over registry
messages, sockets, in-memory lists — any byte channel.

### 2. NodeID resolution over the wire

When cell A's local NodeID `inst=1234` reaches cell B, that integer is
meaningless to B's intern table. What B receives in the wire bytes is
the **structural recipe** — the content. `bytes_to_recipe` re-interns
the structure locally; B's content-addressing returns its own
NodeID for the same content. `node_eq` between A's claim and B's
reconstruction holds because the substrate's identity is structural,
not positional.

This means the wire never carries "A's NodeID 1234" as if it were a
pointer. It carries the recipe; both ends compute their own NodeID
from it. The pointer-shape ambiguity content-addressing prevents.

### 3. Cell construction over the wire

A cell built on the sender side is RECONSTRUCTED on the receiver side
from the bytes. The receiver:

- Walks the deserialized recipe structurally.
- Looks up symbol names — substrate-resident strings that converge by
  content-addressing.
- Reads novel composite values it never authored — the structure
  came across, the receiver re-interned the leaves, the tree exists
  locally.

The demo's beta value is a LIST of three integers. B has never seen
this composite; after deserialization, B can call `node_children`,
take the head, read its `inst` — full traversal of a cell that was
constructed over the wire.

### 4. Shared symbol references

Symbol names are substrate-resident SubstrateStrings. Both cells call
`intern_trivial_string "alpha"` and arrive at the same NodeID by
content-addressing — the wire never has to negotiate the name's
identity. The substrate IS the symbol vocabulary.

`form-stdlib/symbols.fk` provides:

| Op | Returns |
|---|---|
| `(symbol-bind name value)` | SYMBOL-BIND Recipe |
| `(symbol-table bindings)` | SYMBOL-TABLE Recipe |
| `(symbol-lookup table name)` | value-Recipe or `SYMBOL-NOT-FOUND` |
| `(symbol-found? v)` | 1 or 0 — distinguishes "bound" from sentinel |
| `(symbol-table-to-wire table)` | byte-list (.fkb format) |
| `(symbol-table-from-wire bytes)` | local SYMBOL-TABLE NodeID |

The sentinel `SYMBOL-NOT-FOUND` is a substrate-resident NodeID;
callers compare with `node_eq` (via `symbol-found?`) to distinguish
"bound to a Recipe" from "not bound."

## Composing with other walks

```
              SENDER                                 RECEIVER
              ──────                                 ────────

  build symbol-table with                            ← receives bytes
    heterogeneous values                               (over registered
    (substrate-ref / novel-                            channel from L3,
     blueprint / external-uri)                         framed by L2,
                                                       transported by L1)
  (symbol-table-to-wire t)
    → byte list                                      bytes_to_recipe →
                                                       local table NodeID

  packet via channel-query                           (symbol-lookup t "x")
    OR direct send                                    → value Recipe
                                                       (content-addressed
       ────── bytes ─────────▶                          identity)
                                                     traverse, classify,
                                                       fetch external URIs
                                                       (with sha256 verify)
                                                       all from the
                                                       reconstructed cell
```

This walk closes the loop with everything from 21-cell-query-protocol
(mixed content shapes), 23-cell-registry-osi (L3 addressing), and the
substrate's content-addressing discipline that makes the wire honest:
**the substrate is the codebook; the wire carries the structural
recipe; the receiver reconstitutes sovereignly.**

## What this is NOT yet

- **No streaming.** `recipe_to_bytes` materializes the entire
  serialization in memory. Streaming serialization for arbitrarily
  large recipes is a future walk.
- **No signature.** A symbol-table can be tampered with in flight
  (just bytes). Ed25519 over the wire bytes is the cryptographic
  next walk; sha256 already in stdlib.
- **Linear lookup.** `symbol-lookup` walks bindings. For tables with
  hundreds of symbols, a hash-indexed accessor wins; not needed yet.
- **No bytes-over-actual-channel wiring.** The sample passes bytes
  in-process. Wiring this through `channel.fk` (the L2 file transport)
  or sockets (the L1 wire) is straightforward — the byte list IS the
  channel payload — and lives in the next walk.

## Cross-refs

- [`form-stdlib/symbols.fk`](../../../form-stdlib/symbols.fk) — symbol-table module
- 17-novel-nodes — content-addressed convergence on novel structure
- 18-substrate-compression — substrate-refs as wire economics
- 21-cell-query-protocol — the L7 verb vocabulary symbols carry across
- 23-cell-registry-osi — L3 addressing that lets cells find each other
