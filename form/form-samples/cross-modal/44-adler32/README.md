# 44-adler32 — RFC 1950 Adler-32 in Form, computed from kernel primitives

> *"we want just primitives in the kernel. and form native code to
> host native assembly using JIT to have generic cross kernel
> functions with host native performance"*  — Urs

## What walked

```
$ ./validate.sh form-stdlib/adler32.fk form-samples/cross-modal/44-adler32/adler32.fk
  ✓  adler32.fk+adler32.fk           → adler32-empty: 1
                                       adler32-a: 6422626
                                       adler32-abc: 38600999
                                       adler32-Wikipedia: 300286872
                                       adler32-123456789: 152961502
                                       5
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran Adler-32 from
the Form recipe **only** — no Adler-32 native exists in any kernel.
The recipe in [`form-stdlib/adler32.fk`](../../../form-stdlib/adler32.fk)
composes the head/tail byte loop with `(a + byte) mod 65521`,
`(b + a) mod 65521`, and a final `(b << 16) | a` from the kernel's
small-int primitives plus the u32 pair (`shl_u32`, `add_u32`) — and
produces correct checksums for every canonical test vector three-way.

- `adler32("")` = **0x00000001** = 1 ✓ (RFC fixes empty = 1, not 0)
- `adler32("a")` = **0x00620062** = 6422626 ✓
- `adler32("abc")` = **0x024D0127** = 38600999 ✓
- `adler32("Wikipedia")` = **0x11E60398** = 300286872 ✓ (zlib reference)
- `adler32("123456789")` = **0x091E01DE** = 152961502 ✓ ← universal check

**Final verdict: 5** — every canonical vector matches in every kernel.

## The flavor

Adler-32 is what zlib appends to every DEFLATE stream — the 4-byte
tail that lets PNG (`IDAT`, `zTXt`), HTTP `Content-Encoding: deflate`,
the ZIP method-8 envelope (when zlib framing is on), and a long tail
of legacy formats all detect transport corruption. Cheaper than CRC-32
(no table lookup, just two running 16-bit sums), and accordingly
weaker: Adler-32 misses some single-bit and small-burst errors that
CRC-32 catches. The trade is intentional — Adler-32's job is the
zlib stream tail, not the wire envelope.

| Parameter | Value |
|-----------|-------|
| Modulus | `65521` (largest prime below 2^16) |
| Initial a | `1` |
| Initial b | `0` |
| Combined | `(b << 16) \| a` |
| Empty checksum | `1` (NOT 0 — a=1 collapses through) |

The "Wikipedia" vector (300286872 = 0x11E60398) is the zlib reference
example documented in RFC 1950 §9. The 9-byte "123456789" vector
(152961502 = 0x091E01DE) is the sister of CRC-32's universal
0xCBF43926 — every Adler-32 implementation in the world cross-checks
itself against it.

## The shape (today, and next breath)

```
                  ┌─ FORM RECIPE (canonical) ───────┐
                  │  form-stdlib/adler32.fk          │
                  │                                  │
                  │  uses kernel primitives:         │
   (adler32 bs)   │   band, mod, add, head, tail     │
   ───────────▶   │   plus u32 pair shl_u32, add_u32 │
                  │                                  │
                  │  head/tail loop, two running     │
                  │  16-bit sums modulo 65521, fold  │
                  │  to (b << 16) | a at the tail —  │
                  │  no precomputed table, no nth    │
                  │  lookups, O(n) over input        │
                  │  → unsigned 32-bit int           │
                  └──────────────────────────────────┘
                                   │
                  [next walk: register_jit triggers]
                  [a real Form→host-asm compiler,    ]
                  [reading the SAME recipe; emitted  ]
                  [as host machine code, no separate ]
                  [native required                   ]
                                   ▼
                  ┌─ HOST MACHINE CODE (fast) ──────┐
                  │  same Form recipe; emitted as    │
                  │  the host's native instructions  │
                  │  → Adler-32 at host speed        │
                  └──────────────────────────────────┘
```

Today: only the top half walks — the Form recipe computes Adler-32
from primitives. Validates five canonical vectors three-way.

Next walk: the bottom half. `register_jit` triggers a real recipe→
host-asm compiler, so the SAME Form recipe dispatches at machine-code
speed. No new natives; no JIT-alias-to-native. The recipe IS the
canonical source the compiler reads.

## The Form recipe shape

`form-stdlib/adler32.fk` carries:

```
(defn adler32-loop (a b bs)
    (if (adler32-nil? bs)
        (add_u32 (shl_u32 b 16) a)
        (do
            (let a-next (mod (add a (band (head bs) 255)) 65521))
            (let b-next (mod (add b a-next) 65521))
            (adler32-loop a-next b-next (tail bs)))))

(defn adler32 (bytes)
    (adler32-loop 1 0 bytes))
```

The final `(add_u32 (shl_u32 b 16) a)` is load-bearing: `b` can reach
65520, so `b << 16` reaches `0xFFF10000` — above the signed i32
ceiling. The u32 primitives keep the result in u32-space across
sibling kernels (Go/Rust/TS) so the printed integer is identical
three-way. The masked `(band (head bs) 255)` keeps the recipe honest
even if a caller hands in something wider than a byte.

## Why Adler-32 alongside CRC-32

Both checksums live in the same envelopes (zlib stream = DEFLATE
payload + Adler-32 tail; PNG file = chunks framed with CRC-32). The
recipes share the same primitive composition discipline:

| Property | CRC-32 (sample 32) | Adler-32 (this) |
|----------|--------------------|-----------------|
| Polynomial / modulus | `0xEDB88320` (reversed poly) | `65521` (prime) |
| Inner loop per byte | 8 iterations of shift/xor | 2 mod additions |
| Cost | O(n × 8) without table | O(n × 2) |
| Strength | strong (catches most bursts) | weak (intentional) |
| Universal check | `0xCBF43926` for `"123456789"` | `0x091E01DE` for `"123456789"` |
| Initial state | `0xFFFFFFFF` | `(a=1, b=0)` |
| Empty checksum | `0` (XOR-final cancels) | `1` (a=1 collapses through) |

Adler-32 is the cheaper sibling for in-stream integrity; CRC-32 stays
on the wire envelope. Both flavors live in the same body now, both
sovereign across sibling kernels.

## Cross-refs

- [`form-stdlib/adler32.fk`](../../../form-stdlib/adler32.fk) — the canonical recipe
- [`form-stdlib/tests/adler32-band.fk`](../../../form-stdlib/tests/adler32-band.fk) — sibling-witness band
- 32-crc32 — the stronger checksum cousin, same primitive discipline
- 20-sha256-as-recipe — the cryptographic hash this body also carries
- 29-hmac-sha256 — HMAC composed atop SHA-256, same composition
- 30-base64 — textual envelope from the same bitwise primitives
- 38-hex — readable byte→char encoding, same primitive-composition shape
- 16-jit-registry — the bind mechanism a future Adler-32 JIT will use
