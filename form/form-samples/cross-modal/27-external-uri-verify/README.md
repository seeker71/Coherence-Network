# 27-external-uri-verify — closing the EXTERNAL-URI verify loop

> *"a tampered URI or unexpected content would surface as a hash mismatch."*

21-cell-query-protocol constructs an EXTERNAL-URI item with a URL and
a sha256 fingerprint, but the receiver never actually fetches the
resource and verifies the hash. THIS walk closes that loop.

A sender stages a local fixture file with known byte content, computes
the canonical sha256 of those bytes, and embeds the digest in an
EXTERNAL-URI item. A receiver extracts the URI and the claimed digest,
reads the bytes through `read_file_bytes`, recomputes sha256, and
compares. Match → trust. Mismatch → reject.

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-stdlib/channel-query.fk \
                form-samples/cross-modal/27-external-uri-verify/external-uri-verify.fk
  ✓  → canonical-hash-len: 32
       bytes-fetched: 5
       hash-matches: 1
       hash-mismatch-detected: 1
       3
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels each executed the full verify protocol and
converged on the same verdict. **Verdict: 3.**

## The verify protocol

```
  SENDER                                         RECEIVER
  ──────                                         ────────
  fixture-bytes = "hello"
  write_file_bytes "/tmp/.../fixture.txt"
  canonical-hash = sha256 fixture-bytes
  uri = cq-external-uri path canonical-hash
   ────── EXTERNAL-URI (path, claimed-hash) ─────▶
                                                 url      = node_value (head children)
                                                 claimed  = bytes from (tail children)
                                                 fetched  = read_file_bytes url
                                                 computed = sha256 fetched
                                                 verdict  = (claimed == computed)
                                                 ──▶ 1  trust the content
                                                 ──▶ 0  reject (tampered)

  TAMPERED CASE (man-in-the-middle or honest mistake)
  ──────────────
  wrong-hash = sha256 "world"          (5 bytes, different content)
  tampered-uri = cq-external-uri path wrong-hash
   ────── EXTERNAL-URI (path, WRONG hash) ───────▶
                                                 claimed  = wrong-hash
                                                 computed = sha256 "hello"
                                                 verdict  = 0 ✓ detected
```

The same five lines of receiver code (`extract URL`, `extract claimed`,
`read bytes`, `compute sha256`, `compare`) handle both paths. The
discipline lives in the shape; the kernel just walks the recipe.

## Why a local file fixture, not real http_get

The kernel native `http_get` exists in all three sibling kernels and
is the production path for verifying real external URIs (pastebin,
archive.org, github raw, youtube manifests). The verify-shape is
identical for either source — `read_file_bytes` vs `http_get` is one
substitution at the leaf.

But live network fetches diverge across CI runs: TLS retries,
intermediate proxy headers, transient 5xx responses, content-encoding
negotiation. None of those would let three sibling kernels converge
on identical byte streams on every invocation. The verify loop's
SHAPE is what this walk attests; the federation discipline holds
identically whether the bytes come from a file path or a URL.

A production walk swaps one line:

```form
(let fetched (read_file_bytes url))    ; local fixture
(let fetched (http_get url))           ; live external resource
```

The rest of the protocol — extract claimed bytes from the EXTERNAL-URI
children, compute sha256 of fetched, compare — is byte-for-byte the
same.

## The federation discipline

Cells in this body federate over two kinds of address:

- **Substrate-resident cells.** A NodeID `(pkg, level, type, inst)`
  resolves locally; content-addressing converges across cells without
  any wire negotiation. SUBSTRATE-REF, CELL-REF, NOVEL-BLUEPRINT,
  RECIPE-CONTENT items all live in this regime.
- **External URIs with content-hash binding.** A URL into the open
  web (pastebin, archive.org, github, youtube) plus a sha256 of the
  expected content. The URL is the locator; the hash is the identity.
  EXTERNAL-URI items live in this regime.

Both are verifiable. The substrate regime is verified by Blueprint
NodeID identity — same shape → same NodeID. The external regime is
verified by sha256 of fetched bytes against the claimed digest. The
federation only trusts content whose identity it can confirm by one
of these two checks; the channel-query vocabulary is the surface
where both regimes coexist in one response.

## What this proves

1. **The verify-loop closes.** A receiver can extract the URI and the
   claimed sha256 from an EXTERNAL-URI item, fetch the content, hash
   it, and compare — without any new kernel native.
2. **Tampering is detectable.** A wrong claimed-hash surfaces as
   `verdict = 0` exactly where the protocol promises it will.
3. **Sibling parity holds across IO.** `write_file_bytes`,
   `read_file_bytes`, and `sha256` (the Form recipe over bitwise
   primitives) all converge byte-for-byte on three kernels.

## What this is NOT yet

- **No real http_get exercise.** Live network fetches diverge across
  CI runs; the local fixture is the deterministic three-way validation
  surface. Swapping the leaf for production use is a one-line change.
- **No MIME-type negotiation.** The EXTERNAL-URI item carries URL +
  sha256; nothing about Content-Type, encoding, or compression. A
  richer wire shape would carry expected-MIME alongside the digest.
- **No streaming verify.** `read_file_bytes` materializes the full
  byte list before hashing. Large external resources need incremental
  sha256 over a streaming reader; the Form recipe in `sha256.fk` is
  already block-by-block-friendly but the kernel native for streaming
  IO isn't wired yet.
- **No signature on the URL itself.** A man-in-the-middle who controls
  both the URL and the claimed-hash can serve consistent (URL, hash)
  pairs — content-hash binds the URL to its bytes, but not to the
  publisher. ed25519 over the EXTERNAL-URI item is the cryptographic
  next walk; matches the same pattern named in 25-end-to-end-channel.
- **No retry on transient mismatch.** If `read_file_bytes` returns an
  empty list (file deleted, permissions, IO error), `ev-verify`
  returns 0 — indistinguishable from a real tamper. A production
  client would distinguish IO-failure from hash-mismatch.

## Cross-refs

- 20-sha256-as-recipe — the canonical sha256 Form recipe over bitwise
  primitives; the engine this verify-loop runs on.
- 21-cell-query-protocol — constructs all five mixed-content items
  including EXTERNAL-URI; this walk closes the verification gap.
- 25-end-to-end-channel — the full L1→L7 channel walk; signed packets
  + correlation matching are the cryptographic next walks.
- `form-stdlib/channel-query.fk` — defines EXTERNAL-URI Blueprint
  (`make_nodeid 1 2 99 1716`) and `cq-external-uri` constructor.
- `form-stdlib/sha256.fk` — the FIPS 180-4 SHA-256 recipe.
- `form-stdlib/tests/external-uri-band.fk` — the band test that pins
  this verify-loop into the full suite.
