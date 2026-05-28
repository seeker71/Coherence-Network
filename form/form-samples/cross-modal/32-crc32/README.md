# 32-crc32 — IEEE 802.3 CRC-32 in Form, computed from kernel primitives

> *"we want just primitives in the kernel. and form native code to
> host native assembly using JIT to have generic cross kernel
> functions with host native performance"*  — Urs

## What walked

```
$ ./validate.sh form-stdlib/crc32.fk form-samples/cross-modal/32-crc32/crc32.fk
  ✓  crc32.fk+crc32.fk               → crc32-empty: 0
                                       crc32-a: 3904355907
                                       crc32-abc: 891568578
                                       crc32-123456789: 3421780262
                                       4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran CRC-32 from
the Form recipe **only** — no CRC-32 native exists in any kernel.
The recipe in `form-stdlib/crc32.fk` composes the standard 8-iteration
shift/XOR per-byte loop from the kernel's bitwise primitives, and
produces correct checksums for every canonical test vector three-way.

- `crc32("")` = **0x00000000** ✓ (initial-XOR-final cancels)
- `crc32("a")` = **0xE8B7BE43** = 3904355907 ✓
- `crc32("abc")` = **0x352441C2** = 891568578 ✓
- `crc32("123456789")` = **0xCBF43926** = 3421780262 ✓ ← universal check

**Final verdict: 4** — every canonical vector matches in every kernel.

## The flavor

There are several CRCs named "CRC-32" in the wild; this is the one
that ships in zlib, PNG, gzip, ZIP, and Ethernet (802.3):

| Parameter | Value |
|-----------|-------|
| Polynomial (reversed) | `0xEDB88320` = 3988292384 |
| Initial value | `0xFFFFFFFF` = 4294967295 |
| Final XOR | `0xFFFFFFFF` = 4294967295 |
| Reflected input | yes (implicit in reversed poly + right-shift) |
| Reflected output | yes |

POSIX `cksum` is NOT this CRC (different polynomial, different framing,
no final XOR). When in doubt, the 9-byte vector `"123456789"` → `0xCBF43926`
is the cross-implementation witness.

## The shape (today, and next breath)

```
                  ┌─ FORM RECIPE (canonical) ───────┐
                  │  form-stdlib/crc32.fk            │
                  │                                  │
                  │  uses kernel bitwise primitives  │
   (crc32 bs)     │   band, bxor, shr_u32, add_u32  │
   ───────────▶   │                                  │
                  │  inner 8-iteration shift/xor     │
                  │  loop, no precomputed table —    │
                  │  Form list nth would dominate    │
                  │  cost anyway                     │
                  │  → unsigned 32-bit int           │
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
                  │  → CRC at host speed             │
                  └──────────────────────────────────┘
```

Today: only the top half walks — the Form recipe computes CRC-32
from primitives. Validates four canonical vectors three-way.

Next walk: the bottom half. `register_jit` triggers a real recipe→
host-asm compiler, so the SAME Form recipe dispatches at machine-code
speed. No new natives; no JIT-alias-to-native. The recipe IS the
canonical source the compiler reads.

## The Form recipe shape

`form-stdlib/crc32.fk` carries:

```
(defn crc32-fold8 (c i)
    (if (eq i 8) c
        (crc32-fold8
            (if (eq (band c 1) 1)
                (bxor 3988292384 (shr_u32 c 1))   ; 0xEDB88320
                (shr_u32 c 1))
            (add i 1))))

(defn crc32-step (c b)
    (crc32-fold8 (bxor c (band b 255)) 0))

(defn crc32-loop (c bs)
    (if (crc32-nil? bs) c
        (crc32-loop (crc32-step c (head bs)) (tail bs))))

(defn crc32 (bytes)
    (add_u32 (bxor (crc32-loop 4294967295 bytes) 4294967295) 0))
```

The trailing `(add_u32 _ 0)` normalizes the final XOR result to an
unsigned 32-bit integer — Go and Rust print high-bit-set `bxor` values
as signed ints, while `add_u32` always lives in u32-space. The
normalization is what gives identical printed output across all three
sibling kernels.

## Cross-refs

- [`form-stdlib/crc32.fk`](../../../form-stdlib/crc32.fk) — the canonical recipe
- [`form-stdlib/tests/crc32-band.fk`](../../../form-stdlib/tests/crc32-band.fk) — sibling-witness band
- 20-sha256-as-recipe — the SHA-256 walk this echoes
- 29-hmac-sha256 — HMAC composed atop SHA-256, same primitives
- 30-base64 — Base64 from the same bitwise primitives
- 16-jit-registry — the bind mechanism the JIT walk will use
