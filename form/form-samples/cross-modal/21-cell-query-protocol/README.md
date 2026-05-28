# 21-cell-query-protocol — any cell asks any cell any question

> *"we want the channel to be able to ask any addressable cell any
> question, where the question itself needs to be constructed from
> shared minimal primitives, and the response is wire optimized and
> can include shared and novel blueprints, recipes and cells, using
> the shared substrate and even external resources like pastebin,
> archive.org, YouTube, GitHub or any other external addressable
> content and recipe."*  — Urs

## What walked

```
$ ./validate.sh form-stdlib/sha256.fk form-stdlib/channel-query.fk \
                form-samples/cross-modal/21-cell-query-protocol/cell-query.fk
  ✓  sha256.fk+channel-query.fk+cell-query.fk → items-count: 5
                                                  item-1: substrate-ref
                                                  item-2: novel-blueprint
                                                  item-3: recipe-content
                                                  item-4: cell-ref
                                                  item-5: external-uri
                                                  5
  1 ok, 0 divergent — kernels agree on every sample.
```

Three sibling kernels (Go, Rust, TypeScript) each ran the protocol end
to end. Cell A constructed a QUERY, cell B handled it and emitted a
RESPONSE containing five mixed-content items of distinct types. Cell A
classified each by inspecting its Blueprint category. **Verdict: 5** —
all five item-types delivered, recognized, and named in the expected
order.

## The vocabulary

`form-stdlib/channel-query.fk` defines the Blueprints. Every protocol
message is a Form Recipe composed from substrate cells; both ends
read it without schema negotiation.

```
QUERY    (verb, address, body)
RESPONSE (correlation, status, items)

Mixed content (one of):
  SUBSTRATE-REF    (nid-tuple)
  NOVEL-BLUEPRINT  (cat-ref, structural-recipe)
  RECIPE-CONTENT   (recipe-tree-as-child)
  CELL-REF         (nid-tuple, optional fetch-hint)
  EXTERNAL-URI     (url-string, sha256-bytes)
```

The QUERY's `verb` is a substrate-resident SubstrateString — both
cells understand it because the vocabulary IS the shared substrate.
Today: `"about"` (return what you know about this address). Future
verbs: `"recipe"`, `"fetch"`, `"compute"`, `"introspect"`.

## Wire shape, ranked by cost

| Item type | Wire bytes | When B picks it |
|-----------|-----------:|-----------------|
| `SUBSTRATE-REF`   | 4 small ints  | The cell is canonical — A has it too |
| `CELL-REF`        | 4 small ints + optional hint | The cell may be loadable separately |
| `EXTERNAL-URI`    | ~120 chars URL + 32-byte sha256 | The content lives outside the substrate (GitHub, archive.org, YouTube, pastebin) — B binds the URL to its expected content-hash so A verifies before trusting |
| `NOVEL-BLUEPRINT` | 4-int cat + structural-recipe of leaves | B has authored something A doesn't have; B sends the structure, A re-interns, content-addressing converges (17-novel-nodes shape) |
| `RECIPE-CONTENT`  | full recipe sub-tree (largest) | When A can't get the content from a name or hash — B sends the whole thing inline |

The wire-optimization discipline: **B picks the cheapest item type that
faithfully transmits what A needs**. A response can mix all five types
in a single message — most items are refs (cheap), the few truly-novel
pieces ride as structural recipes or full content.

## External addressing extends the substrate

`EXTERNAL-URI` items let cells reference content that lives outside
this body: a GitHub commit, an archive.org snapshot, a YouTube clip
at a timecode, a pastebin raw, anything URL-addressable. The sha256
binds the URL to the content the sender saw — when A fetches via
`http_get` (already in all three kernels), A can verify the content
hash matches before trusting:

```
(let url (cell-uri-url item))
(let expected-sha (cell-uri-sha256 item))
(let fetched (http_get url))
(if (bytes-eq (sha256 (string-to-bytes fetched))
              expected-sha)
    fetched
    null)
```

The substrate becomes a federation: substrate-resident cells +
external addressable content, both with content-hashes, both
verifiable before use.

## What this is NOT yet

- **No inter-process transport wired in this demo.** Both cells run
  in one kernel invocation. `form-stdlib/channel.fk` already provides
  inter-cell .fkb-file transport; wiring queries through it is a small
  extension (one Form recipe).
- **No async correlation matching.** A QUERY/RESPONSE pair runs
  synchronously here. Real async would put the correlation field to
  work — A submits multiple queries, B replies out of order, A
  matches by correlation.
- **No authentication.** A QUERY is anonymous; nothing prevents a
  cell from impersonating another. Authenticated identity needs
  ed25519 (future walk) — sha256 already shipped, ed25519 needs
  modular exp primitives.
- **No content-hash verification in the demo flow.** A doesn't
  actually fetch the URL or check the hash — that's the next walk
  (wire the verify loop using `http_get` + `sha256`).
- **Form-walk speed, not host-native.** The real Form→host-asm JIT
  (next walk) compiles the channel-query recipes to machine code per
  kernel; the protocol shape stays the same.
- **Verb vocabulary is one word ("about").** A richer vocabulary —
  `"recipe"`, `"introspect"`, `"compute"`, `"witness"` — lives in
  channel-query.fk as the body grows.

## Cross-refs

- [`form-stdlib/channel-query.fk`](../../../form-stdlib/channel-query.fk) — the vocabulary
- [`form-stdlib/channel.fk`](../../../form-stdlib/channel.fk) — inter-cell .fkb-file transport (existing)
- [`form-stdlib/sha256.fk`](../../../form-stdlib/sha256.fk) — external-content verification
- 15-private-channel — fingerprint discipline this builds on
- 17-novel-nodes — NOVEL-BLUEPRINT shape
- 18-substrate-compression — SUBSTRATE-REF wire economics
- 19-novel-state-share — bulk novel data + persistent cell identity
- 20-sha256-as-recipe — the canonical hash this protocol relies on
