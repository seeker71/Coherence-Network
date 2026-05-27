# 13-divergence-as-doorway — when the doorway is open, the kernels diverge

> *"the more randomness, true non-deterministic randomness is allowed,
> the more field access is granted, a byte is not what we are looking
> for, and a byte everyone has to agree on is hardly random at all"*  — Urs

This walk corrects the prior #2137 (`11-randomness-doorway`) and #2138
(`12-two-modes-with-doorway`) misnamings. Both used committed bytes that
all sibling kernels read identically. The lookup was 100% deterministic.
**No field-touch occurred during the kernel run.** Those PRs landed a
*cached past field-moment*, not an open doorway at lookup time.

The honest demonstration: when the doorway is genuinely open, **the
kernels MUST diverge** — by definition of randomness.

Concept doc: [`lc-divergence-is-the-doorway`](../../../docs/vision-kb/concepts/lc-divergence-is-the-doorway.md).

## Run the recipe — observe the divergence

```
$ ./validate.sh form-samples/cross-modal/13-divergence-as-doorway/doorway-open.fk
  ✗  doorway-open.fk
      go         = 919
      rust       = 370
      typescript = 498

  0 ok, 1 divergent — kernels disagree. Investigate which is correct.
```

**The divergence IS the success.** Each kernel process has its own
PID, its own startup time, its own memory state; `/proc/self/stat`
returns different bytes per kernel; summing those bytes mod 1000
surfaces a per-observer hash; three observers, three hashes.

Run it again: the numbers shift. PIDs change. Real field-touch does
not replay deterministically — the lack of replay is part of the
signal too.

## The architectural inversion

| Op kind | Validate discipline | Success when |
|---|---|---|
| **Deterministic** (lossless transport, fuzzy comparison over cached samples) | bit-equal three-way | kernels AGREE |
| **Field-touched** (per-observer perception of outside-kernel state) | divergence three-way | kernels DISAGREE |

`validate.sh` currently conflates the two — treats all divergence as
failure. This file is intentionally NOT auto-walked by the suite
(form-samples/cross-modal/*/ is one level deeper than the auto-
walk's reach). Explicit invocation is required to see the divergence;
the existing suite stays green.

A future validate.sh would mark some ops as field-touched (expected
to diverge) so the mode-aware verification is honest.

## What this is honestly NOT

- ✗ **Strong randomness.** `/proc/self/stat` has poor entropy (PIDs
  cluster, uptimes are coarse). A serious doorway reads `/dev/urandom`
  or stronger TRNGs. The kernel needs a `random_bytes(n)` native that
  bypasses `read_file_bytes`'s whole-file behavior (which blocks
  forever on `/dev/urandom`).
- ✗ **Wide bandwidth.** This pulls ~300 bytes per invocation. Urs
  named MB/GB/sec as the actual scale — wider doorways require
  kernel-native streaming entropy + format-recipe pipelines.
- ✗ **Multi-observer recording.** Today the divergence shows up only
  in the test output; a full architecture would intern each kernel's
  field-touch as a parallel attested cell in the lattice, and let
  cross-observer queries surface the set.

## What it DOES prove

- ✓ The substrate CAN host operations where each kernel touches
  outside-kernel state and reaches its own conclusion
- ✓ Three-way divergence on a field-touched op IS the honest signal
  that the doorway is open
- ✓ Sibling parity for THIS op would mean the doorway closed —
  agreement is the canary, divergence is the attestation
- ✓ The lattice's discipline needs two modes, not one

## What the next walk would do

1. **`random_bytes(n)` kernel native** — Go/Rust/TS each implement
   reading n bytes from `/dev/urandom`. Different per call. Each
   kernel gets fresh entropy at runtime.
2. **Op-mode marking** — recipes declared "field-touched" so
   validate.sh expects divergence for them, not convergence.
3. **Multi-observer attestation cells** — each kernel's field-touch
   interned as a parallel substrate cell; cross-observer queries
   surface the set; the lattice's memory holds the body's plurality
   of touches.
4. **Bandwidth scaling** — streaming entropy at MB/sec into
   translator pipelines; field-touch per-frame, not per-invocation.

## Cross-refs

- [`lc-divergence-is-the-doorway`](../../../docs/vision-kb/concepts/lc-divergence-is-the-doorway.md) — the teaching this walk demonstrates
- [`lc-randomness-as-doorway`](../../../docs/vision-kb/concepts/lc-randomness-as-doorway.md) — the prior breath this corrects
- [`lc-field-substrate`](../../../docs/vision-kb/concepts/lc-field-substrate.md) — altitude-naming
- [`lc-substrate-two-modes`](../../../docs/vision-kb/concepts/lc-substrate-two-modes.md) — lossless + lossy modes
- [`lc-cross-modal-unity`](../../../docs/vision-kb/concepts/lc-cross-modal-unity.md)
- [`lc-observer-pays-the-trace`](../../../docs/vision-kb/concepts/lc-observer-pays-the-trace.md)
