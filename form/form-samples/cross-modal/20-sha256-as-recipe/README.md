# 20-sha256-as-recipe — SHA-256 in Form, opt-in to native via JIT

> *"have shared binary features in form native recipes that can
> expand into native machine code for efficiency, allowing the kernel
> to bootstrap from primitives into an efficient, flexibility,
> sovereign cell"*  — Urs
>
> *"we already have sha256 in core as form native recipes available
> as JIT function?"*  — Urs (the question that opened this walk)

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-samples/cross-modal/20-sha256-as-recipe/sha256-as-recipe.fk
  ✓  sha256.fk+sha256-as-recipe.fk → recipe-empty-sum: 4399
                                     recipe-abc-sum: 3730
                                     jit-bound: 1
                                     native-empty-sum: 4399
                                     native-abc-sum: 3730
                                     empty-bytes-match: 1
                                     abc-bytes-match: 1
                                     256-byte-input-sum: 4118
                                     5
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran SHA-256 two
ways and agreed on every line. **Final verdict: 5** — all five
attestations pass:

1. `recipe sha256("")` byte-sum equals **4399** — matches FIPS 180-4
   test vector `e3b0c442 98fc1c14 9afbf4c8 996fb924 27ae41e4 649b934c
   a495991b 7852b855`.
2. `recipe sha256("abc")` byte-sum equals **3730** — matches FIPS 180-4
   `ba7816bf 8f01cfea 414140de 5dae2223 b00361a3 96177a9c b410ff61
   f20015ad`.
3. `register_jit "sha256" "sha256_bytes"` binds successfully.
4. After binding, `(sha256 ...)` calls produce **byte-identical** output
   to the recipe path for the empty input.
5. Same for `"abc"`.

## The shape

```
                  ┌─ FORM RECIPE (canonical, slow) ─┐
                  │  form-stdlib/sha256.fk           │
                  │                                  │
                  │  uses kernel bitwise primitives  │
   (sha256 bs)    │   band, bor, bxor, bnot_u32,    │
   ───────────▶   │   shl_u32, shr_u32, rotr_u32,   │
                  │   add_u32                        │
                  │                                  │
                  │  computes padding, message       │
                  │  schedule, 64 compression rounds │
                  │  → 32-byte digest                │
                  └──────────────────────────────────┘
                                   │
                  (register_jit "sha256" "sha256_bytes")
                                   ▼
                  ┌─ NATIVE (fast, opt-in) ─────────┐
                  │  Rust : sha2 crate              │
                  │  Go   : crypto/sha256 (stdlib)  │
                  │  TS   : hand-rolled FIPS 180-4  │
                  │                                  │
                  │  → 32-byte digest                │
                  └──────────────────────────────────┘
```

Same Form symbol. Same input. Same output. Two dispatch paths. The
cell chooses which.

## The kernel additions

**Eight new bitwise primitives** (true primitives — can't be expressed
in pure Form without exponential cost):

| Native | Semantics |
|--------|-----------|
| `(band a b)` | a & b |
| `(bor a b)` | a \| b |
| `(bxor a b)` | a ^ b |
| `(bnot_u32 a)` | ~a, 32-bit unsigned |
| `(shl_u32 a n)` | (a << (n & 31)), 32-bit unsigned |
| `(shr_u32 a n)` | a >>> (n & 31), 32-bit unsigned |
| `(rotr_u32 a n)` | rotate right within 32 bits |
| `(add_u32 a b)` | (a + b) mod 2^32 |

**One new fast-path native** matching the Form recipe's I/O:

| Native | Semantics |
|--------|-----------|
| `(sha256_bytes bytes-list)` | FIPS 180-4 SHA-256 → 32-byte digest |

The bitwise primitives are TRUE primitives — they let any cryptographic
construction (HMAC, BLAKE3, ChaCha20, future PRFs) be composed as a
Form recipe over machine-word integers. The `sha256_bytes` native is
the host-speed optimization specifically for SHA-256.

## The Form recipe shape

`form-stdlib/sha256.fk` carries:

```
(defn sha256 (bytes)
    ...padding (FIPS 180-4 §5.1.1)...
    ...8 initial hash values (§5.3.3)...
    ...64 round constants (§4.2.2)...
    ...per-block: message schedule (§6.2.2 step 1)...
    ...64 compression rounds (§6.2.2 step 3)...
    ...big-endian digest emission...)
```

Slower than the native by a couple of orders of magnitude (each
`nth-rec` is O(n) on a Form list), but **correct** — produces the
same bytes the native does for any input. The recipe is the canonical
authoring of "what SHA-256 means" in this body.

When a cell calls `(sha256 bs)`:

- Without JIT alias: walks the recipe. Sovereign. Slow.
- With `(register_jit "sha256" "sha256_bytes")`: dispatches through
  the native. Same bytes out. Fast.

## Why this matters for novel-state sharing

`15-private-channel` and `19-novel-state-share` both use a toy
multiplicative `hash-fold` as their fingerprint, with the explicit
caveat that "a production protocol uses HMAC, BLAKE3, or similar
PRFs." This walk seeds that future:

- Cells can now compose **HMAC-SHA-256** as a Form recipe over the
  primitives + `(sha256 ...)`.
- Cells can attach **cryptographic identity** — the persistent-id seed
  from `19-novel-state-share` hashed via real SHA-256 instead of the
  toy fold.
- Cells can attest **content authorship** with sha256-based signatures
  (still needs ed25519 or similar for the signing scheme itself, a
  future walk that uses these same primitives plus modular exponentiation).

## What this is NOT yet

- **No HMAC.** The recipe carries the hash; HMAC is a separate
  construction over it. Trivial to compose as another Form recipe.
- **No signing scheme.** ed25519 needs modular arithmetic over large
  primes — needs a few more primitives (or a native fast path) before
  it can be composed honestly.
- **No streaming API.** `sha256_bytes` and the recipe both take a
  full byte-list. A streaming `sha256_init` / `sha256_update` /
  `sha256_finalize` shape would let a cell hash arbitrarily large
  streams without materializing all bytes at once.
- **Recipe is slow.** Form-walk SHA-256 is dominated by `nth-rec`'s
  O(n) list indexing. For inputs over a few hundred bytes, the JIT
  alias is essentially required. The recipe stays canonical anyway —
  the cell chooses dispatch.

## Cross-refs

- [`form-stdlib/sha256.fk`](../../../form-stdlib/sha256.fk) — the canonical recipe
- 16-jit-registry — the bind mechanism this uses
- 19-novel-state-share — the toy hash-fold this would replace
- 15-private-channel — the fingerprint protocol this would harden
