# 35-bloom — Bloom filter as a Form recipe

A Bloom filter is the simplest content-addressable bag: it answers
"have I seen something shaped like this?" with constant-time bit
probes, accepting a tunable false-positive rate as the trade for not
storing the inputs themselves. The recipe in
[`form-stdlib/bloom.fk`](../../../form-stdlib/bloom.fk) composes it
from the kernel's bitwise primitives plus the sha256 recipe already
living in [`form-stdlib/sha256.fk`](../../../form-stdlib/sha256.fk) —
no host bitset library, no Bloom native. Three sibling kernels (Go,
Rust, TypeScript) all answer the same "might contain?" for the same
insertion sequence.

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-stdlib/bloom.fk \
                form-samples/cross-modal/35-bloom/bloom.fk
  ✓  sha256.fk+bloom.fk+bloom.fk   → bloom-has-a: 1
                                     bloom-has-b: 1
                                     bloom-has-c: 1
                                     bloom-has-d: 0
                                     4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three values inserted (`"a"`, `"b"`, `"c"` — single ASCII bytes);
each one reads back as present. A fourth value (`"d"`) never inserted
reads back as absent. Final verdict **4** matches across every
sibling kernel.

## The shape

```
256-bit filter  →  32 bytes (each holds 8 bits)
                   bit at position p lives in byte p/8, at bit p mod 8

bloom-add(filter, bytes) :
   digest      = sha256(bytes)
   positions   = [ digest[0..1] mod 256,
                   digest[2..3] mod 256,
                   digest[4..5] mod 256 ]
   for p in positions: filter[p/8] |= (1 << (p mod 8))
   return new filter

bloom-might-contain?(filter, bytes) :
   same three positions
   return 1 iff all three bits are set
```

The filter is **functional**: `bloom-add` returns a new filter, the
old one is unchanged. The cons/recursive byte-list walk is O(n) over
32 bytes per bit-flip, which is fine for demo-sized inputs.

## Locked hash positions

Cross-checked at sample-authoring time by running `sha256` on each
single-byte input and reading the three position-extractions:

| input    | sha256 bytes [0..5] → positions |
|----------|---------------------------------|
| `"a"`    | (151, 18,  27)                  |
| `"b"`    | ( 35, 22,  57)                  |
| `"c"`    | (125,  3,  80)                  |
| `"d"`    | (172, 115, 240) — disjoint      |

`"d"` was picked specifically because none of its three positions
overlap the nine seeded by `a/b/c`. Bloom's only failure mode —
false positives from bit collision — does not fire on this fixture;
if it ever does, the chosen `"d"` is the wrong sentinel and needs
swapping for another never-added value whose positions clear the
union of present bits.

## Caveats — Bloom semantics, not bugs

- **False positives possible.** Two values can hash to the same three
  bits; the filter then reports "might contain" for a value never
  added. The probability scales with how full the filter gets — at
  256 bits with three hash functions, a few dozen inserts is fine,
  thousands are not.
- **False negatives never.** A value previously inserted ALWAYS reads
  back as present. The three bits it set stay set.

## Cost note

`sha256` itself is O(n²) per round through Form-list `nth` lookups, so
single-byte inputs are deliberate — they keep the recipe-walk fast
across all three sibling kernels. The Form→host-asm JIT (walking now
in `22-form-to-host-asm` and `33-go-jit`) lifts the same recipe to
native speed without changing the canonical source.

## Cross-refs

- [`form-stdlib/bloom.fk`](../../../form-stdlib/bloom.fk) — the canonical recipe
- [`form-stdlib/sha256.fk`](../../../form-stdlib/sha256.fk) — the hash it composes over
- [`form-stdlib/tests/bloom-band.fk`](../../../form-stdlib/tests/bloom-band.fk) — sibling-witness band test
- 20-sha256-as-recipe — the sha256 walk this builds on
- 29-hmac-sha256, 30-base64, 32-crc32 — sibling Form-recipe constructions
