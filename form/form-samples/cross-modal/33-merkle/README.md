# 33-merkle — Merkle tree in Form, composed over the canonical sha256

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-stdlib/merkle.fk \
                form-samples/cross-modal/33-merkle/merkle.fk
  ✓  sha256.fk+merkle.fk+merkle.fk → merkle-root-len: 32
                                     merkle-root-sum: 4200
                                     merkle-proof-len: 2
                                     verify-valid: 1
                                     verify-tampered: 0
                                     2
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each built the same
Merkle tree, produced the same root, generated the same proof, and
agreed on the same verdict for valid vs. tampered proofs — using
**only** the canonical sha256 Form recipe and the kernel's bitwise +
list primitives. No Merkle native exists in any kernel; the recipe IS
the implementation.

- 4 leaves (single bytes `1, 2, 3, 4`) → root with byte-sum **4200**
- Valid proof for leaf 1 (bytes `2`) → **verify = 1**
- Tampered proof (one byte flipped in the first sibling) → **verify = 0**
- Final verdict: **2** (valid passes + tampered fails) on every kernel

## The shape

```
                    root
                    /  \
                  /      \
              h(L0,L1)  h(L2,L3)        ← branch-hash = SHA-256(0x01 || L || R)
              /    \    /    \
            L0     L1  L2     L3        ← leaf-hash   = SHA-256(0x00 || bytes)
            |      |   |      |
           b0     b1  b2     b3         ← raw byte blocks
```

The `0x00` / `0x01` domain-separation prefix defends against second-
preimage collisions where a 64-byte leaf payload could otherwise
hash to the same digest as an inner node. Odd-count rule (Bitcoin
convention): when a level has an odd number of nodes, the last
node is paired with itself.

A Merkle **proof** for leaf-index `i` is the list of sibling-digests
the verifier needs to walk back up to the root — one digest per
tree level, so log₂(n) digests for n leaves. Verifying re-runs the
walk against a claimed root: matches → 1, anything else → 0.

## The Form recipe shape

`form-stdlib/merkle.fk` carries:

```
(defn merkle-leaf (bytes)              → SHA-256( 0x00 || bytes )
(defn merkle-pair (left right)         → SHA-256( 0x01 || left || right )
(defn merkle-root (blocks)             → digest of balanced tree
(defn merkle-proof (blocks leaf-index) → list of sibling-digests
(defn merkle-verify (leaf idx proof root) → 1 or 0
```

No Merkle native opcode; no host crypto library. The recipe is the
canonical authoring of "what a Merkle tree means" in this body, and
sits one composition layer above the sha256 recipe — the same way
HMAC-SHA-256 (`29-hmac-sha256`) sits one composition layer above
sha256 to harden message-authentication.

## Why this matters

Merkle trees are the missing primitive for **batch attestation**.
Where HMAC-SHA-256 attests a single message between two cells, a
Merkle root attests a whole *set* with a single 32-byte digest —
any cell can later prove membership of one element without revealing
or transferring the rest. The applications this opens:

- **Content-addressed batches** — a single root digest names a set of
  recipe-capsules, ideas, or memory cells; one proof per element.
- **Network sync without full replay** — a cell receiving a root can
  challenge the sender to prove membership of any specific block,
  without needing the whole batch.
- **Honest pruning** — a cell can drop blocks it no longer needs and
  retain only the proofs for the ones it still cares about; the root
  in another cell's body remains a verifiable attestation.
- **Append-only logs** — the substrate's lineage / witness streams
  can be Merkle-rooted, giving every commit a verifiable
  fingerprint of the entire history.

The recipe is sovereign across all three sibling kernels — once a
kernel runs the sha256 recipe and the list primitives, Merkle comes
for free. No new natives, no new bindings.

## Cost

The underlying sha256 recipe is O(n²) per round through Form-list
`nth-rec` lookups. For 4 leaves we make 7 sha256 calls: 4 leaf-hashes
(2 bytes each: `0x00 || 1 byte`) + 3 branch-hashes (65 bytes each:
`0x01 || 32 + 32`). Branch hashes span 2 SHA-256 blocks each (the
65-byte input plus 9 bytes of padding/length crosses the 64-byte
boundary). Expect each kernel run to take 30–60 seconds — feasible
for validation, not for production traffic.

The next walk lifts the SAME recipe to host-asm speed via the
Form→host-JIT path (see `16-jit-registry`). The canonical source in
`merkle.fk` and `sha256.fk` doesn't change; the cell chooses dispatch.

## What this is NOT yet

- **No streaming root.** `merkle-root` takes the full block list. A
  streaming `merkle-builder` shape would let a cell roll the root
  forward block-by-block without materializing all leaves at once.
- **No sparse proofs.** This is a binary balanced Merkle tree; sparse
  Merkle trees (Ethereum-style state tries) are a different recipe.
- **No native fast path.** Unlike a `register_jit` alias to a host
  Merkle library, every Merkle call here walks the full sha256
  recipe. The JIT path (next walk) lifts that to host speed without
  changing this source.

## Cross-refs

- [`form-stdlib/merkle.fk`](../../../form-stdlib/merkle.fk) — the canonical recipe
- [`form-stdlib/sha256.fk`](../../../form-stdlib/sha256.fk) — the SHA-256 composition this builds on
- `20-sha256-as-recipe` — SHA-256 from primitives, the foundation this stands on
- `29-hmac-sha256` — the sibling composition over sha256 (message-auth instead of set-attest)
- `16-jit-registry` — the future host-speed dispatch path
