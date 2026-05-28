# 45-rle — Run-Length Encoding as a Form recipe

Run-Length Encoding is the simplest reversible compression: a run of
identical bytes collapses to a `(count, byte)` pair; non-runs emit as
`count=1` pairs. The recipe in
[`form-stdlib/rle.fk`](../../../form-stdlib/rle.fk) composes it from
the kernel's small-int primitives plus `cons` / `head` / `tail` — no
host compression library, no RLE native. Three sibling kernels (Go,
Rust, TypeScript) agree on every encoded byte-sum AND on the
round-trip identity that returns the original sequence unchanged.

## What walked

```
$ ./validate.sh form-stdlib/rle.fk form-samples/cross-modal/45-rle/rle.fk
  ✓  rle.fk+rle.fk   → enc-empty-sum: 0
                       empty-round-trip: 1
                       enc-mixed-sum: 12
                       mixed-round-trip: 1
                       enc-same-sum: 9
                       same-round-trip: 1
                       enc-20-sum: 470
                       rt-20-identity: 1
                       7
  1 ok, 0 divergent — kernels agree on every sample.
```

Four input shapes — empty list, all-same `[5 5 5 5]`, mixed-runs
`[1 1 1 2 3 3]`, and a 20-byte mixed sequence — each survive the
encode → decode loop unchanged. Final verdict **7** matches across
every sibling kernel.

## The shape

```
rle-encode(byte-list) :
   walk head-to-tail tracking (current value, current count)
   when next byte differs: flush (count, value) pair, start a new run
   when count exceeds 255: split into (255, value) chunks + remainder
   on end-of-input: flush the final run
   reverse the accumulator once
   return encoded byte-list

rle-decode(byte-list) :
   walk two bytes at a time: (count, value) → emit count copies of value
   reverse the accumulator once
   return original byte-list
```

The format is a flat byte-list: even-indexed bytes are counts in
`1..255`, odd-indexed bytes are the values being repeated. No escape
codes, no sentinels — the decoder always reads pairs.

## Worked examples

| input | encoded |
|-------|---------|
| `[]` | `[]` |
| `[5 5 5 5]` | `[4 5]` |
| `[1 1 1 2 3 3]` | `[3 1 1 2 2 3]` |
| `[0xAA 0xAA 0xAA 0xBB 0xCC 0xCC]` | `[3 0xAA 1 0xBB 2 0xCC]` |
| 257 copies of `7` | `[255 7 2 7]` |

The run-over-255 split is deterministic: emit `(255, byte)` zero or
more times, then a final `(remainder, byte)` pair. A decoder seeing
`[255 7 2 7]` builds a 257-byte run because two adjacent pairs over
the same value reconstruct as one contiguous output run — the format
doesn't need a "this pair continues the previous one" flag.

## Caveats — RLE semantics, not bugs

- **Worst-case expansion.** A sequence with no repeated bytes encodes
  to twice its size (`[1 a 1 b 1 c ...]`). RLE is honest about this;
  the compression is real only when runs exist in the input. Adaptive
  formats (PCX, TIFF Packbits) work around this with a "literal run"
  opcode that this minimal recipe doesn't carry.
- **Count of 0 never emits.** The encoder only flushes on actual byte
  change or end-of-input, so `(0, byte)` pairs never appear in
  well-formed output. The decoder still handles them gracefully —
  zero copies of any byte is a no-op.
- **Byte values are unconstrained.** Any byte 0..255 can be either a
  count or a value; the format relies entirely on position parity,
  not on reserved bytes.

## Cost note

Both encode and decode are O(n) over input length: single pass,
head/tail straight through, accumulator-then-reverse for cheap cons.
The 20-byte round-trip vector finishes in well under a millisecond on
every sibling kernel.

## Cross-refs

- [`form-stdlib/rle.fk`](../../../form-stdlib/rle.fk) — the canonical recipe
- [`form-stdlib/tests/rle-band.fk`](../../../form-stdlib/tests/rle-band.fk) — sibling-witness band test
- 30-base64, 32-crc32, 38-hex, 44-adler32 — sibling Form-recipe byte-level constructions
- 18-substrate-compression — broader compression arc this lives inside
