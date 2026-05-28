# 43-ulid — ULID Crockford-Base32 in Form, computed from kernel primitives

> *"we want just primitives in the kernel. and form native code to
> host native assembly using JIT to have generic cross kernel
> functions with host native performance"*  — Urs

## What walked

```
$ ./validate.sh form-stdlib/ulid.fk form-samples/cross-modal/43-ulid/ulid.fk
  ✓  ulid.fk+ulid.fk               → ulid-zero: 00000000000000000000000000
                                     ulid-max:  7ZZZZZZZZZ0000000000000000
                                     len-zero: 26
                                     len-max:  26
                                     zero-matches: 1
                                     max-matches:  1
                                     4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran the
[ULID spec](https://github.com/ulid/spec) encoding from the Form recipe
**only** — no ULID native exists in any kernel. The recipe in
`form-stdlib/ulid.fk` composes the standard 5-bit Crockford-Base32 chunking
from the kernel's bitwise primitives (`band`, `bor`, `shl_u32`, `shr_u32`),
and produces the correct 26-character output for both corner test vectors
three-way.

- Empty ULID (timestamp=0, random=zeros) → **"00000000000000000000000000"** ✓
- Max-timestamp ULID (timestamp=2⁴⁸-1, random=zeros) → **"7ZZZZZZZZZ0000000000000000"** ✓

**Final verdict: 4** — both 26-char length assertions and both exact-string
matches hold across every kernel.

## The shape

A ULID is 128 bits laid out as:

```
  ┌──────────────────────────┬────────────────────────────────────────┐
  │ 48-bit unix-ms timestamp │ 80 bits of randomness                  │
  └──────────────────────────┴────────────────────────────────────────┘
   ◄────────── 10 chars ────►◄────────── 16 chars ──────────────────►
```

26 characters of Crockford Base32 (alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ`
— 32 chars, excludes `I`, `L`, `O`, `U` to dodge digit confusion).

The 128 bits don't divide evenly into 5-bit chunks (128/5 = 25.6), so the
spec prepends 2 zero pad bits at the very top of the timestamp half:
**130 = 26 × 5**. That's why the first character of a max-timestamp ULID
is `7` not `Z` — its 5-bit value is `00 + 111` (the two pad zeros plus the
top three timestamp bits), capping at index 7.

Lexicographic order ↔ chronological order falls out for free, because
Crockford Base32 chars sort in the same order as their values, and the
timestamp lives in the high bits.

## The Form recipe shape

`form-stdlib/ulid.fk` carries two entry points:

```
;; Workhorse: 16-byte input → 26-char Crockford-Base32 string.
(defn ulid-from-bytes (sixteen-bytes)
    (ulid-emit-loop sixteen-bytes 0 2 ""))

;; Convenience: 32-bit timestamp (top 16 bits of the 48-bit slot stay
;; zero, true through year ~2106) + 10 random bytes → 26-char string.
(defn ulid-from-parts (timestamp-32 random-10-bytes)
    ...)
```

The encoder maintains a small bit buffer (low bits of a u32, with `nbits`
tracking how many are valid), starting at `(buf=0, nbits=2)` — those two
zero pad bits represent the front-pad needed to align 128 input bits into
26 × 5-bit chunks. The drain function peels chars while `nbits ≥ 5`; the
outer fold-loop folds in the next input byte (raising `nbits` by 8).

## Two entry points — why not one 48-bit integer

The TS sibling kernel's default math width is **i32** — literal parse,
`div`, `mod`, `add` all funnel through `(n | 0)`. A 48-bit integer literal
silently truncates in TS, so any recipe that accepts `timestamp-48 : integer`
would diverge from Go/Rust (both i64) on values above 2³² - 1.

The **byte-list shape** (`ulid-from-bytes`) sidesteps this entirely — every
byte fits comfortably in 8 bits, and the encoder needs no wide-integer
arithmetic. Production cells split their host-clock timestamp into 6 big-
endian bytes before calling, which is a 3-line `div 256 / mod 256` peel
in any 64-bit-capable host language.

The **convenience shape** (`ulid-from-parts`) accepts a u32 timestamp
directly — practical for unix-millisecond clocks where the top 16 bits
stay zero through the year ~2106. Inside, it composes the 6-byte prefix
(top 2 bytes zero, low 4 bytes from `shr_u32`) and calls `ulid-from-bytes`.

## Wiring randomness in production

The recipe is pure — it never reads a clock or RNG itself. Production cells
wire their host clock and `(random_bytes 10)` into the call:

```
;; In a production cell with a millisecond clock and per-kernel RNG.
(let now-ms       (host-now-millis))            ; 48-bit unix-ms
(let entropy      (random_bytes 10))            ; 80 bits of randomness
(let ts-bytes     (split-48-into-6-bytes now-ms))
(let all-bytes    (bytes-append ts-bytes entropy))
(let id           (ulid-from-bytes all-bytes))
```

**Why this sample does NOT use `(random_bytes 10)`:** the `random_bytes`
native DIVERGES per kernel by design (Go, Rust, and TypeScript draw
randomness from different entropy sources for the cross-kernel divergence
experiments — see [11-randomness-doorway](../11-randomness-doorway/),
[14-live-entropy](../14-live-entropy/)). Sibling-parity validation needs
deterministic byte-lists, which is what this sample passes (zero bytes for
both corners). The recipe stays sovereign across all three kernels.

## Cross-refs

- [`form-stdlib/ulid.fk`](../../../form-stdlib/ulid.fk) — the canonical recipe
- [`form-stdlib/tests/ulid-band.fk`](../../../form-stdlib/tests/ulid-band.fk) — sibling-witness band
- [30-base64](../30-base64/) — the same 5-bit-chunking shape applied to RFC 4648 §4
- [32-crc32](../32-crc32/) — the partner walk for IEEE 802.3 CRC-32 from primitives
- [20-sha256-as-recipe](../20-sha256-as-recipe/) — SHA-256 from the same primitives
- [11-randomness-doorway](../11-randomness-doorway/) — why `random_bytes` diverges
- [16-jit-registry](../16-jit-registry/) — the bind mechanism the JIT walk will use
