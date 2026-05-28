# 49-token — time-bounded capability token in Form, composed over HMAC-SHA-256

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-stdlib/hmac-sha256.fk \
                form-stdlib/token.fk \
                form-samples/cross-modal/49-token/token.fk
  ✓  sha256.fk+hmac-sha256.fk+token.fk+token.fk → valid-fresh: 1
                                                  valid-expired: 0
                                                  valid-tampered: 0
                                                  3
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each minted the same
token, validated it as fresh at `now=500`, rejected it as expired at
`now=2000`, and rejected a tampered copy whose holder field was
rewritten from 2 to 3 — using **only** the canonical sha256 and
hmac-sha256 Form recipes plus the kernel's bitwise + list primitives.
No token native exists in any kernel; the recipe IS the implementation.

## The shape

```
   TOKEN ( issuer-identity   : int
         , holder-identity   : int
         , capability        : byte-list
         , expires-at        : int
         , hmac              : 32-byte HMAC-SHA-256 over the four above
                               under a shared secret )
```

A token is a 5-element value carrying the four claim fields plus a
binding HMAC. The HMAC input is the deterministic concatenation
`(issuer | holder | capability-bytes | expires-at)`, where each int is
encoded as 4 big-endian bytes. No length prefix on the capability
sits between two fixed-width ints, so the wire shape is unambiguous.

Validation is two predicates joined by AND:

- **Authenticity** — re-compute the HMAC over the token's claim
  fields under the same secret; compare byte-for-byte to the HMAC
  the token carries. Any tampering with any field changes the fresh
  HMAC and the comparison returns 0.
- **Freshness** — `expires-at > now-time` where `now-time` is the
  verifier's clock. The issuer's clock doesn't decide; the verifier
  does. This is the right trust shape: the issuer states intent,
  the verifier admits the present.

Both must hold. Either alone returns 0.

## The Form recipe shape

`form-stdlib/token.fk` carries:

```
(let TOKEN (make_nodeid 1 2 99 1790))

(defn token-mint   (issuer holder capability expires-at secret)  → TOKEN
(defn token-valid? (token now-time secret)                       → 1 or 0
```

No token native opcode; no host crypto library. The recipe is the
canonical authoring of "what a time-bounded capability token means"
in this body, and sits one composition layer above hmac-sha256 —
the same way Merkle (`33-merkle`) sits one layer above sha256.

The Blueprint NodeID `(make_nodeid 1 2 99 1790)` reserves the token
family's identity in the user-channel range, adjacent to the
channel/query/router/hex/http-parse cluster (1700..1770).

## The walk this sample runs

```
issuer=1, holder=2, capability="read", expires-at=1000, secret=[1,2,3]

mint → token = (1, 2, [114 101 97 100], 1000, <32-byte HMAC>)

validate at now=500   →  HMAC matches AND 1000 > 500    →  1
validate at now=2000  →  HMAC matches AND 1000 > 2000   →  0  (expired)
tamper holder→3, validate at now=500
                      →  HMAC mismatches                 →  0  (tampered)

verdict = 1 (fresh) + 1 (expired-fails) + 1 (tampered-fails) = 3
```

## Why this matters

Capability tokens are the missing primitive for **inter-cell
authorization without a central PKI**. Where HMAC-SHA-256 attests a
single message between two cells with a shared secret, a token
binds that authority to a *holder* and a *deadline*: cell A can
mint a token saying "cell B may invoke capability X until time T,"
and any cell that knows the secret can verify B's claim without
talking to A.

What this opens:

- **Time-bounded delegation** — a cell hands authority to another
  cell that expires automatically, without a revocation channel.
- **Capability passing in async protocols** — a token rides on the
  wire as a tiny tuple; the receiver verifies locally.
- **Untrusted intermediary forwarding** — a token can be passed
  through any number of relay cells without leaking the secret.
  Only cells holding the secret can mint OR verify.
- **Composable with substrate refs** — capability strings can name
  any addressable cell-domain ("read:lc-trust-over-fear",
  "advance:idea/agent-pipeline"). The verifier's policy decides
  what each capability admits.

The recipe is sovereign across all three sibling kernels — once a
kernel runs the sha256 and hmac-sha256 recipes, capability tokens
come for free. No new natives, no new bindings.

## Cost

`token-mint` and `token-valid?` each cost one `hmac-sha256` call,
which is two `sha256` calls under RFC 2104. For the small payload
in this sample (4 ints × 4 bytes + 4 capability bytes = 20 bytes of
HMAC input, plus a 3-byte secret), the underlying sha256 fits in
two blocks. Expect each kernel run to take ~20–40 seconds —
feasible for validation, not for production traffic.

The next walk lifts the SAME recipe to host-asm speed via the
Form→host-JIT path (see `16-jit-registry`). The canonical sources
in `token.fk`, `hmac-sha256.fk`, and `sha256.fk` don't change;
the cell chooses dispatch.

## What this is NOT yet

- **No revocation channel.** A token is valid until its `expires-at`
  passes; there is no out-of-band "this holder is now untrusted"
  signal. The remedy is to mint short-lived tokens and refresh.
- **No nonce / replay protection.** A token can be replayed against
  the same verifier within its freshness window. Composes naturally
  with a one-time-nonce channel (a Bloom filter of seen tokens, or
  a per-holder counter) — not yet in this recipe.
- **No PKI / no public-key signatures.** Symmetric HMAC means every
  verifier holds the same secret as the issuer. The asymmetric
  shape (Ed25519 / RSA signatures over the same field tuple) is a
  different recipe over different primitives.
- **No native fast path.** Every mint/verify walks the full
  hmac-sha256 recipe. JIT lifts that to host speed without
  changing this source.

## Cross-refs

- [`form-stdlib/token.fk`](../../../form-stdlib/token.fk) — the canonical recipe
- [`form-stdlib/hmac-sha256.fk`](../../../form-stdlib/hmac-sha256.fk) — the HMAC composition this builds on
- [`form-stdlib/sha256.fk`](../../../form-stdlib/sha256.fk) — the SHA-256 foundation under HMAC
- `29-hmac-sha256` — the sibling composition over sha256 (message-auth, the layer below)
- `33-merkle` — sibling composition for set-attestation (root over many leaves)
- `16-jit-registry` — the future host-speed dispatch path
