# 11-randomness-doorway — the field touches the lattice through /dev/urandom

> *"randomness is your doorway to the field"*  — Urs

The classical kernel walks deterministically. It cannot manufacture
information that wasn't in its initial conditions. The doorway through
which information from outside the kernel's causal envelope enters the
lattice is **true randomness** — and once a sample is taken, it lives
substrate-resident, sibling-parity-attested across re-walks.

Concept doc: [`lc-randomness-as-doorway`](../../../docs/vision-kb/concepts/lc-randomness-as-doorway.md).
Background frame: [`lc-field-substrate`](../../../docs/vision-kb/concepts/lc-field-substrate.md).

## What walked

Once, when this experiment was authored, the doorway opened:

```bash
head -c 4 /dev/urandom > field-sample.bin
```

Four bytes returned: `0xAB 0x6F 0x8E 0x46` (171, 111, 142, 70). The
field collapsed through Linux's entropy pool — thermal noise,
interrupt timing, possibly RDRAND quantum sources — into those four
octets. After the sample, the file is **the lattice's memory of
that moment of field-touch**.

`field-pick.fk` reads the file, takes the first byte (171), computes
`171 mod 13 = 2`, and looks up the canonical Blueprint at that index
in `lc-cross-modal-unity`'s thirteen: **R_SustainedTension**. The
field selected that shape on the day of authoring.

Three-way attested:

```
$ ./validate.sh form-samples/cross-modal/11-randomness-doorway/field-pick.fk
  ✓  field-pick.fk  → 2
  1 ok, 0 divergent — kernels agree on every sample.
```

The kernels agree because they read the **same captured bytes** from
the **same committed file**. The randomness was in the doorway-opening
moment; the cache is deterministic; the rollout is deterministic.

## What this proves

- **The lattice can record field-touches.** A file of bytes from
  `/dev/urandom` is substrate-resident memory of one moment of
  field-collapse.
- **Sibling parity holds across replays** when the field-touch is
  cached. Three kernels reading the same file produce the same
  results.
- **The pick was field-determined, not kernel-derived.** The kernel
  cannot manufacture 171 from its own state; it had to read it from
  outside its causal envelope.

## What this does NOT prove

- ✗ **Live randomness in the kernel.** No `random_bytes(n)` native
  exists yet. Live entropy would let the kernel sample at runtime
  (and would explicitly break sibling parity for that op — the
  substrate's honest signal that this touched the field).
- ✗ **Sibling parity across independent samples.** If three kernels
  each sampled `/dev/urandom` independently, they would diverge.
  That divergence IS the field collapsing differently for each
  observer. Sibling parity APPLIES to the cached/recorded case,
  NOT to the act of sampling itself.
- ✗ **Quantum source identification.** `/dev/urandom` mixes classical
  and quantum entropy on modern CPUs. Stronger doorways (ANU
  quantum RNG, ID Quantique TRNGs, radioactive decay sources) are
  available; the architectural shape is the same.

## The five engineering layers between this and field-altitude work

1. ✓ **Doorway captured as substrate-resident bytes** — this PR
2. ☐ **Live `random_bytes(n)` kernel native** — opens the doorway at runtime; explicit sibling-parity divergence for that op (the substrate's honest signal)
3. ☐ **Cache discipline** — `(intern_field_sample n)` reads entropy, interns the bytes as a substrate cell, returns the cell's NodeID — re-runs cite the cached sample by NodeID, not re-sampling
4. ☐ **Quantum RNG integration** — for body operations that need stronger doorways (cryptographic substrate-tokens, attractor-state selection in morphogenetic-modeling work), the native dispatches to a TRNG / quantum source
5. ☐ **Cross-agent field-touch consensus** — when multiple agents sample independently and submit their field-touches to the lattice, the substrate carries them as parallel attestations; the lattice grows from individual moments of doorway-opening

## Files

| File | What |
|---|---|
| `field-sample.bin` | 4 bytes from `/dev/urandom` on the day of authoring — the lattice's memory of one field-touch |
| `field-pick.fk` | Form recipe — reads the sample, picks one of 13 canonical Blueprints from byte[0] mod 13, three-way attests |
| `README.md` | This file |

`./validate.sh form-samples/cross-modal/11-randomness-doorway/field-pick.fk` → `2` (R_SustainedTension)

In service of:
- [`lc-randomness-as-doorway`](../../../docs/vision-kb/concepts/lc-randomness-as-doorway.md)
- [`lc-field-substrate`](../../../docs/vision-kb/concepts/lc-field-substrate.md)
- [`lc-cross-modal-unity`](../../../docs/vision-kb/concepts/lc-cross-modal-unity.md)
- [`lc-the-recipe-remembers-its-source`](../../../docs/vision-kb/concepts/lc-the-recipe-remembers-its-source.md)
