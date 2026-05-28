# 38-hex — Hexadecimal encoding as a Form recipe

> *"we want just primitives in the kernel. and form native code to
> host native assembly using JIT to have generic cross kernel
> functions with host native performance"*  — Urs

## What walked

```
$ ./validate.sh form-stdlib/hex.fk form-samples/cross-modal/38-hex/hex.fk
  ✓  hex.fk+hex.fk                   → encode-match: 1
                                       decode-sum: 824
                                       roundtrip-match: 1
                                       error-detected: 1
                                       4
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran hex encoding from
the Form recipe **only** — no hex native exists in any kernel. The
recipe in [`form-stdlib/hex.fk`](../../../form-stdlib/hex.fk) composes
encode and decode from the kernel's small-int primitives (`div`, `mod`,
`add`, `sub`, `mul`) plus the string natives (`ord`, `substring`,
`str_concat`, `str_len`), and produces correct results for every shape
three-way.

- `hex-encode [0 1 15 16 255]` → **"00010f10ff"**  (edge nibbles + carry)
- `hex-decode "deadbeef"` → **[222 173 190 239]**  (byte-sum 824)
- `decode(encode([42 200 7 255 0 128]))` matches the input
- `hex-decode "xx"` → `HEX-DECODE-ERROR` sentinel

**Final verdict: 4** — every shape lands correctly in every kernel.

## Why hex (alongside Base64)

Base64 (sample 30) is denser — 4 chars per 3 bytes vs hex's 2 chars per
byte. Hex is more readable; the alphabet has no `+`, `/`, `=` to escape
in URLs or shell. Every SHA-256 digest, Merkle root, ETag, content-hash,
and git object-name in this body already wears the hex form. Round-trip
identity holds across the encode/decode pair.

| Property | Hex (this) | Base64 (sample 30) |
|----------|-----------|--------------------|
| Bytes per char | 0.5 | 0.75 |
| Alphabet | `0-9a-f` | `A-Za-z0-9+/` plus `=` pad |
| Padding | none | trailing `=` to mod 3 |
| Case sensitivity | decode accepts both | strict |
| URL-safe | yes (without RFC 4648 §5 swap) | needs §5 url-safe variant |

## The shape

```
                  ┌─ FORM RECIPE (canonical) ───────┐
                  │  form-stdlib/hex.fk              │
                  │                                  │
                  │  uses kernel small-int +         │
   (hex-encode bs)│   string primitives only         │
   ───────────▶   │                                  │
                  │  encode: byte → div/mod 16,      │
                  │   lookup char in "0123456789abcdef"
                  │  decode: char → digit-value      │
                  │   via ASCII range checks         │
                  │   ('0'-'9', 'a'-'f', 'A'-'F')    │
                  │                                  │
                  │  → lowercase hex string          │
                  │  → byte-list OR error sentinel   │
                  └──────────────────────────────────┘
```

## The error sentinel

Decode returns one of two shapes:

- a **byte-list** when input is valid hex (even length, all hex chars)
- the **`HEX-DECODE-ERROR`** NodeID when either condition fails

The sentinel is a substrate-resident `NodeID(1, 2, 99, 1770)` —
addressable, content-equal, and discoverable across kernels. Callers
detect with `(value_eq result HEX-DECODE-ERROR)`. The polymorphic
`value_eq` returns `false` for byte-lists and `true` only for the
exact sentinel, so the caller has a clean dispatch.

```
(let bad (hex-decode "xx"))
(if (value_eq bad (make_nodeid 1 2 99 1770))
    "invalid hex"
    bad)
```

The `hex-valid?` recipe is the same predicate without producing a value
— `1` for inputs `hex-decode` would accept, `0` otherwise.

## The Form recipe shape

`form-stdlib/hex.fk` carries the essential transforms:

```
(defn hex-byte-to-pair (b)
    (str_concat (hex-char-of (div b 16))
                (hex-char-of (mod b 16))))

(defn hex-digit-value (c)
    (if (and (ge c 48) (le c 57))     ; '0'..'9'
        (sub c 48)
        (if (and (ge c 65) (le c 70))  ; 'A'..'F'
            (add (sub c 65) 10)
            (if (and (ge c 97) (le c 102))  ; 'a'..'f'
                (add (sub c 97) 10)
                (sub 0 1)))))           ; not a hex char

(defn hex-decode-loop (s i s-len acc)
    (if (ge i s-len) acc
        (do
            (let hi (hex-digit-value (hex-byte-at s i)))
            (let lo (hex-digit-value (hex-byte-at s (add i 1))))
            (if (or (eq hi -1) (eq lo -1))
                HEX-DECODE-ERROR
                (hex-decode-loop s (add i 2) s-len
                    (cons (add (mul hi 16) lo) acc))))))
```

Cost is O(n) over input length. The decode loop accumulates output
bytes in REVERSE (cheap cons), then the entry point reverses once at
the end. Three sibling kernels converge on identical results.

## Cross-refs

- [`form-stdlib/hex.fk`](../../../form-stdlib/hex.fk) — the canonical recipe
- [`form-stdlib/tests/hex-band.fk`](../../../form-stdlib/tests/hex-band.fk) — sibling-witness band test
- 30-base64 — the denser textual envelope
- 32-crc32 — the same primitive composition discipline
- 20-sha256-as-recipe — what hex is most often used to display
- 16-jit-registry — the bind mechanism a future hex JIT will use
