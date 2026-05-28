# 58-uuid — UUID v4 generation as a Form recipe

> *"we want just primitives in the kernel. and form native code to
> host native assembly using JIT to have generic cross kernel
> functions with host native performance"*  — Urs

## What walked

```
$ ./validate.sh form-stdlib/uuid.fk form-samples/cross-modal/58-uuid/uuid.fk
  ✓  uuid.fk+uuid.fk                 → zero-matches: 1
                                       max-matches: 1
                                       len-zero: 36
                                       roundtrip-match: 1
                                       4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran UUID v4 generation
from the Form recipe **only** — no UUID native exists in any kernel. The
recipe in [`form-stdlib/uuid.fk`](../../../form-stdlib/uuid.fk) composes
the version-and-variant patching from the kernel's bitwise primitives
(`band`, `bor`) plus the string natives (`str_concat`, `substring`,
`byte_to_str`), producing RFC 4122 §4.4 conformant output three-way.

- `uuid-v4 [0]*16` → **"00000000-0000-4000-8000-000000000000"**
  (version nibble `4` at position 14; variant nibble `8` at position 19)
- `uuid-v4 [255]*16` → **"ffffffff-ffff-4fff-bfff-ffffffffffff"**
  (byte 6 high nibble forced to `4`; byte 8 high two bits forced to `10`)
- `uuid-parse uuid-v4(zero-input)` round-trips to the patched binary form
  (byte-sum 192 = `0x40` + `0x80`)
- Output length is exactly 36 chars (32 hex + 4 hyphens)

**Final verdict: 4** — every shape lands correctly in every kernel.

## The shape

UUID v4 is 128 random bits with two fields rewritten from raw randomness:

```
                  ┌─ FORM RECIPE (canonical) ───────┐
                  │  form-stdlib/uuid.fk             │
                  │                                  │
                  │  uses kernel bitwise + string    │
   (uuid-v4 bs)   │   primitives only                │
   ───────────▶   │                                  │
                  │  byte 6: (bor (band b 0x0F) 0x40)│  ← version = 4
                  │  byte 8: (bor (band b 0x3F) 0x80)│  ← variant = 10
                  │                                  │
                  │  emit 8-4-4-4-12 hex with        │
                  │   hyphens at positions 8/13/18/23│
                  │                                  │
                  │  → 36-char canonical string      │
                  │  → 16-byte list OR error sentinel│
                  └──────────────────────────────────┘
```

## Why deterministic byte-lists (not random_bytes)

`(random_bytes 16)` is the production source for the 16 input bytes —
the cell layer wires it in: `(uuid-v4 (random_bytes 16))`. We do **not**
call it from the sample. By design, `random_bytes` DIVERGES across the
three kernels (Go's `crypto/rand`, Rust's `rand::thread_rng`, TS's
`crypto.randomBytes` each draw from different entropy sources), so a
sibling-parity test must pass deterministic input to converge on a single
expected output.

This separation is the same discipline the ULID sample (43-ulid) uses:
the recipe is pure; the entropy is the cell's responsibility.

## The error sentinel

`uuid-parse` returns one of two shapes:

- a **16-byte list** when input is a valid 8-4-4-4-12 hex string
- the **`UUID-PARSE-ERROR`** NodeID for any malformed input

The sentinel is a substrate-resident `NodeID(1, 2, 99, 1871)` —
addressable, content-equal, and discoverable across kernels. Callers
detect with `(value_eq result UUID-PARSE-ERROR)`.

```
(let result (uuid-parse "not-a-uuid"))
(if (value_eq result (make_nodeid 1 2 99 1871))
    "invalid uuid"
    result)
```

Parse rejects: wrong length, hyphens outside positions 8/13/18/23,
non-hex characters at any data position.

## Cross-refs

- [`form-stdlib/uuid.fk`](../../../form-stdlib/uuid.fk) — the canonical recipe
- [`form-stdlib/tests/uuid-band.fk`](../../../form-stdlib/tests/uuid-band.fk) — sibling-witness band test
- 43-ulid — same deterministic-input discipline, different identifier shape
- 38-hex — the lowercase hex alphabet UUID reuses
- 11-randomness-doorway — where `random_bytes` enters the body
- 16-jit-registry — the bind mechanism a future UUID JIT will use
