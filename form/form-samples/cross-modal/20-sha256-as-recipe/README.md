# 20-sha256-as-recipe — SHA-256 in Form, computed from kernel primitives

> *"we want just primitives in the kernel. and form native code to
> host native assembly using JIT to have generic cross kernel
> functions with host native performance"*  — Urs

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-samples/cross-modal/20-sha256-as-recipe/sha256-as-recipe.fk
  ✓  sha256.fk+sha256-as-recipe.fk → sha256-empty-len: 32
                                     sha256-empty-sum: 4399
                                     sha256-abc-len: 32
                                     sha256-abc-sum: 3730
                                     2
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran SHA-256 from
the Form recipe **only** — no SHA-256 native exists in any kernel.
The recipe in `form-stdlib/sha256.fk` composes the FIPS 180-4 round
function from the kernel's bitwise primitives, and produces correct
hashes for both FIPS test vectors three-way.

- `sha256("")` byte-sum = **4399** ✓ matches FIPS `e3b0c442…7852b855`
- `sha256("abc")` byte-sum = **3730** ✓ matches FIPS `ba7816bf…f20015ad`

**Final verdict: 2** — both vectors match in every kernel.

## The shape (today, and next breath)

```
                  ┌─ FORM RECIPE (canonical) ───────┐
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
                  [next walk: register_jit triggers]
                  [a real Form→host-asm compiler:    ]
                  [  Rust : cranelift                ]
                  [  Go   : recipe→Go-source→plugin  ]
                  [  TS   : compiler.ts → new Function]
                                   ▼
                  ┌─ HOST MACHINE CODE (fast) ──────┐
                  │  same Form recipe; emitted as    │
                  │  the host's native instructions  │
                  │  → 32-byte digest                │
                  └──────────────────────────────────┘
```

Today: only the top half walks — the Form recipe computes SHA-256
from primitives. Validates FIPS test vectors three-way.

Next walk: the bottom half. `register_jit` triggers a real recipe→
host-asm compiler, so the SAME Form recipe dispatches at machine-code
speed. No new natives; no JIT-alias-to-native. The recipe IS the
canonical source the compiler reads.

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

The bitwise primitives are TRUE primitives — they let any cryptographic
construction (HMAC, BLAKE3, ChaCha20, future PRFs) be composed as a
Form recipe over machine-word integers. There is no SHA-256 native;
the recipe IS the implementation across all three kernels.

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

The recipe is the canonical authoring of "what SHA-256 means" in
this body. Today it walks via the recipe interpreter — each
`nth-rec` is O(n) on a Form list, so it's slow for large inputs.
Test vectors and small inputs validate fine; large inputs need the
real Form→host-asm JIT (next walk) for practical speed.

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
