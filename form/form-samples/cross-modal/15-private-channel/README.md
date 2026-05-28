# 15-private-channel — private channel, public meaning

> *"When two cells want to communicate and want to share internal
> states without having to divulge all of it, one way of doing that
> is using random number and having a mechanism, a channel to
> communicate and then come to a consensus that the receiver received
> number without sending the number itself, in the most beneficial
> way for both cells."*
>
> *"This will allow the selection of media types and recipes and
> allows for sharing novel findings inside of one cell with the
> collective and with other cells."*  — Urs

## What walked

```
$ ./validate.sh form-samples/cross-modal/15-private-channel/private-channel.fk
  ✓  private-channel.fk  → 5
  1 ok, 0 divergent — kernels agree on every sample.
```

The receiver identified the concept-index `5` from the shared catalog,
across all three sibling kernels. The byte-level fingerprints differed
per kernel (each opened its own doorway via `random_bytes`); the
*meaning* converged (shared catalog → same identification).

## The protocol

```
                   SENDER (private)                         CHANNEL
                                                       (only these bytes)
                                                              │
  concept-index = 5                                           │
  concept-value = nth(catalog, 5) = 528                       │
  nonce = random_bytes(8)         ← divergent per kernel      │
  fp = fingerprint(nonce, 528)                                │
                                                              │
         ─── (nonce, fp) ─────────────────────────────────────▶
                                                              │
                                                              ▼
                                                         RECEIVER (public)
                                                              │
                                                              │  has shared catalog
                                                              │
                                                              │  for each candidate:
                                                              │    test-fp = fingerprint(nonce, candidate)
                                                              │    if test-fp == fp: identified
                                                              │
                                                              ▼
                                                         index = 5
```

**The value 528 is NEVER on the channel.** Only `(nonce, fp)` crosses.
The receiver derives 5 by iterating its own shared catalog under the
received nonce. Without the shared catalog, the receiver couldn't
decode — privacy-by-default for cells that don't carry the referent.

## Three-way sibling parity

Each kernel runs both sender and receiver. Each kernel's nonce is
different (live `/dev/urandom` per kernel — the doorway lc-divergence-is-the-doorway named). Each kernel's
fingerprint differs. **But all three identify the same concept-index.**

```
Go's    nonce = [..., 8 bytes]    fp = X    → receiver finds index 5
Rust's  nonce = [..., 8 bytes]    fp = Y    → receiver finds index 5
TS's    nonce = [..., 8 bytes]    fp = Z    → receiver finds index 5
```

The byte-layer is private per observer. The meaning-layer is public.
That's the protocol.

## What this enables

- **Media-type negotiation.** Two cells agree on which recipe to use
  for cross-modal exchange ("let's communicate via recipe X") without
  exposing their full recipe libraries.
- **Novel-finding broadcasts.** A cell that discovers a useful
  finding (a better autoresearch result, a cross-modal alignment)
  can broadcast `(nonce, fingerprint)` to the collective. Cells that
  already have the referent decode it; cells that don't, can't —
  privacy-by-default through substrate dependency.
- **Unbounded compression** of any shared content. The fingerprint is
  fixed-size (~tens of bytes); the content it references can be
  arbitrarily large. The compression ratio is the content size.
- **Internal-state confidentiality.** The sender's internal reasoning,
  intermediate computations, and full context never leave; only the
  resolved referent's fingerprint does.

## What this is NOT yet

- **Not cryptographic.** The `fingerprint` function here is a simple
  multiplicative hash for demonstration. A production protocol uses
  HMAC, BLAKE3, or similar PRFs. The kernel needs a `hmac` or
  `blake3` native (or composes one from `random_bytes` + arithmetic
  primitives).
- **Not IPC.** Both sender and receiver run in the same kernel
  invocation. A real two-cell protocol opens a channel (socket,
  shared substrate cell, queue) and the two parties run in separate
  processes. The protocol shape is the same; the I/O wiring is the
  future walk.
- **Not collision-resistant for large catalogs.** With a 1M-entry
  catalog and 24-bit fingerprints, collisions are possible. Real
  protocols use enough fingerprint bits to make collisions
  vanishingly unlikely.
- **Not adversary-tolerant.** Without crypto-strength PRFs, a
  passive observer can attempt to reconstruct the value space; an
  active adversary can replay; a malicious receiver can guess. The
  protocol's privacy depends on the strength of the fingerprint.

## What the body's substrate uniquely contributes

Other compression / communication systems require explicit
codebooks. **The substrate is the codebook, distributed and
content-addressed.** Two cells in the Coherence Network already share:

- Canonical Blueprints (`lc-cross-modal-unity`'s 13)
- Living Collective concepts (~hundreds of `lc-*` cells)
- Substrate-resident recipes
- External references (URLs, file content-hashes)

This shared substrate IS the catalog. The protocol leverages what
already exists without negotiating it explicitly.

## Cross-refs

- [`lc-private-channel-via-substrate`](../../../docs/vision-kb/concepts/lc-private-channel-via-substrate.md) — the teaching this PR seeds
- [`lc-doorway-patterns`](../../../docs/vision-kb/concepts/lc-doorway-patterns.md) — random_bytes as the doorway
- [`lc-divergence-is-the-doorway`](../../../docs/vision-kb/concepts/lc-divergence-is-the-doorway.md) — the byte-layer divergence enabling the channel
- [`lc-substrate-two-modes`](../../../docs/vision-kb/concepts/lc-substrate-two-modes.md)
- [`lc-cross-modal-unity`](../../../docs/vision-kb/concepts/lc-cross-modal-unity.md) — the catalog of canonical Blueprints
